"""Public notification-domain API.

This compatibility facade keeps existing imports stable while implementation details
are split into focused modules for writing, querying, presentation, normalization,
and request feedback. New code should import from this module unless it is extending
a specific internal notification concern.
"""

from app.notifications.feedback import (
    build_quick_action_feedback,
    pop_quick_action_feedback,
    queue_quick_action_feedback,
)
from app.notifications.queries import (
    get_navigation_notification_context,
    get_notification_activity_context,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.notifications.writer import create_notification, record_operational_activity

__all__ = [
    'build_quick_action_feedback',
    'create_notification',
    'get_navigation_notification_context',
    'get_notification_activity_context',
    'mark_all_notifications_read',
    'mark_notification_read',
    'pop_quick_action_feedback',
    'queue_quick_action_feedback',
    'record_operational_activity',
]
