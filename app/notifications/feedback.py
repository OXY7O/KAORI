from __future__ import annotations

from typing import Any

from flask import has_request_context, session

from app.notifications.constants import ALLOWED_STATUSES, QUICK_ACTION_FEEDBACK_SESSION_KEY

def build_quick_action_feedback(
    *,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'View details',
    action_icon: str = 'arrow-up-right',
    completed_label: str = 'Completed just now',
    notification_saved: bool = True,
) -> dict[str, Any]:
    """Build the shared top-right operational result payload."""
    return {
        'status': status if status in ALLOWED_STATUSES else 'info',
        'title': title,
        'message': message,
        'detail': detail,
        'view_url': action_url,
        'action_label': action_label,
        'action_icon': action_icon,
        'completed_label': completed_label,
        'notification_saved': notification_saved,
    }


def queue_quick_action_feedback(feedback: dict[str, Any]) -> None:
    """Persist one operational result across a normal redirect."""
    if not has_request_context():
        return

    session[QUICK_ACTION_FEEDBACK_SESSION_KEY] = feedback
    session.modified = True


def pop_quick_action_feedback() -> dict[str, Any] | None:
    """Return and clear the pending redirect result for the current request."""
    if not has_request_context():
        return None

    feedback = session.pop(
        QUICK_ACTION_FEEDBACK_SESSION_KEY,
        None,
    )
    if feedback is not None:
        session.modified = True

    return feedback


