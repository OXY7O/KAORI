from __future__ import annotations

import os

from celery.schedules import crontab


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def notification_delivery_timeout_seconds() -> int:
    return _bounded_int('NOTIFICATION_DELIVERY_TIMEOUT_SECONDS', 10, 1, 60)


def notification_delivery_max_attempts() -> int:
    return _bounded_int('NOTIFICATION_DELIVERY_MAX_ATTEMPTS', 3, 1, 10)


def build_notification_beat_schedule() -> dict[str, dict[str, object]]:
    if str(os.getenv('ALERT_INTELLIGENCE_NOTIFICATION_ENABLED', 'true')).strip().lower() not in {
        '1',
        'true',
        'yes',
        'on',
    }:
        return {}
    interval = _bounded_int('ALERT_INTELLIGENCE_NOTIFICATION_INTERVAL_MINUTES', 1, 1, 60)
    queue = (os.getenv('JOB_MAINTENANCE_CELERY_QUEUE') or 'maintenance').strip() or 'maintenance'
    return {
        'alert-intelligence-notification-dispatch': {
            'task': 'app.alert_delivery.tasks.dispatch_alert_intelligence_notifications',
            'schedule': crontab(minute=f'*/{interval}'),
            'options': {'queue': queue},
        }
    }
