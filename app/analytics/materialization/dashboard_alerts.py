from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.analytics.alerts.sources import load_alerts_by_source
from app.models import Cluster

_ACTIVE_ALERT_STATES = {'active', 'firing', 'pending'}


def build_dashboard_alerts_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    cluster_id = str(query_args.get('cluster_id') or '').strip()
    cluster = Cluster.query.filter_by(id=cluster_id).first() if cluster_id else None
    if cluster is None:
        return _empty_alerts_context('Cluster is unavailable for alert materialization.')

    alerts, source_status = load_alerts_by_source(cluster=cluster, source='auto')
    active_alerts = [
        item
        for item in alerts
        if str(item.get('status', 'active')).lower() in _ACTIVE_ALERT_STATES
    ]
    critical = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'critical')
    warning = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'warning')
    info = max(len(active_alerts) - critical - warning, 0)
    resolved_source = str(source_status.get('resolved_source') or source_status.get('source') or 'alert source')
    connected = bool(source_status.get('connected'))

    return {
        'critical': critical,
        'warning': warning,
        'info': info,
        'items': [
            {
                'title': str(item.get('name') or item.get('alertname') or 'Unknown Alert'),
                'description': str(
                    item.get('summary')
                    or item.get('description')
                    or f"{item.get('namespace') or '-'} / {item.get('target') or '-'}"
                ),
                'severity': str(item.get('severity') or 'none').title(),
                'age': item.get('starts_at') or '',
            }
            for item in active_alerts[:3]
        ],
        'source_connected': connected,
        'resolved_source': resolved_source,
        'message': (
            f'Loaded from {resolved_source.title()} by the analytics worker.'
            if connected
            else str(source_status.get('error') or 'Alert source unavailable during worker refresh.')
        ),
        'generated_at': datetime.now(UTC),
    }


def _empty_alerts_context(message: str) -> dict[str, Any]:
    return {
        'critical': 0,
        'warning': 0,
        'info': 0,
        'items': [],
        'source_connected': False,
        'resolved_source': 'none',
        'message': message,
        'generated_at': datetime.now(UTC),
    }
