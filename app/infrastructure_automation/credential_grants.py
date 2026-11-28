"""Governed automation credential lifecycle candidate (#5184).

Infrastructure Automation qualifies its exact committed target; Access owns
the canonical grant lifecycle primitives and mandatory Activity Audit.
Local activation is explicitly gated; no provider material or dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.access.scope_policy import lock_explicit_permissions
from app.access.scoped_grants import (
    ScopedGrantRejected,
    ScopeGrantValidity,
    commit_scope_grant_transition,
    qualify_scope_grant_validity,
    require_scope_grant_administrator,
    require_scope_grant_principal,
)
from app.extensions.db import db
from app.infrastructure_automation.credential_evidence import resolve_current_credential_evidence
from app.infrastructure_automation.credential_scope_target import (
    CREDENTIAL_USE_PERMISSION,
    READ_ONLY_FACTS_OPERATION,
    exact_credential_target_current,
)
from app.infrastructure_automation.host_enrollment import get_scoped_host_assignment
from app.infrastructure_automation.kubernetes.source_policy import PROFILE_KEY, SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.security_review import (
    begin_security_review_transaction,
    local_security_review_enabled,
)
from app.models.automation import AutomationHostAccessBinding
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.secrets_pki import SecretProviderRepresentation
from app.platform_operations.notifications.service import stage_operational_activity
from app.secrets_pki.issuer_authority import TypedCredentialEvidence


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
        require_scope_grant_administrator(actor_user_id)
        for permission in (CREDENTIAL_USE_PERMISSION, 'secrets_pki.view', 'inventory.view', 'jobs.execute'):
            require_scope_grant_principal(principal_user_id, permission)
        if not isinstance(intent, CredentialGrantIntent):
            raise ScopedGrantRejected('Grant intent is invalid.')
        now = datetime.now(UTC)
        starts, ends = qualify_scope_grant_validity(validity, reason_code, now=now)
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
        policy = ScopeAccessPolicy()
        policy.id = str(uuid4())
        policy.principal_user_id = principal_user_id
        policy.permission_key = CREDENTIAL_USE_PERMISSION
        policy.integration_instance_id = representation.integration_instance_id
        policy.scope_level = 'automation_credential'
        policy.provider_namespace = representation.provider_namespace
        policy.mount = representation.mount
        policy.current_revision = 1
        target = AutomationCredentialScopeTarget()
        target.policy_id = policy.id
        target.ansible_connection_id = intent.connection_id
        target.assignment_id = assignment.id
        target.host_id = assignment.host_id
        target.host_revision = binding.host_revision
        target.reference_fingerprint = binding.reference_fingerprint
        target.secret_identity_id = representation.secret_identity_id
        target.secret_representation_id = representation.id
        target.secret_version = binding.secret_version
        target.source_revision = SOURCE_CANDIDATE_SHA
        target.profile_key = PROFILE_KEY
        target.operation_key = READ_ONLY_FACTS_OPERATION
        if not exact_credential_target_current(policy, target, now=now):
            raise ScopedGrantRejected('Grant target is unavailable.')
        revision = ScopeAccessPolicyRevision()
        revision.policy = policy
        revision.revision_number = 1
        revision.lifecycle_status = 'draft'
        revision.effective_from = starts
        revision.effective_until = ends
        revision.requested_by_user_id = actor_user_id
        revision.change_reason = reason_code
        db.session.add_all((policy, revision))
        db.session.flush()
        db.session.add(target)
        db.session.flush()
        commit_scope_grant_transition(
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


def review_credential_grant_approval(
    *, policy_id: str, approver_user_id: int, expected_revision: int, now: datetime
) -> TypedCredentialEvidence | None:
    """Locked maker/checker precondition for the audited approval writer.

    Does not append an active revision or establish runtime permission. The
    authenticated caller owns the transaction and must roll back on denial.
    """
    if (
        not isinstance(now, datetime)
        or now.utcoffset() is None
        or type(approver_user_id) is not int
        or approver_user_id <= 0
        or type(expected_revision) is not int
        or expected_revision <= 0
        or not lock_explicit_permissions(approver_user_id, {'roles.manage', 'users.manage'})
    ):
        return None
    policy = db.session.execute(
        select(ScopeAccessPolicy)
        .where(ScopeAccessPolicy.id == policy_id)
        .with_for_update(of=ScopeAccessPolicy)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        policy is None
        or policy.scope_level != 'automation_credential'
        or policy.permission_key != CREDENTIAL_USE_PERMISSION
        or policy.current_revision != expected_revision
        or approver_user_id == policy.principal_user_id
    ):
        return None
    current = _latest_revision(policy.id)
    if (
        current is None
        or current.revision_number != expected_revision
        or current.lifecycle_status != 'draft'
        or current.requested_by_user_id == approver_user_id
        or current.effective_from.utcoffset() is None
        or current.effective_until.utcoffset() is None
        or current.effective_until <= now
    ):
        return None
    if not lock_explicit_permissions(current.requested_by_user_id, {'roles.manage', 'users.manage'}):
        return None
    if not lock_explicit_permissions(
        policy.principal_user_id,
        {CREDENTIAL_USE_PERMISSION, 'secrets_pki.view', 'inventory.view', 'jobs.execute'},
    ):
        return None
    target = db.session.get(AutomationCredentialScopeTarget, policy.id, populate_existing=True, with_for_update=True)
    if target is None:
        return None
    evidence = resolve_current_credential_evidence(policy, target, now=now)
    if evidence is None or current.effective_until > evidence.expires_at:
        return None
    # The activation writer serializes local approval transactions. Refuse
    # any overlapping active grant for this principal and assignment, even
    # when another grant has stale metadata or an unqualified proof.
    candidates = db.session.execute(
        select(ScopeAccessPolicy)
        .join(AutomationCredentialScopeTarget, AutomationCredentialScopeTarget.policy_id == ScopeAccessPolicy.id)
        .where(
            ScopeAccessPolicy.id != policy.id,
            ScopeAccessPolicy.principal_user_id == policy.principal_user_id,
            ScopeAccessPolicy.permission_key == CREDENTIAL_USE_PERMISSION,
            ScopeAccessPolicy.scope_level == 'automation_credential',
            AutomationCredentialScopeTarget.ansible_connection_id == target.ansible_connection_id,
            AutomationCredentialScopeTarget.assignment_id == target.assignment_id,
        )
        .order_by(ScopeAccessPolicy.id)
        .limit(33)
        .with_for_update(of=ScopeAccessPolicy)
        .execution_options(populate_existing=True)
    ).scalars().all()
    if len(candidates) > 32:
        return None
    for candidate in candidates:
        latest = _latest_revision(candidate.id)
        if latest is None or latest.revision_number != candidate.current_revision:
            return None
        if latest.lifecycle_status == 'active' and (
            latest.effective_from.utcoffset() is None
            or latest.effective_until.utcoffset() is None
            or (
                latest.effective_from < current.effective_until
                and current.effective_from < latest.effective_until
            )
        ):
            return None
    return evidence


@dataclass(frozen=True, slots=True, repr=False)
class CurrentCredentialGrant:
    policy_id: str
    revision: int
    evidence: TypedCredentialEvidence
    expires_at: datetime


def _latest_revision(policy_id: str) -> ScopeAccessPolicyRevision | None:
    return db.session.execute(
        select(ScopeAccessPolicyRevision)
        .where(ScopeAccessPolicyRevision.policy_id == policy_id)
        .order_by(ScopeAccessPolicyRevision.revision_number.desc())
        .limit(1)
        .with_for_update(of=ScopeAccessPolicyRevision)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def approve_automation_credential_grant(
    *, policy_id: str, approver_user_id: int, expected_revision: int
) -> int:
    """Append independently approved active revision in local review only.

    This does not permit material retrieval or dispatch. All inputs are opaque
    canonical identifiers; no signature, path or proof is supplied by caller.
    """
    committed = False
    try:
        begin_security_review_transaction()
        now = datetime.now(UTC)
        evidence = review_credential_grant_approval(
            policy_id=policy_id, approver_user_id=approver_user_id,
            expected_revision=expected_revision, now=now,
        )
        if evidence is None:
            raise ScopedGrantRejected('Credential grant approval is unavailable.')
        policy = db.session.get(ScopeAccessPolicy, policy_id)
        current = _latest_revision(policy_id)
        if policy is None or current is None:
            raise ScopedGrantRejected('Credential grant approval is unavailable.')
        approved_at = datetime.now(UTC)
        revision = ScopeAccessPolicyRevision(
            policy_id=policy.id,
            revision_number=expected_revision + 1,
            lifecycle_status='active',
            effective_from=current.effective_from,
            effective_until=current.effective_until,
            requested_by_user_id=current.requested_by_user_id,
            approved_by_user_id=approver_user_id,
            approved_at=approved_at,
            change_reason=current.change_reason,
            credential_evidence_ref=evidence.evidence_ref,
        )
        if approved_at >= current.effective_until or approved_at >= evidence.expires_at:
            raise ScopedGrantRejected('Credential grant approval is unavailable.')
        db.session.add(revision)
        policy.current_revision = revision.revision_number
        db.session.flush()
        stage_operational_activity(
            user_id=approver_user_id,
            event_type='access_scope_grant_approved',
            status='success',
            title='Scoped Grant Approved',
            message='A local automation credential grant was approved; execution remains blocked.',
            metadata={
                'actor_user_id': approver_user_id,
                'policy_ref': policy.id,
                'policy_revision': revision.revision_number,
                'permission_key': policy.permission_key,
                'scope_level': policy.scope_level,
                'integration_instance_id': policy.integration_instance_id,
                'audit_contract': 'scoped_policy.v1',
                'execution_authorized': False,
            },
        )
        target = db.session.get(AutomationCredentialScopeTarget, policy.id)
        if target is None or resolve_current_credential_evidence(policy, target, now=datetime.now(UTC)) != evidence:
            raise ScopedGrantRejected('Credential grant evidence changed.')
        db.session.commit()
        committed = True
        return expected_revision + 1
    finally:
        if not committed:
            db.session.rollback()


def review_current_credential_grant(
    *, actor_user_id: int, connection_id: int, assignment_id: int, now: datetime
) -> CurrentCredentialGrant | None:
    """Resolve one current approved exact grant, never a transferable permit.

    Caller owns the transaction and must independently qualify operation,
    target, worker, trust, audit and provider before any material use.
    """
    if (
        not local_security_review_enabled()
        or not isinstance(now, datetime)
        or now.utcoffset() is None
        or any(type(value) is not int or value <= 0 for value in (actor_user_id, connection_id, assignment_id))
        or not lock_explicit_permissions(
            actor_user_id,
            {CREDENTIAL_USE_PERMISSION, 'secrets_pki.view', 'inventory.view', 'jobs.execute'},
        )
    ):
        return None
    policies = db.session.execute(
        select(ScopeAccessPolicy)
        .join(AutomationCredentialScopeTarget, AutomationCredentialScopeTarget.policy_id == ScopeAccessPolicy.id)
        .where(
            ScopeAccessPolicy.principal_user_id == actor_user_id,
            ScopeAccessPolicy.permission_key == CREDENTIAL_USE_PERMISSION,
            ScopeAccessPolicy.scope_level == 'automation_credential',
            AutomationCredentialScopeTarget.ansible_connection_id == connection_id,
            AutomationCredentialScopeTarget.assignment_id == assignment_id,
        )
        .order_by(ScopeAccessPolicy.id)
        .limit(33)
        .with_for_update(of=ScopeAccessPolicy)
        .execution_options(populate_existing=True)
    ).scalars().all()
    if len(policies) > 32:
        return None
    matches = []
    for policy in policies:
        current = _latest_revision(policy.id)
        if current is None or current.revision_number != policy.current_revision:
            return None
        if current.lifecycle_status != 'active':
            continue
        if current.effective_from.utcoffset() is None or current.effective_until.utcoffset() is None:
            return None
        if current.effective_from <= now < current.effective_until:
            matches.append((policy, current))
    if len(matches) != 1:
        return None
    policy, current = matches[0]
    checker = current.approved_by_user_id
    if (
        checker is None
        or checker in (current.requested_by_user_id, actor_user_id)
        or current.approved_at is None
        or current.approved_at.utcoffset() is None
        or current.approved_at > now
        or current.credential_evidence_ref is None
        or not lock_explicit_permissions(checker, {'roles.manage', 'users.manage'})
        or not lock_explicit_permissions(current.requested_by_user_id, {'roles.manage', 'users.manage'})
    ):
        return None
    target = db.session.get(AutomationCredentialScopeTarget, policy.id, populate_existing=True, with_for_update=True)
    if target is None:
        return None
    evidence = resolve_current_credential_evidence(policy, target, now=now)
    if (
        evidence is None
        or evidence.evidence_ref != current.credential_evidence_ref
        or not evidence.issued_at <= current.approved_at <= now < current.effective_until <= evidence.expires_at
    ):
        return None
    return CurrentCredentialGrant(policy.id, current.revision_number, evidence, current.effective_until)
