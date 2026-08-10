from __future__ import annotations

from typing import Any, Literal

from app.alertmanager.service import get_alertmanager_status
from app.analytics.alerts.contracts import (
    AlertIntegrationStatus,
    AlertIntegrationStatusMap,
    AlertSourceHealthCheck,
    AlertSourceHealthSummary,
    AlertSourceStatus,
    NormalizedAlert,
)
from app.models import Cluster
from app.prometheus.repository import resolve_instance_for_cluster


def is_alert_evidence_complete(
    *,
    source_status: AlertSourceStatus,
    anomaly_source_status: dict[str, Any] | None,
) -> bool:
    anomaly_status = anomaly_source_status or {}
    return (
        bool(source_status.get('connected', False))
        and bool(anomaly_status.get('connected', False))
        and not bool(anomaly_status.get('partial', False))
    )


def build_summary(
    *,
    alerts: list[NormalizedAlert],
    anomalies: list[dict[str, Any]],
    source_status: AlertSourceStatus,
) -> dict[str, Any]:
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

    return {
        'active_alerts': active_alerts,
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'detected_anomalies': len(
            anomalies,
        ),
        'source_connected': bool(
            source_status.get(
                'connected',
            )
        ),
    }


def build_prometheus_status(
    *,
    cluster: Cluster | None,
    source_status: AlertSourceStatus,
    anomaly_source_status: dict[str, Any] | None = None,
) -> AlertIntegrationStatus:
    if cluster is None:
        return {
            'configured': False,
            'connected': False,
            'label': 'Prometheus Not Set',
            'status': 'not_set',
            'response_time_ms': None,
        }

    config = resolve_instance_for_cluster(cluster.id)

    if config is None or not getattr(
        config,
        'endpoint',
        None,
    ):
        return {
            'configured': False,
            'connected': False,
            'label': 'Prometheus Not Set',
            'status': 'not_set',
            'response_time_ms': None,
        }

    anomaly_status = anomaly_source_status or {}
    resolved_alert_source = source_status.get('resolved_source') == 'prometheus' and bool(
        source_status.get('connected')
    )
    anomaly_connected = bool(anomaly_status.get('connected'))
    connected = resolved_alert_source or anomaly_connected
    response_time_ms = (
        source_status.get('response_time_ms') if resolved_alert_source else anomaly_status.get('response_time_ms')
    )

    return {
        'configured': True,
        'connected': connected,
        'label': 'Prometheus Connected' if connected else 'Prometheus Configured',
        'status': 'connected' if connected else 'configured',
        'response_time_ms': response_time_ms if connected else None,
    }


def build_alertmanager_integration_status(
    *,
    cluster: Cluster | None,
    source_status: AlertSourceStatus,
) -> AlertIntegrationStatus:
    if cluster is None:
        return {
            'configured': False,
            'connected': False,
            'label': 'Alertmanager Not Set',
            'status': 'not_set',
            'response_time_ms': None,
        }

    resolved_from_alertmanager = (
        source_status.get(
            'resolved_source',
        )
        == 'alertmanager'
    )

    if resolved_from_alertmanager and source_status.get(
        'connected',
    ):
        return {
            'configured': True,
            'connected': True,
            'label': 'Alertmanager Connected',
            'status': 'connected',
            'response_time_ms': source_status.get(
                'response_time_ms',
            ),
        }

    status = get_alertmanager_status(
        cluster_id=cluster.id,
    )

    if not status.get(
        'configured',
    ):
        return {
            'configured': False,
            'connected': False,
            'label': 'Alertmanager Not Set',
            'status': 'not_set',
            'response_time_ms': None,
        }

    connected = bool(
        status.get(
            'connected',
        )
    )

    return {
        'configured': True,
        'connected': connected,
        'label': 'Alertmanager Connected' if connected else 'Alertmanager Configured',
        'status': 'connected' if connected else 'configured',
        'response_time_ms': status.get(
            'response_time_ms',
        ),
    }


def build_integration_status(
    *,
    cluster: Cluster | None,
    source_status: AlertSourceStatus,
    anomaly_source_status: dict[str, Any] | None = None,
) -> AlertIntegrationStatusMap:
    return {
        'prometheus': build_prometheus_status(
            cluster=cluster,
            source_status=source_status,
            anomaly_source_status=anomaly_source_status,
        ),
        'alertmanager': build_alertmanager_integration_status(
            cluster=cluster,
            source_status=source_status,
        ),
    }


