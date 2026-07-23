from __future__ import annotations

from typing import Any

from app.analytics.alerts.metrics import get_metric_labels, get_metric_value
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.models import Cluster
from app.prometheus.service import PrometheusService

POD_RESTART_ANOMALY_QUERY = get_query_expression('analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY')
POD_NOT_READY_ANOMALY_QUERY = get_query_expression('analytics.alerts.queries.POD_NOT_READY_ANOMALY_QUERY')


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
) -> list[dict[str, Any]]:
    try:
        service = PrometheusService(
            cluster,
        )

        restart_result = service.instant_query(
            POD_RESTART_ANOMALY_QUERY,
        )

        not_ready_result = service.instant_query(
            POD_NOT_READY_ANOMALY_QUERY,
        )

    except PrometheusError:
        return []
    except Exception:
        return []

    restart_items = restart_result.get(
        'data',
        {},
    ).get(
        'result',
        [],
    )

    if not isinstance(
        restart_items,
        list,
    ):
        restart_items = []

    not_ready_items = not_ready_result.get(
        'data',
        {},
    ).get(
        'result',
        [],
    )

    if not isinstance(
        not_ready_items,
        list,
    ):
        not_ready_items = []

    anomalies: list[dict[str, Any]] = []

    for item in restart_items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        anomaly = normalize_restart_anomaly(
            item,
        )

        if anomaly is not None:
            anomalies.append(
                anomaly,
            )

    for item in not_ready_items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        anomaly = normalize_not_ready_anomaly(
            item,
        )

        if anomaly is not None:
            anomalies.append(
                anomaly,
            )

    return anomalies


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


def build_anomalies(
    *,
    cluster: Cluster | None,
    severity: str,
    namespace: str,
    search: str,
) -> list[dict[str, Any]]:
    if cluster is None:
        return []

    anomalies = load_prometheus_anomaly_metrics(
        cluster=cluster,
    )

    return filter_anomalies(
        anomalies,
        severity=severity,
        namespace=namespace,
        search=search,
    )
