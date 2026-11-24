"""Internal SSH trust revocation and latest-revision resolution (#5185).

Revocation does not require the candidate or console evidence to remain current.
No trust activation or execution authority is provided by this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.access.scoped_grants import require_scope_grant_administrator
from app.extensions.db import db
from app.models.automation import AutomationHostTrustRevision, AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
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
