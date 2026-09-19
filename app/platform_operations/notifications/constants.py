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

WORK_INBOX_EVENT_TYPES = frozenset(
    {
        'alert_case_assigned',
        'alert_case_acknowledgement_overdue',
        'alert_case_silence_expired',
        'alert_case_verification_required',
        'rule_exception_assigned',
        'rule_exception_expiring',
        'rule_exception_revoked',
    }
)
ACTIVITY_PER_PAGE_OPTIONS = (5, 10, 25, 50)
OPERATIONAL_FEEDBACK_SESSION_KEY = 'operational_feedback'
