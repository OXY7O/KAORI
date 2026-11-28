"""Governed local Plan acknowledgement and target correlation (#4800/#4801).

Reuse canonical JobExecution, explicit Access and append-only AuditEvent.
No Run permission, provider mutation, maintenance operation or dispatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.access.scope_policy import lock_explicit_permissions
from app.extensions.db import db
from app.infrastructure_automation.host_registry import preview_inventory_intent
from app.infrastructure_automation.kubernetes.plan_currentness import committed_kubespray_plan_currentness
from app.infrastructure_automation.kubernetes.plan_review import PLAN_OPERATION, PLAN_RESULT_TYPE
from app.infrastructure_automation.security_review import (
    begin_security_review_transaction,
    local_security_review_enabled,
)
from app.models.audit import AuditEvent
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.fingerprint import payload_fingerprint
from app.platform_operations.jobs.service import acquire_resource_admission_locks

_TARGET = 'automation_kubespray_plan_approval'
_ACK = 'automation.kubespray.plan_acknowledged'
_REVOKE = 'automation.kubespray.plan_acknowledgement_revoked'
_PERMISSIONS = {'integrations.manage', 'inventory.view', 'jobs.execute'}
_HEX = re.compile(r'[a-f0-9]{64}')
_REFERENCE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{2,119}')
_MAX_WINDOW = timedelta(hours=2)


class PlanApprovalDenied(ValueError):
    """Sanitized denial of missing or stale Plan acknowledgement."""


@dataclass(frozen=True, slots=True)
class PlanWindow:
    starts_at: datetime
    ends_at: datetime
    change_reference: str


def _deny() -> PlanApprovalDenied:
    return PlanApprovalDenied('Kubespray Plan acknowledgement is unavailable or unqualified.')


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result if result.utcoffset() == timedelta(0) and result.isoformat() == value else None


def _actor(value: object) -> bool:
    return type(value) is int and value > 0


def _valid_window(window: PlanWindow, *, now: datetime, plan_expiry: datetime) -> bool:
    return (
        isinstance(window, PlanWindow)
        and _aware(window.starts_at)
        and _aware(window.ends_at)
        and _aware(now)
        and _aware(plan_expiry)
        and isinstance(window.change_reference, str)
        and _REFERENCE.fullmatch(window.change_reference) is not None
        and timedelta(0) < window.ends_at - window.starts_at <= _MAX_WINDOW
        and now < plan_expiry
        and now < window.ends_at
        and window.starts_at < plan_expiry
    )


def _latest_ack(connection_id: int) -> AuditEvent | None:
    return (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=str(connection_id))
        .order_by(AuditEvent.id.desc())
        .populate_existing()
        .with_for_update()
        .first()
    )


def _current_plan(
    connection_id: int, *, expected_fingerprint: str, now: datetime
) -> tuple[JobExecution, dict[str, Any], datetime]:
    """Lock exact connection and canonical host resource keys for this transaction.

    This is an acknowledgement transaction lock, not a long-lived Run lease.
    Future mutation admission must hold a persistent conflicting-Run guard.
    """
    if type(connection_id) is not int or connection_id <= 0:
        raise _deny()
    if not isinstance(expected_fingerprint, str) or _HEX.fullmatch(expected_fingerprint) is None:
        raise _deny()
    connection = db.session.get(IntegrationInstance, connection_id, populate_existing=True, with_for_update=True)
    if (
        connection is None
        or connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or not connection.enabled
        or connection.lifecycle_status != 'active'
        or connection.environment not in ('development', 'testing', 'laboratory', 'sandbox')
    ):
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
    if len(assignments) != 3:
        raise _deny()
    acquire_resource_admission_locks(
        f'kubespray:connection:{connection_id}',
        *(f'kubespray:host:{assignment.host_id}' for assignment in assignments),
    )
    for assignment in assignments:
        db.session.refresh(assignment.host, with_for_update=True)
    registry = preview_inventory_intent(connection, assignments)
    roles = [assignment.role for assignment in assignments]
    if (
        registry.inventory_fingerprint is None
        or roles.count('control_plane') != 1
        or roles.count('worker') != 2
        or len({assignment.host.address for assignment in assignments}) != 3
    ):
        raise _deny()
    current = committed_kubespray_plan_currentness(connection)
    expiry = _time(current.expires_at)
    if (
        current.state != 'current_for_review'
        or current.plan_fingerprint != expected_fingerprint
        or not current.job_public_id
        or expiry is None
        or now >= expiry
        or current.execution_authorized is not False
    ):
        raise _deny()
    job = (
        JobExecution.query.filter_by(integration_instance_id=connection_id, operation=PLAN_OPERATION)
        .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
        .populate_existing()
        .with_for_update()
        .first()
    )
    if (
        job is None
        or job.public_id != current.job_public_id
        or job.result_type != PLAN_RESULT_TYPE
        or job.status != 'succeeded'
        or not _actor(job.requested_by_user_id)
        or not isinstance(job.result_summary_json, dict)
    ):
        raise _deny()
    summary = job.result_summary_json
    if (
        summary.get('plan_fingerprint') != expected_fingerprint
        or summary.get('host_registry_fingerprint') != registry.inventory_fingerprint
        or summary.get('mutation_authorized') is not False
        or summary.get('execution_status') != 'blocked'
        or summary.get('approval_status') != 'not_requested'
        or summary.get('expires_at') != expiry.isoformat()
        or not isinstance(summary.get('source_sha'), str)
        or re.fullmatch(r'[a-f0-9]{40}', summary['source_sha']) is None
        or not isinstance(summary.get('execution_environment_digest'), str)
        or re.fullmatch(r'sha256:[a-f0-9]{64}', summary['execution_environment_digest']) is None
        or any(
            not isinstance(summary.get(field), str) or _HEX.fullmatch(summary[field]) is None
            for field in ('inventory_fingerprint', 'host_access_fingerprint')
        )
    ):
        raise _deny()
    return job, summary, expiry


def _approval_record(
    job: JobExecution,
    summary: dict[str, Any],
    *,
    checker_id: int,
    window: PlanWindow,
    now: datetime,
    expiry: datetime,
) -> dict[str, Any]:
    maker = job.requested_by_user_id
    if (
        not _actor(maker)
        or not _actor(checker_id)
        or maker == checker_id
        or not _valid_window(window, now=now, plan_expiry=expiry)
    ):
        raise _deny()
    return {
        'schema_version': 1,
        'status': 'acknowledged_pending_run_admission',
        'connection_id': job.integration_instance_id,
        'plan_job_public_id': job.public_id,
        'plan_fingerprint': summary['plan_fingerprint'],
        'inventory_fingerprint': summary['inventory_fingerprint'],
        'host_registry_fingerprint': summary['host_registry_fingerprint'],
        'host_access_fingerprint': summary['host_access_fingerprint'],
        'source_sha': summary['source_sha'],
        'execution_environment_digest': summary['execution_environment_digest'],
        'requested_by': maker,
        'approved_by': checker_id,
        'approved_at': now.astimezone(UTC).isoformat(),
        'window_start': window.starts_at.astimezone(UTC).isoformat(),
        'window_end': window.ends_at.astimezone(UTC).isoformat(),
        'change_reference': window.change_reference,
        'approval_expires_at': min(expiry, window.ends_at).astimezone(UTC).isoformat(),
        'execution_authorized': False,
        'mutation_authorized': False,
    }


def acknowledge_kubespray_plan(
    *, connection_id: int, plan_fingerprint: str, checker_id: int, window: PlanWindow
) -> dict[str, Any]:
    """Second operator acknowledges current immutable Plan in explicit local review.

    No approval of live infrastructure mutation is inferred from this record.
    """
    committed = False
    try:
        begin_security_review_transaction()
        now = datetime.now(UTC)
        job, summary, expiry = _current_plan(connection_id, expected_fingerprint=plan_fingerprint, now=now)
        record = _approval_record(job, summary, checker_id=checker_id, window=window, now=now, expiry=expiry)
        for actor_id in sorted((record['requested_by'], checker_id)):
            if not lock_explicit_permissions(actor_id, _PERMISSIONS):
                raise _deny()
        previous = _latest_ack(connection_id)
        if previous is not None:
            existing = previous.metadata_json
            if not isinstance(existing, dict):
                raise _deny()
            if existing.get('plan_fingerprint') == plan_fingerprint:
                # A revoked or acknowledged Plan must never be reactivated.
                raise _deny()
            if (previous.action, existing.get('status')) not in (
                (_ACK, 'acknowledged_pending_run_admission'), (_REVOKE, 'revoked'),
            ):
                raise _deny()
            if existing['status'] == 'acknowledged_pending_run_admission':
                previous_expiry = _time(existing.get('approval_expires_at'))
                if previous_expiry is None or now < previous_expiry:
                    raise _deny()
        # Revalidate current plan identity and time immediately before audit.
        fresh_now = datetime.now(UTC)
        fresh_job, fresh, fresh_expiry = _current_plan(
            connection_id, expected_fingerprint=plan_fingerprint, now=fresh_now
        )
        if fresh_job.id != job.id or fresh != summary or fresh_expiry != expiry:
            raise _deny()
        record = _approval_record(
            fresh_job, fresh, checker_id=checker_id, window=window, now=fresh_now, expiry=fresh_expiry
        )
        db.session.add(AuditEvent(
            actor_user_id=checker_id,
            target_type=_TARGET,
            target_id=str(connection_id),
            action=_ACK,
            summary='Independent Kubespray Plan acknowledgement; Run admission remains blocked.',
            metadata_json=record,
        ))
        db.session.commit()
        committed = True
        return record
    finally:
        if not committed:
            db.session.rollback()


def review_current_plan_acknowledgement(
    *, connection_id: int, plan_fingerprint: str, now: datetime
) -> dict[str, Any] | None:
    """Read latest exact acknowledgement in its current change window.

    Caller owns transaction/locks. Return review evidence, never a Run permit.
    """
    if not local_security_review_enabled() or not _aware(now):
        return None
    try:
        job, summary, expiry = _current_plan(connection_id, expected_fingerprint=plan_fingerprint, now=now)
        row = _latest_ack(connection_id)
        if row is None or row.action != _ACK or not isinstance(row.metadata_json, dict):
            return None
        record = row.metadata_json
        approved, starts, ends = (_time(record.get(key)) for key in ('approved_at', 'window_start', 'window_end'))
        checker_id = record.get('approved_by')
        if (
            approved is None or starts is None or ends is None
            or not _actor(checker_id)
            or not approved <= now < expiry
            or not starts <= now < ends
            or row.actor_user_id != checker_id
        ):
            return None
        rebuilt = _approval_record(
            job, summary, checker_id=checker_id,
            window=PlanWindow(starts, ends, str(record.get('change_reference') or '')),
            now=approved, expiry=expiry,
        )
        if payload_fingerprint(rebuilt) != payload_fingerprint(record):
            return None
        for actor_id in sorted((record['requested_by'], checker_id)):
            if not lock_explicit_permissions(actor_id, _PERMISSIONS):
                return None
        return dict(record)
    except PlanApprovalDenied:
        return None


def revoke_plan_acknowledgement(*, connection_id: int, plan_fingerprint: str, actor_id: int) -> None:
    """Revoke exact latest acknowledgement even if source/Plan became stale."""
    committed = False
    try:
        begin_security_review_transaction()
        if (
            type(connection_id) is not int or connection_id <= 0 or not _actor(actor_id)
            or not isinstance(plan_fingerprint, str) or _HEX.fullmatch(plan_fingerprint) is None
            or not lock_explicit_permissions(actor_id, _PERMISSIONS)
        ):
            raise _deny()
        connection = db.session.get(IntegrationInstance, connection_id, with_for_update=True, populate_existing=True)
        if connection is None or connection.integration_type != 'configuration_automation' or connection.provider_key != 'ansible':
            raise _deny()
        row = _latest_ack(connection_id)
        if row is None or row.action != _ACK or not isinstance(row.metadata_json, dict):
            raise _deny()
        record = row.metadata_json
        if record.get('plan_fingerprint') != plan_fingerprint or record.get('status') != 'acknowledged_pending_run_admission':
            raise _deny()
        if actor_id not in (record.get('requested_by'), record.get('approved_by')):
            raise _deny()
        db.session.add(AuditEvent(
            actor_user_id=actor_id,
            target_type=_TARGET,
            target_id=str(connection_id),
            action=_REVOKE,
            summary='Kubespray Plan acknowledgement revoked.',
            metadata_json={
                **record,
                'status': 'revoked',
                'revoked_by': actor_id,
                'revoked_at': datetime.now(UTC).isoformat(),
            },
        ))
        db.session.commit()
        committed = True
    finally:
        if not committed:
            db.session.rollback()
