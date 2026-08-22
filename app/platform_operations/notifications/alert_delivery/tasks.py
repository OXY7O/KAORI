from __future__ import annotations

from celery import shared_task

from app.intelligence.alert_intelligence.lifecycle import expire_silences_and_notify, reconcile_alert_cases
from app.intelligence.alert_intelligence.notifications import dispatch_case_notifications


@shared_task(
    name='app.platform_operations.notifications.alert_delivery.tasks.dispatch_alert_intelligence_notifications',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_alert_intelligence_notifications() -> dict[str, object]:
    """Reconcile committed alert snapshots and dispatch governed Alert Operations notifications."""

    reconciliation = reconcile_alert_cases()
    expired_silences = expire_silences_and_notify()
    delivery = dispatch_case_notifications()
    return {
        'reconciliation': reconciliation,
        'expired_silences': expired_silences,
        'delivery': delivery,
    }
