from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_

from app.common.presentation import present_user_datetime
from app.jobs.service import job_can_cancel
from app.models.job import JobExecution

ALLOWED_PER_PAGE = (5, 10, 25, 50)
_ACTIVE_STATUSES = ('queued', 'running', 'retrying', 'cancel_requested')
_ATTENTION_STATUSES = ('retrying', 'cancel_requested', 'failed', 'partially_succeeded')
_TERMINAL_STATUSES = ('succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired')
_ALLOWED_TABS = ('active', 'registry', 'queues')

_JOB_ICONS = {
    'runtime': 'activity',
    'validation': 'scan-search',
    'analytics': 'chart-no-axes-combined',
    'forecasting': 'chart-spline',
    'standard': 'workflow',
}

_QUEUE_ICONS = {
    'integration-runtime': 'activity',
    'integration-validation': 'scan-search',
    'analytics-batch': 'chart-no-axes-combined',
    'forecasting': 'chart-spline',
    'maintenance': 'archive-restore',
    'inventory': 'database-zap',
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
    if total > 0 or job.is_terminal:
        progress_mode = 'determinate'
        progress_label = f'{progress}%'
    elif job.status == 'queued':
        progress_mode = 'queued'
        progress_label = 'Queued'
    else:
        progress_mode = 'indeterminate'
        progress_label = 'In Progress'

    if job_can_cancel(job):
        action_state = 'cancel'
        action_label = 'Cancel'
        action_icon = 'square'
        action_help = 'Request cancellation for this eligible job.'
    elif job.is_active and job.workload_class in {'validation', 'runtime'}:
        action_state = 'protected'
        action_label = 'Protected Run'
        action_icon = 'shield-check'
        action_help = 'Provider operations are not force-terminated mid-request; queued jobs remain cancellable.'
    else:
        action_state = 'none'
        action_label = 'No Action'
        action_icon = 'minus'
        action_help = 'This job has no available operator action.'
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
        'provider_label': (job.provider_type or 'KAORI').replace('_', ' ').title(),
        'scope': scope,
        'resource_group': job.resource_group,
        'requester': requester,
        'progress': progress,
        'progress_mode': progress_mode,
        'progress_label': progress_label,
        'progress_current': current,
        'progress_total': total,
        'progress_message': job.progress_message or 'Waiting for worker',
        'attempt_count': job.attempt_count,
        'max_attempts': job.max_attempts,
        'queued_at': present_user_datetime(job.queued_at, empty='Not queued'),
        'started_at': present_user_datetime(job.started_at, empty='Not started'),
        'completed_at': present_user_datetime(job.completed_at, empty='In progress'),
        'updated_at': present_user_datetime(job.updated_at, empty='Not updated'),
        'duration': _duration_label(job),
        'error_message': job.error_message,
        'is_active': job.is_active,
        'is_terminal': job.is_terminal,
        'can_cancel': action_state == 'cancel',
        'action_state': action_state,
        'action_label': action_label,
        'action_icon': action_icon,
        'action_help': action_help,
    }


def _queue_icon(queue_name: str) -> str:
    if queue_name in _QUEUE_ICONS:
        return _QUEUE_ICONS[queue_name]
    if 'runtime' in queue_name:
        return 'activity'
    if 'validation' in queue_name:
        return 'scan-search'
    if 'forecast' in queue_name:
        return 'chart-spline'
    if 'analytics' in queue_name:
        return 'chart-no-axes-combined'
    if 'maintenance' in queue_name or 'retention' in queue_name:
        return 'archive-restore'
    return 'workflow'


