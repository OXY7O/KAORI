from __future__ import annotations

from typing import Any

from celery import shared_task

from app.reports.storage.service import refresh_report_storage_readiness


@shared_task(
    name='app.reports.storage.tasks.refresh_report_storage_readiness_task',
    acks_late=False,
)
def refresh_report_storage_readiness_task() -> dict[str, Any]:
    """Refresh the shared report-storage readiness snapshot.

    This is intentionally a lightweight connectivity/readiness probe. Manual
    verification remains the stronger write/exists/delete validation path.
    """

    return refresh_report_storage_readiness(source='periodic')
