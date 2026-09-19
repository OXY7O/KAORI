from __future__ import annotations

import os

from celery.schedules import crontab


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def alert_signal_interval_minutes() -> int:
    return _bounded_int('ALERT_SIGNAL_EVALUATION_INTERVAL_MINUTES', 5, 1, 60)


def alert_signal_freshness_minutes() -> int:
    default = max(alert_signal_interval_minutes() * 2, 2)
    return _bounded_int('ALERT_SIGNAL_FRESHNESS_MINUTES', default, 2, 120)


def build_alert_signal_beat_schedule() -> dict[str, dict[str, object]]:
    if str(os.getenv('ALERT_SIGNAL_EVALUATION_ENABLED', 'true')).strip().lower() not in {
        '1',
        'true',
        'yes',
        'on',
    }:
        return {}
    interval = alert_signal_interval_minutes()
    queue = (os.getenv('JOB_MAINTENANCE_CELERY_QUEUE') or 'maintenance').strip() or 'maintenance'
    return {
        'alert-signal-evaluation': {
            'task': 'app.intelligence.alert_signals.tasks.refresh_alert_signals',
            'schedule': crontab(minute=f'*/{interval}'),
            'options': {'queue': queue},
        }
    }
