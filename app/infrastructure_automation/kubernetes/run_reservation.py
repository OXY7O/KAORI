"""Durable target exclusion for a current acknowledged pilot Plan (#4801).

This reserves review targets only. No execution permit or Run is created.
An eventual execution writer must atomically adopt these claims and define
its own terminal reconciliation before dispatch can be enabled.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from ipaddress import IPv4Address
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.access.scope_policy import lock_explicit_permissions
from app.extensions.db import db
from app.infrastructure_automation.host_registry import preview_inventory_intent
from app.infrastructure_automation.kubernetes.plan_approval import review_current_plan_acknowledgement
from app.infrastructure_automation.kubernetes.plan_review import PLAN_OPERATION
from app.infrastructure_automation.security_review import begin_security_review_transaction
from app.models.audit import AuditEvent
from app.models.automation import AutomationInventoryAssignment, AutomationRunTargetClaim
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.service import acquire_resource_admission_locks

_PERMISSIONS = {'integrations.manage', 'inventory.view', 'jobs.execute'}
_TARGET = 'automation_kubespray_target_reservation'
_RESERVED = 'automation.kubespray.targets_reserved'
_RELEASED = 'automation.kubespray.targets_released'


class TargetReservationDenied(ValueError):
    """Sanitized rejection of conflicting or unqualified pilot reservations."""


def _deny() -> TargetReservationDenied:
    return TargetReservationDenied('Kubespray target reservation is unavailable or conflicts with existing evidence.')


def _resource_keys(connection_id: int, assignments: list[AutomationInventoryAssignment]) -> tuple[str, ...]:
    if len(assignments) != 3 or len({item.host_id for item in assignments}) != 3:
        raise _deny()
    keys = [f'kubespray:connection:{connection_id}']
    try:
        for item in assignments:
            if item.integration_instance_id != connection_id or not item.enabled or item.host is None:
                raise _deny()
            address = str(IPv4Address(item.host.address))
            keys.extend((
                f'kubespray:host:{item.host_id}',
                'kubespray:endpoint:' + sha256(address.encode('ascii')).hexdigest(),
            ))
    except ValueError:
        raise _deny() from None
    if len(set(keys)) != 7:
        raise _deny()
    return tuple(sorted(keys))


def _plan_targets(connection_id: int, approval: dict) -> tuple[JobExecution, tuple[str, ...]]:
    connection = db.session.get(IntegrationInstance, connection_id, with_for_update=True, populate_existing=True)
    if connection is None:
        raise _deny()
    assignments = list(db.session.execute(
        select(AutomationInventoryAssignment)
        .where(
            AutomationInventoryAssignment.integration_instance_id == connection_id,
            AutomationInventoryAssignment.enabled.is_(True),
        )
        .order_by(AutomationInventoryAssignment.host_id)
        .limit(4)
        .with_for_update(of=AutomationInventoryAssignment)
        .execution_options(populate_existing=True)
    ).scalars().all())
    for item in assignments:
        db.session.refresh(item.host, with_for_update=True)
    registry = preview_inventory_intent(connection, assignments)
    if registry.inventory_fingerprint != approval.get('host_registry_fingerprint') or registry.host_count != 3:
        raise _deny()
    keys = _resource_keys(connection_id, assignments)
    acquire_resource_admission_locks(*keys)
    job = db.session.execute(
        select(JobExecution)
        .where(
            JobExecution.integration_instance_id == connection_id,
            JobExecution.public_id == approval.get('plan_job_public_id'),
            JobExecution.operation == PLAN_OPERATION,
        )
        .with_for_update(of=JobExecution)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if job is None or job.status != 'succeeded' or job.requested_by_user_id != approval.get('requested_by'):
        raise _deny()
    return job, keys


def reserve_review_targets(*, connection_id: int, plan_fingerprint: str, actor_id: int) -> str:
    """Persist all seven exclusions atomically, with no time-based unlock.

    Endpoint digests are deliberately global, conservative even for separate
    environments. Same Plan cannot be reserved twice, including after release.
    """
    committed = False
    try:
        begin_security_review_transaction()
        if type(actor_id) is not int or actor_id <= 0:
            raise _deny()
        approval = review_current_plan_acknowledgement(
            connection_id=connection_id, plan_fingerprint=plan_fingerprint, now=datetime.now(UTC)
        )
        if approval is None or approval.get('requested_by') != actor_id:
            raise _deny()
        job, keys = _plan_targets(connection_id, approval)
        existing = db.session.execute(
            select(AutomationRunTargetClaim.id).where(
                (AutomationRunTargetClaim.active_resource_key.in_(keys))
                | (AutomationRunTargetClaim.plan_job_id == job.id)
            ).limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            raise _deny()
        now = datetime.now(UTC)
        current = review_current_plan_acknowledgement(
            connection_id=connection_id, plan_fingerprint=plan_fingerprint, now=now
        )
        if current != approval:
            raise _deny()
        reservation_id = str(uuid4())
        db.session.add_all([
            AutomationRunTargetClaim(
                reservation_id=reservation_id,
                plan_job_id=job.id,
                resource_key=key,
                active_resource_key=key,
                plan_fingerprint=plan_fingerprint,
                reserved_by_user_id=actor_id,
                reserved_at=now,
            )
            for key in keys
        ])
        db.session.add(AuditEvent(
            actor_user_id=actor_id,
            target_type=_TARGET,
            target_id=reservation_id,
            action=_RESERVED,
            summary='Persistent pilot review target reservation; Run remains blocked.',
            metadata_json={
                'connection_id': connection_id,
                'plan_job_public_id': job.public_id,
                'plan_fingerprint': plan_fingerprint,
                'resource_count': len(keys),
                'execution_authorized': False,
            },
        ))
        db.session.commit()
        committed = True
        return reservation_id
    except IntegrityError:
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()


def _reservation_rows(reservation_id: str) -> list[AutomationRunTargetClaim]:
    try:
        if not isinstance(reservation_id, str) or str(UUID(reservation_id)) != reservation_id:
            raise _deny()
    except ValueError:
        raise _deny() from None
    return list(db.session.execute(
        select(AutomationRunTargetClaim)
        .where(AutomationRunTargetClaim.reservation_id == reservation_id)
        .order_by(AutomationRunTargetClaim.resource_key)
        .limit(8)
        .with_for_update(of=AutomationRunTargetClaim)
        .execution_options(populate_existing=True)
    ).scalars().all())


def release_review_targets(*, reservation_id: str, actor_id: int) -> None:
    """Explicit release of a never-dispatched review reservation by its maker.

    Not a recovery or cancellation API. No mutation Run may adopt a claim
    until its own persistent claim lifecycle supersedes this review service.
    """
    committed = False
    try:
        begin_security_review_transaction()
        if type(actor_id) is not int or actor_id <= 0 or not lock_explicit_permissions(actor_id, _PERMISSIONS):
            raise _deny()
        rows = _reservation_rows(reservation_id)
        if (
            len(rows) != 7
            or len({row.plan_job_id for row in rows}) != 1
            or len({row.plan_fingerprint for row in rows}) != 1
            or any(
                row.reserved_by_user_id != actor_id
                or row.released_at is not None
                or row.active_resource_key != row.resource_key
                for row in rows
            )
        ):
            raise _deny()
        job = db.session.get(JobExecution, rows[0].plan_job_id, with_for_update=True, populate_existing=True)
        if job is None or job.operation != PLAN_OPERATION or job.requested_by_user_id != actor_id:
            raise _deny()
        # Future child Run attempts, even terminal or unknown, must be
        # reconciled explicitly; this review-only release cannot clear them.
        child = db.session.execute(
            select(JobExecution.id).where(JobExecution.parent_job_id == job.id).limit(1)
        ).scalar_one_or_none()
        if child is not None:
            raise _deny()
        now = datetime.now(UTC)
        for row in rows:
            row.active_resource_key = None
            row.released_at = now
        db.session.add(AuditEvent(
            actor_user_id=actor_id,
            target_type=_TARGET,
            target_id=reservation_id,
            action=_RELEASED,
            summary='Released never-dispatched pilot review targets.',
            metadata_json={
                'plan_job_public_id': job.public_id,
                'plan_fingerprint': rows[0].plan_fingerprint,
                'resource_count': len(rows),
                'execution_authorized': False,
            },
        ))
        db.session.commit()
        committed = True
    finally:
        if not committed:
            db.session.rollback()
