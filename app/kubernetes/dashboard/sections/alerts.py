from __future__ import annotations

from typing import Any

from app.kubernetes.analytics.alerts.source_messages import friendly_combined_alert_error
from app.kubernetes.dashboard.schema import AlertItem, AlertsSnapshot


def alerts_snapshot_with_message(
    message: str,
    *,
    source_status: str = 'Unavailable',
) -> AlertsSnapshot:
    snapshot = AlertsSnapshot()
    snapshot.source_status = source_status
    snapshot.message = message
    return snapshot


def build_alerts_snapshot(*, context: dict[str, Any] | None, unavailable_reason: str) -> AlertsSnapshot:
    if not context:
        return alerts_snapshot_with_message(unavailable_reason)

    raw_items = context.get('items') or []
    items = [
        AlertItem(
            title=str(item.get('title') or 'Unknown Alert'),
            description=str(item.get('description') or '-'),
            severity=str(item.get('severity') or 'None'),
            age=str(item.get('age') or ''),
        )
        for item in raw_items[:3]
        if isinstance(item, dict)
    ]
    connected = bool(context.get('source_connected'))
    message = str(context.get('message') or 'Alert source connected.') if connected else friendly_combined_alert_error()
    return AlertsSnapshot(
        critical=int(context.get('critical') or 0),
        warning=int(context.get('warning') or 0),
        info=int(context.get('info') or 0),
        items=items,
        source_status='Available' if connected else 'Unavailable',
        message=message,
    )
