from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_

from app.common.celery_queue_health import get_queue_readiness, inspect_celery_topology
from app.common.job_execution_presentation import present_job_execution_row
from app.common.presentation import present_user_datetime
from app.jobs.service import job_can_cancel
from app.models.job import JobExecution

ALLOWED_PER_PAGE = (5, 10, 25, 50)
_ACTIVE_STATUSES = ('queued', 'running', 'retrying', 'cancel_requested')
_ACTIVE_ATTENTION_STATUSES = ('retrying', 'cancel_requested')
_RECENT_ATTENTION_STATUSES = ('failed', 'partially_succeeded', 'expired')
_TERMINAL_STATUSES = ('succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired')
_ALLOWED_TABS = ('active', 'registry', 'queues')

_QUEUE_ICONS = {
    'integration-runtime': 'activity',
    'integration-validation': 'scan-search',
    'analytics-batch': 'chart-no-axes-combined',
    'forecasting': 'chart-spline',
    'maintenance': 'archive-restore',
    'inventory': 'database-zap',
    'reports': 'file-clock',
}


def _row(job: JobExecution) -> dict[str, Any]:
    row = present_job_execution_row(job)
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
    row.update(
        {
            'can_cancel': action_state == 'cancel',
            'action_state': action_state,
            'action_label': action_label,
            'action_icon': action_icon,
            'action_help': action_help,
        }
    )
    return row


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


def _attention_counts(query: Any, cutoff: datetime) -> tuple[int, int, int]:
    active_attention = query.filter(
        JobExecution.status.in_(_ACTIVE_ATTENTION_STATUSES)
    ).count()
    recent_terminal_attention = query.filter(
        JobExecution.status.in_(_RECENT_ATTENTION_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    ).count()
    return (
        active_attention,
        recent_terminal_attention,
        active_attention + recent_terminal_attention,
    )


def _queue_activity(queue_names: list[str], cutoff: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    topology = inspect_celery_topology() if queue_names else None
    for queue_name in queue_names:
        query = JobExecution.query.filter(JobExecution.queue_name == queue_name)
        active = query.filter(JobExecution.status.in_(_ACTIVE_STATUSES)).count()
        queued = query.filter_by(status='queued').count()
        running = query.filter_by(status='running').count()
        active_attention, recent_attention_24h, attention = _attention_counts(query, cutoff)
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
        readiness = get_queue_readiness(queue_name, topology=topology)
        readiness_tone = str(readiness.get('tone') or 'unknown')
        if readiness_tone == 'critical':
            posture_tone = 'critical'
        elif attention or readiness.get('show_warning'):
            posture_tone = 'warning'
        elif active:
            posture_tone = 'info'
        else:
            posture_tone = 'normal'
        posture_label = 'Attention' if attention or readiness.get('show_warning') else ('Active' if active else 'Idle')
        rows.append(
            {
                'name': queue_name,
                'icon': _queue_icon(queue_name),
                'state': 'attention' if attention else ('active' if active else 'idle'),
                'posture_label': posture_label,
                'posture_tone': posture_tone,
                'active': active,
                'queued': queued,
                'running': running,
                'active_attention': active_attention,
                'recent_attention_24h': recent_attention_24h,
                'attention': attention,
                'completed_24h': completed_24h,
                'failed_24h': failed_24h,
                'latest_activity': present_user_datetime(latest.updated_at, empty='No activity')
                if latest
                else 'No activity',
                'worker_readiness': readiness,
            }
        )
    return rows


def build_job_execution_status_context(*, tab: str = 'active') -> dict[str, Any]:
    """Return lightweight counters for the live Execution Overview poller."""
    selected_tab = tab if tab in _ALLOWED_TABS else _ALLOWED_TABS[0]
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    active_count = JobExecution.query.filter(JobExecution.status.in_(_ACTIVE_STATUSES)).count()
    running_count = JobExecution.query.filter_by(status='running').count()
    active_attention_count, recent_attention_24h_count, attention_count = _attention_counts(
        JobExecution.query,
        cutoff,
    )
    completed_24h_count = JobExecution.query.filter(
        JobExecution.status.in_(_TERMINAL_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    ).count()
    total_count = JobExecution.query.count()
    queue_count = JobExecution.query.with_entities(JobExecution.queue_name).distinct().count()
    return {
        'job_stats': {
            'total': total_count,
            'active': active_count,
            'running': running_count,
            'active_attention': active_attention_count,
            'recent_attention_24h': recent_attention_24h_count,
            'attention': attention_count,
            'completed_24h': completed_24h_count,
            'queues': queue_count,
        },
        'selected_job_tab': selected_tab,
        'job_last_refreshed_at': present_user_datetime(datetime.now(UTC), empty='Just now'),
    }


def build_job_execution_context(
    *,
    page: int = 1,
    per_page: int = 5,
    status: str = '',
    workload: str = '',
    queue: str = '',
    search: str = '',
    tab: str = 'active',
    include_queue_activity: bool = True,
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
        query = query.filter(
            or_(
                JobExecution.operation.ilike(value),
                JobExecution.job_type.ilike(value),
                JobExecution.provider_type.ilike(value),
                JobExecution.scope_key.ilike(value),
                JobExecution.resource_group.ilike(value),
                JobExecution.public_id.ilike(value),
                JobExecution.queue_name.ilike(value),
            )
        )
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
    active_attention_count, recent_attention_24h_count, attention_count = _attention_counts(
        JobExecution.query,
        cutoff,
    )
    failed_24h_count = JobExecution.query.filter(
        JobExecution.status == 'failed',
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    ).count()
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
    queue_rows = _queue_activity(queue_options, cutoff) if include_queue_activity else []

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
            'active_attention': active_attention_count,
            'recent_attention_24h': recent_attention_24h_count,
            'attention': attention_count,
            'failed_24h': failed_24h_count,
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
