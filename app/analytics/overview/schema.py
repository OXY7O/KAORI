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
        'prometheus': _empty_prometheus(),
        'snapshot_summary': _empty_snapshot_summary(),
        'health_summary': _empty_health_summary(),
        'resource_snapshot': _empty_resource_snapshot(),
        'capacity_snapshot': _empty_capacity_snapshot(),
        'storage_snapshot': _empty_storage_snapshot(),
        'workload_snapshot': _empty_workload_snapshot(),
        'top_consumers': _empty_top_consumers(),
        'forecast_snapshot': _empty_forecast_snapshot(),
        'alerts_snapshot': _empty_alerts_snapshot(),
        'actionable_recommendations': _empty_actionable_recommendations(),
        'actionable_recommendation_count': 0,
        'recommendations': [],
    }


def _empty_prometheus() -> dict[str, Any]:
    return {
        'configured': False,
        'connected': False,
        'status': 'not_configured',
        'status_label': 'Not configured',
        'status_tone': 'gray',
        'endpoint': '',
        'response_time_ms': None,
        'message': 'Prometheus configuration is not available for this cluster.',
        'last_checked_at': utc_now_display(),
    }


def _empty_snapshot_summary() -> dict[str, Any]:
    return {
        'status': 'Unavailable',
        'tone': 'unknown',
        'description': 'No committed Analytics Overview snapshot is available for this cluster.',
        'latest_generated_at': 'Not Available',
        'latest_attempt_at': 'Not Available',
        'latest_dataset': 'No Snapshot',
        'current_dataset_count': 0,
        'available_dataset_count': 0,
        'expected_dataset_count': 7,
        'stale_dataset_count': 0,
        'pending_dataset_count': 0,
        'failed_dataset_count': 0,
        'missing_dataset_count': 7,
        'datasets': {},
        'analysis_window': 'Last 24 Hours',
    }


def _empty_health_summary() -> dict[str, Any]:
    definitions = [
        ('cluster_health', 'Cluster Health', 'Unknown', 'shield-question', 'Cluster health data is not available yet.'),
        ('resource_pressure', 'Resource Pressure', 'Unknown', 'gauge', 'Resource pressure data is not available yet.'),
        ('capacity_risk', 'Capacity Risk', 'Unknown', 'triangle-alert', 'Capacity risk data is not available yet.'),
        ('active_alerts', 'Active Alerts', 'N/A', 'bell', 'Active alert evidence is not available yet.'),
        ('forecast_risk', 'Forecast Risk', 'Unknown', 'trending-up', 'Forecast data is not available yet.'),
        ('top_risk_namespace', 'Top Risk Namespace', '-', 'folder', 'Namespace risk data is not available yet.'),
    ]
    return {
        key: build_metric_card(
            label=label,
            value=value,
            status='unknown',
            tone='gray',
            icon=icon,
            description=description,
        )
        for key, label, value, icon, description in definitions
    }


def _empty_resource_snapshot() -> dict[str, Any]:
    definitions = {
        'cpu': ('CPU Utilization', 'cpu', 'CPU utilization data is not available.', '/analytics/utilization'),
        'memory': ('Memory Utilization', 'memory-stick', 'Memory utilization data is not available.', '/analytics/utilization'),
        'storage': ('Storage Utilization', 'database', 'Storage utilization data is not available.', '/analytics/storage'),
        'pods': ('Pod Utilization', 'boxes', 'Pod utilization data is not available.', '/analytics/utilization'),
    }
    return {
        'available': False,
        **{
            key: build_metric_card(
                label=label,
                value='N/A',
                unit='%',
                status='unknown',
                tone='gray',
                icon=icon,
                description=description,
                percent=None,
                href=href,
            )
            for key, (label, icon, description, href) in definitions.items()
        },
    }


