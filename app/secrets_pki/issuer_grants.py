"""Governed issuer scope grants using canonical Access revision and audit (#5245).

Internal authenticated administrator caller only; no public route or seeded
grant. A signed deployment receipt is required for request/approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import CredentialIssuerScope
from app.access.scoped_grants import (
    ScopedGrantRejected,
    ScopeGrantValidity,
    commit_scope_grant_transition,
    qualify_scope_grant_validity,
    require_scope_grant_administrator,
    require_scope_grant_principal,
)
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.secrets_pki.issuer_authority import resolve_deployment_authority

_REQUEST = 'secrets_pki.request_credential_issuer'
_APPROVE = 'secrets_pki.approve_credential_issuer'
_REVOKE = 'secrets_pki.revoke_credential_issuer'
_PERMISSIONS = frozenset({_REQUEST, _APPROVE, _REVOKE})


@dataclass(frozen=True, slots=True, repr=False)
class IssuerGrantIntent:
    scope: CredentialIssuerScope
    principal_user_id: int
    permission_key: str
    validity: ScopeGrantValidity
    reason_code: str


def _deny() -> ScopedGrantRejected:
    return ScopedGrantRejected('Issuer scope grant could not be recorded.')


def _require_principal(principal: int, permission: str, scope: CredentialIssuerScope, now: datetime) -> None:
    if type(principal) is not int or principal <= 0 or permission not in _PERMISSIONS:
        raise _deny()
    require_scope_grant_principal(principal, permission)
    require_scope_grant_principal(principal, 'secrets_pki.view')
    source = db.session.get(IntegrationInstance, scope.instance_id, with_for_update=True, populate_existing=True)
    evidence = resolve_deployment_authority(scope, now=now)
    if (
        source is None
        or source.integration_type != 'secrets_pki'
        or source.provider_key != scope.provider_key
        or not source.enabled
        or source.lifecycle_status != 'active'
        or source.readiness_status != 'ready'
        or evidence is None
    ):
        raise _deny()
    if permission == _REQUEST and principal != evidence.source_owner_id:
        raise _deny()
    if permission == _APPROVE and principal != evidence.checker_id:
        raise _deny()
    if permission == _REVOKE and principal == evidence.source_owner_id:
        raise _deny()


def request_issuer_grant(*, actor_user_id: int, intent: IssuerGrantIntent) -> str:
    committed = False
    try:
        require_scope_grant_administrator(actor_user_id)
        if not isinstance(intent, IssuerGrantIntent) or not isinstance(intent.scope, CredentialIssuerScope):
            raise _deny()
        now = datetime.now(UTC)
        _require_principal(intent.principal_user_id, intent.permission_key, intent.scope, now)
        starts, ends = qualify_scope_grant_validity(intent.validity, intent.reason_code, now=now)
        policy = ScopeAccessPolicy()
        policy.principal_user_id = intent.principal_user_id
        policy.permission_key = intent.permission_key
        policy.integration_instance_id = intent.scope.instance_id
        policy.scope_level = 'credential_issuer'
        policy.provider_namespace = intent.scope.provider_namespace
        policy.mount = intent.scope.mount
        policy.issuer_deployment_ref = intent.scope.deployment_ref
        policy.current_revision = 1
        revision = ScopeAccessPolicyRevision()
        revision.policy = policy
        revision.revision_number = 1
        revision.lifecycle_status = 'draft'
        revision.effective_from = starts
        revision.effective_until = ends
        revision.requested_by_user_id = actor_user_id
        revision.change_reason = intent.reason_code
        db.session.add_all((policy, revision))
        db.session.flush()
        policy_id = policy.id
        commit_scope_grant_transition(
            actor_user_id=actor_user_id,
            policy=policy,
            revision_number=1,
            event_type='access_scope_grant_requested',
            label='Scoped Grant Requested',
        )
        committed = True
        return policy_id
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()


def _locked_policy(policy_id: str) -> tuple[ScopeAccessPolicy, ScopeAccessPolicyRevision]:
    policy = db.session.execute(
        select(ScopeAccessPolicy)
        .where(ScopeAccessPolicy.id == policy_id)
        .with_for_update(of=ScopeAccessPolicy)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if policy is None or policy.scope_level != 'credential_issuer' or policy.permission_key not in _PERMISSIONS:
        raise _deny()
    current = db.session.execute(
        select(ScopeAccessPolicyRevision)
        .where(ScopeAccessPolicyRevision.policy_id == policy.id)
        .order_by(ScopeAccessPolicyRevision.revision_number.desc())
        .limit(1)
        .with_for_update(of=ScopeAccessPolicyRevision)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if current is None or current.revision_number != policy.current_revision:
        raise _deny()
    return policy, current


def _policy_scope(policy: ScopeAccessPolicy) -> CredentialIssuerScope:
    source = db.session.get(IntegrationInstance, policy.integration_instance_id, populate_existing=True)
    if (
        source is None
        or not isinstance(policy.provider_namespace, str)
        or not isinstance(policy.mount, str)
        or not isinstance(policy.issuer_deployment_ref, str)
    ):
        raise _deny()
    return CredentialIssuerScope(
        source.id, source.provider_key, policy.provider_namespace, policy.mount, policy.issuer_deployment_ref
    )


def approve_issuer_grant(*, actor_user_id: int, policy_id: str, expected_revision: int) -> None:
    committed = False
    try:
        require_scope_grant_administrator(actor_user_id)
        policy, current = _locked_policy(policy_id)
        now = datetime.now(UTC)
        if (
            type(expected_revision) is not int
            or expected_revision != current.revision_number
            or current.lifecycle_status != 'draft'
            or actor_user_id in (current.requested_by_user_id, policy.principal_user_id)
            or current.effective_until.utcoffset() is None
            or current.effective_until <= now
        ):
            raise _deny()
        _require_principal(policy.principal_user_id, policy.permission_key, _policy_scope(policy), now)
        revision = ScopeAccessPolicyRevision()
        revision.policy_id = policy.id
        revision.revision_number = expected_revision + 1
        revision.lifecycle_status = 'active'
        revision.effective_from = current.effective_from
        revision.effective_until = current.effective_until
        revision.requested_by_user_id = current.requested_by_user_id
        revision.approved_by_user_id = actor_user_id
        revision.approved_at = now
        revision.change_reason = current.change_reason
        db.session.add(revision)
        policy.current_revision = revision.revision_number
        db.session.flush()
        commit_scope_grant_transition(
            actor_user_id=actor_user_id,
            policy=policy,
            revision_number=revision.revision_number,
            event_type='access_scope_grant_approved',
            label='Scoped Grant Approved',
        )
        committed = True
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()


def revoke_issuer_grant(*, actor_user_id: int, policy_id: str, expected_revision: int) -> None:
    """Immediate scoped grant withdrawal; no provider availability prerequisite."""
    committed = False
    try:
        require_scope_grant_administrator(actor_user_id)
        policy, current = _locked_policy(policy_id)
        if (
            type(expected_revision) is not int
            or expected_revision != current.revision_number
            or current.lifecycle_status not in ('draft', 'active')
        ):
            raise _deny()
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
        commit_scope_grant_transition(
            actor_user_id=actor_user_id,
            policy=policy,
            revision_number=revision.revision_number,
            event_type='access_scope_grant_revoked',
            label='Scoped Grant Revoked',
        )
        committed = True
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()
