from __future__ import annotations

from typing import Any

from app.alertmanager.service import get_alertmanager_status
from app.analytics.alerts.anomalies import build_anomalies
from app.analytics.alerts.contracts import AlertSourceStatus, NormalizedAlert
from app.analytics.alerts.sources import load_alerts_by_source
from app.models import Cluster


def build_resource_links(
    *,
    cluster: Cluster | None,
) -> dict[str, dict[str, Any]]:
    alertmanager_url = None
    alertmanager_configured = False

    if cluster is not None:
        alertmanager_status = get_alertmanager_status(cluster_id=cluster.id)
        alertmanager_url = alertmanager_status.get('endpoint')
        alertmanager_configured = bool(alertmanager_status.get('configured') and alertmanager_url)

    return {
        'alertmanager': {
            'configured': alertmanager_configured,
            'label': 'Alertmanager Console',
            'url': alertmanager_url,
            'description': (
                'Open the configured Alertmanager endpoint for this cluster '
                'to inspect grouping, routing, inhibition, and silences.'
            ),
        },
        'runbook': {
            'configured': False,
            'label': 'Runbook Portal',
            'url': None,
            'description': ('Runbook portal URL is not configured yet. This will be managed from Settings later.'),
        },
        'contact_point': {
            'configured': False,
            'label': 'Contact Point',
            'name': None,
            'email': None,
            'url': None,
            'description': (
                'Escalation contact point or PIC is not configured yet. This will be managed from Settings later.'
            ),
        },
    }


