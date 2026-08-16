from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func, or_

from app.common.celery_queue_health import get_queue_readiness, inspect_celery_topology
from app.common.job_execution_presentation import present_job_execution_row
from app.common.pagination import paginate_query
from app.common.presentation import present_user_datetime
from app.extensions.db import db
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


def _execution_summary(cutoff: datetime) -> dict[str, int]:
    """Return the global execution counters from one aggregate SQL query."""
    active_condition = JobExecution.status.in_(_ACTIVE_STATUSES)
    active_attention_condition = JobExecution.status.in_(_ACTIVE_ATTENTION_STATUSES)
    recent_attention_condition = and_(
        JobExecution.status.in_(_RECENT_ATTENTION_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    )
    completed_condition = and_(
        JobExecution.status.in_(_TERMINAL_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    )
    failed_condition = and_(
        JobExecution.status == 'failed',
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    )
    heavy_condition = and_(
        active_condition,
        JobExecution.workload_class.in_(('analytics', 'forecasting')),
    )

    result = (
        db.session.query(
            func.count(JobExecution.id).label('total'),
            func.sum(case((active_condition, 1), else_=0)).label('active'),
            func.sum(case((JobExecution.status == 'queued', 1), else_=0)).label('queued'),
            func.sum(case((JobExecution.status == 'running', 1), else_=0)).label('running'),
            func.sum(case((heavy_condition, 1), else_=0)).label('heavy'),
            func.sum(case((active_attention_condition, 1), else_=0)).label('active_attention'),
            func.sum(case((recent_attention_condition, 1), else_=0)).label('recent_attention_24h'),
            func.sum(case((failed_condition, 1), else_=0)).label('failed_24h'),
            func.sum(case((completed_condition, 1), else_=0)).label('completed_24h'),
            func.count(func.distinct(JobExecution.queue_name)).label('queues'),
        )
        .one()
    )
    active_attention = int(result.active_attention or 0)
    recent_attention = int(result.recent_attention_24h or 0)
    return {
        'total': int(result.total or 0),
        'active': int(result.active or 0),
        'queued': int(result.queued or 0),
        'running': int(result.running or 0),
        'heavy': int(result.heavy or 0),
        'active_attention': active_attention,
        'recent_attention_24h': recent_attention,
        'attention': active_attention + recent_attention,
        'failed_24h': int(result.failed_24h or 0),
        'completed_24h': int(result.completed_24h or 0),
        'queues': int(result.queues or 0),
    }


def _queue_activity(cutoff: datetime) -> list[dict[str, Any]]:
    """Build queue activity with one grouped DB query plus one shared Celery snapshot."""
    active_condition = JobExecution.status.in_(_ACTIVE_STATUSES)
    active_attention_condition = JobExecution.status.in_(_ACTIVE_ATTENTION_STATUSES)
    recent_attention_condition = and_(
        JobExecution.status.in_(_RECENT_ATTENTION_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    )
    completed_condition = and_(
        JobExecution.status.in_(_TERMINAL_STATUSES),
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    )
    failed_condition = and_(
        JobExecution.status == 'failed',
        JobExecution.completed_at.isnot(None),
        JobExecution.completed_at >= cutoff,
    )
    aggregates = (
        db.session.query(
            JobExecution.queue_name.label('queue_name'),
            func.sum(case((active_condition, 1), else_=0)).label('active'),
            func.sum(case((JobExecution.status == 'queued', 1), else_=0)).label('queued'),
            func.sum(case((JobExecution.status == 'running', 1), else_=0)).label('running'),
            func.sum(case((active_attention_condition, 1), else_=0)).label('active_attention'),
            func.sum(case((recent_attention_condition, 1), else_=0)).label('recent_attention_24h'),
            func.sum(case((completed_condition, 1), else_=0)).label('completed_24h'),
            func.sum(case((failed_condition, 1), else_=0)).label('failed_24h'),
            func.max(JobExecution.updated_at).label('latest_activity'),
        )
        .group_by(JobExecution.queue_name)
        .order_by(JobExecution.queue_name.asc())
        .all()
    )
    topology = inspect_celery_topology() if aggregates else None
    rows: list[dict[str, Any]] = []
    for aggregate in aggregates:
        queue_name = str(aggregate.queue_name)
        active = int(aggregate.active or 0)
        active_attention = int(aggregate.active_attention or 0)
        recent_attention = int(aggregate.recent_attention_24h or 0)
        attention = active_attention + recent_attention
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
                'queued': int(aggregate.queued or 0),
                'running': int(aggregate.running or 0),
                'active_attention': active_attention,
                'recent_attention_24h': recent_attention,
                'attention': attention,
                'completed_24h': int(aggregate.completed_24h or 0),
                'failed_24h': int(aggregate.failed_24h or 0),
                'latest_activity': present_user_datetime(aggregate.latest_activity, empty='No activity'),
                'worker_readiness': readiness,
            }
        )
    return rows


def _registry_query(*, status: str, workload: str, queue: str, search: str):
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
    return query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc())


def _empty_pagination(per_page: int) -> dict[str, Any]:
    return {
        'page': 1,
        'per_page': per_page,
        'total_items': 0,
        'total_pages': 1,
        'start_item': 0,
        'end_item': 0,
        'has_prev': False,
        'has_next': False,
        'prev_page': 0,
        'next_page': 2,
        'pages': [1],
        'allowed_per_page': list(ALLOWED_PER_PAGE),
    }


def build_job_execution_status_context(*, tab: str = 'active') -> dict[str, Any]:
    """Return lightweight counters for the live Execution Overview poller."""
    selected_tab = tab if tab in _ALLOWED_TABS else _ALLOWED_TABS[0]
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    return {
        'job_stats': _execution_summary(cutoff),
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
) -> dict[str, Any]:
    """Build only the execution sub-workspace the operator is currently viewing."""
    selected_per_page = per_page if per_page in ALLOWED_PER_PAGE else ALLOWED_PER_PAGE[0]
    selected_page = max(page, 1)
    selected_tab = tab if tab in _ALLOWED_TABS else _ALLOWED_TABS[0]
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    job_stats = _execution_summary(cutoff)

    job_rows: list[dict[str, Any]] = []
    active_jobs: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    queue_options: list[str] = []
    pagination = _empty_pagination(selected_per_page)

    if selected_tab == 'active':
        active_jobs = [
            _row(job)
            for job in JobExecution.query.filter(JobExecution.status.in_(_ACTIVE_STATUSES))
            .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
            .limit(6)
            .all()
        ]
    elif selected_tab == 'registry':
        query = _registry_query(status=status, workload=workload, queue=queue, search=search)
        paged_jobs, pagination = paginate_query(
            query,
            page=selected_page,
            per_page=selected_per_page,
            allowed_per_page=ALLOWED_PER_PAGE,
        )
        job_rows = [_row(job) for job in paged_jobs]
        queue_options = [
            str(row[0])
            for row in JobExecution.query.with_entities(JobExecution.queue_name)
            .distinct()
            .order_by(JobExecution.queue_name.asc())
            .all()
        ]
    elif selected_tab == 'queues':
        queue_rows = _queue_activity(cutoff)

    return {
        'job_rows': job_rows,
        'active_job_rows': active_jobs,
        'active_job_overflow': max(job_stats['active'] - len(active_jobs), 0),
        'job_queue_rows': queue_rows,
        'job_stats': job_stats,
        'job_pagination': pagination,
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
