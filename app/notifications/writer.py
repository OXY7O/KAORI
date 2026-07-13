from __future__ import annotations

import logging
from typing import Any

from app.extensions import db
from app.models.notification import Notification
from app.notifications.constants import ALLOWED_STATUSES
from app.notifications.feedback import build_quick_action_feedback, queue_quick_action_feedback
from app.notifications.normalization import standardize_activity_text

logger = logging.getLogger(__name__)

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
    normalized_status = status if status in ALLOWED_STATUSES else 'info'

    notification = Notification()
    notification.user_id = user_id
    notification.event_type = event_type
    notification.status = normalized_status
    notification.title = standardize_activity_text(
        title,
        event_type=event_type,
        status=normalized_status,
    ) or 'Operational activity'
    notification.message = standardize_activity_text(
        message,
        event_type=event_type,
        status=normalized_status,
    ) or 'The operation was recorded by KAORI.'
    notification.detail = standardize_activity_text(
        detail,
        event_type=event_type,
        status=normalized_status,
    )
    notification.action_url = action_url
    notification.metadata_json = metadata

    db.session.add(notification)
    db.session.commit()

    return notification



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
    """Save an activity record and return the matching top-right toast context.

    Notification persistence is deliberately isolated from the primary operation.
    A notification storage failure must not turn a successful cluster or integration
    change into a failed user action.
    """
    notification_saved = True
    normalized_status = status if status in ALLOWED_STATUSES else 'info'
    normalized_title = standardize_activity_text(
        title,
        event_type=event_type,
        status=normalized_status,
    ) or 'Operational activity'
    normalized_message = standardize_activity_text(
        message,
        event_type=event_type,
        status=normalized_status,
    ) or 'The operation was recorded by KAORI.'
    normalized_detail = standardize_activity_text(
        detail,
        event_type=event_type,
        status=normalized_status,
    )

    try:
        create_notification(
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
            create_notification(
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
        queue_quick_action_feedback(
            feedback,
        )

    return feedback


