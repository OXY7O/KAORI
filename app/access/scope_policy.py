"""Canonical, source-qualified human scoped policy admission (#724, #2725).

This module never grants a capability through global RBAC alone. Read-only
scope decisions MUST NOT be treated as read authorization without the
audited, locking caller transaction. The governed Registry route uses
exact-policy admission under that transaction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import (
    current_local_inventory_source,
)
from app.models.integration import IntegrationInstance
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.user import User
from app.models.vault import VaultInstance

_SENSITIVE_PERMISSION = 'secrets_pki.view'
VAULT_CASE_OPERATOR_PERMISSION = 'intelligence.decisions.create'
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


def _valid_vault_mount_scope_request(
    actor_user_id: int, instance_id: int, provider_namespace: str, mount: str, permission_key: str
) -> bool:
    """Exact Vault mount scope only: no wildcard, inherited scope or malformed identity."""
    return not (
        type(actor_user_id) is not int
        or actor_user_id <= 0
        or type(instance_id) is not int
        or instance_id <= 0
        or permission_key != _SENSITIVE_PERMISSION
        or not isinstance(provider_namespace, str)
        or not isinstance(mount, str)
        or not mount
        or len(provider_namespace) > 255
        or len(mount) > 160
        or '*' in mount
    )


def _vault_mount_actor_allowed(actor: User | None, permission_key: str) -> bool:
    """Explicit active-role permission, without local super-admin shortcut."""
    return not (
        actor is None
        or not actor.is_active
        or actor.role_record is None
        or not actor.role_record.is_active
        or permission_key not in actor.role_record.permission_keys()
    )


def _ready_vault_mount_source(source: IntegrationInstance | None) -> bool:
    return not (
        source is None
        or source.integration_type != 'secrets_pki'
        or source.provider_key != 'vault'
        or not source.enabled
        or source.lifecycle_status != 'active'
        or source.readiness_status != 'ready'
    )


def _eligible_exact_revision_end(current: ScopeAccessPolicyRevision | None, *, instant: datetime) -> datetime | None:
    """Only active, separately approved, effective exact revision is eligible."""
    if (
        current is None
        or current.lifecycle_status != 'active'
        or current.approved_by_user_id is None
        or current.approved_by_user_id == current.requested_by_user_id
        or current.approved_at is None
    ):
        return None
    starts, ends = _timestamp(current.effective_from), _timestamp(current.effective_until)
    approved = _timestamp(current.approved_at)
    if starts is None or ends is None or approved is None or starts > instant or instant >= ends or approved > instant:
        return None
    return ends


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
    """Preserve the existing exact Vault mount admission contract."""
    return _evaluate_exact_metadata_scope(
        actor_user_id=actor_user_id, instance_id=instance_id, provider_namespace=provider_namespace,
        mount=mount, permission_key=permission_key, now=now, lock_for_read=lock_for_read,
        scope_level='vault_mount',
    )


def evaluate_exact_openbao_scope(
    *,
    actor_user_id: int,
    instance_id: int,
    provider_namespace: str,
    mount: str,
    now: datetime | None = None,
    lock_for_read: bool = False,
) -> ScopeAdmission:
    """Exact local OpenBao metadata scope; never a material-use permit."""
    if provider_namespace != '' or not isinstance(mount, str) or '+' in mount:
        return ScopeAdmission('deny', 'invalid_scope')
    return _evaluate_exact_metadata_scope(
        actor_user_id=actor_user_id, instance_id=instance_id, provider_namespace=provider_namespace,
        mount=mount, permission_key=_SENSITIVE_PERMISSION, now=now, lock_for_read=lock_for_read,
        scope_level='openbao_mount',
    )


def _evaluate_exact_metadata_scope(
    *,
    actor_user_id: int,
    instance_id: int,
    provider_namespace: str,
    mount: str,
    permission_key: str,
    now: datetime | None,
    lock_for_read: bool,
    scope_level: Literal['vault_mount', 'openbao_mount'],
) -> ScopeAdmission:
    """Check persisted latest policy; lock the policy row for audited sensitive reads.

    No default inheritance from the instance to the namespace/mount.
    This read-only result is a *precondition*, not an exportable permit.
    """
    if not _valid_vault_mount_scope_request(actor_user_id, instance_id, provider_namespace, mount, permission_key):
        return ScopeAdmission('deny', 'invalid_scope')
    instant = _timestamp(now or datetime.now(UTC))
    if instant is None:
        return ScopeAdmission('deny', 'invalid_time')

    try:
        actor = db.session.get(User, actor_user_id)
        if not _vault_mount_actor_allowed(actor, permission_key):
            # Do not inherit the local super-admin's global permission shortcut.
            return ScopeAdmission('deny', 'permission_required')
        source = db.session.get(IntegrationInstance, instance_id)
        if scope_level == 'vault_mount':
            if not _ready_vault_mount_source(source):
                return ScopeAdmission('deny', 'source_unqualified')
            vault = VaultInstance.query.filter_by(integration_instance_id=instance_id).first()
            if vault is None or (vault.namespace or '') != provider_namespace or mount not in (vault.kv2_mounts or ()):
                return ScopeAdmission('deny', 'source_unqualified')
        elif current_local_inventory_source(
            source, namespace=provider_namespace, mount=mount, lock=False
        ) is None:
            return ScopeAdmission('deny', 'source_unqualified')

        query = (
            ScopeAccessPolicy.query.filter(
                ScopeAccessPolicy.principal_user_id == actor_user_id,
                ScopeAccessPolicy.permission_key == permission_key,
                ScopeAccessPolicy.integration_instance_id == instance_id,
                ScopeAccessPolicy.scope_level == scope_level,
                ScopeAccessPolicy.provider_namespace == provider_namespace,
                ScopeAccessPolicy.mount == mount,
            )
            .enable_eagerloads(False)
            .order_by(ScopeAccessPolicy.id.asc())
            .limit(_MAX_MATCHING_POLICIES + 1)
        )
        if lock_for_read:
            query = query.with_for_update(of=ScopeAccessPolicy)
        candidates = query.all()
        if len(candidates) > _MAX_MATCHING_POLICIES:
            return ScopeAdmission('deny', 'ambiguous_scope')
        approved_matches: list[tuple[ScopeAccessPolicy, ScopeAccessPolicyRevision, datetime]] = []
        for policy in candidates:
            revisions = ScopeAccessPolicyRevision.query.filter(
                ScopeAccessPolicyRevision.policy_id == policy.id,
                ScopeAccessPolicyRevision.revision_number == policy.current_revision,
            )
            if lock_for_read:
                revisions = revisions.with_for_update(of=ScopeAccessPolicyRevision)
            current = revisions.first()
            ends = _eligible_exact_revision_end(current, instant=instant)
            if ends is None or current is None:
                continue
            approved_matches.append((policy, current, ends))
            if len(approved_matches) > 1:
                return ScopeAdmission('deny', 'ambiguous_scope')
        if len(approved_matches) == 1:
            if scope_level == 'openbao_mount' and lock_for_read:
                source = db.session.get(IntegrationInstance, instance_id, populate_existing=True, with_for_update=True)
                if current_local_inventory_source(
                    source, namespace=provider_namespace, mount=mount, lock=True
                ) is None:
                    return ScopeAdmission('deny', 'source_unqualified')
            policy, current, ends = approved_matches[0]
            return ScopeAdmission(
                'allow',
                'exact_approved_grant',
                actor_id=actor_user_id,
                instance_id=instance_id,
                policy_ref=policy.id,
                revision=current.revision_number,
                expires_at=ends,
            )
        return ScopeAdmission('deny', 'scope_grant_required')
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return ScopeAdmission('unavailable', 'policy_evidence_unavailable')


def _approved_instance_case_revision(revision: ScopeAccessPolicyRevision) -> bool:
    """Keep exact active, separately approved instance-case policy evidence."""
    return not (
        revision.lifecycle_status != 'active'
        or revision.approved_by_user_id is None
        or revision.approved_by_user_id == revision.requested_by_user_id
    )


def evaluate_exact_vault_instance_case_scope(
    *,
    actor_user_id: int,
    instance_id: int,
    now: datetime | None = None,
) -> ScopeAdmission:
    """Authorize exact read scope; never treat it as operator authorization."""
    return _evaluate_exact_vault_instance_case_permission(
        actor_user_id=actor_user_id,
        instance_id=instance_id,
        permission_key=_SENSITIVE_PERMISSION,
        now=now,
    )


def evaluate_exact_vault_instance_operator_scope(
    *,
    actor_user_id: int,
    instance_id: int,
    now: datetime | None = None,
) -> ScopeAdmission:
    """Require independent exact read and decision grants in fixed lock order.

    Internal precondition only. The owning command must requalify its action,
    source, case and mandatory audit in the same transaction. No route is wired.
    """
    instant = now or datetime.now(UTC)
    read = evaluate_exact_vault_instance_case_scope(actor_user_id=actor_user_id, instance_id=instance_id, now=instant)
    if not read.allowed:
        return read
    return _evaluate_exact_vault_instance_case_permission(
        actor_user_id=actor_user_id,
        instance_id=instance_id,
        permission_key=VAULT_CASE_OPERATOR_PERMISSION,
        now=instant,
    )


def _approved_instance_revision_end(revision: ScopeAccessPolicyRevision, *, instant: datetime) -> datetime | None:
    if not _approved_instance_case_revision(revision):
        return None
    start = _timestamp(revision.effective_from)
    end = _timestamp(revision.effective_until)
    approval = _timestamp(revision.approved_at)
    if start is None or end is None or approval is None or start > instant or instant >= end or approval > instant:
        return None
    return end


def _evaluate_exact_vault_instance_case_permission(
    *,
    actor_user_id: int,
    instance_id: int,
    permission_key: str,
    now: datetime | None = None,
) -> ScopeAdmission:
    """Authorize exact instance-level case access, never inherited mount access.

    An allowed decision is only a precondition: the caller must audit and
    commit a sensitive read before projecting any case row.
    """
    if type(actor_user_id) is not int or actor_user_id < 1 or type(instance_id) is not int or instance_id < 1:
        return ScopeAdmission('deny', 'invalid_scope')
    if permission_key not in {_SENSITIVE_PERMISSION, VAULT_CASE_OPERATOR_PERMISSION}:
        return ScopeAdmission('deny', 'invalid_scope')
    instant = _timestamp(now or datetime.now(UTC))
    if instant is None:
        return ScopeAdmission('deny', 'invalid_time')
    try:
        actor = db.session.get(User, actor_user_id, populate_existing=True)
        if (
            actor is None
            or not actor.is_active
            or actor.role_record is None
            or not actor.role_record.is_active
            or not {_SENSITIVE_PERMISSION, 'intelligence.view', permission_key}.issubset(
                actor.role_record.permission_keys()
            )
        ):
            return ScopeAdmission('deny', 'permission_required')
        source = db.session.get(IntegrationInstance, instance_id, populate_existing=True)
        if (
            source is None
            or source.integration_type != 'secrets_pki'
            or source.provider_key != 'vault'
            or not source.enabled
            or source.lifecycle_status != 'active'
        ):
            return ScopeAdmission('deny', 'source_unqualified')
        policies = (
            ScopeAccessPolicy.query.filter(
                ScopeAccessPolicy.principal_user_id == actor_user_id,
                ScopeAccessPolicy.permission_key == permission_key,
                ScopeAccessPolicy.integration_instance_id == instance_id,
                ScopeAccessPolicy.scope_level == 'instance',
                ScopeAccessPolicy.provider_namespace.is_(None),
                ScopeAccessPolicy.mount.is_(None),
            )
            .enable_eagerloads(False)
            .populate_existing()
            .order_by(ScopeAccessPolicy.id.asc())
            .limit(_MAX_MATCHING_POLICIES + 1)
            .with_for_update(of=ScopeAccessPolicy)
            .all()
        )
        if len(policies) > _MAX_MATCHING_POLICIES:
            return ScopeAdmission('deny', 'ambiguous_scope')
        approved: list[tuple[ScopeAccessPolicy, ScopeAccessPolicyRevision, datetime]] = []
        for policy in policies:
            revision = (
                ScopeAccessPolicyRevision.query.filter(
                    ScopeAccessPolicyRevision.policy_id == policy.id,
                    ScopeAccessPolicyRevision.revision_number == policy.current_revision,
                )
                .populate_existing()
                .with_for_update(of=ScopeAccessPolicyRevision)
                .first()
            )
            if revision is None:
                continue
            end = _approved_instance_revision_end(revision, instant=instant)
            if end is None:
                continue
            approved.append((policy, revision, end))
        if len(approved) != 1:
            return ScopeAdmission('deny', 'ambiguous_scope' if approved else 'scope_grant_required')
        policy, revision, end = approved[0]
        return ScopeAdmission(
            'allow',
            'exact_approved_instance_grant',
            actor_id=actor_user_id,
            instance_id=instance_id,
            policy_ref=policy.id,
            revision=revision.revision_number,
            expires_at=end,
        )
    except (SQLAlchemyError, TypeError, ValueError, AttributeError):
        return ScopeAdmission('unavailable', 'policy_evidence_unavailable')


# No default grant or implied permission. These names belong to the canonical Access catalog.
_ISSUER_PERMISSIONS = frozenset(
    {
        'secrets_pki.request_credential_issuer',
        'secrets_pki.approve_credential_issuer',
        'secrets_pki.revoke_credential_issuer',
    }
)
_ISSUER_DEPLOYMENT = re.compile(r'[a-f0-9]{64}')


@dataclass(frozen=True, slots=True, repr=False)
class CredentialIssuerScope:
    instance_id: int
    provider_key: str
    provider_namespace: str
    mount: str
    deployment_ref: str


def _valid_issuer_scope(scope: CredentialIssuerScope) -> bool:
    return (
        isinstance(scope, CredentialIssuerScope)
        and type(scope.instance_id) is int
        and scope.instance_id > 0
        and scope.provider_key in ('vault', 'openbao')
        and isinstance(scope.deployment_ref, str)
        and _ISSUER_DEPLOYMENT.fullmatch(scope.deployment_ref) is not None
        and isinstance(scope.provider_namespace, str)
        and len(scope.provider_namespace) <= 255
        and isinstance(scope.mount, str)
        and 0 < len(scope.mount) <= 160
        and all(
            ord(char) >= 32 and ord(char) != 127 and char not in '*+' for char in scope.provider_namespace + scope.mount
        )
    )


def lock_explicit_permissions(actor_id: int, required: set[str]) -> bool:
    # Lock actual role membership rows, not only a previously loaded relationship.
    actor = db.session.execute(
        select(User).where(User.id == actor_id).with_for_update(of=User).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if actor is None or not actor.is_active or actor.role_id is None:
        return False
    role = db.session.execute(
        select(Role).where(Role.id == actor.role_id).with_for_update(of=Role).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if role is None or not role.is_active:
        return False
    keys = (
        db.session.execute(
            select(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id, Permission.key.in_(required))
            .order_by(Permission.key)
            .with_for_update(of=(RolePermission, Permission))
        )
        .scalars()
        .all()
    )
    return set(keys) == required


def _locked_issuer_source(scope: CredentialIssuerScope, permission_key: str) -> bool:
    source = db.session.execute(
        select(IntegrationInstance)
        .where(IntegrationInstance.id == scope.instance_id)
        .with_for_update(of=IntegrationInstance)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if source is None or source.integration_type != 'secrets_pki' or source.provider_key != scope.provider_key:
        return False
    if permission_key == 'secrets_pki.revoke_credential_issuer':
        # Revocation must remain possible even when the original source is disabled.
        return True
    return source.enabled is True and source.lifecycle_status == 'active' and source.readiness_status == 'ready'


def _locked_issuer_policies(
    actor_id: int, scope: CredentialIssuerScope, permission_key: str
) -> list[ScopeAccessPolicy]:
    return list(
        db.session.execute(
            select(ScopeAccessPolicy)
            .where(
                ScopeAccessPolicy.principal_user_id == actor_id,
                ScopeAccessPolicy.permission_key == permission_key,
                ScopeAccessPolicy.integration_instance_id == scope.instance_id,
                ScopeAccessPolicy.scope_level == 'credential_issuer',
                ScopeAccessPolicy.provider_namespace == scope.provider_namespace,
                ScopeAccessPolicy.mount == scope.mount,
                ScopeAccessPolicy.issuer_deployment_ref == scope.deployment_ref,
            )
            .order_by(ScopeAccessPolicy.id)
            .limit(_MAX_MATCHING_POLICIES + 1)
            .with_for_update(of=ScopeAccessPolicy)
            .execution_options(populate_existing=True)
        )
        .scalars()
        .all()
    )


def _current_issuer_grant(
    policy: ScopeAccessPolicy, instant: datetime
) -> tuple[ScopeAccessPolicyRevision, datetime] | None:
    latest = db.session.execute(
        select(ScopeAccessPolicyRevision)
        .where(ScopeAccessPolicyRevision.policy_id == policy.id)
        .order_by(ScopeAccessPolicyRevision.revision_number.desc())
        .limit(1)
        .with_for_update(of=ScopeAccessPolicyRevision)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if latest is None or latest.revision_number != policy.current_revision:
        return None
    expires = _eligible_exact_revision_end(latest, instant=instant)
    return (latest, expires) if expires is not None else None


def evaluate_exact_issuer_scope(
    *, actor_user_id: int, scope: CredentialIssuerScope, permission_key: str, now: datetime | None = None
) -> ScopeAdmission:
    """Locked Access precondition only, never a custody or deployment attestation.

    Authenticated service caller owns the transaction, current independently
    verified deployment/intent, mandatory audit and rollback. No public route
    may treat this result as a transferable permit. Source and actor locks
    must remain held through the protected transaction.
    """
    if (
        type(actor_user_id) is not int
        or actor_user_id <= 0
        or permission_key not in _ISSUER_PERMISSIONS
        or not _valid_issuer_scope(scope)
    ):
        return ScopeAdmission('deny', 'invalid_scope')
    instant = now or datetime.now(UTC)
    if not isinstance(instant, datetime) or instant.utcoffset() is None:
        return ScopeAdmission('deny', 'invalid_time')
    try:
        if not lock_explicit_permissions(actor_user_id, {permission_key, 'secrets_pki.view'}):
            return ScopeAdmission('deny', 'permission_required')
        if not _locked_issuer_source(scope, permission_key):
            return ScopeAdmission('deny', 'source_unqualified')
        candidates = _locked_issuer_policies(actor_user_id, scope, permission_key)
        if len(candidates) > _MAX_MATCHING_POLICIES:
            return ScopeAdmission('deny', 'ambiguous_scope')
        matches = []
        for candidate in candidates:
            grant = _current_issuer_grant(candidate, instant)
            if grant is not None:
                matches.append((candidate, *grant))
        if len(matches) != 1:
            return ScopeAdmission('deny', 'ambiguous_scope' if matches else 'scope_grant_required')
        policy, current, expires = matches[0]
        return ScopeAdmission(
            'allow',
            'exact_approved_issuer_grant',
            actor_id=actor_user_id,
            instance_id=scope.instance_id,
            policy_ref=policy.id,
            revision=current.revision_number,
            expires_at=expires,
        )
    except (SQLAlchemyError, TypeError, ValueError, AttributeError):
        return ScopeAdmission('unavailable', 'policy_evidence_unavailable')
