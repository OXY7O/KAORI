from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.jobs.constants import ACTIVE_JOB_STATUSES, DEFAULT_PRIORITIES, HEAVY_WORKLOAD_CLASSES
from app.jobs.fingerprint import build_deduplication_key, payload_fingerprint
from app.models.job import JobExecution, JobExecutionSubscriber


class JobQuotaExceeded(RuntimeError):
    pass


class JobCancellationNotAllowed(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _config_int(name: str, default: int) -> int:
    try:
        return max(int(current_app.config.get(name, default)), 0)
    except (TypeError, ValueError):
        return default


def _active_query():
    return JobExecution.query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))


def _advisory_lock_key(value: str) -> int:
    digest = hashlib.sha256(value.encode('utf-8')).digest()[:8]
    return int.from_bytes(digest, byteorder='big', signed=True)


def _acquire_admission_locks(*values: str | None) -> None:
    """Serialize PostgreSQL admission checks across Flask replicas.

    The unique active deduplication key already protects identical jobs. These
    transaction-scoped advisory locks additionally make per-user and per-resource
    quota checks deterministic when distinct jobs are submitted concurrently.
    Non-PostgreSQL test environments safely skip this database-specific guard.
    """
    bind = db.session.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for value in sorted({item for item in values if item}):
        db.session.execute(
            text('SELECT pg_advisory_xact_lock(:lock_key)'),
            {'lock_key': _advisory_lock_key(value)},
        )


def acquire_resource_admission_locks(*resource_groups: str | None) -> None:
    """Serialize job admission and destructive resource operations.

    Callers must keep the current database transaction open until the guarded
    operation commits or rolls back. PostgreSQL transaction-scoped advisory
    locks are re-entrant within the same transaction and are skipped in
    non-PostgreSQL test environments.
    """
    _acquire_admission_locks(*(f'job-resource:{group}' for group in resource_groups if group))


def find_active_job(
    *,
    deduplication_key: str | None = None,
    provider_type: str | None = None,
    provider_instance_id: int | None = None,
    operation: str | None = None,
    scope_key: str | None = None,
) -> JobExecution | None:
    query = _active_query()
    if deduplication_key:
        query = query.filter(JobExecution.active_deduplication_key == deduplication_key)
    if provider_type:
        query = query.filter(JobExecution.provider_type == provider_type)
    if provider_instance_id is not None:
        query = query.filter(JobExecution.provider_instance_id == provider_instance_id)
    if operation:
        query = query.filter(JobExecution.operation == operation)
    if scope_key:
        query = query.filter(JobExecution.scope_key == scope_key)
    return query.order_by(JobExecution.created_at.desc()).first()


def attach_job_subscriber(job: JobExecution, user_id: int | None) -> None:
    if user_id is None:
        return
    existing = JobExecutionSubscriber.query.filter_by(
        job_execution_id=job.id,
        user_id=user_id,
    ).first()
    if existing is not None:
        existing.last_seen_at = _now()
        db.session.commit()
        return
    subscriber = JobExecutionSubscriber()
    subscriber.job_execution_id = job.id
    subscriber.user_id = user_id
    subscriber.notify_on_completion = True
    subscriber.last_seen_at = _now()
    db.session.add(subscriber)
    try:
        db.session.commit()
    except IntegrityError:
        # Another web replica may subscribe the same user at the same time.
        db.session.rollback()


def _enforce_quotas(
    *,
    requested_by_user_id: int | None,
    workload_class: str,
    resource_group: str | None,
) -> None:
    if requested_by_user_id is not None:
        max_active = _config_int('JOB_MAX_ACTIVE_PER_USER', 5)
        if (
            max_active
            and _active_query().filter(JobExecution.requested_by_user_id == requested_by_user_id).count() >= max_active
        ):
            raise JobQuotaExceeded('The user already has the maximum number of active jobs.')
        if workload_class in HEAVY_WORKLOAD_CLASSES:
            max_heavy = _config_int('JOB_MAX_HEAVY_PER_USER', 1)
            if (
                max_heavy
                and _active_query()
                .filter(
                    JobExecution.requested_by_user_id == requested_by_user_id,
                    JobExecution.workload_class.in_(HEAVY_WORKLOAD_CLASSES),
                )
                .count()
                >= max_heavy
            ):
                raise JobQuotaExceeded('The user already has an active heavy analytics job.')
    if resource_group:
        max_resource = _config_int('JOB_MAX_ACTIVE_PER_RESOURCE', 2)
        if (
            max_resource
            and _active_query().filter(JobExecution.resource_group == resource_group).count() >= max_resource
        ):
            raise JobQuotaExceeded('The target resource has reached its active job limit.')


