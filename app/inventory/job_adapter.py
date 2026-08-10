from __future__ import annotations

from typing import Any

from app.cluster.sync_jobs import (
    NoEligibleInventoryTargets,
    build_fleet_inventory_targets,
    enqueue_all_cluster_inventory_sync,
    enqueue_cluster_inventory_sync,
)
from app.common.job_execution_presentation import present_job_execution
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.policies.presentation import present_interval
from app.models.cluster import Cluster
from app.models.job import JobExecution, JobPolicy


def _job_progress(job: JobExecution) -> tuple[int, str]:
    total = max(job.progress_total, 0)
    current = max(job.progress_current, 0)
    if total:
        percent = min(int((current / total) * 100), 100)
        return percent, f'{current} of {total} Clusters'
    if job.is_terminal:
        return 100, 'Execution Completed'
    if job.status == 'queued':
        return 0, 'Waiting For Inventory Worker'
    return 0, 'Preparing Inventory Execution'


def present_inventory_job(job: JobExecution) -> dict[str, Any]:
    payload = job.payload_json or {}
    progress, progress_label = _job_progress(job)
    row = present_job_execution(job)
    row.update(
        {
            'progress': progress,
            'progress_label': progress_label,
            'target_count': int(payload.get('total_count') or job.progress_total or 0),
            'progress_message': job.progress_message or 'Waiting for the inventory worker.',
        }
    )
    return row


def dispatch_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    cluster_id = str((parameters or {}).get('cluster_id') or '').strip()
    if cluster_id:
        cluster = Cluster.query.filter_by(id=cluster_id).first()
        if cluster is None:
            return RegisteredJobDispatchResult(
                status='blocked',
                message='The selected Kubernetes cluster no longer exists.',
            )
        try:
            job, created = enqueue_cluster_inventory_sync(
                cluster=cluster,
                requested_by_user_id=requested_by_user_id,
                trigger_type=trigger_type,
            )
        except (LookupError, RuntimeError) as exc:
            return RegisteredJobDispatchResult(status='blocked', message=str(exc))
        return RegisteredJobDispatchResult(
            status='queued' if created else 'reused',
            message=(
                f'Inventory synchronization was queued for {cluster.name}.'
                if created
                else f'The request joined the active inventory synchronization for {cluster.name}.'
            ),
            job=job,
            created=created,
        )

    try:
        job, created = enqueue_all_cluster_inventory_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
        )
    except NoEligibleInventoryTargets:
        return RegisteredJobDispatchResult(
            status='blocked',
            message='No eligible Kubernetes cluster has an enabled canonical binding.',
        )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'A canonical fleet inventory execution was queued.'
            if created
            else 'The request joined the active fleet inventory execution.'
        ),
        job=job,
        created=created,
    )


def build_inventory_sync_context(policy: JobPolicy) -> dict[str, Any]:
    registered_cluster_count = Cluster.query.count()
    eligible_targets = build_fleet_inventory_targets(log_skipped=False)
    eligible_cluster_count = len(eligible_targets)
    blocked_cluster_count = max(registered_cluster_count - eligible_cluster_count, 0)

    jobs_query = JobExecution.query.filter(
        JobExecution.job_type == 'kubernetes_inventory',
        JobExecution.operation == 'inventory_sync_all',
    )
    active_job = (
        jobs_query.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest_job = recent_jobs[0] if recent_jobs else None

    if policy.enabled and eligible_cluster_count:
        scheduler_state = {
            'label': 'Enabled',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Automatic fleet sync is scheduled.',
        }
    elif policy.enabled:
        scheduler_state = {
            'label': 'Waiting For Cluster',
            'tone': 'warning',
            'icon': 'triangle-alert',
            'description': 'Enabled, but no eligible binding is available.',
        }
    else:
        scheduler_state = {
            'label': 'Disabled',
            'tone': 'disabled',
            'icon': 'circle-pause',
            'description': 'Automatic sync is disabled.',
        }

    if eligible_cluster_count:
        readiness_state = {
            'label': 'Sync Eligible',
            'tone': 'normal',
            'icon': 'link-2',
            'description': 'Eligible Kubernetes bindings are ready for sync.',
        }
    else:
        readiness_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': 'No eligible Kubernetes binding is available.',
        }

    if active_job is not None:
        configuration_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
        }
    elif not eligible_cluster_count:
        configuration_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
        }
    elif policy.enabled:
        configuration_state = {
            'label': 'Enabled',
            'tone': 'normal',
            'icon': 'circle-check',
        }
    else:
        configuration_state = {
            'label': 'Manual Only',
            'tone': 'unknown',
            'icon': 'mouse-pointer-click',
        }

    if active_job is not None:
        execution_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'A fleet inventory job is active.',
        }
    elif eligible_cluster_count:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'The eligible fleet is ready to sync.',
        }
    else:
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': 'Enable a Kubernetes binding before syncing.',
        }

    return {
        'registered_cluster_count': registered_cluster_count,
        'eligible_cluster_count': eligible_cluster_count,
        'blocked_cluster_count': blocked_cluster_count,
        'eligible_targets': eligible_targets,
        'scheduler_state': scheduler_state,
        'readiness_state': readiness_state,
        'configuration_state': configuration_state,
        'execution_state': execution_state,
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_inventory_job(active_job) if active_job is not None else None,
        'latest_job': present_inventory_job(latest_job) if latest_job is not None else None,
        'recent_jobs': [present_inventory_job(job) for job in recent_jobs],
    }
