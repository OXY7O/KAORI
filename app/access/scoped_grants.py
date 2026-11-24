"""Governed scope-policy lifecycle; no Secret read authorization is exposed.

#724 / #2724. Existing Access RBAC and Activity Audit remain authoritative.
The policy evaluator and Vault Secret Registry are intentionally NOT enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import load_only

from app.extensions.db import db
from app.infrastructure_automation.credential_scope_target import (
    CREDENTIAL_USE_PERMISSION,
    READ_ONLY_FACTS_OPERATION,
    exact_credential_target_current,
)
from app.infrastructure_automation.host_enrollment import get_scoped_host_assignment
from app.infrastructure_automation.kubernetes.source_policy import PROFILE_KEY, SOURCE_CANDIDATE_SHA
from app.models.automation import AutomationHostAccessBinding
from app.models.integration import IntegrationInstance
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.secrets_pki import SecretProviderRepresentation
from app.models.user import User
from app.models.vault import VaultInstance
from app.platform_operations.notifications.service import stage_operational_activity

_ADMIN_PERMISSIONS = frozenset({'roles.manage', 'users.manage'})
_SUPPORTED_PERMISSION = 'secrets_pki.view'
_REASON_CODES = frozenset({'operational_access', 'incident_response', 'audit_review'})


class ScopedGrantRejected(ValueError):
    """A scoped policy transition is not authorized or fails qualification."""


def _administrator(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or user.role_record is None
        or not user.role_record.is_active
        or not _ADMIN_PERMISSIONS.issubset(user.role_record.permission_keys())
    ):
        # An unassigned local Super Admin is not an implicit resource-policy administrator.
        raise ScopedGrantRejected('Scoped grant administration is not authorized.')
    return user


def _principal(user_id: int, permission_key: str) -> None:
    user = db.session.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or user.role_record is None
        or not user.role_record.is_active
        or permission_key not in user.role_record.permission_keys()
    ):
        raise ScopedGrantRejected('Grant principal is not eligible for the requested permission.')


def _target(
    *,
    integration_instance_id: int,
    scope_level: str,
    provider_namespace: str | None,
    mount: str | None,
) -> tuple[str | None, str | None]:
    identity = db.session.get(IntegrationInstance, integration_instance_id)
    if (
        identity is None
        or not identity.enabled
        or identity.lifecycle_status != 'active'
        or identity.integration_type != 'secrets_pki'
        or identity.provider_key != 'vault'
    ):
        raise ScopedGrantRejected('Grant target is unavailable.')
    vault = VaultInstance.query.filter_by(integration_instance_id=integration_instance_id).first()
    if vault is None:
        raise ScopedGrantRejected('Grant target is unavailable.')
    if scope_level == 'instance' and provider_namespace is None and mount is None:
        return None, None
    if scope_level != 'vault_mount':
        raise ScopedGrantRejected('Grant requires an exact approved scope.')
    namespace = str(vault.namespace or '')
    # No automatic inheritance, arbitrary provider path, wildcard or partial mount name.
    if provider_namespace != namespace or not mount or mount not in (vault.kv2_mounts or []):
        raise ScopedGrantRejected('Grant requires an exact approved scope.')
    if '*' in mount or len(mount) > 160:
        raise ScopedGrantRejected('Grant requires an exact approved scope.')
    return namespace, mount


def _window(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ScopedGrantRejected(f'{label} must be timezone-aware.')
    return value.astimezone(UTC)


def _persisted_window(value: datetime) -> datetime:
    """Read existing UTC validity after database timezone metadata round-trips."""
    if not isinstance(value, datetime):
        raise ScopedGrantRejected('Persisted grant validity is unavailable.')
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _commit_transition(
    *,
    actor_user_id: int,
    policy: ScopeAccessPolicy,
    revision_number: int,
    event_type: str,
    label: str,
) -> None:
    # Stage the canonical Activity Audit record into the SAME transaction.
    # Unlike record_operational_activity, this propagates persistence errors.
    # Do not put Vault path, mount, namespace, Secret identity or credentials in the audit.
    stage_operational_activity(
        user_id=actor_user_id,
        event_type=event_type,
        status='success',
        title=label,
        message='A governed scoped policy lifecycle change was recorded.',
        metadata={
            'actor_user_id': actor_user_id,
            'policy_ref': policy.id,
            'policy_revision': revision_number,
            'permission_key': policy.permission_key,
            'scope_level': policy.scope_level,
            'integration_instance_id': policy.integration_instance_id,
            'audit_contract': 'scoped_policy.v1',
        },
    )
    db.session.commit()


@dataclass(frozen=True, slots=True)
class ScopeGrantValidity:
    effective_from: datetime
    effective_until: datetime


def request_scope_grant(
    *,
    actor_user_id: int,
    principal_user_id: int,
    integration_instance_id: int,
    scope_level: str,
    provider_namespace: str | None,
    mount: str | None,
    validity: ScopeGrantValidity,
    reason_code: str,
) -> ScopeAccessPolicy:
    """Create draft only; requesting a policy NEVER activates a permit."""
    _administrator(actor_user_id)
    _principal(principal_user_id, _SUPPORTED_PERMISSION)
    namespace, exact_mount = _target(
        integration_instance_id=integration_instance_id,
        scope_level=scope_level,
        provider_namespace=provider_namespace,
        mount=mount,
    )
    if not isinstance(validity, ScopeGrantValidity):
        raise ScopedGrantRejected('Grant validity or reason is invalid.')
    starts, ends = _window(validity.effective_from, 'Start'), _window(validity.effective_until, 'End')
    if starts >= ends or ends <= datetime.now(UTC) or reason_code not in _REASON_CODES:
        raise ScopedGrantRejected('Grant validity or reason is invalid.')
    policy = ScopeAccessPolicy()
    policy.principal_user_id = principal_user_id
    policy.permission_key = _SUPPORTED_PERMISSION
    policy.integration_instance_id = integration_instance_id
    policy.scope_level = scope_level
    policy.provider_namespace = namespace
    policy.mount = exact_mount
    policy.current_revision = 1
    revision = ScopeAccessPolicyRevision()
    revision.policy = policy
    revision.revision_number = 1
    revision.lifecycle_status = 'draft'
    revision.effective_from = starts
    revision.effective_until = ends
    revision.requested_by_user_id = actor_user_id
    revision.change_reason = reason_code
    try:
        db.session.add(policy)
        db.session.add(revision)
        db.session.flush()
        _commit_transition(
            actor_user_id=actor_user_id,
            policy=policy,
            revision_number=1,
            event_type='access_scope_grant_requested',
            label='Scoped Grant Requested',
        )
    except Exception:
        db.session.rollback()
        raise
    return policy


@dataclass(frozen=True, slots=True, repr=False)
class CredentialGrantIntent:
    connection_id: int
    host_id: str
    expected_host_revision: str
    expected_reference_fingerprint: str


def request_automation_credential_grant(
    *,
    actor_user_id: int,
    principal_user_id: int,
    intent: CredentialGrantIntent,
    validity: ScopeGrantValidity,
    reason_code: str,
) -> ScopeAccessPolicy:
    """Record an exact draft and mandatory audit, never an active credential grant.

    The caller supplies authenticated identities and an opaque host selection,
    not a provider path, material, operation, scope or approval flag.
    """
    committed = False
    try:
        _administrator(actor_user_id)
        for permission in (CREDENTIAL_USE_PERMISSION, 'secrets_pki.view', 'inventory.view', 'jobs.execute'):
            _principal(principal_user_id, permission)
        if not isinstance(intent, CredentialGrantIntent) or not isinstance(validity, ScopeGrantValidity):
            raise ScopedGrantRejected('Grant intent or validity is invalid.')
        starts, ends = _window(validity.effective_from, 'Start'), _window(validity.effective_until, 'End')
        now = datetime.now(UTC)
        if starts >= ends or ends <= now or reason_code not in _REASON_CODES:
            raise ScopedGrantRejected('Grant validity or reason is invalid.')
        assignment = get_scoped_host_assignment(intent.connection_id, intent.host_id)
        if assignment is None:
            raise ScopedGrantRejected('Grant target is unavailable.')
        binding = db.session.get(AutomationHostAccessBinding, assignment.id, populate_existing=True)
        if (
            binding is None
            or binding.host_revision != intent.expected_host_revision
            or binding.reference_fingerprint != intent.expected_reference_fingerprint
        ):
            raise ScopedGrantRejected('Grant target is unavailable.')
        representation = db.session.get(
            SecretProviderRepresentation,
            binding.secret_representation_id,
            populate_existing=True,
            options=[
                load_only(
                    SecretProviderRepresentation.id,
                    SecretProviderRepresentation.integration_instance_id,
                    SecretProviderRepresentation.provider_namespace,
                    SecretProviderRepresentation.mount,
                    SecretProviderRepresentation.secret_identity_id,
                )
            ],
        )
        if representation is None:
            raise ScopedGrantRejected('Grant target is unavailable.')
        policy = ScopeAccessPolicy(
            id=str(uuid4()),
            principal_user_id=principal_user_id,
            permission_key=CREDENTIAL_USE_PERMISSION,
            integration_instance_id=representation.integration_instance_id,
            scope_level='automation_credential',
            provider_namespace=representation.provider_namespace,
            mount=representation.mount,
            current_revision=1,
        )
        target = AutomationCredentialScopeTarget(
            policy_id=policy.id,
            ansible_connection_id=intent.connection_id,
            assignment_id=assignment.id,
            host_id=assignment.host_id,
            host_revision=binding.host_revision,
            reference_fingerprint=binding.reference_fingerprint,
            secret_identity_id=representation.secret_identity_id,
            secret_representation_id=representation.id,
            secret_version=binding.secret_version,
            source_revision=SOURCE_CANDIDATE_SHA,
            profile_key=PROFILE_KEY,
            operation_key=READ_ONLY_FACTS_OPERATION,
        )
        if not exact_credential_target_current(policy, target, now=now):
            raise ScopedGrantRejected('Grant target is unavailable.')
        revision = ScopeAccessPolicyRevision(
            policy=policy,
            revision_number=1,
            lifecycle_status='draft',
            effective_from=starts,
            effective_until=ends,
            requested_by_user_id=actor_user_id,
            change_reason=reason_code,
        )
        db.session.add_all((policy, revision))
        db.session.flush()
        db.session.add(target)
        db.session.flush()
        _commit_transition(
            actor_user_id=actor_user_id,
            policy=policy,
            revision_number=1,
            event_type='access_scope_grant_requested',
            label='Scoped Grant Requested',
        )
        committed = True
    finally:
        if not committed:
            db.session.rollback()
    return policy


def _lock_current(policy_id: str) -> tuple[ScopeAccessPolicy, ScopeAccessPolicyRevision]:
    policy = (
        ScopeAccessPolicy.query.filter_by(id=policy_id)
        .enable_eagerloads(False)
        .with_for_update(of=ScopeAccessPolicy)
        .first()
    )
    if policy is None:
        raise ScopedGrantRejected('Scoped policy is unavailable.')
    revision = ScopeAccessPolicyRevision.query.filter_by(
        policy_id=policy.id,
        revision_number=policy.current_revision,
    ).first()
    if revision is None:
        raise ScopedGrantRejected('Scoped policy revision is unavailable.')
    return policy, revision


def approve_scope_grant(
    *,
    policy_id: str,
    approver_user_id: int,
    expected_revision: int,
) -> ScopeAccessPolicy:
    """Independently approve an exact draft and commit mandatory audit atomically."""
    _administrator(approver_user_id)
    try:
        policy, current = _lock_current(policy_id)
        if (
            expected_revision != policy.current_revision
            or current.lifecycle_status != 'draft'
            or current.requested_by_user_id == approver_user_id
        ):
            raise ScopedGrantRejected('Grant approval is stale or is not independent.')
        _principal(policy.principal_user_id, policy.permission_key)
        _target(
            integration_instance_id=policy.integration_instance_id,
            scope_level=policy.scope_level,
            provider_namespace=policy.provider_namespace,
            mount=policy.mount,
        )
        if _persisted_window(current.effective_until) <= datetime.now(UTC):
            raise ScopedGrantRejected('Grant validity has expired.')
        revision = ScopeAccessPolicyRevision()
        revision.policy_id = policy.id
        revision.revision_number = expected_revision + 1
        revision.lifecycle_status = 'active'
        revision.effective_from = current.effective_from
        revision.effective_until = current.effective_until
        revision.requested_by_user_id = current.requested_by_user_id
        revision.approved_by_user_id = approver_user_id
        revision.approved_at = datetime.now(UTC)
        revision.change_reason = current.change_reason
        db.session.add(revision)
        policy.current_revision = revision.revision_number
        db.session.flush()
        _commit_transition(
            actor_user_id=approver_user_id,
            policy=policy,
            revision_number=revision.revision_number,
            event_type='access_scope_grant_approved',
            label='Scoped Grant Approved',
        )
    except Exception:
        db.session.rollback()
        raise
    return policy


def revoke_scope_grant(
    *,
    policy_id: str,
    actor_user_id: int,
    expected_revision: int,
) -> ScopeAccessPolicy:
    """Immediately revoke a current active grant, retaining immutable history."""
    _administrator(actor_user_id)
    try:
        policy, current = _lock_current(policy_id)
        if expected_revision != policy.current_revision or current.lifecycle_status != 'active':
            raise ScopedGrantRejected('Scoped grant is not active or revision has changed.')
        revision = ScopeAccessPolicyRevision()
        revision.policy_id = policy.id
        revision.revision_number = expected_revision + 1
        revision.lifecycle_status = 'revoked'
        revision.effective_from = current.effective_from
        revision.effective_until = current.effective_until
        revision.requested_by_user_id = actor_user_id
        revision.approved_by_user_id = current.approved_by_user_id
        revision.approved_at = current.approved_at
        revision.change_reason = 'revocation'
        db.session.add(revision)
        policy.current_revision = revision.revision_number
        db.session.flush()
        _commit_transition(
            actor_user_id=actor_user_id,
            policy=policy,
            revision_number=revision.revision_number,
            event_type='access_scope_grant_revoked',
            label='Scoped Grant Revoked',
        )
    except Exception:
        db.session.rollback()
        raise
    return policy
