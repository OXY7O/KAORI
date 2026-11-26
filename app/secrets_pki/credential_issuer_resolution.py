"""Read-only exact-scope issuer candidate resolution (#5204).

Internal use only. Resolve public key material from the latest persisted
revision, never from the signed claim or a caller-selected key. No issuer
activation, scope authorization, provider identity attestation or execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretCredentialIssuerRevision

_DIGEST = re.compile(r'[a-f0-9]{64}')


@dataclass(frozen=True, slots=True, repr=False)
class IssuerResolutionTarget:
    """Internal candidate selector, not a permission or provider identity proof."""

    integration_instance_id: int
    provider_key: str
    provider_namespace: str
    mount: str
    deployment_ref: str
    revision_number: int


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _exact_scope(value: object, limit: int, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, str)
        and (allow_empty or bool(value))
        and len(value) <= limit
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
        and '*' not in value
        and '+' not in value
    )


def _digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _valid_target(target: IssuerResolutionTarget) -> bool:
    return (
        isinstance(target, IssuerResolutionTarget)
        and _positive_int(target.integration_instance_id)
        and _positive_int(target.revision_number)
        and target.provider_key in ('vault', 'openbao')
        and _exact_scope(target.provider_namespace, 255, allow_empty=True)
        and _exact_scope(target.mount, 160)
        and _digest(target.deployment_ref)
    )


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _current_window(row: SecretCredentialIssuerRevision, now: datetime) -> bool:
    approved = row.approved_at
    if approved is None or not all(
        _aware(value) for value in (approved, row.recorded_at, row.effective_from, row.effective_until, now)
    ):
        return False
    return approved <= row.recorded_at <= now and row.effective_from <= now < row.effective_until


def _independent_record(row: SecretCredentialIssuerRevision) -> bool:
    return (
        _positive_int(row.requested_by_user_id)
        and _positive_int(row.approved_by_user_id)
        and row.approved_by_user_id != row.requested_by_user_id
        and row.recorded_by_user_id == row.approved_by_user_id
        and _digest(row.evidence_ref)
    )


def _matching_source(
    source: IntegrationInstance, row: SecretCredentialIssuerRevision, target: IssuerResolutionTarget
) -> bool:
    return (
        source.id == target.integration_instance_id == row.integration_instance_id
        and source.integration_type == 'secrets_pki'
        and source.provider_key == target.provider_key == row.provider_key
        and source.enabled is True
        and source.lifecycle_status == 'active'
        and source.readiness_status == 'ready'
        and row.provider_namespace == target.provider_namespace
        and row.mount == target.mount
        and row.deployment_ref == target.deployment_ref
        and row.revision_number == target.revision_number
        and row.lifecycle_status == 'active'
    )


def issuer_candidate_key(
    *,
    target: IssuerResolutionTarget,
    source: IntegrationInstance,
    latest: SecretCredentialIssuerRevision,
    now: datetime,
) -> Ed25519PublicKey | None:
    """Qualify latest committed metadata shape; not proof of issuer custody or authorization."""
    if (
        not _valid_target(target)
        or not _matching_source(source, latest, target)
        or not _independent_record(latest)
        or not _current_window(latest, now)
        or latest.algorithm != 'ed25519'
        or not _digest(latest.public_key_hex)
        or not _digest(latest.key_sha256)
    ):
        return None
    raw = bytes.fromhex(latest.public_key_hex)
    if sha256(raw).hexdigest() != latest.key_sha256:
        return None
    try:
        return Ed25519PublicKey.from_public_bytes(raw)
    except ValueError:
        return None


def _latest_issuer(
    session: Session, target: IssuerResolutionTarget
) -> tuple[SecretCredentialIssuerRevision, IntegrationInstance] | None:
    # Do not filter by provider, deployment, requested revision, or lifecycle
    # before selecting latest: that could revive superseded authority.
    row = session.execute(
        select(SecretCredentialIssuerRevision, IntegrationInstance)
        .join(IntegrationInstance, IntegrationInstance.id == SecretCredentialIssuerRevision.integration_instance_id)
        .where(
            SecretCredentialIssuerRevision.integration_instance_id == target.integration_instance_id,
            SecretCredentialIssuerRevision.provider_namespace == target.provider_namespace,
            SecretCredentialIssuerRevision.mount == target.mount,
        )
        .order_by(SecretCredentialIssuerRevision.revision_number.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def resolve_issuer_candidate(target: IssuerResolutionTarget) -> Ed25519PublicKey | None:
    """Read latest persisted candidate using an independent non-writing session.

    Not an authorization decision. The future governed caller must recheck
    current provider identity, issuer custody, grant and version at use.
    """
    if not _valid_target(target):
        return None
    try:
        with Session(db.engine, autoflush=False) as session:
            result = _latest_issuer(session, target)
            if result is None:
                return None
            latest, source = result
            return issuer_candidate_key(target=target, source=source, latest=latest, now=datetime.now(UTC))
    except SQLAlchemyError:
        return None
