from __future__ import annotations

from typing import Any

from app.analytics.alerts.contracts import (
    AlertSelectedClusterSignalOverview,
    AlertSourceStatus,
    AlertsSnapshot,
    NormalizedAlert,
)
from app.analytics.alerts.inhibition import build_inhibition_summary
from app.analytics.alerts.ownership import build_empty_ownership_summary
from app.analytics.alerts.readiness import build_empty_incident_readiness
from app.analytics.alerts.routing import build_empty_routing_summary
from app.analytics.alerts.silences import build_empty_silence_summary
from app.intelligence.recommendation_engine import count_actionable_recommendations


def get_alerts_snapshot(
    cluster_id: str,
) -> AlertsSnapshot | None:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.alerts',
        parameters={'cluster_id': str(cluster_id), 'source': 'auto'},
    )
    context = result.context or {}
    if not result.available:
        return None
    alerts = list(context.get('all_alerts') or [])
    anomalies = list(context.get('all_anomalies') or [])
    source_status = context.get('source_status') or _empty_source_status()
    signal_overview = context.get('selected_cluster_signal_overview') or {}
    firing_alerts = _count_alerts_by_status(alerts=alerts, statuses=['firing', 'active'])
    pending_alerts = _count_alerts_by_status(alerts=alerts, statuses=['pending'])
    critical_alerts = _count_alerts_by_severity(alerts=alerts, severity='critical')
    warning_alerts = _count_alerts_by_severity(alerts=alerts, severity='warning')
    highest_alert = _get_highest_severity_alert(alerts)
    recommendations = context.get('actionable_recommendations') or []
    return {
        'firing_alerts': firing_alerts,
        'pending_alerts': pending_alerts,
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'recent_anomalies': len(anomalies),
        'highest_severity': _resolve_highest_severity(
            critical_alerts=critical_alerts,
            warning_alerts=warning_alerts,
            anomalies=anomalies,
        ),
        'highest_severity_description': _resolve_highest_severity_description(
            highest_alert=highest_alert,
            anomalies=anomalies,
            signal_overview=signal_overview,
        ),
        'source': source_status.get('resolved_source', 'none'),
        'resolved_source': source_status.get('resolved_source', 'none'),
        'fallback_used': bool(source_status.get('fallback_used', False)),
        'fallback_reason': source_status.get('fallback_reason'),
        'source_connected': bool(source_status.get('connected', False)),
        'source_health': context.get('source_health') or {},
        'routing_summary': context.get('routing_summary') or build_empty_routing_summary(),
        'silence_summary': context.get('silence_summary') or build_empty_silence_summary(),
        'inhibition_summary': context.get('inhibition_summary') or build_inhibition_summary(
            alerts=[], source_status=_empty_source_status()
        ),
        'ownership_summary': context.get('ownership_summary') or build_empty_ownership_summary(),
        'incident_readiness': context.get('incident_readiness') or build_empty_incident_readiness(),
        'priority': signal_overview.get('priority', {}),
        'insight': signal_overview.get('insight', {}),
        'recommendation_count': count_actionable_recommendations(
            recommendations if isinstance(recommendations, list) else []
        ),
    }

def _empty_source_status() -> AlertSourceStatus:
    """Return a complete unavailable-source contract for empty snapshots."""
    return {
        'source': 'none',
        'selected_source': 'auto',
        'resolved_source': 'none',
        'label': 'No Alert Source',
        'configured': False,
        'connected': False,
        'fallback_used': False,
        'fallback_reason': None,
        'error': None,
        'response_time_ms': None,
        'last_checked_at': None,
    }


def _count_alerts_by_status(
    *,
    alerts: list[NormalizedAlert],
    statuses: list[str],
) -> int:
    normalized_statuses = {status.lower() for status in statuses}

    return sum(
        1
        for alert in alerts
        if str(
            alert.get(
                'status',
                '',
            )
        ).lower()
        in normalized_statuses
    )


def _count_alerts_by_severity(
    *,
    alerts: list[NormalizedAlert],
    severity: str,
) -> int:
    normalized_severity = severity.lower()

    return sum(
        1
        for alert in alerts
        if str(
            alert.get(
                'severity',
                '',
            )
        ).lower()
        == normalized_severity
    )


def _get_highest_severity_alert(
    alerts: list[NormalizedAlert],
) -> NormalizedAlert | None:
    severity_rank = {
        'critical': 0,
        'warning': 1,
        'info': 2,
        'none': 3,
    }

    if not alerts:
        return None

    sorted_alerts = sorted(
        alerts,
        key=lambda alert: severity_rank.get(
            str(
                alert.get(
                    'severity',
                    'none',
                )
            ).lower(),
            4,
        ),
    )

    return sorted_alerts[0]


def _resolve_highest_severity(
    *,
    critical_alerts: int,
    warning_alerts: int,
    anomalies: list[dict[str, Any]],
) -> str:
    if critical_alerts > 0:
        return 'Critical'

    if warning_alerts > 0:
        return 'Warning'

    if anomalies:
        return 'Anomaly'

    return '-'


def _resolve_highest_severity_description(
    *,
    highest_alert: NormalizedAlert | None,
    anomalies: list[dict[str, Any]],
    signal_overview: AlertSelectedClusterSignalOverview,
) -> str:
    if highest_alert is not None:
        description = str(
            highest_alert.get(
                'description',
                '',
            )
            or highest_alert.get(
                'summary',
                '',
            )
            or highest_alert.get(
                'name',
                '',
            )
        )

        if description:
            return description

    if anomalies:
        first_anomaly = anomalies[0]

        description = str(
            first_anomaly.get(
                'description',
                '',
            )
            or first_anomaly.get(
                'summary',
                '',
            )
            or first_anomaly.get(
                'name',
                '',
            )
        )

        if description:
            return description

    priority = signal_overview.get(
        'priority',
        {},
    )

    if isinstance(
        priority,
        dict,
    ):
        priority_description = str(
            priority.get(
                'description',
                '',
            )
        )

        if priority_description:
            return priority_description

    return 'No active critical alert detected.'
