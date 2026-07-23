from __future__ import annotations

from typing import Any

from app.analytics.alerts.anomalies import load_prometheus_anomaly_metrics
from app.analytics.alerts.contracts import AlertsSnapshot, NormalizedAlert
from app.analytics.alerts.health import build_integration_status, build_source_health
from app.analytics.alerts.inhibition import build_inhibition_summary
from app.analytics.alerts.ownership import build_empty_ownership_summary, build_ownership_summary
from app.analytics.alerts.readiness import (
    build_empty_incident_readiness,
    build_incident_readiness,
)
from app.analytics.alerts.routing import build_empty_routing_summary, build_routing_summary
from app.analytics.alerts.selection import get_selected_cluster
from app.analytics.alerts.signals import build_selected_cluster_signal_overview
from app.analytics.alerts.silences import build_empty_silence_summary, build_silence_summary
from app.analytics.alerts.sources import load_alerts_by_source
from app.intelligence.recommendation_engine import (
    build_alerts_actionable_recommendations,
    count_actionable_recommendations,
)


def get_alerts_snapshot(
    cluster_id: str,
) -> AlertsSnapshot:
    selected_cluster = get_selected_cluster(
        cluster_id=cluster_id,
    )

    if selected_cluster is None:
        return _empty_alerts_snapshot()

    try:
        alerts, source_status = load_alerts_by_source(
            cluster=selected_cluster,
            source='auto',
        )

        anomalies = load_prometheus_anomaly_metrics(
            cluster=selected_cluster,
        )

        signal_overview = build_selected_cluster_signal_overview(
            cluster=selected_cluster,
            alerts=alerts,
            anomalies=anomalies,
            source_status=source_status,
        )

        firing_alerts = _count_alerts_by_status(
            alerts=alerts,
            statuses=[
                'firing',
                'active',
            ],
        )

        pending_alerts = _count_alerts_by_status(
            alerts=alerts,
            statuses=[
                'pending',
            ],
        )

        critical_alerts = _count_alerts_by_severity(
            alerts=alerts,
            severity='critical',
        )

        warning_alerts = _count_alerts_by_severity(
            alerts=alerts,
            severity='warning',
        )

        highest_alert = _get_highest_severity_alert(
            alerts,
        )

        highest_severity = _resolve_highest_severity(
            critical_alerts=critical_alerts,
            warning_alerts=warning_alerts,
            anomalies=anomalies,
        )

        highest_severity_description = _resolve_highest_severity_description(
            highest_alert=highest_alert,
            anomalies=anomalies,
            signal_overview=signal_overview,
        )

        actionable_recommendations = build_alerts_actionable_recommendations(
            {
                'alerts': alerts,
                'all_alerts': alerts,
                'anomalies': anomalies,
                'all_anomalies': anomalies,
                'source_status': source_status,
                'selected_cluster_signal_overview': signal_overview,
            }
        )

        integration_status = build_integration_status(
            cluster=selected_cluster,
            source_status=source_status,
        )

        source_health = build_source_health(
            cluster=selected_cluster,
            source_status=source_status,
            integration_status=integration_status,
        )

        routing_summary = build_routing_summary(
            alerts=alerts,
            source_status=source_status,
        )

        silence_summary = build_silence_summary(
            cluster=selected_cluster,
            alerts=alerts,
            source_status=source_status,
        )

        inhibition_summary = build_inhibition_summary(
            alerts=alerts,
            source_status=source_status,
        )

        ownership_summary = build_ownership_summary(
            alerts=alerts,
            source_status=source_status,
        )

        incident_readiness = build_incident_readiness(
            signal_overview=signal_overview,
            source_health=source_health,
            routing_summary=routing_summary,
            silence_summary=silence_summary,
            inhibition_summary=inhibition_summary,
            ownership_summary=ownership_summary,
        )

        return {
            'firing_alerts': firing_alerts,
            'pending_alerts': pending_alerts,
            'critical_alerts': critical_alerts,
            'warning_alerts': warning_alerts,
            'recent_anomalies': len(
                anomalies,
            ),
            'highest_severity': highest_severity,
            'highest_severity_description': highest_severity_description,
            'source': source_status.get(
                'resolved_source',
                'none',
            ),
            'resolved_source': source_status.get(
                'resolved_source',
                'none',
            ),
            'fallback_used': bool(
                source_status.get(
                    'fallback_used',
                    False,
                )
            ),
            'fallback_reason': source_status.get(
                'fallback_reason',
                None,
            ),
            'source_connected': bool(
                source_status.get(
                    'connected',
                    False,
                )
            ),
            'source_health': source_health,
            'routing_summary': routing_summary,
            'silence_summary': silence_summary,
            'inhibition_summary': inhibition_summary,
            'ownership_summary': ownership_summary,
            'incident_readiness': incident_readiness,
            'priority': signal_overview.get(
                'priority',
                {},
            ),
            'insight': signal_overview.get(
                'insight',
                {},
            ),
            'recommendation_count': count_actionable_recommendations(
                actionable_recommendations,
            ),
        }

    except Exception:
        return _empty_alerts_snapshot()


def _empty_alerts_snapshot() -> AlertsSnapshot:
    return {
        'firing_alerts': 0,
        'pending_alerts': 0,
        'critical_alerts': 0,
        'warning_alerts': 0,
        'recent_anomalies': 0,
        'highest_severity': '-',
        'highest_severity_description': 'No active critical alert detected.',
        'source': 'none',
        'resolved_source': 'none',
        'fallback_used': False,
        'fallback_reason': None,
        'source_connected': False,
        'source_health': {
            'score': 0,
            'level': 'unavailable',
            'label': 'No Alert Source',
            'description': 'No alert source health signal is available.',
            'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
            'icon': 'circle-off',
            'checks': [],
            'selected_source': 'auto',
            'resolved_source': 'none',
            'fallback_used': False,
        },
        'routing_summary': build_empty_routing_summary(),
        'silence_summary': build_empty_silence_summary(),
        'inhibition_summary': build_inhibition_summary(
            alerts=[],
            source_status={
                'resolved_source': 'none',
                'connected': False,
            },
        ),
        'ownership_summary': build_empty_ownership_summary(),
        'incident_readiness': build_empty_incident_readiness(),
        'priority': {
            'level': 'normal',
            'label': 'Normal',
            'description': 'No active alert or anomaly signal detected.',
            'icon': 'shield-check',
        },
        'insight': {
            'dominant_signal': 'No signal',
            'dominant_signal_count': 0,
            'dominant_anomaly': 'No anomaly',
            'dominant_anomaly_count': 0,
            'action_hint': 'No immediate inspection is required.',
        },
        'recommendation_count': 0,
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
    signal_overview: dict[str, Any],
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
