from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_

from app.common.job_execution_presentation import present_job_execution
from app.common.presentation import present_user_datetime
from app.kubernetes.tenant.sync_service import build_tenant_inventory_snapshot
from app.kubernetes.tenant.tasks import sync_tenant_inventory_task
from app.models.job import JobExecution, JobExecutionSubscriber, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_STANDARD
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job
from app.platform_operations.jobs.policies.presentation import present_interval
from app.platform_operations.jobs.policies.service import get_or_create_job_policy

TENANT_SYNC_JOB_KEY = 'kubernetes.tenant.sync'
TENANT_SYNC_JOB_TYPE = 'kubernetes_tenant_inventory'
TENANT_SYNC_OPERATION = 'sync_kubernetes_tenant_inventory'
TENANT_SYNC_QUEUE = 'inventory'
_SUCCESS_STATUSES = ('succeeded', 'partially_succeeded')


def get_visible_tenant_sync_job(*, public_id: str, user_id: int) -> JobExecution | None:
    subscriber_can_view = JobExecution.subscribers.any(
        JobExecutionSubscriber.user_id == user_id,
    )
    return (
        JobExecution.query.filter(
            JobExecution.job_type == TENANT_SYNC_JOB_TYPE,
            JobExecution.operation == TENANT_SYNC_OPERATION,
            or_(
                JobExecution.requested_by_user_id == user_id,
                subscriber_can_view,
            ),
            JobExecution.public_id == public_id,
        )
        .order_by(JobExecution.id.desc())
        .first()
    )


def dispatch_tenant_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    job, created = enqueue_canonical_job(
        task=sync_tenant_inventory_task,
        task_kwargs={
            'requested_by_user_id': requested_by_user_id,
            'trigger_type': trigger_type,
        },
        job_type=TENANT_SYNC_JOB_TYPE,
        operation=TENANT_SYNC_OPERATION,
        queue_name=TENANT_SYNC_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='container_orchestrator',
        integration_instance_id=None,
        scope_type='kubernetes_tenant_fleet',
        scope_key='all',
        resource_group='kubernetes-tenant-inventory:global',
        parameters={'scope': 'all_clusters'},
        payload={
            'scope': 'all_clusters',
            'trigger_type': trigger_type,
        },
        max_attempts=3,
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'Tenant inventory synchronization was queued in the inventory worker.'
            if created
            else 'The request joined the active Tenant inventory synchronization.'
        ),
        job=job,
        created=created,
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def build_tenant_sync_state() -> dict[str, Any]:
    policy = get_or_create_job_policy(TENANT_SYNC_JOB_KEY)
    jobs = JobExecution.query.filter(
        JobExecution.job_type == TENANT_SYNC_JOB_TYPE,
        JobExecution.operation == TENANT_SYNC_OPERATION,
    )
    active_job = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(50).all()
    latest_job = recent_jobs[0] if recent_jobs else None
    latest_success = next((job for job in recent_jobs if job.status in _SUCCESS_STATUSES), None)

    interval_minutes = max(int(policy.interval_minutes or 60), 1)
    last_success_at = _as_utc(latest_success.completed_at if latest_success else None)
    stale_after = timedelta(minutes=interval_minutes + min(max(interval_minutes // 4, 15), 180))
    is_stale = last_success_at is not None and datetime.now(UTC) - last_success_at > stale_after

    if active_job is not None and active_job.status == 'queued':
        label, tone, icon = 'Queued', 'pending', 'clock-3'
        helper = active_job.progress_message or 'Waiting for the inventory worker to start Tenant synchronization.'
    elif active_job is not None:
        label, tone, icon = 'Syncing', 'pending', 'loader-circle'
        helper = active_job.progress_message or 'Tenant inventory synchronization is running in the inventory worker.'
    elif latest_job is not None and latest_job.status == 'failed':
        label, tone, icon = 'Sync Failed', 'critical', 'circle-x'
        helper = 'The most recent Tenant synchronization failed. Review Jobs & Executions before retrying.'
    elif latest_success is None:
        label, tone, icon = 'Not Collected', 'warning', 'clock-alert'
        helper = 'Run the first Tenant sync to establish a committed Tenant collection snapshot.'
    elif is_stale:
        label, tone, icon = 'Stale', 'warning', 'clock-alert'
        helper = 'Tenant inventory is older than the configured automatic synchronization window.'
    else:
        label, tone, icon = 'Current', 'normal', 'circle-check'
        helper = 'Tenant inventory is within the configured synchronization window.'

    summary = dict(latest_success.result_summary_json or {}) if latest_success is not None else {}
    progress_current = max(int(active_job.progress_current or 0), 0) if active_job is not None else 0
    progress_total = max(int(active_job.progress_total or 0), 0) if active_job is not None else 0
    progress_percent = 0
    if progress_total:
        progress_percent = max(0, min(round((progress_current / progress_total) * 100), 100))

    return {
        'label': label,
        'tone': tone,
        'icon': icon,
        'helper': helper,
        'is_active': active_job is not None,
        'active_job_public_id': active_job.public_id if active_job is not None else None,
        'active_job': present_job_execution(active_job) if active_job is not None else None,
        'latest_job': present_job_execution(latest_job) if latest_job is not None else None,
        'last_success_at': last_success_at,
        'last_success_label': present_user_datetime(last_success_at, empty='Never'),
        'automatic_enabled': bool(policy.enabled),
        'interval_minutes': interval_minutes,
        'interval_label': present_interval(interval_minutes),
        'next_run_at': policy.next_run_at,
        'next_run_label': present_user_datetime(policy.next_run_at, empty='Not Scheduled'),
        'progress_current': progress_current,
        'progress_total': progress_total,
        'progress_percent': progress_percent,
        'progress_message': active_job.progress_message if active_job is not None else None,
        'snapshot': summary,
    }


def build_tenant_sync_context(policy: JobPolicy) -> dict[str, Any]:
    state = build_tenant_sync_state()
    preview = build_tenant_inventory_snapshot()
    return {
        'registered_cluster_count': preview['registered_cluster_count'],
        'tenant_cluster_count': preview['tenant_cluster_count'],
        'tenant_count': preview['tenant_count'],
        'namespace_count': preview['namespace_count'],
        'interval_label': present_interval(policy.interval_minutes),
        'configuration_state': {
            'label': 'Execution Active'
            if state['is_active']
            else 'Enabled'
            if policy.enabled
            else 'Manual Only',
            'tone': 'pending' if state['is_active'] else 'normal' if policy.enabled else 'unknown',
            'icon': 'loader-circle' if state['is_active'] else 'circle-check' if policy.enabled else 'mouse-pointer-click',
        },
        'execution_state': {
            'label': state['label'],
            'tone': state['tone'],
            'icon': state['icon'],
            'description': state['helper'],
        },
        'active_job': state['active_job'],
        'latest_job': state['latest_job'],
        'recent_jobs': [
            present_job_execution(job)
            for job in JobExecution.query.filter(
                JobExecution.job_type == TENANT_SYNC_JOB_TYPE,
                JobExecution.operation == TENANT_SYNC_OPERATION,
            )
            .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
            .limit(5)
            .all()
        ],
    }
