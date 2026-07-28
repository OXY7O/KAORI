from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.analytics.alerts.metrics import get_metric_labels, get_metric_value
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.models import Cluster
from app.prometheus.service import PrometheusService

POD_RESTART_ANOMALY_QUERY = get_query_expression('analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY')
POD_NOT_READY_ANOMALY_QUERY = get_query_expression('analytics.alerts.queries.POD_NOT_READY_ANOMALY_QUERY')
logger = logging.getLogger(__name__)


def normalize_restart_anomaly(
    item: dict[str, Any],
) -> dict[str, Any] | None:
    metric = get_metric_labels(
        item,
    )

    restart_count = get_metric_value(
        item,
    )

    if restart_count <= 0:
        return None

    namespace = str(
        metric.get(
            'namespace',
            '-',
        )
    )

    pod = str(
        metric.get(
            'pod',
            '-',
        )
    )

    rounded_restart_count = round(
        restart_count,
        2,
    )

    severity = 'critical' if restart_count >= 5 else 'warning'

    restart_label = (
        str(
            int(
                restart_count,
            )
        )
        if restart_count.is_integer()
        else str(
            rounded_restart_count,
        )
    )

    return {
        'name': 'Pod Restart Spike',
        'severity': severity,
        'namespace': namespace,
        'target': pod,
        'signal': f'{restart_label} restarts / 15m',
        'summary': 'Pod restarted recently',
        'description': (
            f'Pod {pod} in namespace {namespace} restarted '
            f'{restart_label} time(s) within the last 15 minutes. '
            'Review container logs, recent rollout activity, probes, '
            'resource limits, and dependency availability.'
        ),
        'source': 'Prometheus',
        'labels': metric,
        'value': restart_count,
    }


def normalize_not_ready_anomaly(
    item: dict[str, Any],
) -> dict[str, Any] | None:
    metric = get_metric_labels(
        item,
    )

    value = get_metric_value(
        item,
    )

    if value < 1:
        return None

    namespace = str(
        metric.get(
            'namespace',
            '-',
        )
    )

    pod = str(
        metric.get(
            'pod',
            '-',
        )
    )

    return {
        'name': 'Pod Not Ready',
        'severity': 'warning',
        'namespace': namespace,
        'target': pod,
        'signal': 'readiness=false',
        'summary': 'Pod readiness check is failing',
        'description': (
            f'Pod {pod} in namespace {namespace} is currently not ready. '
            'Review pod events, readiness probes, container state, service '
            'endpoints, and recent rollout status.'
        ),
        'source': 'Prometheus',
        'labels': metric,
        'value': value,
    }


def load_prometheus_anomaly_metrics(
    *,
    cluster: Cluster,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load optional Prometheus anomaly candidates with explicit source status.

    Alertmanager alerts remain usable when this optional Prometheus query fails,
    but the worker snapshot and UI must expose the partial-data condition instead
    of silently presenting an empty anomaly list as a healthy result.
    """

    started = perf_counter()
    try:
        service = PrometheusService(cluster)
        restart_result = service.instant_query(POD_RESTART_ANOMALY_QUERY)
        not_ready_result = service.instant_query(POD_NOT_READY_ANOMALY_QUERY)
    except PrometheusError as exc:
        elapsed_ms = max(int((perf_counter() - started) * 1000), 0)
        logger.warning(
            'Prometheus anomaly candidate collection failed for cluster %s: %s',
            cluster.id,
            exc,
            extra={
                'cluster_id': str(cluster.id),
                'analytics_component': 'alert_anomaly_candidates',
                'error': str(exc)[:1000],
            },
        )
        return [], {
            'connected': False,
            'label': 'Anomaly Signals Unavailable',
            'error': str(exc),
            'response_time_ms': elapsed_ms,
            'partial': True,
        }
    except Exception as exc:
        elapsed_ms = max(int((perf_counter() - started) * 1000), 0)
        logger.exception(
            'Unexpected Prometheus anomaly candidate collection failure for cluster %s.',
            cluster.id,
            extra={
                'cluster_id': str(cluster.id),
                'analytics_component': 'alert_anomaly_candidates',
            },
        )
        return [], {
            'connected': False,
            'label': 'Anomaly Signal Error',
            'error': str(exc) or exc.__class__.__name__,
            'response_time_ms': elapsed_ms,
            'partial': True,
        }

    restart_items = restart_result.get('data', {}).get('result', [])
    if not isinstance(restart_items, list):
        restart_items = []
    not_ready_items = not_ready_result.get('data', {}).get('result', [])
    if not isinstance(not_ready_items, list):
        not_ready_items = []

    anomalies: list[dict[str, Any]] = []
    for item in restart_items:
        if isinstance(item, dict) and (anomaly := normalize_restart_anomaly(item)) is not None:
            anomalies.append(anomaly)
    for item in not_ready_items:
        if isinstance(item, dict) and (anomaly := normalize_not_ready_anomaly(item)) is not None:
            anomalies.append(anomaly)

    return anomalies, {
        'connected': True,
        'label': 'Anomaly Signals Available',
        'error': None,
        'response_time_ms': max(int((perf_counter() - started) * 1000), 0),
        'partial': False,
    }


def filter_anomalies(
    anomalies: list[dict[str, Any]],
    *,
    severity: str,
    namespace: str,
    search: str,
) -> list[dict[str, Any]]:
    filtered = anomalies

    if severity != 'all':
        filtered = [
            item
            for item in filtered
            if str(
                item.get(
                    'severity',
                    '',
                )
            ).lower()
            == severity
        ]

    if namespace:
        namespace_query = namespace.lower()

        filtered = [
            item
            for item in filtered
            if namespace_query
            in str(
                item.get(
                    'namespace',
                    '',
                )
            ).lower()
        ]

    if search:
        search_query = search.lower()

        filtered = [
            item
            for item in filtered
            if search_query
            in ' '.join(
                [
                    str(
                        item.get(
                            'name',
                            '',
                        )
                    ),
                    str(
                        item.get(
                            'namespace',
                            '',
                        )
                    ),
                    str(
                        item.get(
                            'target',
                            '',
                        )
                    ),
                    str(
                        item.get(
                            'signal',
                            '',
                        )
                    ),
                    str(
                        item.get(
                            'summary',
                            '',
                        )
                    ),
                    str(
                        item.get(
                            'description',
                            '',
                        )
                    ),
                ]
            ).lower()
        ]

    return filtered
