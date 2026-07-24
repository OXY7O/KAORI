from __future__ import annotations

from typing import Any

from app.cluster.sync_jobs import build_fleet_inventory_targets
from app.common.presentation import present_user_datetime
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.models.cluster import Cluster
from app.models.inventory_sync import InventorySyncPolicy
from app.models.job import JobExecution

_STATUS_PRESENTATION = {
    'queued': ('Queued', 'pending', 'clock-3'),
    'running': ('Running', 'pending', 'loader-circle'),
    'retrying': ('Retrying', 'warning', 'rotate-ccw'),
    'cancel_requested': ('Cancel Requested', 'warning', 'octagon-alert'),
    'succeeded': ('Succeeded', 'normal', 'circle-check'),
    'partially_succeeded': ('Partially Succeeded', 'warning', 'triangle-alert'),
    'failed': ('Failed', 'critical', 'circle-x'),
    'canceled': ('Canceled', 'unknown', 'ban'),
    'expired': ('Expired', 'unknown', 'clock-alert'),
}


def _interval_label(minutes: int) -> str:
    if minutes < 60:
        return f'{minutes} Minutes'
    hours, remainder = divmod(minutes, 60)
    if remainder == 0:
        return f'{hours} Hour' if hours == 1 else f'{hours} Hours'
    return f'{hours}h {remainder}m'


def _job_progress(job: JobExecution) -> tuple[int, str]:
    total = max(job.progress_total, 0)
    current = max(job.progress_current, 0)
    if total:
        percent = min(int((current / total) * 100), 100)
        return percent, f'{current} of {total} Clusters'
    if job.is_terminal:
        return 100, 'Execution Completed'
    return 0, 'Waiting For Worker'


def _present_job(job: JobExecution) -> dict[str, Any]:
    payload = job.payload_json or {}
    status_label, status_tone, status_icon = _STATUS_PRESENTATION.get(
        job.status,
        (job.status.replace('_', ' ').title(), 'unknown', 'circle-help'),
    )
    progress, progress_label = _job_progress(job)
    requester = job.requested_by.display_label if job.requested_by is not None else 'KAORI Scheduler'
    trigger_type = str(payload.get('trigger_type') or ('scheduled' if job.requested_by_user_id is None else 'manual'))
    target_count = int(payload.get('total_count') or job.progress_total or 0)
    return {
        'public_id': job.public_id,
        'status': job.status,
        'status_label': status_label,
        'status_tone': status_tone,
        'status_icon': status_icon,
        'trigger_type': trigger_type,
        'trigger_label': trigger_type.replace('_', ' ').title(),
        'trigger_icon': 'calendar-clock' if trigger_type == 'scheduled' else 'mouse-pointer-click',
        'requester': requester,
        'target_count': target_count,
        'progress': progress,
        'progress_label': progress_label,
        'progress_message': job.progress_message or 'Waiting for the inventory worker.',
        'queued_at': present_user_datetime(job.queued_at, empty='Not Queued'),
        'started_at': present_user_datetime(job.started_at, empty='Not Started'),
        'completed_at': present_user_datetime(job.completed_at, empty='In Progress'),
        'is_active': job.is_active,
        'is_terminal': job.is_terminal,
        'error_message': job.error_message,
    }


def build_inventory_sync_page_context(policy: InventorySyncPolicy) -> dict[str, Any]:
    registered_cluster_count = Cluster.query.count()
    eligible_targets = build_fleet_inventory_targets(log_skipped=False)
    eligible_cluster_count = len(eligible_targets)
    blocked_cluster_count = max(registered_cluster_count - eligible_cluster_count, 0)

    jobs_query = JobExecution.query.filter(
        JobExecution.job_type == 'kubernetes_inventory',
        JobExecution.operation == 'inventory_sync_all',
    )
    active_job = (
        jobs_query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
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
            'description': 'Automatic fleet synchronization is scheduled.',
        }
    elif policy.enabled:
        scheduler_state = {
            'label': 'Waiting For Cluster',
            'tone': 'warning',
            'icon': 'triangle-alert',
            'description': 'The schedule is enabled, but no eligible Kubernetes binding is available.',
        }
    else:
        scheduler_state = {
            'label': 'Disabled',
            'tone': 'disabled',
            'icon': 'circle-pause',
            'description': 'Only manual inventory synchronization is available.',
        }

    if active_job is not None:
        execution_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'A fleet inventory job is already queued or running.',
        }
    elif eligible_cluster_count:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'The eligible fleet can be synchronized on demand.',
        }
    else:
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': 'Register and enable a canonical Kubernetes binding before synchronizing.',
        }

    return {
        'registered_cluster_count': registered_cluster_count,
        'eligible_cluster_count': eligible_cluster_count,
        'blocked_cluster_count': blocked_cluster_count,
        'eligible_targets': eligible_targets,
        'scheduler_state': scheduler_state,
        'execution_state': execution_state,
        'interval_label': _interval_label(policy.interval_minutes),
        'active_job': _present_job(active_job) if active_job is not None else None,
        'latest_job': _present_job(latest_job) if latest_job is not None else None,
        'recent_jobs': [_present_job(job) for job in recent_jobs],
    }
