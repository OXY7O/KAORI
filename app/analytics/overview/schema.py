from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def utc_now_display() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')


def build_metric_card(
    *,
    label: str,
    value: str | int | float,
    unit: str = '',
    status: str = 'normal',
    tone: str = 'blue',
    icon: str = 'activity',
    description: str = '',
    href: str = '',
    percent: float | int | None = None,
) -> dict[str, Any]:
    return {
        'label': label,
        'value': value,
        'unit': unit,
        'status': status,
        'tone': tone,
        'icon': icon,
        'description': description,
        'href': href,
        'percent': percent,
    }


def build_empty_overview_payload() -> dict[str, Any]:
    return {
        'clusters': [],
        'selected_cluster': None,
        'selected_cluster_id': '',
        'selected_time_range': '24h',
        'last_analyzed_at': utc_now_display(),
        'prometheus': {
            'configured': False,
            'connected': False,
            'status': 'not_configured',
            'status_label': 'Not configured',
            'status_tone': 'gray',
            'endpoint': '',
            'response_time_ms': None,
            'message': 'Prometheus configuration is not available for this cluster.',
            'last_checked_at': utc_now_display(),
        },
        'health_summary': {
            'cluster_health': build_metric_card(
                label='Cluster Health',
                value='Unknown',
                status='unknown',
                tone='gray',
                icon='shield-question',
                description='Cluster health data is not available yet.',
            ),
            'resource_pressure': build_metric_card(
                label='Resource Pressure',
                value='Unknown',
                status='unknown',
                tone='gray',
                icon='gauge',
                description='Resource pressure data is not available yet.',
            ),
            'capacity_risk': build_metric_card(
                label='Capacity Risk',
                value='Unknown',
                status='unknown',
                tone='gray',
                icon='triangle-alert',
                description='Capacity risk data is not available yet.',
            ),
            'active_alerts': build_metric_card(
                label='Active Alerts',
                value=0,
                status='normal',
                tone='green',
                icon='bell',
                description='No active alert data available.',
            ),
            'forecast_risk': build_metric_card(
                label='Forecast Risk',
                value='Unknown',
                status='unknown',
                tone='gray',
                icon='trending-up',
                description='Forecast data is not available yet.',
            ),
            'top_risk_namespace': build_metric_card(
                label='Top Risk Namespace',
                value='-',
                status='unknown',
                tone='gray',
                icon='folder',
                description='Namespace risk data is not available yet.',
            ),
        },
        'resource_snapshot': {
            'cpu': build_metric_card(
                label='CPU Utilization',
                value=0,
                unit='%',
                status='unknown',
                tone='gray',
                icon='cpu',
                description='CPU utilization data is not available.',
                percent=0,
                href='/analytics/utilization',
            ),
            'memory': build_metric_card(
                label='Memory Utilization',
                value=0,
                unit='%',
                status='unknown',
                tone='gray',
                icon='memory-stick',
                description='Memory utilization data is not available.',
                percent=0,
                href='/analytics/utilization',
            ),
            'storage': build_metric_card(
                label='Storage Utilization',
                value=0,
                unit='%',
                status='unknown',
                tone='gray',
                icon='database',
                description='Storage utilization data is not available.',
                percent=0,
                href='/analytics/storage',
            ),
            'pods': build_metric_card(
                label='Pod Utilization',
                value=0,
                unit='%',
                status='unknown',
                tone='gray',
                icon='boxes',
                description='Pod utilization data is not available.',
                percent=0,
                href='/analytics/utilization',
            ),
        },
        'capacity_snapshot': {
            'cpu_headroom': build_metric_card(
                label='CPU Headroom',
                value='-',
                unit='Cores',
                status='unknown',
                tone='gray',
                icon='cpu',
                description='Remaining worker CPU allocatable capacity.',
                href='/analytics/capacity',
            ),
            'memory_headroom': build_metric_card(
                label='Memory Headroom',
                value='-',
                unit='GiB',
                status='unknown',
                tone='gray',
                icon='memory-stick',
                description='Remaining worker memory allocatable capacity.',
                href='/analytics/capacity',
            ),
            'pod_capacity_remaining': build_metric_card(
                label='Pod Capacity Remaining',
                value='-',
                unit='Pods',
                status='unknown',
                tone='gray',
                icon='box',
                description='Available pod slots across worker nodes.',
                href='/analytics/capacity',
            ),
            'recommendations': build_metric_card(
                label='Capacity Recommendations',
                value=0,
                unit='Items',
                status='normal',
                tone='blue',
                icon='lightbulb',
                description='Capacity findings that need review.',
                href='/analytics/capacity',
            ),
        },
        'storage_snapshot': {
            'pvc_requested': '0 GiB',
            'pvc_used': '0 GiB',
            'pvc_free': '0 GiB',
            'pvc_risk_count': 0,
            'used_percent': 0,
            'free_percent': 0,
            'top_namespace': '-',
            'status': 'unknown',
            'tone': 'gray',
            'href': '/analytics/storage',
            'recommendation_count': 0,
        },
        'workload_snapshot': {
            'missing_cpu_requests': 0,
            'missing_memory_requests': 0,
            'missing_cpu_limits': 0,
            'missing_memory_limits': 0,
            'over_provisioned': 0,
            'under_provisioned': 0,
            'status': 'unknown',
            'tone': 'gray',
            'href': '/analytics/workload',
            'recommendation_count': 0,
        },
        'top_consumers': {
            'cpu': [],
            'memory': [],
            'storage': [],
            'href': '/analytics/top-consumers',
            'recommendation_count': 0,
        },
        'forecast_snapshot': {
            'cpu_trend': 'Unknown',
            'memory_trend': 'Unknown',
            'storage_trend': 'Unknown',
            'pod_trend': 'Unknown',
            'risk_count': 0,
            'risk_note': 'Forecast data is not available yet.',
            'series': [],
            'href': '/analytics/forecast',
            'recommendation_count': 0,
        },
        'alerts_snapshot': {
            'firing_alerts': 0,
            'pending_alerts': 0,
            'critical_alerts': 0,
            'warning_alerts': 0,
            'recent_anomalies': 0,
            'highest_severity': '-',
            'highest_severity_description': 'No alert data available.',
            'status': 'unknown',
            'tone': 'gray',
            'href': '/analytics/alerts-anomalies',
            'source_connected': False,
            'recommendation_count': 0,
        },
        'actionable_recommendations': {
            'total_count': 0,
            'status': 'Normal',
            'tone': 'green',
            'description': 'No actionable recommendation detected across analytics domains.',
            'sources': [],
            'priority_summary': {
                'critical': 0,
                'warning': 0,
            },
            'items': [],
            'capacity_recommendations': [],
            'utilization_recommendations': [],
        },
        'actionable_recommendation_count': 0,
        'recommendations': [],
    }


def classify_percent(value: float | int | None) -> dict[str, str]:
    if value is None:
        return {
            'status': 'unknown',
            'tone': 'gray',
            'label': 'Unknown',
        }

    percent = float(value)

    if percent >= 90:
        return {
            'status': 'critical',
            'tone': 'red',
            'label': 'Critical',
        }

    if percent >= 75:
        return {
            'status': 'warning',
            'tone': 'amber',
            'label': 'Warning',
        }

    return {
        'status': 'normal',
        'tone': 'green',
        'label': 'Normal',
    }


def classify_count_risk(value: int | None) -> dict[str, str]:
    if value is None:
        return {
            'status': 'unknown',
            'tone': 'gray',
            'label': 'Unknown',
        }

    if value >= 5:
        return {
            'status': 'critical',
            'tone': 'red',
            'label': 'Critical',
        }

    if value > 0:
        return {
            'status': 'warning',
            'tone': 'amber',
            'label': 'Warning',
        }

    return {
        'status': 'normal',
        'tone': 'green',
        'label': 'Normal',
    }