def create_or_attach_job(
    *,
    job_type: str,
    operation: str,
    queue_name: str,
    workload_class: str,
    requested_by_user_id: int | None,
    provider_type: str | None = None,
    provider_instance_id: int | None = None,
    scope_type: str | None = None,
    scope_key: str | None = None,
    resource_group: str | None = None,
    parameters: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    deduplication_key: str | None = None,
    priority: int | None = None,
    max_attempts: int = 3,
    celery_task_id: str | None = None,
    parent_job_id: int | None = None,
) -> tuple[JobExecution, bool]:
    fingerprint = payload_fingerprint(parameters)
    key = deduplication_key or build_deduplication_key(
        job_type,
        operation,
        provider_type,
        provider_instance_id,
        scope_type,
        scope_key,
        fingerprint=fingerprint,
    )
    _acquire_admission_locks(
        f'job-dedup:{key}',
        f'job-user:{requested_by_user_id}' if requested_by_user_id is not None else None,
    )
    acquire_resource_admission_locks(resource_group)
    existing = find_active_job(deduplication_key=key)
    if existing is not None:
        attach_job_subscriber(existing, requested_by_user_id)
        return existing, False

    _enforce_quotas(
        requested_by_user_id=requested_by_user_id,
        workload_class=workload_class,
        resource_group=resource_group,
    )
    job = JobExecution()
    job.job_type = job_type
    job.operation = operation
    job.workload_class = workload_class
    job.queue_name = queue_name
    job.priority = priority if priority is not None else DEFAULT_PRIORITIES.get(workload_class, 5)
    job.status = 'queued'
    job.requested_by_user_id = requested_by_user_id
    job.provider_type = provider_type
    job.provider_instance_id = provider_instance_id
    job.scope_type = scope_type
    job.scope_key = scope_key
    job.resource_group = resource_group
    job.deduplication_key = key
    job.active_deduplication_key = key
    job.parameter_fingerprint = fingerprint
    job.payload_json = payload or parameters or {}
    job.celery_task_id = celery_task_id or str(uuid4())
    job.parent_job_id = parent_job_id
    job.max_attempts = max(max_attempts, 1)
    job.queued_at = _now()
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = find_active_job(deduplication_key=key)
        if existing is None:
            raise
        attach_job_subscriber(existing, requested_by_user_id)
        return existing, False
    attach_job_subscriber(job, requested_by_user_id)
    return job, True


def get_job_by_task_id(task_id: str) -> JobExecution | None:
    return JobExecution.query.filter_by(celery_task_id=task_id).first()


def _terminalize(job: JobExecution, status: str) -> None:
    job.status = status
    job.active_deduplication_key = None
    job.completed_at = _now()
    job.heartbeat_at = job.completed_at


def mark_job_running(task_id: str, *, message: str | None = None, total: int | None = None) -> JobExecution | None:
    job = get_job_by_task_id(task_id)
    if job is None:
        return None
    if job.is_terminal or job.status == 'cancel_requested':
        return job
    now = _now()
    job.status = 'running'
    job.started_at = job.started_at or now
    job.heartbeat_at = now
    job.attempt_count += 1
    if message is not None:
        job.progress_message = message[:255]
    if total is not None:
        job.progress_total = max(total, 0)
    db.session.commit()
    return job


def update_job_progress(
    task_id: str,
    *,
    current: int | None = None,
    total: int | None = None,
    message: str | None = None,
) -> JobExecution | None:
    job = get_job_by_task_id(task_id)
    if job is None:
        return None
    if current is not None:
        job.progress_current = max(current, 0)
    if total is not None:
        job.progress_total = max(total, 0)
    if message is not None:
        job.progress_message = message[:255]
    job.heartbeat_at = _now()
    db.session.commit()
    return job


def mark_job_succeeded(
    task_id: str,
    *,
    result_summary: dict[str, Any] | None = None,
    result_type: str | None = None,
    result_reference: str | None = None,
    partial: bool = False,
) -> JobExecution | None:
    job = get_job_by_task_id(task_id)
    if job is None:
        return None
    if job.is_terminal:
        return job
    if job.status == 'cancel_requested':
        _terminalize(job, 'canceled')
        job.progress_message = 'Canceled before completion was committed'
        db.session.commit()
        return job
    _terminalize(job, 'partially_succeeded' if partial else 'succeeded')
    job.result_summary_json = result_summary or {}
    job.result_type = result_type
    job.result_reference = result_reference
    if job.progress_total:
        job.progress_current = job.progress_total
    job.progress_message = 'Completed'
    db.session.commit()
    return job


def mark_job_failed(task_id: str, *, error: Exception | str, error_code: str | None = None) -> JobExecution | None:
    job = get_job_by_task_id(task_id)
    if job is None:
        return None
    if job.is_terminal:
        return job
    if job.status == 'cancel_requested':
        _terminalize(job, 'canceled')
        job.progress_message = 'Canceled before failure finalization'
        db.session.commit()
        return job
    _terminalize(job, 'failed')
    job.error_code = error_code or (type(error).__name__ if isinstance(error, Exception) else 'job_failed')
    job.error_message = str(error)[:4000]
    job.progress_message = 'Failed'
    db.session.commit()
    return job


def request_job_cancel(job: JobExecution) -> JobExecution:
    if not job.is_active:
        return job
    job.status = 'cancel_requested'
    job.cancel_requested_at = _now()
    job.heartbeat_at = job.cancel_requested_at
    db.session.commit()
    return job


