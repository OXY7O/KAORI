from __future__ import annotations

from typing import Any

from app.dashboards.kubernetes.schema import AlertItem, AlertsSnapshot


def alerts_snapshot_with_message(
    message: str,
    *,
    source_status: str = 'Unavailable',
) -> AlertsSnapshot:
    snapshot = AlertsSnapshot()
    snapshot.source_status = source_status
    snapshot.message = message
    return snapshot

def build_alerts_snapshot(*, live_cluster: Any | None) -> AlertsSnapshot:
    if live_cluster is None:
        return alerts_snapshot_with_message(
            'Select a specific cluster to load AlertManager or Prometheus alert snapshots.'
        )

    try:
        from app.analytics.alerts.service import load_alerts_by_source

        alerts, source_status = load_alerts_by_source(cluster=live_cluster, source='auto')
    except Exception as exc:
        return alerts_snapshot_with_message(f'Alert snapshot unavailable: {exc}')

    active_alerts = [
        item for item in alerts if str(item.get('status', 'active')).lower() in {'active', 'firing', 'pending'}
    ]
    critical = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'critical')
    warning = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'warning')
    info = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() in {'info', 'none', ''})

    snapshot_items = []
    for item in active_alerts[:3]:
        name = str(item.get('name') or item.get('alertname') or 'Unknown Alert')
        namespace = str(item.get('namespace') or '-')
        target = str(item.get('target') or '-')
        description = str(item.get('summary') or item.get('description') or f'{namespace} / {target}')
        snapshot_items.append(
            AlertItem(
                title=name,
                description=description,
                severity=str(item.get('severity') or 'none').title(),
                age=str(item.get('starts_at_display') or item.get('starts_at') or ''),
            )
        )

    connected = bool(source_status.get('connected'))
    resolved_source = str(source_status.get('resolved_source') or source_status.get('source') or 'alert source')

    snapshot = AlertsSnapshot()
    snapshot.critical = critical
    snapshot.warning = warning
    snapshot.info = info
    snapshot.items = snapshot_items
    snapshot.source_status = 'Available' if connected or active_alerts else 'Unavailable'
    snapshot.message = (
        f'Loaded from {resolved_source.title()}.'
        if connected
        else str(source_status.get('error') or 'Alert source unavailable.')
    )
    return snapshot
