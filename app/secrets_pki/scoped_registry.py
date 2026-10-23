"""Fail-closed committed Secret registry read model.

The exact actor/source #724 evaluator and mandatory Activity Audit are
enforced by read_governed_scoped_secret_registry. Public read-only HTTP
callers must use that governed entrypoint and never fabricate decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import parse_approved_kv2_mounts
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance

_PAGE_SIZES = frozenset({5, 10, 25, 50})
_MAX_RECORDS = 200
_FRESHNESS = timedelta(hours=24)


@dataclass(frozen=True, slots=True, repr=False)
class ScopedRegistryDecision:
    """Internal-only future #724 evaluator output; NEVER build from request args.

    This data type is not itself an authorization service or policy grant.
    """

    actor_id: int
    instance_id: int
    provider_namespace: str
    mount: str
    permission_allowed: bool
    resource_allowed: bool
    decision_authority: Literal['resource_scope_policy', 'unavailable']
    policy_reference: str | None
    evaluated_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ScopedSecretRow:
    """Authorized opaque identity and lifecycle metadata only."""

    secret_identity_id: str
    current_version: int
    observed_version_count: int
    logical_lifecycle: str
    cas_required: bool
    last_observed_at: datetime


@dataclass(frozen=True, slots=True)
class ScopedSecretPage:
    status: Literal['ready', 'scope_required', 'source_unavailable']
    total_items: int | None
    page: int
    per_page: int
    rows: tuple[ScopedSecretRow, ...]

    @property
    def total_pages(self) -> int | None:
        if self.total_items is None:
            return None
        return max(1, (self.total_items + self.per_page - 1) // self.per_page)


def _time(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(UTC)


def _persisted_time(value: datetime | None) -> datetime | None:
    """SQLAlchemy/SQLite may round-trip timezone UTC as naive datetime."""
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _denied(*, page: int, per_page: int, status: Literal['scope_required', 'source_unavailable']) -> ScopedSecretPage:
    return ScopedSecretPage(status, None, page, per_page, ())


def _approved(decision: ScopedRegistryDecision | None, *, actor_id: int, now: datetime) -> bool:
    if decision is None:
        return False
    at, end = _time(decision.evaluated_at), _time(decision.expires_at)
    try:
        reference = str(UUID(decision.policy_reference or ''))
    except (ValueError, TypeError, AttributeError):
        return False
    return bool(
        type(actor_id) is int and actor_id > 0
        and type(decision.actor_id) is int and decision.actor_id == actor_id
        and type(decision.instance_id) is int and decision.instance_id > 0
        and decision.permission_allowed is True
        and decision.resource_allowed is True
        and decision.decision_authority == 'resource_scope_policy'
        and reference == decision.policy_reference
        and at is not None and end is not None
        and timedelta(0) <= now - at <= timedelta(minutes=5)
        and now < end <= at + timedelta(minutes=15)
        and isinstance(decision.provider_namespace, str)
        and len(decision.provider_namespace) <= 255
        and isinstance(decision.mount, str) and 0 < len(decision.mount) <= 160
    )


def _schema_ready() -> bool:
    required = {
        'integration_instances', 'vault_instances', 'secrets_pki_secret_identities',
        'secrets_pki_inventory_collection_states', 'secrets_pki_secret_representations',
        'secrets_pki_secret_versions',
    }
    return required.issubset(set(inspect(db.engine).get_table_names()))


def read_scoped_secret_registry(
    *,
    decision: ScopedRegistryDecision | None,
    actor_id: int,
    page: int = 1,
    per_page: int = 5,
    now: datetime | None = None,
) -> ScopedSecretPage:
    """Query only safe SQL columns after exact actor+source policy admission.

    Only the governed, audited wrapper may be called from operational HTTP.
    A view permission or knowing an integration ID is never enough.
    """
    instant = _time(now or datetime.now(UTC))
    if instant is None or type(page) is not int or page < 1 or type(per_page) is not int or per_page not in _PAGE_SIZES:
        return _denied(page=1, per_page=5, status='scope_required')
    if not _approved(decision, actor_id=actor_id, now=instant):
        return _denied(page=page, per_page=per_page, status='scope_required')
    assert decision is not None
    try:
        if not _schema_ready():
            return _denied(page=page, per_page=per_page, status='source_unavailable')
        source = db.session.execute(
            select(IntegrationInstance.id, IntegrationInstance.enabled, IntegrationInstance.lifecycle_status,
                   IntegrationInstance.readiness_status, VaultInstance.namespace, VaultInstance.kv2_mounts)
            .join(VaultInstance, VaultInstance.integration_instance_id == IntegrationInstance.id)
            .where(IntegrationInstance.id == decision.instance_id,
                   IntegrationInstance.integration_type == 'secrets_pki',
                   IntegrationInstance.provider_key == 'vault')
        ).one_or_none()
        if (
            source is None or not source.enabled or source.lifecycle_status != 'active'
            or source.readiness_status != 'ready' or (source.namespace or '') != decision.provider_namespace
            or decision.mount not in parse_approved_kv2_mounts(','.join(source.kv2_mounts or ()))
        ):
            return _denied(page=page, per_page=per_page, status='source_unavailable')
        state = db.session.execute(
            select(SecretInventoryCollectionState.status, SecretInventoryCollectionState.observed_count,
                   SecretInventoryCollectionState.last_observed_at, SecretInventoryCollectionState.last_committed_at)
            .where(SecretInventoryCollectionState.integration_instance_id == decision.instance_id,
                   SecretInventoryCollectionState.provider_namespace == decision.provider_namespace,
                   SecretInventoryCollectionState.mount == decision.mount)
        ).one_or_none()
        if state is None or state.status != 'ready' or type(state.observed_count) is not int:
            return _denied(page=page, per_page=per_page, status='source_unavailable')
        source_at, committed_at = _persisted_time(state.last_observed_at), _persisted_time(state.last_committed_at)
        if (
            source_at is None or committed_at is None
            or not 0 <= state.observed_count <= _MAX_RECORDS
            or not timedelta(0) <= instant - source_at <= _FRESHNESS
            or not timedelta(0) <= instant - committed_at <= _FRESHNESS
        ):
            return _denied(page=page, per_page=per_page, status='source_unavailable')
        selected = db.session.execute(
            select(
                SecretProviderRepresentation.id,
                SecretProviderRepresentation.secret_identity_id,
                SecretProviderRepresentation.current_version,
                SecretProviderRepresentation.cas_required,
                SecretProviderRepresentation.last_observed_at,
                SecretIdentity.lifecycle_status,
            )
            .join(SecretIdentity, SecretIdentity.id == SecretProviderRepresentation.secret_identity_id)
            .where(
                SecretProviderRepresentation.integration_instance_id == decision.instance_id,
                SecretProviderRepresentation.provider_key == 'vault',
                SecretProviderRepresentation.representation_role == 'material_authority',
                SecretProviderRepresentation.provider_namespace == decision.provider_namespace,
                SecretProviderRepresentation.mount == decision.mount,
                SecretProviderRepresentation.observation_status == 'observed',
            )
            .order_by(SecretProviderRepresentation.id.asc())
            .limit(_MAX_RECORDS + 1)
        ).all()
        if len(selected) != state.observed_count or any(_persisted_time(row.last_observed_at) != source_at for row in selected):
            return _denied(page=page, per_page=per_page, status='source_unavailable')
        chosen = selected[(page - 1) * per_page:page * per_page]
        if not chosen:
            return ScopedSecretPage('ready', len(selected), page, per_page, ())
        representation_ids = [row.id for row in chosen]
        observed_versions = dict(db.session.execute(
            select(SecretVersionObservation.representation_id, func.count(SecretVersionObservation.id))
            .where(SecretVersionObservation.representation_id.in_(representation_ids),
                   SecretVersionObservation.last_observed_at == state.last_observed_at)
            .group_by(SecretVersionObservation.representation_id)
        ).all())
        if any(not 1 <= observed_versions.get(row.id, 0) <= 100 for row in chosen):
            return _denied(page=page, per_page=per_page, status='source_unavailable')
        return ScopedSecretPage(
            'ready', len(selected), page, per_page,
            tuple(ScopedSecretRow(
                secret_identity_id=row.secret_identity_id,
                current_version=row.current_version,
                observed_version_count=observed_versions[row.id],
                logical_lifecycle=row.lifecycle_status,
                cas_required=row.cas_required,
                last_observed_at=source_at,
            ) for row in chosen),
        )
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return _denied(page=page, per_page=per_page, status='source_unavailable')


def read_governed_scoped_secret_registry(
    *,
    actor_id: int,
    instance_id: int,
    provider_namespace: str,
    mount: str,
    page: int = 1,
    per_page: int = 5,
    now: datetime | None = None,
) -> ScopedSecretPage:
    """Admission-checked, mandatory-audited internal Registry entrypoint.

    The policy row is locked from admission through bounded source read and
    audit commit, so a concurrent revocation cannot become visible during
    this protected transaction. The scoped read-only HTTP Registry uses it.
    """
    from app.access.scope_policy import evaluate_exact_vault_scope
    from app.platform_operations.notifications.service import stage_operational_activity

    instant = _time(now or datetime.now(UTC))
    if instant is None or type(page) is not int or page < 1 or type(per_page) is not int or per_page not in _PAGE_SIZES:
        return _denied(page=1, per_page=5, status='scope_required')
    try:
        admission = evaluate_exact_vault_scope(
            actor_user_id=actor_id,
            instance_id=instance_id,
            provider_namespace=provider_namespace,
            mount=mount,
            now=instant,
            lock_for_read=True,
        )
        if (
            not admission.allowed
            or admission.policy_ref is None or admission.revision is None
            or admission.expires_at is None
        ):
            db.session.rollback()
            return _denied(page=page, per_page=per_page, status='scope_required')
        decision = ScopedRegistryDecision(
            actor_id=actor_id,
            instance_id=instance_id,
            provider_namespace=provider_namespace,
            mount=mount,
            permission_allowed=True,
            resource_allowed=True,
            decision_authority='resource_scope_policy',
            policy_reference=admission.policy_ref,
            evaluated_at=instant,
            expires_at=min(admission.expires_at, instant + timedelta(minutes=10)),
        )
        result = read_scoped_secret_registry(
            decision=decision,
            actor_id=actor_id,
            page=page,
            per_page=per_page,
            now=instant,
        )
        if result.status != 'ready':
            db.session.rollback()
            return result
        # Same transaction: no Secret row/page is returned before audit commit.
        # Canonical Activity Audit redaction cannot be treated as an async
        # background toast or best-effort notification for sensitive reads.
        stage_operational_activity(
            user_id=actor_id,
            event_type='access_scope_secret_registry_read',
            status='success',
            title='Scoped Secret Registry Read',
            message='Authorized committed Secret metadata was inspected.',
            metadata={
                'actor_user_id': actor_id,
                'policy_ref': admission.policy_ref,
                'policy_revision': admission.revision,
                'permission_key': 'secrets_pki.view',
                'scope_level': 'vault_mount',
                'integration_instance_id': instance_id,
                'audit_contract': 'scoped_policy.v1',
                'result': 'allow',
            },
        )
        db.session.commit()
        return result
    except Exception:
        # Do not expose source, policy or commit error details; deny and
        # rollback when mandatory evidence or provider-qualified SQL fails.
        db.session.rollback()
        return _denied(page=page, per_page=per_page, status='scope_required')
