from __future__ import annotations

from celery import shared_task

from app.intelligence.alert_intelligence.lifecycle import (
    expire_acknowledgements_and_notify,
    expire_silences_and_notify,
)
from app.intelligence.alert_intelligence.notifications import dispatch_case_notifications
from app.intelligence.alert_intelligence.recommendation_source import reconcile_recommendation_alert_cases
from app.intelligence.rule_exceptions import notify_expiring_rule_exceptions


@shared_task(
    name='app.platform_operations.notifications.alert_delivery.tasks.dispatch_alert_intelligence_notifications',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_alert_intelligence_notifications() -> dict[str, object]:
    """Reconcile KAORI recommendations and dispatch governed Alert Operations notifications.

    External Prometheus/Alertmanager alerts remain resource-dashboard evidence for now.
    Alert Management intentionally materializes only recommendation-origin AlertCase records.
    """

    recommendation_reconciliation = reconcile_recommendation_alert_cases()
    expired_acknowledgements = expire_acknowledgements_and_notify()
    expired_silences = expire_silences_and_notify()
    expiring_rule_exceptions = notify_expiring_rule_exceptions()
    delivery = dispatch_case_notifications()
    return {
        'recommendation_reconciliation': recommendation_reconciliation,
        'expired_acknowledgements': expired_acknowledgements,
        'expired_silences': expired_silences,
        'expiring_rule_exceptions': expiring_rule_exceptions,
        'delivery': delivery,
    }
