from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_

from app.extensions.db import db
from app.models.notification import Notification
from app.models.user import User
from app.notifications.constants import ACTIVITY_PER_PAGE_OPTIONS, ALLOWED_STATUSES, NAVIGATION_NOTIFICATION_LIMIT
from app.notifications.event_catalog import event_label
from app.notifications.presentation import _serialize_notification, _user_label


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = NAVIGATION_NOTIFICATION_LIMIT,
) -> dict[str, Any]:
    normalized_limit = max(1, min(limit, NAVIGATION_NOTIFICATION_LIMIT))
    base_query = Notification.query.filter(
        Notification.user_id == user_id,
        Notification.event_type != 'authentication',
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
    normalized_per_page = per_page if per_page in ACTIVITY_PER_PAGE_OPTIONS else ACTIVITY_PER_PAGE_OPTIONS[0]
    normalized_status = status if status in ALLOWED_STATUSES else 'all'
    normalized_event_type = event_type.strip() or 'all'
    normalized_read_state = read_state if read_state in {'all', 'read', 'unread'} else 'all'
    normalized_search = search.strip()
    normalized_user_id = _normalize_user_filter(user_id)

    filtered_query = Notification.query.outerjoin(
        User,
        User.id == Notification.user_id,
    )

    if normalized_user_id is not None:
        filtered_query = filtered_query.filter(
            Notification.user_id == normalized_user_id,
        )

    event_type_query = db.session.query(Notification.event_type).outerjoin(
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

    page_user_ids = {notification.user_id for notification in pagination.items if notification.user_id is not None}
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
                'label': event_label(value),
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
            'allowed_per_page': ACTIVITY_PER_PAGE_OPTIONS,
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
