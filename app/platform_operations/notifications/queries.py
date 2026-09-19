from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    case,
    func,
    or_,
)
from sqlalchemy.orm import joinedload

from app.common.celery_queue_health import get_queue_readiness, inspect_celery_topology
from app.common.job_execution_presentation import present_job_execution
from app.extensions.db import db
from app.models.job import JobExecution, JobExecutionSubscriber
from app.models.notification import Notification
from app.platform_operations.notifications.constants import (
    ACTIVITY_CENTER_ACTIVE_JOB_STATUSES,
    ACTIVITY_CENTER_ATTENTION_STATUSES,
    ACTIVITY_CENTER_JOB_LIMIT,
    ACTIVITY_CENTER_NOTIFICATION_LIMIT,
    ACTIVITY_PER_PAGE_OPTIONS,
    ALLOWED_STATUSES,
    NAVIGATION_NOTIFICATION_LIMIT,
    WORK_INBOX_EVENT_TYPES,
)
from app.platform_operations.notifications.event_catalog import (
    CATEGORY_LABELS,
    activity_category_keys,
    notification_center_category_keys,
)
from app.platform_operations.notifications.presentation import _serialize_notification

_CENTER_CATEGORY_ORDER = notification_center_category_keys()
_AUDIT_CATEGORY_ORDER = activity_category_keys()
_ACTIVITY_TIME_RANGES = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '90d': timedelta(days=90),
    'all': None,
}


def _activity_cutoff(time_range: str) -> datetime | None:
    delta = _ACTIVITY_TIME_RANGES.get(time_range)
    if delta is None:
        return None
    return datetime.now(UTC) - delta


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = NAVIGATION_NOTIFICATION_LIMIT,
    include_all_jobs: bool = False,
) -> dict[str, Any]:
    return get_activity_center_context(
        user_id=user_id,
        job_limit=ACTIVITY_CENTER_JOB_LIMIT,
        notification_limit=limit,
        include_all_jobs=include_all_jobs,
    )


def _user_notification_query(user_id: int):
    return Notification.query.filter(
        Notification.user_id == user_id,
        Notification.event_type != 'authentication',
        Notification.deck_visible.is_(True),
    )


def _general_notification_query(user_id: int):
    return _user_notification_query(user_id).filter(
        Notification.event_type.notin_(WORK_INBOX_EVENT_TYPES),
    )


def _work_inbox_query(user_id: int):
    return _user_notification_query(user_id).filter(
        Notification.event_type.in_(WORK_INBOX_EVENT_TYPES),
    )


def _user_job_query(user_id: int):
    return JobExecution.query.filter(
        or_(
            JobExecution.requested_by_user_id == user_id,
            JobExecution.subscribers.any(
                JobExecutionSubscriber.user_id == user_id,
            ),
        )
    )


def get_activity_center_context(
    *,
    user_id: int,
    job_limit: int = ACTIVITY_CENTER_JOB_LIMIT,
    notification_limit: int = ACTIVITY_CENTER_NOTIFICATION_LIMIT,
    include_all_jobs: bool = False,
) -> dict[str, Any]:
    """Return one synchronized source for the top drawer and notification page."""

    normalized_job_limit = max(1, min(job_limit, 50))
    normalized_notification_limit = max(
        1,
        min(notification_limit, 50),
    )
    base_query = _general_notification_query(user_id)
    inbox_query = _work_inbox_query(user_id)
    unread_count = base_query.filter(
        Notification.read_at.is_(None),
    ).count()
    inbox_unread_count = inbox_query.filter(
        Notification.read_at.is_(None),
    ).count()
    total_count = base_query.count()
    inbox_total_count = inbox_query.count()

    history_notifications = (
        base_query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(normalized_notification_limit)
        .all()
    )
    inbox_notifications = (
        inbox_query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(normalized_notification_limit)
        .all()
    )

    attention_query = base_query.filter(
        Notification.status.in_(ACTIVITY_CENTER_ATTENTION_STATUSES),
        Notification.read_at.is_(None),
    )
    attention_count = attention_query.count()
    attention_notifications = (
        attention_query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(normalized_notification_limit)
        .all()
    )

    active_query = (JobExecution.query if include_all_jobs else _user_job_query(user_id)).filter(
        JobExecution.status.in_(ACTIVITY_CENTER_ACTIVE_JOB_STATUSES),
    )
    active_count = active_query.count()
    active_jobs = (
        active_query.options(joinedload(JobExecution.requested_by))
        .order_by(
            JobExecution.updated_at.desc(),
            JobExecution.id.desc(),
        )
        .limit(normalized_job_limit)
        .all()
    )

    history_items = [
        _serialize_notification(
            notification,
            include_metadata=False,
        )
        for notification in history_notifications
    ]
    attention_items = [
        _serialize_notification(
            notification,
            include_metadata=False,
        )
        for notification in attention_notifications
    ]
    inbox_items = [
        _serialize_notification(
            notification,
            include_metadata=False,
        )
        for notification in inbox_notifications
    ]

    presented_jobs = [present_job_execution(job) for job in active_jobs]
    queued_jobs = [job for job in presented_jobs if job['status'] == 'queued']
    if queued_jobs:
        topology = inspect_celery_topology()
        queue_health = {
            queue_name: get_queue_readiness(queue_name, topology=topology)
            for queue_name in {str(job['queue_name']) for job in queued_jobs}
        }
        for job in queued_jobs:
            job['queue_health'] = queue_health[str(job['queue_name'])]

    return {
        'items': history_items,
        'history_items': history_items,
        'attention_items': attention_items,
        'inbox_items': inbox_items,
        'active_jobs': presented_jobs,
        'active_count': active_count,
        'attention_count': attention_count,
        'unread_count': unread_count,
        'inbox_unread_count': inbox_unread_count,
        'inbox_total_count': inbox_total_count,
        'total_count': total_count,
        'display_limit': normalized_notification_limit,
        'job_display_limit': normalized_job_limit,
    }


