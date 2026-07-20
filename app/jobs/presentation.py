from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.common.presentation import present_user_datetime
from app.jobs.service import job_can_cancel
from app.models.job import JobExecution

ALLOWED_PER_PAGE = (5, 10, 25, 50)

_JOB_ICONS = {
    'runtime': 'activity',
    'validation': 'scan-search',
    'analytics': 'chart-no-axes-combined',
    'forecasting': 'chart-spline',
    'standard': 'workflow',
}


def _duration_label(job: JobExecution) -> str:
    start = job.started_at or job.queued_at
    end = job.completed_at
    if start is None:
        return 'Not started'
    if end is None:
        return 'In progress'
    seconds = max(int((end - start).total_seconds()), 0)
    if seconds < 60:
        return f'{seconds}s'
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes}m {remaining}s'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m'


def _row(job: JobExecution) -> dict[str, Any]:
    total = max(job.progress_total, 0)
    current = max(job.progress_current, 0)
    progress = min(int((current / total) * 100), 100) if total else (100 if job.is_terminal else 0)
    requester = job.requested_by.display_label if job.requested_by is not None else 'KAORI Scheduler'
    scope = job.scope_key or (
        f'{job.provider_type}:{job.provider_instance_id}'
        if job.provider_type and job.provider_instance_id is not None
        else job.resource_group or 'Global'
    )
    return {
        'public_id': job.public_id,
        'task_id': job.celery_task_id,
        'job_type': job.job_type,
        'operation': job.operation,
        'operation_label': job.operation.replace('_', ' ').title(),
        'workload_class': job.workload_class,
        'workload_label': job.workload_class.replace('_', ' ').title(),
        'icon': _JOB_ICONS.get(job.workload_class, 'workflow'),
        'queue_name': job.queue_name,
        'priority': job.priority,
        'status': job.status,
        'status_label': job.status.replace('_', ' ').title(),
        'provider_type': job.provider_type,
        'scope': scope,
        'resource_group': job.resource_group,
        'requester': requester,
        'progress': progress,
        'progress_current': current,
        'progress_total': total,
        'progress_message': job.progress_message or 'Waiting for worker',
        'attempt_count': job.attempt_count,
        'max_attempts': job.max_attempts,
        'queued_at': present_user_datetime(job.queued_at, empty='Not queued'),
        'started_at': present_user_datetime(job.started_at, empty='Not started'),
        'completed_at': present_user_datetime(job.completed_at, empty='In progress'),
        'duration': _duration_label(job),
        'error_message': job.error_message,
        'is_active': job.is_active,
        'is_terminal': job.is_terminal,
        'can_cancel': job_can_cancel(job),
    }


def build_job_execution_context(
    *,
    page: int = 1,
    per_page: int = 5,
    status: str = '',
    workload: str = '',
    queue: str = '',
    search: str = '',
) -> dict[str, Any]:
    selected_per_page = per_page if per_page in ALLOWED_PER_PAGE else ALLOWED_PER_PAGE[0]
    selected_page = max(page, 1)
    query = JobExecution.query
    if status:
        query = query.filter(JobExecution.status == status)
    if workload:
        query = query.filter(JobExecution.workload_class == workload)
    if queue:
        query = query.filter(JobExecution.queue_name == queue)
    if search:
        value = f'%{search.strip()}%'
        query = query.filter(or_(
            JobExecution.operation.ilike(value),
            JobExecution.job_type.ilike(value),
            JobExecution.provider_type.ilike(value),
            JobExecution.scope_key.ilike(value),
            JobExecution.resource_group.ilike(value),
            JobExecution.public_id.ilike(value),
        ))
    query = query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
    paginated = query.paginate(page=selected_page, per_page=selected_per_page, error_out=False)
    total_pages = max(paginated.pages, 1)
    current_page = min(max(paginated.page, 1), total_pages)
    items = [_row(job) for job in paginated.items]

    active_count = JobExecution.query.filter(JobExecution.status.in_(('queued', 'running', 'retrying', 'cancel_requested'))).count()
    running_count = JobExecution.query.filter_by(status='running').count()
    heavy_count = JobExecution.query.filter(
        JobExecution.status.in_(('queued', 'running', 'retrying', 'cancel_requested')),
        JobExecution.workload_class.in_(('analytics', 'forecasting')),
    ).count()
    failed_count = JobExecution.query.filter_by(status='failed').count()
    queue_options = [row[0] for row in JobExecution.query.with_entities(JobExecution.queue_name).distinct().order_by(JobExecution.queue_name.asc()).all()]

    start_item = ((current_page - 1) * selected_per_page) + 1 if paginated.total else 0
    return {
        'job_rows': items,
        'job_stats': {
            'active': active_count,
            'running': running_count,
            'heavy': heavy_count,
            'failed': failed_count,
        },
        'job_pagination': {
            'page': current_page,
            'per_page': selected_per_page,
            'total_items': paginated.total,
            'total_pages': total_pages,
            'start_item': start_item,
            'end_item': min(current_page * selected_per_page, paginated.total),
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next,
            'prev_page': current_page - 1,
            'next_page': current_page + 1,
            'pages': list(range(1, total_pages + 1)),
            'allowed_per_page': list(ALLOWED_PER_PAGE),
        },
        'selected_job_status': status,
        'selected_job_workload': workload,
        'selected_job_queue': queue,
        'job_search': search,
        'job_has_filters': bool(status or workload or queue or search),
        'job_status_options': [
            ('queued', 'Queued'),
            ('running', 'Running'),
            ('retrying', 'Retrying'),
            ('cancel_requested', 'Cancel Requested'),
            ('succeeded', 'Succeeded'),
            ('partially_succeeded', 'Partially Succeeded'),
            ('failed', 'Failed'),
            ('canceled', 'Canceled'),
            ('expired', 'Expired'),
        ],
        'job_workload_options': [
            ('runtime', 'Runtime'),
            ('validation', 'Validation'),
            ('analytics', 'Analytics'),
            ('forecasting', 'Forecasting'),
            ('standard', 'Standard'),
        ],
        'job_queue_options': queue_options,
    }
