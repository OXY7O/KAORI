"""Local, non-authorizing recovery hold for an unresolved adopted Run (#4801).

A hold is not a terminal transition or proof a remote worker stopped.
No native read, credential access, worker dispatch or target release occurs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from flask import current_app
from sqlalchemy import select

from app.access.scope_policy import lock_explicit_permissions
from app.extensions.db import db
from app.infrastructure_automation.kubernetes.plan_review import PLAN_OPERATION, PLAN_RESULT_TYPE
from app.infrastructure_automation.kubernetes.run_reservation import RUN_OPERATION, _reservation_rows
from app.infrastructure_automation.security_review import begin_security_review_transaction
from app.infrastructure_automation.target_claims import connection_resource
from app.models.audit import AuditEvent
from app.models.automation import AutomationRunReservationAdoption, AutomationRunTargetClaim
from app.models.job import JobExecution
from app.platform_operations.jobs.fingerprint import payload_fingerprint

_HEX = re.compile(r'[a-f0-9]{64}')
_HOST_KEY = re.compile(r'kubespray:host:[0-9a-f-]{36}')
_ENDPOINT_KEY = re.compile(r'kubespray:endpoint:[a-f0-9]{64}')
_PERMISSIONS = {'integrations.manage', 'inventory.view', 'jobs.execute'}
_ACTION = 'automation.kubespray.recovery_hold_recorded'


class RunRecoveryDenied(ValueError):
    """Sanitized denial of unqualified recovery correlation."""


def _deny() -> RunRecoveryDenied:
    return RunRecoveryDenied('Kubespray Run recovery hold is unavailable or unqualified.')


def _uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _expired(value: datetime | None, now: datetime, config: str, default: int) -> bool:
    if value is None or not _aware(value):
        return False
    try:
        seconds = int(current_app.config.get(config, default))
    except (ValueError, TypeError, OverflowError):
        return False
    return 0 < seconds <= 86400 * 30 and value < now - timedelta(seconds=seconds)


def _stale_reason(run: JobExecution, now: datetime) -> str:
    if run.status == 'queued' and (
        _expired(run.queued_at, now, 'JOB_QUEUED_STALE_SECONDS', 1800)
        or (run.expires_at is not None and _aware(run.expires_at) and run.expires_at < now)
    ):
        return 'queued_start_unconfirmed'
    if run.status in ('running', 'retrying') and _expired(
        run.heartbeat_at or run.started_at or run.queued_at, now, 'JOB_RUNNING_STALE_SECONDS', 7200
    ):
        return 'worker_heartbeat_stale'
    if run.status == 'cancel_requested' and _expired(
        run.cancel_requested_at, now, 'JOB_CANCEL_GRACE_SECONDS', 120
    ):
        return 'cancellation_outcome_unconfirmed'
    raise _deny()


def _historical_fingerprint(plan: JobExecution, adoption: AutomationRunReservationAdoption) -> str:
    summary = plan.result_summary_json
    if (
        plan.operation != PLAN_OPERATION
        or plan.result_type != PLAN_RESULT_TYPE
        or plan.status != 'succeeded'
        or plan.integration_type != 'configuration_automation'
        or plan.integration_instance_id is None
        or plan.requested_by_user_id != adoption.adopted_by_user_id
        or plan.completed_at is None
        or not _aware(plan.completed_at)
        or not _aware(adoption.adopted_at)
        or plan.completed_at > adoption.adopted_at
        or not isinstance(summary, dict)
        or summary.get('mutation_authorized') is not False
        or summary.get('execution_status') != 'blocked'
    ):
        raise _deny()
    fingerprint = summary.get('plan_fingerprint')
    if not isinstance(fingerprint, str) or _HEX.fullmatch(fingerprint) is None:
        raise _deny()
    return fingerprint


def _require_claims(
    rows: list[AutomationRunTargetClaim], adoption: AutomationRunReservationAdoption,
    plan_fingerprint: str, connection_id: int,
) -> None:
    keys = {row.resource_key for row in rows}
    if (
        len(rows) != 7
        or len(keys) != 7
        or connection_resource(connection_id) not in keys
        or sum(_HOST_KEY.fullmatch(key) is not None for key in keys) != 3
        or sum(_ENDPOINT_KEY.fullmatch(key) is not None for key in keys) != 3
        or any(
            row.reservation_id != adoption.reservation_id
            or row.plan_job_id != adoption.plan_job_id
            or row.plan_fingerprint != plan_fingerprint
            or row.reserved_by_user_id != adoption.adopted_by_user_id
            or row.released_at is not None
            or row.active_resource_key != row.resource_key
            for row in rows
        )
    ):
        raise _deny()


def _require_run(
    run: JobExecution, plan: JobExecution, adoption: AutomationRunReservationAdoption, fingerprint: str
) -> None:
    payload = run.payload_json
    if (
        run.id != adoption.run_job_id
        or run.parent_job_id != plan.id
        or run.operation != RUN_OPERATION
        or run.job_type != 'infrastructure_automation'
        or run.queue_name != 'automation'
        or run.integration_type != 'configuration_automation'
        or run.integration_instance_id != plan.integration_instance_id
        or run.scope_type != 'ansible_source_connection'
        or run.scope_key != str(plan.integration_instance_id)
        or run.requested_by_user_id != adoption.adopted_by_user_id
        or run.max_attempts != 1
        or not run.active_deduplication_key
        or run.completed_at is not None
        or not run.celery_task_id
        or not isinstance(payload, dict)
        or payload.get('reservation_id') != adoption.reservation_id
        or payload.get('plan_job_public_id') != plan.public_id
        or payload.get('plan_fingerprint') != fingerprint
        or payload_fingerprint(payload) != run.parameter_fingerprint
    ):
        raise _deny()


def _lock_adopted_run(reservation_id: str, owner_id: int) -> tuple[JobExecution, JobExecution, str]:
    # Resolve identity, then use Plan -> claims -> child lock order, matching
    # adoption/review release. Historical evidence remains usable after expiry.
    adoption = db.session.execute(
        select(AutomationRunReservationAdoption)
        .where(AutomationRunReservationAdoption.reservation_id == reservation_id)
    ).scalar_one_or_none()
    if adoption is None or adoption.adopted_by_user_id == owner_id:
        raise _deny()
    plan = db.session.get(JobExecution, adoption.plan_job_id, with_for_update=True, populate_existing=True)
    if plan is None:
        raise _deny()
    adoption = db.session.get(
        AutomationRunReservationAdoption, adoption.id, with_for_update=True, populate_existing=True
    )
    if adoption is None or adoption.plan_job_id != plan.id or adoption.reservation_id != reservation_id:
        raise _deny()
    if adoption.adopted_by_user_id == owner_id:
        raise _deny()
    fingerprint = _historical_fingerprint(plan, adoption)
    connection_id = plan.integration_instance_id
    if connection_id is None:
        raise _deny()
    _require_claims(_reservation_rows(reservation_id), adoption, fingerprint, connection_id)
    run = db.session.get(JobExecution, adoption.run_job_id, with_for_update=True, populate_existing=True)
    if run is None:
        raise _deny()
    _require_run(run, plan, adoption, fingerprint)
    return plan, run, fingerprint


def record_run_recovery_hold(*, reservation_id: str, owner_id: int) -> dict:
    """Commit a local independent operator hold and audit, not a Run permit.

    The owner is a different currently permitted actor. No status, heartbeat,
    deduplication slot, immutable payload or claim is changed. No fresh Plan
    approval is required to record an already unresolved historical attempt.
    """
    committed = False
    try:
        begin_security_review_transaction()
        if (
            not _uuid(reservation_id)
            or type(owner_id) is not int
            or owner_id <= 0
            or not lock_explicit_permissions(owner_id, _PERMISSIONS)
        ):
            raise _deny()
        plan, run, fingerprint = _lock_adopted_run(reservation_id, owner_id)
        now = datetime.now(UTC)
        reason = _stale_reason(run, now)
        previous = run.result_summary_json
        if previous is not None and (not isinstance(previous, dict) or 'recovery_hold' in previous):
            raise _deny()
        evidence = {
            'schema_version': 1,
            'status': 'recovery_required',
            'reason_code': reason,
            'reservation_id': reservation_id,
            'plan_job_public_id': plan.public_id,
            'run_job_public_id': run.public_id,
            'plan_fingerprint': fingerprint,
            'recovery_owner_user_id': owner_id,
            'recorded_at': now.isoformat(),
            'observed_job_status': run.status,
            'worker_stopped_verified': False,
            'provisioning_verified': False,
            'reservation_released': False,
            'execution_authorized': False,
        }
        run.result_summary_json = {**(previous or {}), 'recovery_hold': evidence}
        run.progress_message = 'Recovery required; worker outcome unverified; targets retained'
        db.session.add(AuditEvent(
            actor_user_id=owner_id,
            target_type='job_execution',
            target_id=run.public_id,
            action=_ACTION,
            summary='Independent recovery hold recorded; worker outcome remains unverified.',
            metadata_json=evidence,
        ))
        db.session.commit()
        committed = True
        return evidence
    finally:
        if not committed:
            db.session.rollback()
