"""Canonical, source-qualified human scoped policy admission (#724, #2725).

This module never grants a capability through global RBAC alone. No public
Secret Registry API/route is enabled. Read-only decisions MUST NOT be treated
as read authorization without the audited, locking caller transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.user import User
from app.models.vault import VaultInstance

_SENSITIVE_PERMISSION = 'secrets_pki.view'
_MAX_MATCHING_POLICIES = 32


@dataclass(frozen=True, slots=True, repr=False)
class ScopeAdmission:
    status: Literal['allow', 'deny', 'unavailable']
    reason: str
    actor_id: int | None = None
    instance_id: int | None = None
    policy_ref: str | None = None
    revision: int | None = None
    expires_at: datetime | None = None

    @property
    def allowed(self) -> bool:
        return self.status == 'allow'


def _timestamp(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    # PostgreSQL retains UTC offsets; SQLite contract fixtures may round-trip naive.
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def evaluate_exact_vault_scope(
    *,
    actor_user_id: int,
    instance_id: int,
    provider_namespace: str,
    mount: str,
    permission_key: str = _SENSITIVE_PERMISSION,
    now: datetime | None = None,
    lock_for_read: bool = False,
) -> ScopeAdmission:
    """Check persisted latest policy; lock the policy row for audited sensitive reads.

    No default inheritance from the instance to the namespace/mount.
    This read-only result is a *precondition*, not an exportable permit.
    """
    if (
        type(actor_user_id) is not int or actor_user_id <= 0
        or type(instance_id) is not int or instance_id <= 0
        or permission_key != _SENSITIVE_PERMISSION
        or not isinstance(provider_namespace, str)
        or not isinstance(mount, str) or not mount
        or len(provider_namespace) > 255 or len(mount) > 160
        or '*' in mount
    ):
        return ScopeAdmission('deny', 'invalid_scope')
    instant = _timestamp(now or datetime.now(UTC))
    if instant is None:
        return ScopeAdmission('deny', 'invalid_time')

    try:
        actor = db.session.get(User, actor_user_id)
        if (
            actor is None or not actor.is_active or actor.role_record is None
            or not actor.role_record.is_active
            or permission_key not in actor.role_record.permission_keys()
        ):
            # Do not inherit the local super-admin's global permission shortcut.
            return ScopeAdmission('deny', 'permission_required')
        source = db.session.get(IntegrationInstance, instance_id)
        if (
            source is None or source.integration_type != 'secrets_pki'
            or source.provider_key != 'vault'
            or not source.enabled or source.lifecycle_status != 'active'
            or source.readiness_status != 'ready'
        ):
            return ScopeAdmission('deny', 'source_unqualified')
        vault = VaultInstance.query.filter_by(integration_instance_id=instance_id).first()
        if (
            vault is None or (vault.namespace or '') != provider_namespace
            or mount not in (vault.kv2_mounts or ())
        ):
            return ScopeAdmission('deny', 'source_unqualified')

        query = (
            ScopeAccessPolicy.query.filter(
                ScopeAccessPolicy.principal_user_id == actor_user_id,
                ScopeAccessPolicy.permission_key == permission_key,
                ScopeAccessPolicy.integration_instance_id == instance_id,
                ScopeAccessPolicy.scope_level == 'vault_mount',
                ScopeAccessPolicy.provider_namespace == provider_namespace,
                ScopeAccessPolicy.mount == mount,
            )
            .enable_eagerloads(False)
            .order_by(ScopeAccessPolicy.id.asc())
            .limit(_MAX_MATCHING_POLICIES)
        )
        if lock_for_read:
            query = query.with_for_update(of=ScopeAccessPolicy)
        candidates = query.all()
        for policy in candidates:
            current = ScopeAccessPolicyRevision.query.filter(
                ScopeAccessPolicyRevision.policy_id == policy.id,
                ScopeAccessPolicyRevision.revision_number == policy.current_revision,
            ).first()
            if (
                current is None or current.lifecycle_status != 'active'
                or current.approved_by_user_id is None
                or current.approved_by_user_id == current.requested_by_user_id
                or current.approved_at is None
            ):
                continue
            starts, ends = _timestamp(current.effective_from), _timestamp(current.effective_until)
            approved = _timestamp(current.approved_at)
            if (
                starts is None or ends is None or approved is None
                or starts > instant or instant >= ends
                or approved > instant
            ):
                continue
            return ScopeAdmission(
                'allow', 'exact_approved_grant',
                actor_id=actor_user_id,
                instance_id=instance_id,
                policy_ref=policy.id,
                revision=current.revision_number,
                expires_at=ends,
            )
        return ScopeAdmission('deny', 'scope_grant_required')
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return ScopeAdmission('unavailable', 'policy_evidence_unavailable')
