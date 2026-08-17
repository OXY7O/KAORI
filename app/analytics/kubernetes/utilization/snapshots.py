from __future__ import annotations

from typing import Any

from app.analytics.kubernetes.common.clusters import get_selected_cluster as resolve_selected_cluster
from app.analytics.kubernetes.common.presentation import present_metrics_source_status
from app.analytics.kubernetes.utilization.service import get_utilization_clusters
from app.analytics.shared.coercion import safe_float
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.metrics_sources.consumer import MetricsConsumer


def get_metrics_source_status_snapshot(cluster_id: str) -> dict[str, Any]:
    clusters = get_utilization_clusters()
    cluster = resolve_selected_cluster(clusters, cluster_id or '')
    if not cluster:
        return present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'label': 'Waiting for Cluster',
            }
        )
    try:
        consumer = MetricsConsumer(cluster)
        response = consumer.analytics_status()
    except MetricsSourceError as exc:
        return present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'error': str(exc),
            }
        )

    payload = response.payload if isinstance(response.payload, dict) else {}
    diagnostic = response.diagnostics[0] if not response.ok and response.diagnostics else None
    detail = None
    if not response.ok:
        detail = (
            diagnostic.detail
            if diagnostic is not None and diagnostic.detail
            else (diagnostic.message if diagnostic is not None else 'Metrics Source is unavailable.')
        )
    return present_metrics_source_status(
        {
            'configured': bool(payload.get('configured', True)),
            'connected': response.ok,
            'endpoint': getattr(consumer.config, 'endpoint', ''),
            'response_time_ms': payload.get('response_time_ms'),
            'last_checked_at': payload.get('last_checked_at'),
            'observation_degraded': bool(payload.get('observation_degraded')),
            'last_error': payload.get('last_error'),
            'error': detail,
        }
    )


def get_utilization_snapshot(cluster_id: str, time_range: str = '24h') -> dict[str, float | None] | None:
    _ = time_range
    from app.analytics.kubernetes.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.utilization.summary',
        parameters={'cluster_id': str(cluster_id)},
    )
    summary = (result.context or {}).get('summary') if result.available else None
    if not isinstance(summary, dict):
        return None

    def percent(utilization_key: str, capacity_key: str) -> float | None:
        if capacity_key not in summary or safe_float(summary.get(capacity_key)) <= 0:
            return None
        return round(safe_float(summary.get(utilization_key)), 2)

    return {
        'cpu_percent': percent('cpu_utilization', 'cpu_capacity'),
        'memory_percent': percent('memory_utilization', 'memory_capacity'),
        'storage_percent': percent('storage_utilization', 'storage_capacity'),
        'pod_percent': percent('pod_utilization', 'pod_capacity'),
    }
