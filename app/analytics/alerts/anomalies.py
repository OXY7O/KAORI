from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.analytics.alerts.metrics import get_metric_labels, get_metric_value
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.models import Cluster
from app.prometheus.repository import resolve_instance_for_cluster
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


def _query_anomaly_candidates(
    *,
    service: PrometheusService,
    cluster: Cluster,
    query: str,
    signal_name: str,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = service.instant_query(query)
    except PrometheusError as exc:
        logger.warning(
            'Prometheus %s anomaly collection failed for cluster %s: %s',
            signal_name,
            cluster.id,
            exc,
            extra={
                'cluster_id': str(cluster.id),
                'analytics_component': 'alert_anomaly_candidates',
                'anomaly_signal': signal_name,
                'error': str(exc)[:1000],
            },
        )
        return [], str(exc) or exc.__class__.__name__
    items = result.get('data', {}).get('result', [])
    return (items if isinstance(items, list) else []), None


def _anomaly_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get('name') or '').strip().lower(),
        str(item.get('namespace') or '').strip().lower(),
        str(item.get('target') or '').strip().lower(),
    )


def deduplicate_anomalies(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []
    severity_rank = {'critical': 3, 'warning': 2, 'info': 1}
    for item in items:
        identity = _anomaly_identity(item)
        current = selected.get(identity)
        if current is None:
            order.append(identity)
            selected[identity] = item
            continue
        current_priority = (
            severity_rank.get(str(current.get('severity') or '').lower(), 0),
            float(current.get('value') or 0),
        )
        item_priority = (
            severity_rank.get(str(item.get('severity') or '').lower(), 0),
            float(item.get('value') or 0),
        )
        if item_priority > current_priority:
            selected[identity] = item
    return [selected[identity] for identity in order]


def load_prometheus_anomaly_metrics(
    *,
    cluster: Cluster,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect restart and readiness candidates independently.

    One failed optional query no longer discards the successful signal family.
    The returned status makes partial evidence explicit to the snapshot and UI.
    """

    started = perf_counter()
    configured = resolve_instance_for_cluster(cluster.id) is not None
    if not configured:
        return [], {
            'configured': False,
            'connected': False,
            'label': 'Anomaly Signals Not Configured',
            'error': 'No canonical Prometheus runtime is bound to this Kubernetes cluster.',
            'response_time_ms': max(int((perf_counter() - started) * 1000), 0),
            'partial': True,
            'available_queries': [],
            'failed_queries': ['restart', 'readiness'],
        }

    try:
        service = PrometheusService(cluster)
    except PrometheusError as exc:
        logger.warning(
            'Prometheus anomaly source resolution failed for cluster %s: %s',
            cluster.id,
            exc,
            extra={
                'cluster_id': str(cluster.id),
                'analytics_component': 'alert_anomaly_candidates',
                'error': str(exc)[:1000],
            },
        )
        return [], {
            'configured': True,
            'connected': False,
            'label': 'Anomaly Signals Unavailable',
            'error': str(exc) or exc.__class__.__name__,
            'response_time_ms': max(int((perf_counter() - started) * 1000), 0),
            'partial': True,
            'available_queries': [],
            'failed_queries': ['restart', 'readiness'],
        }

    restart_items, restart_error = _query_anomaly_candidates(
        service=service,
        cluster=cluster,
        query=POD_RESTART_ANOMALY_QUERY,
        signal_name='restart',
    )
    not_ready_items, readiness_error = _query_anomaly_candidates(
        service=service,
        cluster=cluster,
        query=POD_NOT_READY_ANOMALY_QUERY,
        signal_name='readiness',
    )

    anomalies: list[dict[str, Any]] = []
    for item in restart_items:
        if isinstance(item, dict) and (anomaly := normalize_restart_anomaly(item)) is not None:
            anomalies.append(anomaly)
    for item in not_ready_items:
        if isinstance(item, dict) and (anomaly := normalize_not_ready_anomaly(item)) is not None:
            anomalies.append(anomaly)

    errors = {name: error for name, error in (('restart', restart_error), ('readiness', readiness_error)) if error}
    available_queries = [
        name for name, error in (('restart', restart_error), ('readiness', readiness_error)) if not error
    ]
    partial = bool(errors)
    connected = bool(available_queries)
    error_message = '; '.join(f'{name}: {error}' for name, error in errors.items()) or None
    if connected and partial:
        label = 'Anomaly Signals Partially Available'
    elif connected:
        label = 'Anomaly Signals Available'
    else:
        label = 'Anomaly Signals Unavailable'

    return deduplicate_anomalies(anomalies), {
        'configured': configured,
        'connected': connected,
        'label': label,
        'error': error_message,
        'response_time_ms': max(int((perf_counter() - started) * 1000), 0),
        'partial': partial,
        'available_queries': available_queries,
        'failed_queries': sorted(errors),
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

        filtered = [item for item in filtered if str(item.get('namespace', '')).strip().lower() == namespace_query]

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
