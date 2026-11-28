"""Internal SSH trust revocation and latest-revision resolution (#5185).

Revocation does not require the candidate or console evidence to remain current.
No trust activation or execution authority is provided by this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.access.scope_policy import lock_explicit_permissions
from app.access.scoped_grants import require_scope_grant_administrator
from app.extensions.db import db
from app.infrastructure_automation.credential_scope_target import exact_credential_target_current
from app.infrastructure_automation.ssh_trust_authority import ConsoleEvidence, console_target, resolve_console_evidence
from app.infrastructure_automation.ssh_trust_candidate import trust_revision_candidate_matches
from app.models.automation import AutomationHostAccessBinding, AutomationHostTrustRevision, AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy
from app.platform_operations.notifications.service import stage_operational_activity


class SSHTrustTransitionDenied(ValueError):
    """Generic denial of an unavailable or unauthorized trust transition."""


def latest_host_trust_revision(assignment_id: int, *, lock: bool = False) -> AutomationHostTrustRevision | None:
    """Resolve the latest revision regardless of state, never an older active row.

    The caller must enforce scope; for a writer, hold the assignment lock
    before this query, including when no revision exists.
    """
    query = (
        AutomationHostTrustRevision.query.filter_by(assignment_id=assignment_id)
        .order_by(AutomationHostTrustRevision.revision_number.desc())
        .populate_existing()
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def _locked_revocation_target(
    *, actor_id: int, connection_id: int, assignment_id: int
) -> AutomationInventoryAssignment:
    actor = require_scope_grant_administrator(actor_id)
    role = actor.role_record
    if role is None or not {'integrations.manage', 'inventory.view'}.issubset(role.permission_keys()):
        raise SSHTrustTransitionDenied('SSH trust revocation is not available.')
    connection = db.session.get(IntegrationInstance, connection_id, populate_existing=True, with_for_update=True)
    assignment = db.session.get(
        AutomationInventoryAssignment, assignment_id, populate_existing=True, with_for_update=True
    )
    if (
        connection is None
        or connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or assignment is None
        or assignment.integration_instance_id != connection.id
    ):
        raise SSHTrustTransitionDenied('SSH trust revocation is not available.')
    return assignment


def _revoked_revision(current: AutomationHostTrustRevision, actor_id: int) -> AutomationHostTrustRevision:
    record = AutomationHostTrustRevision()
    record.assignment_id = current.assignment_id
    record.revision_number = current.revision_number + 1
    record.lifecycle_status = 'revoked'
    record.host_revision = current.host_revision
    record.reference_fingerprint = current.reference_fingerprint
    record.address = current.address
    record.ssh_port = current.ssh_port
    record.algorithm = current.algorithm
    record.public_key = current.public_key
    record.host_key_digest = current.host_key_digest
    record.source_kind = current.source_kind
    record.evidence_ref = current.evidence_ref
    record.requested_by_user_id = current.requested_by_user_id
    record.verified_by_user_id = current.verified_by_user_id
    record.verified_at = current.verified_at
    record.effective_until = current.effective_until
    record.recorded_at = datetime.now(UTC)
    record.recorded_by_user_id = actor_id
    return record


def revoke_host_trust(*, actor_id: int, connection_id: int, assignment_id: int, expected_revision: int) -> int:
    """Append a terminal revocation and mandatory audit atomically.

    No provider or SSH operation is performed. Expired evidence and disabled
    inventory are intentionally revocable; no old active row is modified.
    """
    committed = False
    try:
        if any(
            type(value) is not int or value <= 0
            for value in (actor_id, connection_id, assignment_id, expected_revision)
        ):
            raise SSHTrustTransitionDenied('SSH trust revocation is not available.')
        assignment = _locked_revocation_target(
            actor_id=actor_id, connection_id=connection_id, assignment_id=assignment_id
        )
        current = latest_host_trust_revision(assignment.id, lock=True)
        if current is None or current.revision_number != expected_revision or current.lifecycle_status != 'active':
            raise SSHTrustTransitionDenied('SSH trust revocation is not available.')
        record = _revoked_revision(current, actor_id)
        db.session.add(record)
        db.session.flush()
        stage_operational_activity(
            user_id=actor_id,
            event_type='automation_host_trust_revoked',
            status='success',
            title='SSH Host Trust Revoked',
            message='The latest SSH host trust revision was revoked. Execution remains blocked.',
            metadata={
                'actor_user_id': actor_id,
                'integration_instance_id': connection_id,
                'assignment_id': assignment.id,
                'trust_revision': record.revision_number,
                'execution_authorized': False,
            },
        )
        revision = record.revision_number
        db.session.commit()
        committed = True
        return revision
    finally:
        if not committed:
            db.session.rollback()


def _current_console_context(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> tuple[AutomationInventoryAssignment, AutomationHostAccessBinding, AutomationHostTrustRevision | None] | None:
    # Caller owns locked canonical policy and target; re-use the complete
    # reference/collection/source qualification rather than a second classifier.
    if not exact_credential_target_current(policy, target, now=now):
        return None
    assignment = db.session.get(
        AutomationInventoryAssignment, target.assignment_id, populate_existing=True, with_for_update=True
    )
    binding = db.session.get(
        AutomationHostAccessBinding, target.assignment_id, populate_existing=True, with_for_update=True
    )
    if assignment is None or binding is None:
        return None
    return assignment, binding, latest_host_trust_revision(assignment.id, lock=True)


def _console_actors_current(requester_id: int, verifier_id: int) -> bool:
    if (
        type(requester_id) is not int
        or requester_id <= 0
        or type(verifier_id) is not int
        or verifier_id <= 0
        or requester_id == verifier_id
    ):
        return False
    # Proposed verifier authority follows the existing administrative trust
    # revocation boundary. Do not infer authorization from console evidence.
    for actor_id in sorted((requester_id, verifier_id)):
        permissions = {'integrations.manage', 'inventory.view'}
        if actor_id == verifier_id:
            permissions.update(('roles.manage', 'users.manage'))
        if not lock_explicit_permissions(actor_id, permissions):
            return False
    return True


def review_console_trust_activation(
    policy: ScopeAccessPolicy,
    target: AutomationCredentialScopeTarget,
    *,
    requester_id: int,
    verifier_id: int,
    expected_revision: int,
    now: datetime,
) -> ConsoleEvidence | None:
    """Review proposed next trust revision, without writing or granting trust."""
    if (
        type(expected_revision) is not int
        or expected_revision < 0
        or not _console_actors_current(requester_id, verifier_id)
    ):
        return None
    context = _current_console_context(policy, target, now=now)
    if context is None:
        return None
    assignment, binding, latest = context
    if latest is None:
        if expected_revision != 0:
            return None
    elif latest.revision_number != expected_revision or latest.lifecycle_status != 'revoked':
        # Never overwrite existing trust or revive an old active revision.
        return None
    selected = console_target(
        assignment,
        binding,
        revision_number=expected_revision + 1,
        requester_id=requester_id,
        verifier_id=verifier_id,
    )
    if selected is None:
        return None
    evidence = resolve_console_evidence(selected, now=now)
    if evidence is None or binding.recorded_at.utcoffset() is None or evidence.verified_at < binding.recorded_at:
        return None
    return evidence


def review_current_console_trust(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> ConsoleEvidence | None:
    """Re-read latest persisted trust and exact current independent artifact.

    This is still an internal evidence review, not SSH or material authorization.
    The caller owns the transaction and operation authorization.
    """
    context = _current_console_context(policy, target, now=now)
    if context is None:
        return None
    assignment, binding, latest = context
    if latest is None or not trust_revision_candidate_matches(
        latest=latest, assignment=assignment, binding=binding, now=now
    ):
        return None
    verifier_id = latest.verified_by_user_id
    if verifier_id is None or not _console_actors_current(latest.requested_by_user_id, verifier_id):
        return None
    selected = console_target(
        assignment,
        binding,
        revision_number=latest.revision_number,
        requester_id=latest.requested_by_user_id,
        verifier_id=verifier_id,
    )
    if selected is None:
        return None
    evidence = resolve_console_evidence(selected, now=now)
    if (
        evidence is None
        or latest.verified_at is None
        or evidence.verified_at != latest.verified_at
        or binding.recorded_at.utcoffset() is None
        or evidence.verified_at < binding.recorded_at
        or evidence.expires_at != latest.effective_until
        or evidence.evidence_ref != latest.evidence_ref
        or evidence.public_key != latest.public_key
    ):
        return None
    return evidence
