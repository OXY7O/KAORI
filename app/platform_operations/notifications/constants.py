from __future__ import annotations

ALLOWED_STATUSES = frozenset(
    {
        'success',
        'warning',
        'error',
        'info',
    }
)
NAVIGATION_NOTIFICATION_LIMIT = 8
ACTIVITY_CENTER_JOB_LIMIT = 6
ACTIVITY_CENTER_NOTIFICATION_LIMIT = 8
ACTIVITY_CENTER_PAGE_LIMIT = 25
ACTIVITY_CENTER_ACTIVE_JOB_STATUSES = (
    'queued',
    'running',
    'retrying',
    'cancel_requested',
)
ACTIVITY_CENTER_ATTENTION_STATUSES = ('warning', 'error')
ACTIVITY_PER_PAGE_OPTIONS = (5, 10, 25, 50)
OPERATIONAL_FEEDBACK_SESSION_KEY = 'operational_feedback'
