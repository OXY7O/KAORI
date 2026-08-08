from __future__ import annotations

import logging
from typing import Any

from app.extensions.db import db
from app.models.notification import Notification
from app.notifications.constants import (
    ACTIVITY_CENTER_JOB_LIMIT,
    ACTIVITY_CENTER_NOTIFICATION_LIMIT,
    ALLOWED_STATUSES,
    NAVIGATION_NOTIFICATION_LIMIT,
)
from app.notifications.feedback import (
    OperationalDeliveryPolicy,
    OperationalFeedbackSpec,
    build_operational_feedback,
    queue_operational_feedback,
)
from app.notifications.normalization import standardize_activity_text, standardize_activity_title
from app.notifications.queries import (
    get_activity_center_context as _get_activity_center_context,
)
from app.notifications.queries import (
    get_navigation_notification_context as _get_navigation_notification_context,
)
from app.notifications.queries import (
    get_notification_activity_context as _get_notification_activity_context,
)
from app.notifications.queries import (
    get_notification_center_page_context as _get_notification_center_page_context,
)
from app.notifications.queries import (
    mark_all_notifications_read as _mark_all_notifications_read,
)
from app.notifications.queries import (
    mark_notification_read as _mark_notification_read,
)
from app.notifications.writer import persist_notification

logger = logging.getLogger(__name__)

_BACKGROUND_EVENT_HINTS = (
    'queued',
    'already_running',
    'sync',
    'materializ',
    'runtime_refresh',
    'validation',
    'schedule',
    'report_generation',
    'archive',
    'cleanup',
)


def _feedback_delivery(
    *,
    event_type: str,
    status: str,
    metadata: dict[str, Any] | None,
) -> str:
    """Keep background progress in the Activity Center instead of toast stacks."""

    normalized_event = event_type.strip().lower()
    event_metadata = metadata or {}
    explicit_delivery = str(
        event_metadata.get('feedback_delivery') or ''
    ).strip().lower()
    if explicit_delivery in {'toast', 'activity_center'}:
        return explicit_delivery

    has_job_reference = any(
        event_metadata.get(key)
        for key in (
            'task_id',
            'job_id',
            'job_execution_id',
            'celery_task_id',
        )
    )
    is_background_event = has_job_reference or any(
        hint in normalized_event for hint in _BACKGROUND_EVENT_HINTS
    )
    if is_background_event:
        return 'activity_center'

    return 'toast'


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
        standardize_activity_title(
            standardize_activity_text(
                title,
                event_type=event_type,
                status=normalized_status,
            )
        )
        or 'Operational Activity'
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
    deck_visible: bool = True,
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
        deck_visible=deck_visible,
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
    delivery_policy: OperationalDeliveryPolicy | str = OperationalDeliveryPolicy.PERSISTENT,
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

    policy = OperationalDeliveryPolicy.normalize(delivery_policy)
    deck_visible = policy.deck_visible(normalized_status)
    activity_audit_saved = True
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
            deck_visible=deck_visible,
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
                deck_visible=deck_visible,
            )
        except Exception:
            db.session.rollback()
            activity_audit_saved = False
            logger.exception(
                'Could not persist operational notification for event %s.',
                event_type,
            )

    feedback = build_operational_feedback(
        OperationalFeedbackSpec(
            status=normalized_status,
            title=normalized_title,
            message=normalized_message,
            detail=normalized_detail,
            action_url=action_url,
            action_label=action_label,
            action_icon=action_icon,
            activity_audit_saved=activity_audit_saved,
            notification_deck_visible=deck_visible and activity_audit_saved,
            delivery_policy=policy,
            delivery=_feedback_delivery(
                event_type=event_type,
                status=normalized_status,
                metadata=metadata,
            ),
        )
    )

    if queue_feedback:
        queue_operational_feedback(feedback)

    return feedback



def create_transient_feedback(
    *,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'View details',
    action_icon: str = 'arrow-up-right',
    queue_feedback: bool = False,
) -> dict[str, Any]:
    """Build immediate feedback without Activity Audit or Notification Deck persistence."""
    normalized_status, normalized_title, normalized_message, normalized_detail = _normalize_notification_content(
        event_type='operational_feedback',
        status=status,
        title=title,
        message=message,
        detail=detail,
    )
    feedback = build_operational_feedback(
        OperationalFeedbackSpec(
            status=normalized_status,
            title=normalized_title,
            message=normalized_message,
            detail=normalized_detail,
            action_url=action_url,
            action_label=action_label,
            action_icon=action_icon,
            activity_audit_saved=False,
            activity_audit_expected=False,
            notification_deck_visible=False,
            delivery='toast',
            delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
        )
    )
    if queue_feedback:
        queue_operational_feedback(feedback)
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
    """Queue one non-persistent operational toast for the next rendered response."""
    return create_transient_feedback(
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url,
        action_label=action_label,
        action_icon=action_icon,
        queue_feedback=True,
    )


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = NAVIGATION_NOTIFICATION_LIMIT,
    include_all_jobs: bool = False,
) -> dict[str, Any]:
    """Build the notification-center context for one user."""
    return _get_navigation_notification_context(
        user_id=user_id,
        limit=limit,
        include_all_jobs=include_all_jobs,
    )


def get_activity_center_context(
    *,
    user_id: int,
    job_limit: int = ACTIVITY_CENTER_JOB_LIMIT,
    notification_limit: int = ACTIVITY_CENTER_NOTIFICATION_LIMIT,
    include_all_jobs: bool = False,
) -> dict[str, Any]:
    """Build the shared Activity Center context for drawer and full page."""

    return _get_activity_center_context(
        user_id=user_id,
        job_limit=job_limit,
        notification_limit=notification_limit,
        include_all_jobs=include_all_jobs,
    )


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
    """Build the full filtered and paginated Notification Center page context."""

    return _get_notification_center_page_context(
        user_id=user_id,
        page=page,
        per_page=per_page,
        job_limit=job_limit,
        include_all_jobs=include_all_jobs,
        status=status,
        read_state=read_state,
        category=category,
        search=search,
    )


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