def get_notification_center_page_context(
    *,
    user_id: int,
    page: int,
    per_page: int,
    job_limit: int = ACTIVITY_CENTER_JOB_LIMIT,
    include_all_jobs: bool = False,
    status: str = 'all',
    read_state: str = 'all',
    category: str = 'all',
    search: str = '',
) -> dict[str, Any]:
    """Return the full Notification Center page with standard filters and pagination."""

    base_context = get_activity_center_context(
        user_id=user_id,
        job_limit=job_limit,
        notification_limit=1,
        include_all_jobs=include_all_jobs,
    )
    normalized_page = max(page, 1)
    normalized_per_page = per_page if per_page in ACTIVITY_PER_PAGE_OPTIONS else ACTIVITY_PER_PAGE_OPTIONS[0]
    normalized_status = status if status in ALLOWED_STATUSES else 'all'
    normalized_read_state = read_state if read_state in {'all', 'read', 'unread'} else 'all'
    normalized_category = category if category in _CENTER_CATEGORY_ORDER else 'all'
    normalized_search = search.strip()

    filtered_query = _user_notification_query(user_id)
    if normalized_status != 'all':
        filtered_query = filtered_query.filter(Notification.status == normalized_status)
    if normalized_read_state == 'read':
        filtered_query = filtered_query.filter(Notification.read_at.is_not(None))
    elif normalized_read_state == 'unread':
        filtered_query = filtered_query.filter(Notification.read_at.is_(None))
    if normalized_category != 'all':
        filtered_query = filtered_query.filter(Notification.category_key == normalized_category)
    if normalized_search:
        pattern = f'%{normalized_search}%'
        filtered_query = filtered_query.filter(
            or_(
                Notification.title.ilike(pattern),
                Notification.message.ilike(pattern),
                Notification.detail.ilike(pattern),
                Notification.event_type.ilike(pattern),
            )
        )

    pagination = filtered_query.order_by(Notification.created_at.desc(), Notification.id.desc()).paginate(
        page=normalized_page, per_page=normalized_per_page, error_out=False
    )
    total = int(pagination.total or 0)
    base_context.update(
        {
            'history_items': [
                _serialize_notification(notification, include_metadata=False) for notification in pagination.items
            ],
            'items': [
                _serialize_notification(notification, include_metadata=False) for notification in pagination.items
            ],
            'notification_filters': {
                'status': normalized_status,
                'read_state': normalized_read_state,
                'category': normalized_category,
                'search': normalized_search,
            },
            'notification_category_options': [
                {'key': key, 'label': CATEGORY_LABELS[key]} for key in _CENTER_CATEGORY_ORDER
            ],
            'notification_pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': total,
                'pages': max(int(pagination.pages or 0), 1),
                'start_item': ((pagination.page - 1) * pagination.per_page + 1) if total else 0,
                'end_item': min(pagination.page * pagination.per_page, total),
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next,
                'prev_num': pagination.prev_num,
                'next_num': pagination.next_num,
                'allowed_per_page': ACTIVITY_PER_PAGE_OPTIONS,
            },
        }
    )
    return base_context


def _normalize_actor_filter(actor_key: str | None) -> str | None:
    normalized = str(actor_key or '').strip()
    return normalized or None


def get_notification_activity_summary() -> dict[str, int | str]:
    """Return recent evidence volume without treating evidence outcomes as workspace health."""

    cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
    events_24h, success_24h, attention_24h, actors_24h = (
        db.session.query(
            func.count(Notification.id),
            func.coalesce(func.sum(case((Notification.status == 'success', 1), else_=0)), 0),
            func.coalesce(func.sum(case((Notification.status.in_(['warning', 'error']), 1), else_=0)), 0),
            func.count(func.distinct(Notification.actor_key)),
        )
        .filter(Notification.created_at >= cutoff_24h)
        .one()
    )
    events = int(events_24h or 0)
    attention = int(attention_24h or 0)
    return {
        'events_24h': events,
        'success_24h': int(success_24h or 0),
        'attention_24h': attention,
        'actors_24h': int(actors_24h or 0),
        'posture_label': 'Available',
        'posture_tone': 'normal',
        'evidence_label': 'Evidence Recorded' if events else 'No Recent Evidence',
        'attention_label': 'Attention Recorded' if attention else 'No Attention Recorded',
    }


