from __future__ import annotations

import logging
from typing import Any

from app.extensions.db import db
from app.models.notification import Notification
from app.notifications.constants import ALLOWED_STATUSES, NAVIGATION_NOTIFICATION_LIMIT
from app.notifications.feedback import (
    build_quick_action_feedback,
)
from app.notifications.feedback import (
    pop_quick_action_feedback as _pop_quick_action_feedback,
)
from app.notifications.feedback import (
    queue_quick_action_feedback as _queue_quick_action_feedback,
)
from app.notifications.normalization import standardize_activity_text
from app.notifications.queries import (
    get_navigation_notification_context as _get_navigation_notification_context,
)
from app.notifications.queries import (
    get_notification_activity_context as _get_notification_activity_context,
)
from app.notifications.queries import (
    mark_all_notifications_read as _mark_all_notifications_read,
)
from app.notifications.queries import (
    mark_notification_read as _mark_notification_read,
)
from app.notifications.writer import persist_notification

logger = logging.getLogger(__name__)


def _normalize_notification_content(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None,
) -> tuple[str, str, str, str | None]:
    normalized_status = status if status in ALLOWED_STATUSES else 'info'
    normalized_title = (
        standardize_activity_text(
            title,
            event_type=event_type,
            status=normalized_status,
        )
        or 'Operational activity'
    )
    normalized_message = (
        standardize_activity_text(
            message,
            event_type=event_type,
            status=normalized_status,
        )
        or 'The operation was recorded by KAORI.'
    )
    normalized_detail = standardize_activity_text(
        detail,
        event_type=event_type,
        status=normalized_status,
    )
    return normalized_status, normalized_title, normalized_message, normalized_detail


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
    """Create one normalized notification through the domain service."""
    normalized_status, normalized_title, normalized_message, normalized_detail = _normalize_notification_content(
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
    )

    return persist_notification(
        user_id=user_id,
        event_type=event_type,
        status=normalized_status,
        title=normalized_title,
        message=normalized_message,
        detail=normalized_detail,
        action_url=action_url,
        metadata=metadata,
    )


def record_operational_activity(
    *,
    user_id: int,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'View details',
    action_icon: str = 'arrow-up-right',
    metadata: dict[str, Any] | None = None,
    queue_feedback: bool = False,
) -> dict[str, Any]:
    """Record an audit event and build its matching user feedback payload.

    Notification persistence is isolated from the primary operation. A storage
    failure is logged and retried, but it does not turn the originating operation
    into a user-visible failure.
    """
    normalized_status, normalized_title, normalized_message, normalized_detail = _normalize_notification_content(
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
    )

    notification_saved = True
    try:
        persist_notification(
            user_id=user_id,
            event_type=event_type,
            status=normalized_status,
            title=normalized_title,
            message=normalized_message,
            detail=normalized_detail,
            action_url=action_url,
            metadata=metadata,
        )
    except Exception:
        db.session.rollback()
        logger.exception(
            'Initial notification persistence failed for event %s; retrying after rollback.',
            event_type,
        )
        try:
            persist_notification(
                user_id=user_id,
                event_type=event_type,
                status=normalized_status,
                title=normalized_title,
                message=normalized_message,
                detail=normalized_detail,
                action_url=action_url,
                metadata=metadata,
            )
        except Exception:
            db.session.rollback()
            notification_saved = False
            logger.exception(
                'Could not persist operational notification for event %s.',
                event_type,
            )

    feedback = build_quick_action_feedback(
        status=normalized_status,
        title=normalized_title,
        message=normalized_message,
        detail=normalized_detail,
        action_url=action_url,
        action_label=action_label,
        action_icon=action_icon,
        notification_saved=notification_saved,
    )

    if queue_feedback:
        _queue_quick_action_feedback(feedback)

    return feedback


def queue_transient_feedback(
    *,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'View details',
    action_icon: str = 'arrow-up-right',
) -> dict[str, Any]:
    """Queue one non-persistent operational toast for the next rendered response.

    Use this for validation, navigation, or read-only failures that should not
    create an Activity Audit record. Mutating operations should use
    ``record_operational_activity`` instead.
    """
    normalized_status, normalized_title, normalized_message, normalized_detail = _normalize_notification_content(
        event_type='operational_feedback',
        status=status,
        title=title,
        message=message,
        detail=detail,
    )
    feedback = build_quick_action_feedback(
        status=normalized_status,
        title=normalized_title,
        message=normalized_message,
        detail=normalized_detail,
        action_url=action_url,
        action_label=action_label,
        action_icon=action_icon,
        notification_saved=False,
    )
    _queue_quick_action_feedback(feedback)
    return feedback


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = NAVIGATION_NOTIFICATION_LIMIT,
) -> dict[str, Any]:
    """Build the notification-center context for one user."""
    return _get_navigation_notification_context(user_id=user_id, limit=limit)


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
    """Build the filtered administrative activity-audit context."""
    return _get_notification_activity_context(
        user_id=user_id,
        page=page,
        per_page=per_page,
        status=status,
        event_type=event_type,
        read_state=read_state,
        search=search,
    )


def mark_notification_read(*, notification_id: int, user_id: int) -> None:
    _mark_notification_read(notification_id=notification_id, user_id=user_id)


def mark_all_notifications_read(*, user_id: int) -> None:
    _mark_all_notifications_read(user_id=user_id)


def queue_quick_action_feedback(feedback: dict[str, Any]) -> None:
    _queue_quick_action_feedback(feedback)


def pop_quick_action_feedback() -> dict[str, Any] | None:
    return _pop_quick_action_feedback()
