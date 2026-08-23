from __future__ import annotations

from celery import shared_task

from app.intelligence.alert_signals.service import refresh_all_kubernetes_runtime_signals


@shared_task(
    name='app.intelligence.alert_signals.tasks.refresh_alert_signals',
    acks_late=True,
    reject_on_worker_lost=True,
)
def refresh_alert_signals() -> dict[str, object]:
    """Refresh compact operational signals used by fast Alert Intelligence rules."""

    return {'kubernetes_runtime_health': refresh_all_kubernetes_runtime_signals()}