def get_notification_activity_context(
    *,
    actor_key: str | None,
    page: int,
    per_page: int,
    status: str,
    category: str,
    time_range: str,
    search: str,
    include_summary: bool = True,
) -> dict[str, Any]:
    normalized_page = max(page, 1)
    normalized_per_page = per_page if per_page in ACTIVITY_PER_PAGE_OPTIONS else ACTIVITY_PER_PAGE_OPTIONS[0]
    normalized_status = status if status in ALLOWED_STATUSES else 'all'
    normalized_category = category if category in _AUDIT_CATEGORY_ORDER else 'all'
    normalized_time_range = time_range if time_range in _ACTIVITY_TIME_RANGES else '7d'
    normalized_search = search.strip()
    normalized_actor_key = _normalize_actor_filter(actor_key)

    filtered_query = Notification.query

    if normalized_actor_key is not None:
        filtered_query = filtered_query.filter(Notification.actor_key == normalized_actor_key)

    if normalized_status != 'all':
        filtered_query = filtered_query.filter(Notification.status == normalized_status)

    if normalized_category != 'all':
        filtered_query = filtered_query.filter(Notification.category_key == normalized_category)

    cutoff = _activity_cutoff(normalized_time_range)
    if cutoff is not None:
        filtered_query = filtered_query.filter(Notification.created_at >= cutoff)

    if normalized_search:
        pattern = f'%{normalized_search}%'
        filtered_query = filtered_query.filter(
            or_(
                Notification.title.ilike(pattern),
                Notification.message.ilike(pattern),
                Notification.detail.ilike(pattern),
                Notification.event_type.ilike(pattern),
                Notification.actor_label.ilike(pattern),
            )
        )

    pagination = filtered_query.order_by(
        Notification.created_at.desc(),
        Notification.id.desc(),
    ).paginate(
        page=normalized_page,
        per_page=normalized_per_page,
        error_out=False,
    )

    actor_rows = (
        db.session.query(
            Notification.actor_key,
            func.max(Notification.actor_label).label('actor_label'),
        )
        .filter(Notification.actor_key.is_not(None), Notification.actor_label.is_not(None))
        .group_by(Notification.actor_key)
        .order_by(func.max(Notification.actor_label).asc(), Notification.actor_key.asc())
        .all()
    )
    pagination_total = int(pagination.total or 0)

    context: dict[str, Any] = {
        'items': [
            _serialize_notification(
                notification,
                include_metadata=False,
            )
            for notification in pagination.items
        ],
        'filters': {
            'actor_key': normalized_actor_key,
            'status': normalized_status,
            'category': normalized_category,
            'time_range': normalized_time_range,
            'search': normalized_search,
        },
        'actor_options': [
            {
                'key': str(row.actor_key),
                'label': str(row.actor_label),
            }
            for row in actor_rows
        ],
        'category_options': [{'key': key, 'label': CATEGORY_LABELS[key]} for key in _AUDIT_CATEGORY_ORDER],
        'time_range_options': [
            ('24h', '24 Hours'),
            ('7d', '7 Days'),
            ('30d', '30 Days'),
            ('90d', '90 Days'),
            ('all', 'All Hot Records'),
        ],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination_total,
            'pages': max(int(pagination.pages or 0), 1),
            'start_item': ((pagination.page - 1) * pagination.per_page + 1) if pagination_total else 0,
            'end_item': min(pagination.page * pagination.per_page, pagination_total),
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num,
            'allowed_per_page': ACTIVITY_PER_PAGE_OPTIONS,
        },
    }

    if include_summary:
        context['summary'] = get_notification_activity_summary()

    return context


def get_notification_activity_detail(*, notification_id: int) -> dict[str, Any] | None:
    notification = Notification.query.filter(Notification.id == notification_id).first()
    if notification is None:
        return None

    return _serialize_notification(notification, include_metadata=True)


def mark_notification_read(
    *,
    notification_id: int,
    user_id: int,
) -> None:
    notification = Notification.query.filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
        Notification.deck_visible.is_(True),
    ).first()

    if notification is None or notification.read_at is not None:
        return

    notification.read_at = datetime.now(UTC)
    db.session.commit()


def mark_all_notifications_read(
    *,
    user_id: int,
    scope: str = 'all',
) -> None:
    now = datetime.now(UTC)
    query = Notification.query.filter(
        Notification.user_id == user_id,
        Notification.deck_visible.is_(True),
        Notification.read_at.is_(None),
    )
    normalized_scope = str(scope or 'all').strip().lower()
    if normalized_scope == 'inbox':
        query = query.filter(Notification.event_type.in_(WORK_INBOX_EVENT_TYPES))
    elif normalized_scope == 'notifications':
        query = query.filter(Notification.event_type.notin_(WORK_INBOX_EVENT_TYPES))

    query.update(
        {
            Notification.read_at: now,
        },
        synchronize_session=False,
    )

    db.session.commit()