def build_cluster_signal_overview(
    *,
    clusters: list[Cluster],
    source: str,
) -> list[dict[str, Any]]:
    overview: list[dict[str, Any]] = []

    for cluster in clusters:
        alerts, source_status = load_alerts_by_source(
            cluster=cluster,
            source=source,
        )

        anomalies = build_anomalies(
            cluster=cluster,
            severity='all',
            namespace='',
            search='',
        )

        critical_alerts = sum(
            1
            for alert in alerts
            if alert.get(
                'severity',
            )
            == 'critical'
        )

        warning_alerts = sum(
            1
            for alert in alerts
            if alert.get(
                'severity',
            )
            == 'warning'
        )

        active_alerts = sum(
            1
            for alert in alerts
            if alert.get(
                'status',
            )
            in {
                'active',
                'firing',
                'pending',
            }
        )

        anomaly_count = len(
            anomalies,
        )

        total_signals = active_alerts + anomaly_count

        overview.append(
            {
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'active_alerts': active_alerts,
                'critical_alerts': critical_alerts,
                'warning_alerts': warning_alerts,
                'anomalies': anomaly_count,
                'total_signals': total_signals,
                'connected': bool(
                    source_status.get(
                        'connected',
                    )
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
            }
        )

    max_signals = max(
        [
            item.get(
                'total_signals',
                0,
            )
            for item in overview
        ],
        default=0,
    )

    for item in overview:
        total_signals = int(
            item.get(
                'total_signals',
                0,
            )
        )

        if max_signals <= 0:
            item['bar_width'] = 0
        else:
            item['bar_width'] = max(
                int((total_signals / max_signals) * 100),
                8,
            )

    return sorted(
        overview,
        key=lambda item: (
            item.get(
                'critical_alerts',
                0,
            ),
            item.get(
                'total_signals',
                0,
            ),
            item.get(
                'cluster_name',
                '',
            ),
        ),
        reverse=True,
    )


def build_bar_units(
    *,
    value: int,
    max_value: int,
) -> int:
    if value <= 0 or max_value <= 0:
        return 0

    return max(
        round((value / max_value) * 12),
        1,
    )


def build_selected_cluster_signal_overview(
    *,
    cluster: Cluster | None,
    alerts: list[NormalizedAlert],
    anomalies: list[dict[str, Any]],
    source_status: AlertSourceStatus,
) -> dict[str, Any]:
    if cluster is None:
        return {
            'cluster_id': '',
            'cluster_name': 'No cluster selected',
            'source': 'none',
            'fallback_used': False,
            'fallback_reason': None,
            'connected': False,
            'active_alerts': 0,
            'critical_alerts': 0,
            'warning_alerts': 0,
            'info_alerts': 0,
            'pending_alerts': 0,
            'resolved_alerts': 0,
            'anomalies': 0,
            'restart_anomalies': 0,
            'not_ready_anomalies': 0,
            'total_signals': 0,
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
            'bars': {
                'active_alerts': 0,
                'critical_alerts': 0,
                'warning_alerts': 0,
                'anomalies': 0,
            },
        }

    critical_alerts = sum(
        1
        for alert in alerts
        if alert.get(
            'severity',
        )
        == 'critical'
    )

    warning_alerts = sum(
        1
        for alert in alerts
        if alert.get(
            'severity',
        )
        == 'warning'
    )

    info_alerts = sum(
        1
        for alert in alerts
        if alert.get(
            'severity',
        )
        == 'info'
    )

    active_alerts = sum(
        1
        for alert in alerts
        if alert.get(
            'status',
        )
        in {
            'active',
            'firing',
            'pending',
        }
    )

    pending_alerts = sum(
        1
        for alert in alerts
        if alert.get(
            'status',
        )
        == 'pending'
    )

    resolved_alerts = sum(
        1
        for alert in alerts
        if alert.get(
            'status',
        )
        == 'resolved'
    )

    restart_anomalies = sum(
        1
        for anomaly in anomalies
        if anomaly.get(
            'name',
        )
        == 'Pod Restart Spike'
    )

    not_ready_anomalies = sum(
        1
        for anomaly in anomalies
        if anomaly.get(
            'name',
        )
        == 'Pod Not Ready'
    )

    anomaly_count = len(
        anomalies,
    )

    total_signals = active_alerts + anomaly_count

    if critical_alerts > 0:
        priority = {
            'level': 'critical',
            'label': 'Critical',
            'description': 'Critical alert signals are active. Prioritize immediate inspection.',
            'icon': 'circle-alert',
        }
    elif warning_alerts > 0 or anomaly_count > 0:
        priority = {
            'level': 'warning',
            'label': 'Warning',
            'description': 'Warning alerts or anomaly candidates were detected. Review affected workloads.',
            'icon': 'alert-triangle',
        }
    else:
        priority = {
            'level': 'normal',
            'label': 'Normal',
            'description': 'No active alert or anomaly signal detected for this cluster.',
            'icon': 'shield-check',
        }

    signal_candidates = [
        {
            'label': 'Active Alerts',
            'count': active_alerts,
        },
        {
            'label': 'Critical Alerts',
            'count': critical_alerts,
        },
        {
            'label': 'Warning Alerts',
            'count': warning_alerts,
        },
        {
            'label': 'Anomalies',
            'count': anomaly_count,
        },
    ]

    dominant_signal = max(
        signal_candidates,
        key=lambda item: int(
            item.get(
                'count',
                0,
            )
        ),
    )

    anomaly_candidates = [
        {
            'label': 'Restart anomalies',
            'count': restart_anomalies,
        },
        {
            'label': 'Not ready anomalies',
            'count': not_ready_anomalies,
        },
    ]

    dominant_anomaly = max(
        anomaly_candidates,
        key=lambda item: int(
            item.get(
                'count',
                0,
            )
        ),
    )

    if critical_alerts > 0:
        action_hint = 'Inspect critical alert labels, affected target, and runbook first.'
    elif warning_alerts > 0:
        action_hint = 'Review warning alerts and validate whether workload behavior is expected.'
    elif anomaly_count > 0:
        action_hint = 'Inspect restart and readiness anomaly candidates from Prometheus metrics.'
    else:
        action_hint = 'No immediate inspection is required.'

    max_value = max(
        active_alerts,
        critical_alerts,
        warning_alerts,
        anomaly_count,
        1,
    )

    return {
        'cluster_id': cluster.id,
        'cluster_name': cluster.name,
        'source': source_status.get(
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
        'connected': bool(
            source_status.get(
                'connected',
            )
        ),
        'active_alerts': active_alerts,
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'info_alerts': info_alerts,
        'pending_alerts': pending_alerts,
        'resolved_alerts': resolved_alerts,
        'anomalies': anomaly_count,
        'restart_anomalies': restart_anomalies,
        'not_ready_anomalies': not_ready_anomalies,
        'total_signals': total_signals,
        'priority': priority,
        'insight': {
            'dominant_signal': dominant_signal.get(
                'label',
                'No signal',
            ),
            'dominant_signal_count': dominant_signal.get(
                'count',
                0,
            ),
            'dominant_anomaly': dominant_anomaly.get(
                'label',
                'No anomaly',
            ),
            'dominant_anomaly_count': dominant_anomaly.get(
                'count',
                0,
            ),
            'action_hint': action_hint,
        },
        'bars': {
            'active_alerts': build_bar_units(
                value=active_alerts,
                max_value=max_value,
            ),
            'critical_alerts': build_bar_units(
                value=critical_alerts,
                max_value=max_value,
            ),
            'warning_alerts': build_bar_units(
                value=warning_alerts,
                max_value=max_value,
            ),
            'anomalies': build_bar_units(
                value=anomaly_count,
                max_value=max_value,
            ),
        },
    }
