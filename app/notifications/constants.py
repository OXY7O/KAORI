from __future__ import annotations

ALLOWED_STATUSES = frozenset({
    'success',
    'warning',
    'error',
    'info',
})
NAVIGATION_NOTIFICATION_LIMIT = 8
ACTIVITY_PER_PAGE_OPTIONS = (5, 10, 25, 50)
QUICK_ACTION_FEEDBACK_SESSION_KEY = 'quick_action_feedback'