def _empty_capacity_snapshot() -> dict[str, Any]:
    definitions = {
        'cpu_headroom': ('CPU Headroom', 'Cores', 'cpu', 'Remaining worker CPU allocatable capacity.'),
        'memory_headroom': ('Memory Headroom', 'GiB', 'memory-stick', 'Remaining worker memory allocatable capacity.'),
        'pod_capacity_remaining': ('Pod Capacity Remaining', 'Pods', 'box', 'Available pod slots across worker nodes.'),
        'recommendations': ('Capacity Recommendations', 'Items', 'lightbulb', 'Capacity findings that need review.'),
    }
    return {
        'available': False,
        **{
            key: build_metric_card(
                label=label,
                value='N/A' if key == 'recommendations' else '-',
                unit=unit,
                status='unknown',
                tone='gray',
                icon=icon,
                description=description,
                href='/analytics/capacity',
            )
            for key, (label, unit, icon, description) in definitions.items()
        },
    }


def _empty_storage_snapshot() -> dict[str, Any]:
    return {
        'available': False,
        'pressure_available': False,
        'pvc_requested': 'N/A',
        'pvc_capacity': 'N/A',
        'pvc_used': 'N/A',
        'pvc_free': 'N/A',
        'pvc_risk_count': 0,
        'used_percent': None,
        'free_percent': None,
        'top_namespace': '-',
        'status': 'unknown',
        'tone': 'gray',
        'href': '/analytics/storage',
        'recommendation_count': 0,
    }


def _empty_workload_snapshot() -> dict[str, Any]:
    return {
        'available': False,
        'missing_cpu_requests': 0,
        'missing_memory_requests': 0,
        'cpu_limits_unset': 0,
        'memory_limits_missing': 0,
        'over_provisioned': 0,
        'under_provisioned': 0,
        'status': 'unknown',
        'tone': 'gray',
        'href': '/analytics/workload',
        'recommendation_count': 0,
    }


def _empty_top_consumers() -> dict[str, Any]:
    return {
        'available': False,
        'cpu': [],
        'memory': [],
        'storage': [],
        'pods': [],
        'href': '/analytics/top-consumers',
        'recommendation_count': 0,
    }


def _empty_forecast_snapshot() -> dict[str, Any]:
    return {
        'available': False,
        'cpu_trend': 'Unknown',
        'memory_trend': 'Unknown',
        'storage_trend': 'Unknown',
        'pod_trend': 'Unknown',
        'risk_count': 0,
        'risk_note': 'Forecast data is not available yet.',
        'forecast_risk': 'Unknown',
        'forecast_horizon': '30 Days',
        'highest_projected_resource': 'N/A',
        'highest_projected_percent': None,
        'series': [],
        'href': '/analytics/forecast',
        'recommendation_count': 0,
    }


def _empty_alerts_snapshot() -> dict[str, Any]:
    return {
        'available': False,
        'firing_alerts': 0,
        'pending_alerts': 0,
        'critical_alerts': 0,
        'warning_alerts': 0,
        'recent_anomalies': 0,
        'highest_severity': 'Unknown',
        'highest_severity_description': 'No committed alert data is available.',
        'status': 'Unknown',
        'tone': 'unknown',
        'evidence_complete': False,
        'anomaly_evidence_partial': False,
        'href': '/analytics/alerts?tab=alerts',
        'source_connected': False,
        'recommendation_count': 0,
    }


def _empty_actionable_recommendations() -> dict[str, Any]:
    return {
        'total_count': 0,
        'status': 'Unknown',
        'tone': 'gray',
        'description': 'Committed analytics evidence is not available for recommendation assessment.',
        'evidence_available': False,
        'evidence_complete': False,
        'available_dataset_count': 0,
        'expected_dataset_count': 7,
        'sources': [],
        'priority_summary': {'critical': 0, 'warning': 0},
        'items': [],
        'capacity_recommendations': [],
        'utilization_recommendations': [],
        'storage_recommendations': [],
        'workload_recommendations': [],
        'forecast_recommendations': [],
        'top_consumers_recommendations': [],
        'alerts_recommendations': [],
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