def mark_job_retrying(task_id: str, *, message: str, error: Exception | str | None = None) -> JobExecution | None:
    job = get_job_by_task_id(task_id)
    if job is None:
        return None
    if job.is_terminal or job.status == 'cancel_requested':
        return job
    job.status = 'retrying'
    job.heartbeat_at = _now()
    job.progress_message = message[:255]
    if error is not None:
        job.error_code = type(error).__name__ if isinstance(error, Exception) else 'retrying'
        job.error_message = str(error)[:4000]
    db.session.commit()
    return job


def mark_job_canceled(task_id: str, *, message: str = 'Canceled') -> JobExecution | None:
    job = get_job_by_task_id(task_id)
    if job is None:
        return None
    if job.is_terminal:
        return job
    _terminalize(job, 'canceled')
    job.progress_message = message[:255]
    db.session.commit()
    return job


def job_can_cancel(job: JobExecution) -> bool:
    return bool(job.status == 'queued' or (job.is_active and job.workload_class in HEAVY_WORKLOAD_CLASSES))


def cancel_job_execution(job: JobExecution, *, terminate: bool = False) -> JobExecution:
    if not job_can_cancel(job):
        raise JobCancellationNotAllowed(
            'Only queued jobs or cooperative analytics and forecasting jobs can be canceled.'
        )
    if job.celery_task_id:
        current_app.extensions['celery'].control.revoke(
            job.celery_task_id,
            terminate=terminate,
        )
    if job.status == 'queued':
        if job.celery_task_id:
            return mark_job_canceled(job.celery_task_id, message='Canceled before worker execution') or job
        _terminalize(job, 'canceled')
        job.progress_message = 'Canceled before worker execution'
        db.session.commit()
        return job
    request_job_cancel(job)
    job.progress_message = 'Cancellation requested; waiting for a worker checkpoint'
    db.session.commit()
    return job


def is_cancel_requested(task_id: str) -> bool:
    job = get_job_by_task_id(task_id)
    return bool(job and job.status == 'cancel_requested')


def subscriber_user_ids(job: JobExecution, *, notify_only: bool = True) -> list[int]:
    query = JobExecutionSubscriber.query.filter_by(job_execution_id=job.id)
    if notify_only:
        query = query.filter_by(notify_on_completion=True)
    return [row.user_id for row in query.order_by(JobExecutionSubscriber.id.asc()).all()]


def job_snapshot(job: JobExecution) -> dict[str, Any]:
    total = max(job.progress_total, 0)
    current = max(job.progress_current, 0)
    percentage = min(int((current / total) * 100), 100) if total else (100 if job.is_terminal else 0)
    return {
        'job_execution_id': job.id,
        'job_public_id': job.public_id,
        'task_id': job.celery_task_id,
        'job_type': job.job_type,
        'operation': job.operation,
        'workload_class': job.workload_class,
        'queue_name': job.queue_name,
        'priority': job.priority,
        'status': job.status,
        'provider_type': job.provider_type,
        'instance_id': job.provider_instance_id,
        'scope_type': job.scope_type,
        'scope_key': job.scope_key,
        'resource_group': job.resource_group,
        'requested_by_user_id': job.requested_by_user_id,
        'progress_current': current,
        'progress_total': total,
        'progress_percentage': percentage,
        'progress_message': job.progress_message,
        'attempt_count': job.attempt_count,
        'max_attempts': job.max_attempts,
        'queued_at': job.queued_at.isoformat() if job.queued_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'heartbeat_at': job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        'finished_at': job.completed_at.isoformat() if job.completed_at else None,
        'error_code': job.error_code,
        'error_message': job.error_message,
        'result': job.result_summary_json or {},
        'is_active': job.is_active,
        'is_complete': job.is_terminal,
    }


def recover_stale_jobs() -> dict[str, int]:
    now = _now()
    running_cutoff = now - timedelta(seconds=_config_int('JOB_RUNNING_STALE_SECONDS', 7200))
    queued_cutoff = now - timedelta(seconds=_config_int('JOB_QUEUED_STALE_SECONDS', 1800))
    candidates = JobExecution.query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES)).all()
    recovered = 0
    expired = 0
    for job in candidates:
        stale = False
        if job.status == 'queued':
            # A healthy forecasting backlog can legitimately stay queued for a
            # long time. Only expire an explicit deadline or an orphan record that
            # was never assigned a Celery task identifier.
            stale = bool(
                (job.expires_at is not None and job.expires_at < now)
                or (job.celery_task_id is None and job.queued_at < queued_cutoff)
            )
        elif job.status in {'running', 'retrying', 'cancel_requested'}:
            heartbeat = job.heartbeat_at or job.started_at or job.queued_at
            stale = heartbeat < running_cutoff
        if not stale:
            continue
        _terminalize(job, 'expired')
        job.error_code = 'stale_job_recovered'
        job.error_message = 'KAORI marked the job expired because its worker heartbeat became stale.'
        job.progress_message = 'Expired after stale worker heartbeat'
        recovered += 1
        expired += 1
    if recovered:
        db.session.commit()
    return {'recovered': recovered, 'expired': expired}
