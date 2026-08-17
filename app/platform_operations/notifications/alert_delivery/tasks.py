from __future__ import annotations

from celery import shared_task
from flask import current_app

from app.integrations.delivery.notification_channels.service import dispatch_alert_notification
from app.intelligence.alert_intelligence.service import list_active_alert_events
from app.models.notification_channel import NotificationChannel


@shared_task(
    name='app.platform_operations.notifications.alert_delivery.tasks.dispatch_alert_intelligence_notifications',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_alert_intelligence_notifications() -> dict[str, int]:
    """Poll active supported alert streams and dispatch enriched channel messages."""
    eligible_channels = NotificationChannel.query.filter(
        NotificationChannel.enabled.is_(True),
        NotificationChannel.test_status == 'success',
    ).count()
    totals = {
        'channels': eligible_channels,
        'events': 0,
        'eligible': 0,
        'sent': 0,
        'failed': 0,
        'retried': 0,
        'duplicate': 0,
        'skipped': 0,
    }
    if eligible_channels == 0:
        return totals

    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').strip()
    for event in list_active_alert_events():
        totals['events'] += 1
        result = dispatch_alert_notification(
            domain=str(event['domain']),
            asset_type=str(event['asset_type']),
            asset_key=str(event['asset_key']),
            asset_name=str(event['asset_name']),
            alert=dict(event['alert']),
            recommendations=list(event.get('recommendations') or []),
            base_url=base_url,
        )
        for key in ('eligible', 'sent', 'failed', 'retried', 'duplicate', 'skipped'):
            totals[key] += int(result.get(key, 0))
    return totals
