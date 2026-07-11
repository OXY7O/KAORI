from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User

_ALLOWED_STATUSES = {
    'success',
    'warning',
    'error',
    'info',
}
_NAVIGATION_NOTIFICATION_LIMIT = 8
_ACTIVITY_PER_PAGE_OPTIONS = (5, 10, 25, 50)


def create_notification(
    *,
    user_id: int,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Notification:
    normalized_status = status if status in _ALLOWED_STATUSES else 'info'

    notification = Notification()
    notification.user_id = user_id
    notification.event_type = event_type
    notification.status = normalized_status
    notification.title = title
    notification.message = message
    notification.detail = detail
    notification.action_url = action_url
    notification.metadata_json = metadata

    db.session.add(notification)
    db.session.commit()

    return notification


def _normalize_created_at(created_at: datetime) -> datetime:
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=UTC)

    return created_at.astimezone(UTC)


def _created_label(created_at: datetime) -> str:
    normalized_created_at = _normalize_created_at(created_at)
    age_seconds = max(
        0,
        int((datetime.now(UTC) - normalized_created_at).total_seconds()),
    )

    if age_seconds < 60:
        return 'Just now'
    if age_seconds < 3600:
        minutes = age_seconds // 60
        return f'{minutes} min ago'
    if age_seconds < 86400:
        hours = age_seconds // 3600
        return f'{hours} hr ago'

    days = age_seconds // 86400
    return f'{days} day ago' if days == 1 else f'{days} days ago'


def _event_label(event_type: str) -> str:
    return event_type.replace('_', ' ').strip().title() or 'Operational Activity'


def _metadata_value(value: Any) -> str:
    if isinstance(value, list):
        return ', '.join(str(item) for item in value) if value else '-'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if value is None:
        return '-'
    return str(value)


def _metadata_items(metadata: dict[str, Any]) -> list[dict[str, str]]:
    preferred_order = (
        'task_id',
        'total_count',
        'synced_count',
        'failed_count',
        'failed_clusters',
        'duration_seconds',
    )
    keys = [key for key in preferred_order if key in metadata]
    keys.extend(sorted(key for key in metadata if key not in preferred_order))

    return [
        {
            'label': key.replace('_', ' ').title(),
            'value': _metadata_value(metadata[key]),
        }
        for key in keys
    ]


def _user_label(user: User | None, user_id: int) -> str:
    if user is None:
        return f'User #{user_id}'

    suffix = ' · Deleted' if user.deleted_at is not None else ''
    return f'{user.display_label}{suffix}'


def _serialize_notification(
    notification: Notification,
    *,
    include_metadata: bool,
    user: User | None = None,
) -> dict[str, Any]:
    metadata = notification.metadata_json or {}
    created_at = _normalize_created_at(notification.created_at)

    item: dict[str, Any] = {
        'id': notification.id,
        'user_id': notification.user_id,
        'user_label': _user_label(user, notification.user_id),
        'user_email': user.email if user is not None else None,
        'event_type': notification.event_type,
        'event_label': _event_label(notification.event_type),
        'status': notification.status,
        'title': notification.title,
        'message': notification.message,
        'detail': notification.detail,
        'action_url': notification.action_url,
        'created_at': created_at,
        'created_label': _created_label(created_at),
        'is_read': notification.is_read,
        'read_label': 'Read' if notification.is_read else 'Unread',
        'synced_count': metadata.get('synced_count'),
        'failed_count': metadata.get('failed_count'),
        'total_count': metadata.get('total_count'),
        'duration_seconds': metadata.get('duration_seconds'),
    }

    if include_metadata:
        item['metadata_items'] = _metadata_items(metadata)

    return item


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = _NAVIGATION_NOTIFICATION_LIMIT,
) -> dict[str, Any]:
    normalized_limit = max(1, min(limit, _NAVIGATION_NOTIFICATION_LIMIT))
    base_query = Notification.query.filter(
        Notification.user_id == user_id,
    )
    unread_count = base_query.filter(
        Notification.read_at.is_(None),
    ).count()
    total_count = base_query.count()

    notifications = (
        base_query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(normalized_limit)
        .all()
    )

    return {
        'items': [
            _serialize_notification(
                notification,
                include_metadata=False,
            )
            for notification in notifications
        ],
        'unread_count': unread_count,
        'total_count': total_count,
        'display_limit': normalized_limit,
    }


def _normalize_user_filter(user_id: int | None) -> int | None:
    if user_id is None or user_id <= 0:
        return None
    return user_id


