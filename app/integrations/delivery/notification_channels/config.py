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


def notification_delivery_retry_delay_seconds() -> int:
    # Keep the claim stale-window longer than the maximum transport timeout.
    return _bounded_int('NOTIFICATION_DELIVERY_RETRY_DELAY_SECONDS', 180, 120, 86400)


def build_notification_beat_schedule() -> dict[str, dict[str, object]]:
    queue = (os.getenv('JOB_MAINTENANCE_CELERY_QUEUE') or 'maintenance').strip() or 'maintenance'
    schedule: dict[str, dict[str, object]] = {}
    # Safe opt-in: never trigger outbound retries before governed UAT.
    if str(os.getenv('NOTIFICATION_DELIVERY_RECOVERY_ENABLED', 'false')).strip().lower() in {
        '1', 'true', 'yes', 'on'
    }:
        interval = _bounded_int('NOTIFICATION_DELIVERY_RECOVERY_INTERVAL_MINUTES', 1, 1, 60)
        schedule['notification-channel-delivery-recovery'] = {
            'task': 'app.platform_operations.notifications.alert_delivery.tasks.recover_notification_channel_deliveries',
            'schedule': crontab(minute=f'*/{interval}'),
            'options': {'queue': queue},
        }
    if str(os.getenv('ALERT_INTELLIGENCE_NOTIFICATION_ENABLED', 'true')).strip().lower() in {
        '1', 'true', 'yes', 'on'
    }:
        interval = _bounded_int('ALERT_INTELLIGENCE_NOTIFICATION_INTERVAL_MINUTES', 1, 1, 60)
        schedule['alert-intelligence-notification-dispatch'] = {
            'task': 'app.platform_operations.notifications.alert_delivery.tasks.dispatch_alert_intelligence_notifications',
            'schedule': crontab(minute=f'*/{interval}'),
            'options': {'queue': queue},
        }
    return schedule
