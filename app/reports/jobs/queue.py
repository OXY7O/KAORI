from __future__ import annotations

from flask import current_app

DEFAULT_REPORTS_QUEUE = 'reports'


def get_reports_queue_name() -> str:
    """Return the configured queue shared by report dispatchers and workers."""

    configured_queue = current_app.config.get(
        'REPORTS_CELERY_QUEUE',
        DEFAULT_REPORTS_QUEUE,
    )
    return str(configured_queue or DEFAULT_REPORTS_QUEUE).strip() or DEFAULT_REPORTS_QUEUE
