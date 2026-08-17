from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4

from flask import has_request_context, session

from app.platform_operations.notifications.constants import ALLOWED_STATUSES, OPERATIONAL_FEEDBACK_SESSION_KEY


class OperationalDeliveryPolicy(StrEnum):
    """Control Activity Audit persistence and Notification Deck visibility."""

    AUDIT_ONLY = 'audit_only'
    DECK_ON_FAILURE = 'deck_on_failure'
    PERSISTENT = 'persistent'

    @classmethod
    def normalize(cls, value: OperationalDeliveryPolicy | str) -> OperationalDeliveryPolicy:
        try:
            return cls(str(value))
        except ValueError:
            return cls.PERSISTENT

    def deck_visible(self, status: str) -> bool:
        if self is self.PERSISTENT:
            return True
        if self is self.DECK_ON_FAILURE:
            return status in {'warning', 'error'}
        return False


@dataclass(frozen=True)
class OperationalFeedbackSpec:
    status: str
    title: str
    message: str
    detail: str | None = None
    action_url: str | None = None
    action_label: str = 'View details'
    action_icon: str = 'arrow-up-right'
    completed_label: str = 'Completed just now'
    activity_audit_saved: bool = True
    activity_audit_expected: bool = True
    notification_deck_visible: bool = False
    delivery: str = 'toast'
    delivery_policy: OperationalDeliveryPolicy | str = OperationalDeliveryPolicy.PERSISTENT
    feedback_id: str | None = None
    auto_dismiss_ms: int | None = None


def build_operational_feedback(spec: OperationalFeedbackSpec) -> dict[str, Any]:
    """Build one canonical top-right operational result payload."""
    normalized_status = spec.status if spec.status in ALLOWED_STATUSES else 'info'
    auto_dismiss_ms = spec.auto_dismiss_ms
    if auto_dismiss_ms is None:
        auto_dismiss_ms = {
            'success': 8000,
            'info': 10000,
            'warning': 12000,
            'error': 0,
        }.get(normalized_status, 10000)
    policy = OperationalDeliveryPolicy.normalize(spec.delivery_policy)
    return {
        'feedback_id': spec.feedback_id or f'feedback-{uuid4().hex}',
        'status': normalized_status,
        'title': spec.title,
        'message': spec.message,
        'detail': spec.detail,
        'view_url': spec.action_url,
        'action_label': spec.action_label,
        'action_icon': spec.action_icon,
        'completed_label': spec.completed_label,
        'activity_audit_saved': spec.activity_audit_saved,
        'activity_audit_expected': spec.activity_audit_expected,
        'notification_deck_visible': spec.notification_deck_visible,
        'delivery': spec.delivery if spec.delivery in {'toast', 'activity_center'} else 'toast',
        'delivery_policy': policy.value,
        'auto_dismiss_ms': max(0, int(auto_dismiss_ms)),
    }


def queue_operational_feedback(feedback: dict[str, Any]) -> None:
    """Persist one operational result across a normal redirect."""
    if not has_request_context():
        return

    session[OPERATIONAL_FEEDBACK_SESSION_KEY] = feedback
    session.modified = True


def pop_operational_feedback() -> dict[str, Any] | None:
    """Return and clear the pending redirect result for the current request."""
    if not has_request_context():
        return None

    feedback = session.pop(OPERATIONAL_FEEDBACK_SESSION_KEY, None)
    if feedback is not None:
        session.modified = True

    return feedback