def build_source_health(
    *,
    cluster: Cluster | None,
    source_status: AlertSourceStatus,
    integration_status: AlertIntegrationStatusMap,
) -> AlertSourceHealthSummary:
    if cluster is None:
        return {
            'score': 0,
            'level': 'unavailable',
            'label': 'No Cluster Selected',
            'description': 'Select a cluster before evaluating alert source health.',
            'icon': 'circle-off',
            'checks': [
                {
                    'label': 'Cluster selected',
                    'status': 'fail',
                    'description': 'No cluster is selected for alert analysis.',
                }
            ],
        }

    alertmanager_status = integration_status['alertmanager']
    prometheus_status = integration_status['prometheus']

    selected_source = str(
        source_status.get(
            'selected_source',
            'auto',
        )
        or 'auto'
    )
    resolved_source = str(
        source_status.get(
            'resolved_source',
            'none',
        )
        or 'none'
    )
    connected = bool(
        source_status.get(
            'connected',
            False,
        )
    )
    fallback_used = bool(
        source_status.get(
            'fallback_used',
            False,
        )
    )
    alertmanager_configured = bool(
        alertmanager_status.get(
            'configured',
            False,
        )
    )
    alertmanager_connected = bool(
        alertmanager_status.get(
            'connected',
            False,
        )
    )
    prometheus_configured = bool(
        prometheus_status.get(
            'configured',
            False,
        )
    )
    prometheus_connected = bool(
        prometheus_status.get(
            'connected',
            False,
        )
    )

    level: Literal['healthy', 'fallback', 'degraded', 'unavailable']

    if connected and resolved_source == 'alertmanager' and not fallback_used:
        score = 100
        level = 'healthy'
        label = 'Alertmanager Healthy'
        description = 'Alertmanager is connected and used as the primary alert source.'
        icon = 'shield-check'
    elif connected and resolved_source == 'prometheus' and fallback_used:
        score = 60 if alertmanager_configured else 80
        level = 'fallback'
        label = 'Prometheus Fallback Active'
        description = 'Alertmanager is unavailable, but Prometheus ALERTS fallback is connected.'
        icon = 'route'
    elif connected and resolved_source == 'prometheus':
        score = 75
        level = 'degraded'
        label = 'Prometheus Alerts Only'
        description = 'Prometheus ALERTS is connected, but Alertmanager routing, grouping, silence, and inhibition context is not the active source.'
        icon = 'activity'
    elif alertmanager_configured or prometheus_configured:
        score = 40
        level = 'unavailable'
        label = 'Alert Source Unavailable'
        description = 'At least one alert source is configured, but no alert source is currently connected.'
        icon = 'circle-alert'
    else:
        score = 20
        level = 'unavailable'
        label = 'Alert Sources Not Configured'
        description = (
            'Configure Alertmanager as the primary source and Prometheus as fallback before relying on alert analysis.'
        )
        icon = 'plug-zap'

    checks: list[AlertSourceHealthCheck] = [
        {
            'label': 'Cluster selected',
            'status': 'pass',
            'description': f'Cluster {cluster.name} is selected.',
        },
        {
            'label': 'Alertmanager configured',
            'status': 'pass' if alertmanager_configured else 'warning',
            'description': 'Alertmanager endpoint is configured.'
            if alertmanager_configured
            else 'Alertmanager endpoint is not configured.',
        },
        {
            'label': 'Alertmanager connected',
            'status': 'pass' if alertmanager_connected else 'fail',
            'description': 'Alertmanager is connected and can provide alert lifecycle context.'
            if alertmanager_connected
            else 'Alertmanager is not connected for the selected cluster.',
        },
        {
            'label': 'Prometheus evidence connected',
            'status': 'pass' if prometheus_connected else ('warning' if prometheus_configured else 'fail'),
            'description': 'Prometheus alert or anomaly evidence is connected.'
            if prometheus_connected
            else 'Prometheus alert and anomaly evidence is not currently connected.',
        },
        {
            'label': 'Fallback mode active',
            'status': 'warning' if fallback_used else 'pass',
            'description': str(
                source_status.get(
                    'fallback_reason',
                    'Primary source is active; fallback is not being used.',
                )
                or 'Primary source is active; fallback is not being used.'
            ),
        },
    ]

    return {
        'score': score,
        'level': level,
        'label': label,
        'description': description,
        'icon': icon,
        'checks': checks,
        'selected_source': selected_source,
        'resolved_source': resolved_source,
        'fallback_used': fallback_used,
    }