def get_notification_activity_context(
    *,
    user_id: int | None,
    page: int,
    per_page: int,
    status: str,
    event_type: str,
    read_state: str,
    search: str,
) -> dict[str, Any]:
    normalized_page = max(page, 1)
    normalized_per_page = per_page if per_page in _ACTIVITY_PER_PAGE_OPTIONS else _ACTIVITY_PER_PAGE_OPTIONS[0]
    normalized_status = status if status in _ALLOWED_STATUSES else 'all'
    normalized_event_type = event_type.strip() or 'all'
    normalized_read_state = read_state if read_state in {'all', 'read', 'unread'} else 'all'
    normalized_search = search.strip()
    normalized_user_id = _normalize_user_filter(user_id)

    filtered_query = Notification.query.join(
        User,
        User.id == Notification.user_id,
    )

    if normalized_user_id is not None:
        filtered_query = filtered_query.filter(
            Notification.user_id == normalized_user_id,
        )

    event_type_query = db.session.query(Notification.event_type).join(
        User,
        User.id == Notification.user_id,
    )
    if normalized_user_id is not None:
        event_type_query = event_type_query.filter(
            Notification.user_id == normalized_user_id,
        )

    if normalized_status != 'all':
        filtered_query = filtered_query.filter(
            Notification.status == normalized_status,
        )

    if normalized_event_type != 'all':
        filtered_query = filtered_query.filter(
            Notification.event_type == normalized_event_type,
        )

    if normalized_read_state == 'read':
        filtered_query = filtered_query.filter(
            Notification.read_at.is_not(None),
        )
    elif normalized_read_state == 'unread':
        filtered_query = filtered_query.filter(
            Notification.read_at.is_(None),
        )

    if normalized_search:
        pattern = f'%{normalized_search}%'
        filtered_query = filtered_query.filter(
            or_(
                Notification.title.ilike(pattern),
                Notification.message.ilike(pattern),
                Notification.detail.ilike(pattern),
                Notification.event_type.ilike(pattern),
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.display_name.ilike(pattern),
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

    page_user_ids = {notification.user_id for notification in pagination.items}
    page_users = User.query.filter(User.id.in_(page_user_ids)).all() if page_user_ids else []
    users_by_id = {user.id: user for user in page_users}

    event_types = [row[0] for row in (event_type_query.distinct().order_by(Notification.event_type.asc()).all())]

    all_notifications_query = Notification.query
    total_count = all_notifications_query.count()
    unread_count = all_notifications_query.filter(
        Notification.read_at.is_(None),
    ).count()
    success_count = all_notifications_query.filter(
        Notification.status == 'success',
    ).count()
    attention_count = all_notifications_query.filter(
        Notification.status.in_(['warning', 'error']),
    ).count()
    pagination_total = int(pagination.total or 0)
    pagination_pages = max(int(pagination.pages or 0), 1)

    user_options = User.query.order_by(
        User.username.asc(),
        User.id.asc(),
    ).all()

    return {
        'items': [
            _serialize_notification(
                notification,
                include_metadata=True,
                user=users_by_id.get(notification.user_id),
            )
            for notification in pagination.items
        ],
        'summary': {
            'total_count': total_count,
            'unread_count': unread_count,
            'success_count': success_count,
            'attention_count': attention_count,
        },
        'filters': {
            'user_id': normalized_user_id,
            'status': normalized_status,
            'event_type': normalized_event_type,
            'read_state': normalized_read_state,
            'search': normalized_search,
        },
        'user_options': [
            {
                'id': user.id,
                'label': _user_label(user, user.id),
                'email': user.email,
            }
            for user in user_options
        ],
        'event_types': [
            {
                'value': value,
                'label': _event_label(value),
            }
            for value in event_types
        ],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total_items': pagination_total,
            'total_pages': pagination_pages,
            'start_item': ((pagination.page - 1) * pagination.per_page + 1) if pagination_total else 0,
            'end_item': min(pagination.page * pagination.per_page, pagination_total),
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_page': pagination.prev_num,
            'next_page': pagination.next_num,
            'allowed_per_page': _ACTIVITY_PER_PAGE_OPTIONS,
        },
    }


def mark_notification_read(
    *,
    notification_id: int,
    user_id: int,
) -> None:
    notification = Notification.query.filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()

    if notification is None or notification.read_at is not None:
        return

    notification.read_at = datetime.now(UTC)
    db.session.commit()


def mark_all_notifications_read(
    *,
    user_id: int,
) -> None:
    now = datetime.now(UTC)

    Notification.query.filter(
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    ).update(
        {
            Notification.read_at: now,
        },
        synchronize_session=False,
    )

    db.session.commit()
