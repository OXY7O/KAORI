from __future__ import annotations

from typing import Any

from app.alertmanager.service import get_alertmanager_status
from app.analytics.alerts.contracts import (
    AlertResourceLinks,
    AlertSelectedClusterSignalOverview,
    AlertSignalPriority,
    AlertSourceStatus,
    NormalizedAlert,
)
from app.models import Cluster


def build_resource_links(
    *,
    cluster: Cluster | None,
) -> AlertResourceLinks:
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


def _signal_priority(
    *,
    source_connected: bool,
    evidence_complete: bool,
    critical_alerts: int,
    warning_alerts: int,
    anomaly_count: int,
) -> AlertSignalPriority:
    if not source_connected:
        return {
            'level': 'unknown',
            'label': 'Unknown',
            'description': 'Committed alert-source evidence is unavailable for this cluster.',
            'icon': 'circle-help',
        }
    if critical_alerts > 0:
        return {
            'level': 'critical',
            'label': 'Critical',
            'description': 'Critical alert signals are active. Prioritize immediate inspection.',
            'icon': 'circle-alert',
        }
    if warning_alerts > 0 or anomaly_count > 0:
        return {
            'level': 'warning',
            'label': 'Warning',
            'description': 'Warning alerts or anomaly candidates were detected. Review affected workloads.',
            'icon': 'alert-triangle',
        }
    if not evidence_complete:
        return {
            'level': 'unknown',
            'label': 'Limited Evidence',
            'description': 'Alert evidence is available, but one or more anomaly signal families are incomplete.',
            'icon': 'circle-help',
        }
    return {
        'level': 'normal',
        'label': 'Normal',
        'description': 'No active alert or anomaly signal detected for this cluster.',
        'icon': 'shield-check',
    }


def _signal_action_hint(
    *,
    critical_alerts: int,
    warning_alerts: int,
    anomaly_count: int,
    evidence_complete: bool,
) -> str:
    if critical_alerts > 0:
        return 'Inspect critical alert labels, affected target, and runbook first.'
    if warning_alerts > 0:
        return 'Review warning alerts and validate whether workload behavior is expected.'
    if anomaly_count > 0:
        return 'Inspect restart and readiness anomaly candidates from Prometheus metrics.'
    if not evidence_complete:
        return 'Restore complete anomaly evidence before confirming a stable signal posture.'
    return 'No immediate inspection is required.'


def build_selected_cluster_signal_overview(
    *,
    cluster: Cluster | None,
    alerts: list[NormalizedAlert],
    anomalies: list[dict[str, Any]],
    source_status: AlertSourceStatus,
    evidence_complete: bool,
) -> AlertSelectedClusterSignalOverview:
    if cluster is None:
        return {
            'cluster_id': '',
            'cluster_name': 'No cluster selected',
            'source': 'none',
            'fallback_used': False,
            'fallback_reason': None,
            'connected': False,
            'evidence_complete': False,
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
                'level': 'unknown',
                'label': 'Unknown',
                'description': 'Select a cluster before evaluating alert and anomaly signals.',
                'icon': 'circle-help',
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

    source_connected = bool(source_status.get('connected'))
    priority = _signal_priority(
        source_connected=source_connected,
        evidence_complete=evidence_complete,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        anomaly_count=anomaly_count,
    )

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

    action_hint = _signal_action_hint(
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        anomaly_count=anomaly_count,
        evidence_complete=evidence_complete,
    )

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
        'connected': source_connected,
        'evidence_complete': evidence_complete,
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