def _queue_activity(queue_names: list[str], cutoff: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for queue_name in queue_names:
        query = JobExecution.query.filter(JobExecution.queue_name == queue_name)
        active = query.filter(JobExecution.status.in_(_ACTIVE_STATUSES)).count()
        queued = query.filter_by(status='queued').count()
        running = query.filter_by(status='running').count()
        attention = query.filter(JobExecution.status.in_(_ATTENTION_STATUSES)).count()
        completed_24h = query.filter(
            JobExecution.status.in_(_TERMINAL_STATUSES),
            JobExecution.completed_at.isnot(None),
            JobExecution.completed_at >= cutoff,
        ).count()
        failed_24h = query.filter(
            JobExecution.status == 'failed',
            JobExecution.completed_at.isnot(None),
            JobExecution.completed_at >= cutoff,
        ).count()
        latest = query.order_by(JobExecution.updated_at.desc(), JobExecution.id.desc()).first()
        state = 'attention' if failed_24h or attention else ('active' if active else 'idle')
        rows.append({
            'name': queue_name,
            'icon': _queue_icon(queue_name),
            'state': state,
            'active': active,
            'queued': queued,
            'running': running,
            'attention': attention,
            'completed_24h': completed_24h,
            'failed_24h': failed_24h,
            'latest_activity': present_user_datetime(latest.updated_at, empty='No activity') if latest else 'No activity',
        })
    return rows


def build_job_execution_context(
    *,
    page: int = 1,
    per_page: int = 5,
    status: str = '',
    workload: str = '',
    queue: str = '',
    search: str = '',
    tab: str = 'active',
) -> dict[str, Any]:
    selected_per_page = per_page if per_page in ALLOWED_PER_PAGE else ALLOWED_PER_PAGE[0]
    selected_page = max(page, 1)
    selected_tab = tab if tab in _ALLOWED_TABS else _ALLOWED_TABS[0]
    cutoff = datetime.now(UTC) - timedelta(hours=24)

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
            JobExecution.queue_name.ilike(value),
        ))
    query = query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
    paginated = query.paginate(page=selected_page, per_page=selected_per_page, error_out=False)
    total_items = int(paginated.total or 0)
    total_pages = max(int(paginated.pages or 0), 1)
    current_page = min(max(paginated.page, 1), total_pages)
    items = [_row(job) for job in paginated.items]

    active_query = JobExecution.query.filter(JobExecution.status.in_(_ACTIVE_STATUSES))
    active_jobs = [
        _row(job)
        for job in active_query.order_by(JobExecution.updated_at.desc(), JobExecution.id.desc()).limit(6).all()
    ]
    active_count = active_query.count()
    queued_count = JobExecution.query.filter_by(status='queued').count()
    running_count = JobExecution.query.filter_by(status='running').count()
    heavy_count = active_query.filter(JobExecution.workload_class.in_(('analytics', 'forecasting'))).count()
    attention_count = JobExecution.query.filter(JobExecution.status.in_(_ATTENTION_STATUSES)).count()
    failed_count = JobExecution.query.filter_by(status='failed').count()
    completed_24h_count = JobExecution.query.filter(
        JobExecution.status.in_(_TERMINAL_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    ).count()
    total_count = JobExecution.query.count()
    queue_options = [
        row[0]
        for row in JobExecution.query.with_entities(JobExecution.queue_name)
        .distinct()
        .order_by(JobExecution.queue_name.asc())
        .all()
    ]
    queue_rows = _queue_activity(queue_options, cutoff)

    start_item = ((current_page - 1) * selected_per_page) + 1 if total_items else 0
    return {
        'job_rows': items,
        'active_job_rows': active_jobs,
        'active_job_overflow': max(active_count - len(active_jobs), 0),
        'job_queue_rows': queue_rows,
        'job_stats': {
            'total': total_count,
            'active': active_count,
            'queued': queued_count,
            'running': running_count,
            'heavy': heavy_count,
            'attention': attention_count,
            'failed': failed_count,
            'completed_24h': completed_24h_count,
            'queues': len(queue_options),
        },
        'job_pagination': {
            'page': current_page,
            'per_page': selected_per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': start_item,
            'end_item': min(current_page * selected_per_page, total_items),
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
        'selected_job_tab': selected_tab,
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
        'job_last_refreshed_at': present_user_datetime(datetime.now(UTC), empty='Just now'),
    }
