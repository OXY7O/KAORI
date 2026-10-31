"""Transactional, authenticated GitHub webhook delivery staging (SC-02).

No public endpoint, live-provider mutation, asynchronous dispatch, or source
event publication happens here. A caller must commit the transaction before
it can enqueue SC-03's authorized reconciliation task.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extensions.db import db
from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.webhook import (
    GitHubWebhookError,
    verify_webhook,
)
from app.models.source_control import SourceInstallation, SourceWebhookDelivery


@dataclass(frozen=True, slots=True)
class WebhookClaim:
    """Delivery was atomically staged; never evidence that a refresh ran."""

    delivery_id: str
    installation_id: int
    newly_staged: bool


def _eligible_installation(installation: SourceInstallation) -> str:
    """Fail closed on disabled, cross-provider, or unadmitted App installations."""
    if not provider_kind('source_control', 'github').available:
        raise GitHubWebhookError('GitHub webhook ingress has not been admitted.')
    canonical = installation.integration_instance
    app = installation.github_app_credential
    if (
        canonical is None
        or canonical.integration_type != 'source_control'
        or canonical.provider_key != 'github'
        or canonical.adapter_key != 'github_rest_v3'
        or not canonical.enabled
        or canonical.lifecycle_status != 'active'
        or installation.integration_instance_id != canonical.id
        or installation.account_id is None
        or installation.account is None
        or app is None
        or installation.github_app_credential_id != app.id
        or not app.enabled
        or app.host_key != 'github.com'
        or installation.provider_key != 'github'
        or installation.host_key != 'github.com'
        or installation.native_app_id != app.native_app_id
    ):
        raise GitHubWebhookError('GitHub webhook installation is not eligible.')
    return app.webhook_secret


def claim_verified_delivery(
    *,
    installation: SourceInstallation,
    payload: bytes,
    headers: Mapping[str, str],
    session: Session,
) -> WebhookClaim:
    """Verify original bytes and stage a unique, tenant-scoped transport envelope.

    A replay with the same digest is idempotent; reusing the same delivery
    identity with different signed content is rejected. This service does not
    commit; an eventual ingress handler owns transaction finalization and must
    dispatch only after commit has succeeded.
    """
    secret = _eligible_installation(installation)
    verified = verify_webhook(
        payload=payload,
        headers=headers,
        webhook_secret=secret,
        expected_installation_id=int(installation.native_installation_id),
    )
    if installation.id is None:
        raise GitHubWebhookError('GitHub webhook installation has no committed identity.')
    digest = hashlib.sha256(payload).hexdigest()
    scope = (
        SourceWebhookDelivery.installation_id == installation.id,
        SourceWebhookDelivery.delivery_id == verified.delivery_id,
    )
    existing = session.execute(select(SourceWebhookDelivery).where(*scope)).scalar_one_or_none()
    if existing is not None:
        if existing.payload_sha256 != digest:
            raise GitHubWebhookError('GitHub webhook delivery identity was reused with different content.')
        return WebhookClaim(verified.delivery_id, installation.id, False)

    record = SourceWebhookDelivery()
    record.installation_id = installation.id
    record.delivery_id = verified.delivery_id
    record.payload_sha256 = digest
    record.event_type = verified.event
    record.action = verified.action
    record.repository_native_id_hint = str(verified.repository_id) if verified.repository_id is not None else None
    record.processing_state = 'received'
    record.received_at = datetime.now(UTC)
    record.attempt_count = 0
    try:
        # Savepoint preserves the outer transaction on concurrent duplicate
        # delivery races. Database uniqueness remains the race authority.
        with session.begin_nested():
            session.add(record)
            session.flush()
    except IntegrityError:
        same = session.execute(select(SourceWebhookDelivery).where(*scope)).scalar_one_or_none()
        if same is None or same.payload_sha256 != digest:
            raise GitHubWebhookError('GitHub webhook delivery collision could not be verified.') from None
        return WebhookClaim(verified.delivery_id, installation.id, False)
    return WebhookClaim(verified.delivery_id, installation.id, True)


def stage_signed_github_webhook_delivery(
    *, native_installation_id: int, payload: bytes, headers: Mapping[str, str]
) -> None:
    """Commit only an authenticated, installation-scoped GitHub transport envelope.

    The installation identifier is an untrusted hint until the existing
    per-application HMAC verifier proves the original request bytes.
    An invalid/failed claim always resets the scoped transaction.
    """
    candidates = (
        SourceInstallation.query.filter_by(
            host_key='github.com',
            provider_key='github',
            native_installation_id=str(native_installation_id),
        )
        .limit(2)
        .all()
    )
    if len(candidates) != 1:
        raise GitHubWebhookError('GitHub installation could not be uniquely resolved.')

    committed = False
    try:
        claim_verified_delivery(
            installation=candidates[0],
            payload=payload,
            headers=headers,
            session=cast(Session, db.session),
        )
        db.session.commit()
        committed = True
    finally:
        # Failed ingress may never leave an authenticated envelope uncommitted.
        if not committed:
            db.session.rollback()
