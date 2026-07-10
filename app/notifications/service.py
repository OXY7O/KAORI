from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db
from app.models.notification import Notification


_ALLOWED_STATUSES = {
    'success',
    'warning',
    'error',
    'info',
}


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

    notification = Notification(
        user_id=user_id,
        event_type=event_type,
        status=normalized_status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url,
        metadata_json=metadata,
    )

    db.session.add(notification)
    db.session.commit()

    return notification


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = 8,
) -> dict[str, Any]:
    unread_count = (
        Notification.query.filter(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .count()
    )

    notifications = (
        Notification.query.filter(
            Notification.user_id == user_id,
        )
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(limit)
        .all()
    )

    now = datetime.now(UTC)
    items: list[dict[str, Any]] = []

    for notification in notifications:
        created_at = notification.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        age_seconds = max(
            0,
            int((now - created_at).total_seconds()),
        )

        if age_seconds < 60:
            created_label = 'Just now'
        elif age_seconds < 3600:
            minutes = age_seconds // 60
            created_label = f'{minutes} min ago'
        elif age_seconds < 86400:
            hours = age_seconds // 3600
            created_label = f'{hours} hr ago'
        else:
            days = age_seconds // 86400
            created_label = f'{days} day ago' if days == 1 else f'{days} days ago'

        metadata = notification.metadata_json or {}

        items.append(
            {
                'id': notification.id,
                'status': notification.status,
                'title': notification.title,
                'message': notification.message,
                'detail': notification.detail,
                'action_url': notification.action_url,
                'created_label': created_label,
                'is_read': notification.is_read,
                'synced_count': metadata.get('synced_count'),
                'failed_count': metadata.get('failed_count'),
                'total_count': metadata.get('total_count'),
                'duration_seconds': metadata.get('duration_seconds'),
            }
        )

    return {
        'items': items,
        'unread_count': unread_count,
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
