"""Read-only exact-scope issuer candidate resolution (#5204).

Internal use only. Resolve public key material from the latest persisted
revision, never from the signed claim or a caller-selected key. No issuer
activation, scope authorization, provider identity attestation or execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


def _record_target(row: SecretCredentialIssuerRevision) -> IssuerResolutionTarget:
    return IssuerResolutionTarget(
        row.integration_instance_id,
        row.provider_key,
        row.provider_namespace,
        row.mount,
        row.deployment_ref,
        row.revision_number,
    )


def _scope(row: SecretCredentialIssuerRevision) -> tuple[int, str, str]:
    return row.integration_instance_id, row.provider_namespace, row.mount


def _binding(row: SecretCredentialIssuerRevision) -> tuple[object, ...]:
    return (*_scope(row), row.provider_key, row.deployment_ref, row.public_key_hex, row.key_sha256)


def _revision_shape(row: SecretCredentialIssuerRevision, now: datetime) -> bool:
    return (
        _valid_target(_record_target(row))
        and row.algorithm == 'ed25519'
        and _digest(row.public_key_hex)
        and _digest(row.key_sha256)
        and sha256(bytes.fromhex(row.public_key_hex)).hexdigest() == row.key_sha256
        and _digest(row.evidence_ref)
        and _positive_int(row.requested_by_user_id)
        and _positive_int(row.recorded_by_user_id)
        and all(_aware(value) for value in (row.recorded_at, row.effective_from, row.effective_until, now))
        and row.recorded_at <= now
        and row.effective_from < row.effective_until
    )


def _draft_actor_shape(row: SecretCredentialIssuerRevision) -> bool:
    return (
        row.approved_by_user_id is None
        and row.approved_at is None
        and row.recorded_by_user_id == row.requested_by_user_id
    )


def _revision_snapshot(row: SecretCredentialIssuerRevision) -> tuple[object, ...]:
    return (
        *_binding(row),
        row.revision_number,
        row.lifecycle_status,
        row.algorithm,
        row.evidence_ref,
        row.requested_by_user_id,
        row.approved_by_user_id,
        row.recorded_by_user_id,
        row.approved_at,
        row.recorded_at,
        row.effective_from,
        row.effective_until,
    )


def _continuation_shape(
    candidate: SecretCredentialIssuerRevision,
    latest: SecretCredentialIssuerRevision,
    key_history: tuple[SecretCredentialIssuerRevision, ...],
    now: datetime,
) -> bool:
    approved = candidate.approved_at
    return (
        latest.lifecycle_status in ('draft', 'active')
        and (candidate.lifecycle_status == 'revoked' or latest.lifecycle_status == 'draft')
        and (latest.lifecycle_status != 'draft' or _draft_actor_shape(latest))
        and _binding(candidate) == _binding(latest)
        and candidate.requested_by_user_id == latest.requested_by_user_id
        and candidate.effective_from == latest.effective_from
        and candidate.effective_until == latest.effective_until
        and _independent_record(candidate)
        and approved is not None
        and _aware(approved)
        and latest.recorded_at <= approved <= candidate.recorded_at
        and len({row.revision_number for row in key_history}) == len(key_history)
        and any(_revision_snapshot(row) == _revision_snapshot(latest) for row in key_history)
        and all(
            _revision_shape(row, now)
            and _binding(row) == _binding(candidate)
            and row.lifecycle_status in ('draft', 'active')
            and row.revision_number <= latest.revision_number
            for row in key_history
        )
    )


def issuer_transition_shape_qualified(
    *,
    source: IntegrationInstance,
    latest: SecretCredentialIssuerRevision | None,
    candidate: SecretCredentialIssuerRevision,
    expected_revision: int,
    current_deployment_ref: str,
    key_history: tuple[SecretCredentialIssuerRevision, ...],
    now: datetime,
) -> bool:
    """Qualify a prospective append-only revision shape, never permit a write.

    Internal inputs must eventually be independently resolved under locks:
    latest exact-scope revision, complete history for the candidate key digest,
    provider deployment identity, authenticated actors and custody evidence.
    This pure helper cannot establish completeness, authority or key custody.
    """
    if (
        not _revision_shape(candidate, now)
        or type(expected_revision) is not int
        or expected_revision < 0
        or candidate.revision_number != expected_revision + 1
        or source.id != candidate.integration_instance_id
        or source.integration_type != 'secrets_pki'
        or source.provider_key != candidate.provider_key
        or candidate.deployment_ref != current_deployment_ref
    ):
        return False
    if latest is None:
        if expected_revision != 0:
            return False
    elif (
        not _revision_shape(latest, now)
        or _scope(latest) != _scope(candidate)
        or latest.revision_number != expected_revision
        or latest.recorded_at > candidate.recorded_at
    ):
        return False
    state = candidate.lifecycle_status
    if state != 'revoked' and (
        source.enabled is not True or source.lifecycle_status != 'active' or source.readiness_status != 'ready'
    ):
        return False
    if state == 'draft':
        # Initial enrollment or explicit revoke-then-enroll with a fresh key.
        return (
            (latest is None or (latest.lifecycle_status == 'revoked' and latest.key_sha256 != candidate.key_sha256))
            and not key_history
            and _draft_actor_shape(candidate)
            and now < candidate.effective_until
        )
    if (
        latest is None
        or state not in ('active', 'revoked')
        or not _continuation_shape(candidate, latest, key_history, now)
    ):
        return False
    if state == 'revoked':
        # Expired or disabled sources must not prevent same-binding revocation.
        return True
    return issuer_candidate_key(target=_record_target(candidate), source=source, latest=candidate, now=now) is not None


def issuer_proof_window_qualified(
    row: SecretCredentialIssuerRevision, *, issued_at: datetime, expires_at: datetime, now: datetime
) -> bool:
    """Check time containment only; caller must revalidate current issuer and signature."""
    return (
        row.lifecycle_status == 'active'
        and _independent_record(row)
        and _current_window(row, now)
        and _aware(issued_at)
        and _aware(expires_at)
        and row.recorded_at <= issued_at
        and row.effective_from <= issued_at <= now < expires_at <= row.effective_until
    )


@dataclass(frozen=True, slots=True, repr=False)
class IssuerCustodyEvidenceShape:
    """Prospective evidence references only; none is an admitted trust anchor."""

    target: IssuerResolutionTarget
    key_sha256: str
    challenge_sha256: str
    deployment_evidence_ref: str
    possession_evidence_ref: str
    custody_evidence_ref: str
    access_decision_ref: str
    source_owner_id: int
    checker_id: int
    issued_at: datetime
    approved_at: datetime
    expires_at: datetime


def issuer_custody_evidence_shape_qualified(
    evidence: IssuerCustodyEvidenceShape,
    *,
    target: IssuerResolutionTarget,
    key_sha256: str,
    expected_challenge_sha256: str,
    challenge_issued_at: datetime,
    now: datetime,
) -> bool:
    """Check offline binding and chronology only; never authorize or consume a challenge.

    The future locked caller must independently resolve the target, single-use
    challenge, authenticated actors and each current evidence authority. A
    matching digest, well-formed receipt or signature is not proof of custody.
    No operational evidence resolver is admitted by this increment.
    """
    if not isinstance(evidence, IssuerCustodyEvidenceShape) or not _valid_target(target):
        return False
    refs = (
        evidence.deployment_evidence_ref,
        evidence.possession_evidence_ref,
        evidence.custody_evidence_ref,
        evidence.access_decision_ref,
    )
    if not all(_digest(ref) for ref in refs):
        return False
    return (
        _valid_target(evidence.target)
        and evidence.target == target
        and _digest(key_sha256)
        and evidence.key_sha256 == key_sha256
        and _digest(expected_challenge_sha256)
        and evidence.challenge_sha256 == expected_challenge_sha256
        and len(set(refs)) == len(refs)
        and _positive_int(evidence.source_owner_id)
        and _positive_int(evidence.checker_id)
        and evidence.source_owner_id != evidence.checker_id
        and all(
            _aware(value)
            for value in (challenge_issued_at, evidence.issued_at, evidence.approved_at, evidence.expires_at, now)
        )
        and challenge_issued_at <= evidence.issued_at <= evidence.approved_at <= now < evidence.expires_at
        and evidence.expires_at - challenge_issued_at <= timedelta(hours=24)
    )
