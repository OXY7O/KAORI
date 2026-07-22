from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from time import perf_counter
from typing import Any

from app.alertmanager.service import (
    get_alertmanager_alerts,
    get_alertmanager_silences,
    get_alertmanager_status,
)
from app.integrations.prometheus.query_profiles import get_query_expression
from app.common.dependencies import (
    alert_source_connection_blocker,
    alert_source_setup_blocker,
    cluster_required_blocker,
)
from app.extensions import db
from app.intelligence.recommendation_engine import (
    build_alerts_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster, NamespaceInventory
from app.integrations.prometheus.exceptions import PrometheusError
from app.prometheus.repository import resolve_instance_for_cluster
from app.prometheus.service import PrometheusService

PROMETHEUS_ALERTS_QUERY = get_query_expression(
    'analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY'
)
POD_RESTART_ANOMALY_QUERY = get_query_expression(
    'analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY'
)
POD_NOT_READY_ANOMALY_QUERY = get_query_expression(
    'analytics.alerts.queries.POD_NOT_READY_ANOMALY_QUERY'
)

DEFAULT_PER_PAGE = 5

PER_PAGE_OPTIONS = [
    5,
    10,
    25,
    50,
]

SOURCE_OPTIONS = [
    'auto',
    'alertmanager',
    'prometheus',
]

SEVERITY_OPTIONS = [
    'all',
    'critical',
    'warning',
    'info',
    'none',
]

STATUS_OPTIONS = [
    'all',
    'firing',
    'pending',
    'resolved',
    'active',
]


@dataclass(frozen=True)
class AlertsPagination:
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_prev: bool
    has_next: bool
    prev_page: int
    next_page: int
    start_item: int
    end_item: int


def normalize_page(
    value: str | int | None,
) -> int:
    try:
        page = int(
            value or 1,
        )
    except (
        TypeError,
        ValueError,
    ):
        return 1

    return max(
        page,
        1,
    )


def normalize_per_page(
    value: str | int | None,
) -> int:
    try:
        per_page = int(
            value or DEFAULT_PER_PAGE,
        )
    except (
        TypeError,
        ValueError,
    ):
        return DEFAULT_PER_PAGE

    if per_page not in PER_PAGE_OPTIONS:
        return DEFAULT_PER_PAGE

    return per_page


def normalize_string(
    value: str | None,
    *,
    default: str = '',
) -> str:
    return (value or default).strip()


def normalize_option(
    value: str | None,
    *,
    allowed: list[str],
    default: str,
) -> str:
    normalized = (value or default).strip().lower()

    if normalized not in allowed:
        return default

    return normalized


def build_pagination(
    *,
    page: int,
    per_page: int,
    total_items: int,
) -> AlertsPagination:
    total_pages = max(
        ceil(
            total_items / per_page,
        ),
        1,
    )

    page = min(
        page,
        total_pages,
    )

    if total_items == 0:
        start_item = 0
        end_item = 0
    else:
        start_item = ((page - 1) * per_page) + 1
        end_item = min(
            page * per_page,
            total_items,
        )

    return AlertsPagination(
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        prev_page=max(
            page - 1,
            1,
        ),
        next_page=min(
            page + 1,
            total_pages,
        ),
        start_item=start_item,
        end_item=end_item,
    )


def paginate_items(
    items: list[dict[str, Any]],
    *,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], AlertsPagination]:
    pagination = build_pagination(
        page=page,
        per_page=per_page,
        total_items=len(
            items,
        ),
    )

    start = (pagination.page - 1) * pagination.per_page
    end = start + pagination.per_page

    return items[start:end], pagination


def get_clusters_for_filter() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(), Cluster.id.asc(),
    ).all()


def get_selected_cluster(
    *,
    cluster_id: str | None,
) -> Cluster | None:
    if cluster_id:
        cluster = db.session.get(
            Cluster,
            cluster_id,
        )

        if cluster is not None:
            return cluster

    return Cluster.query.order_by(
        Cluster.name,
    ).first()


def get_namespace_options(
    *,
    cluster: Cluster | None,
) -> list[str]:
    if cluster is None:
        return []

    namespaces = (
        NamespaceInventory.query.filter_by(
            cluster_id=cluster.id,
        )
        .order_by(
            NamespaceInventory.namespace,
        )
        .all()
    )

    return [namespace.namespace for namespace in namespaces if namespace.namespace]


def get_metric_value(
    item: dict[str, Any],
) -> float:
    value = item.get(
        'value',
        [],
    )

    if not isinstance(
        value,
        list,
    ):
        return 0.0

    if (
        len(
            value,
        )
        < 2
    ):
        return 0.0

    try:
        return float(
            value[1],
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def get_metric_labels(
    item: dict[str, Any],
) -> dict[str, Any]:
    metric = item.get(
        'metric',
        {},
    )

    if isinstance(
        metric,
        dict,
    ):
        return metric

    return {}


def build_empty_source_status(
    *,
    source: str,
    message: str,
) -> dict[str, Any]:
    return {
        'source': source,
        'selected_source': source,
        'resolved_source': 'none',
        'label': message,
        'configured': False,
        'connected': False,
        'fallback_used': False,
        'fallback_reason': None,
        'error': message,
        'response_time_ms': None,
        'last_checked_at': None,
    }


def format_alert_datetime(
    value: Any,
) -> str:
    if value is None:
        return '-'

    text_value = str(
        value,
    ).strip()

    if not text_value or text_value == '-':
        return '-'

    try:
        normalized_value = text_value.replace(
            'Z',
            '+00:00',
        )

        parsed_value = datetime.fromisoformat(
            normalized_value,
        )

        return parsed_value.strftime(
            '%Y-%m-%d %H:%M',
        )
    except ValueError:
        return text_value[:16]


def normalize_alertmanager_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    labels = item.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    annotations = item.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    status_payload = item.get(
        'status',
        {},
    )

    if not isinstance(
        status_payload,
        dict,
    ):
        status_payload = {}

    starts_at = item.get(
        'starts_at',
    ) or item.get(
        'startsAt',
    )

    ends_at = item.get(
        'ends_at',
    ) or item.get(
        'endsAt',
    )

    alert_name = (
        item.get(
            'alertname',
        )
        or labels.get(
            'alertname',
        )
        or item.get(
            'name',
        )
        or 'Unknown Alert'
    )

    severity = (
        item.get(
            'severity',
        )
        or labels.get(
            'severity',
        )
        or 'none'
    )

    status = (
        item.get(
            'status',
        )
        if isinstance(
            item.get(
                'status',
            ),
            str,
        )
        else status_payload.get(
            'state',
            'active',
        )
    )

    namespace = (
        item.get(
            'namespace',
        )
        or labels.get(
            'namespace',
        )
        or '-'
    )

    target = (
        item.get(
            'pod',
        )
        or labels.get(
            'pod',
        )
        or labels.get(
            'node',
        )
        or labels.get(
            'instance',
        )
        or labels.get(
            'job',
        )
        or '-'
    )

    summary = (
        item.get(
            'summary',
        )
        or annotations.get(
            'summary',
        )
        or annotations.get(
            'message',
        )
        or '-'
    )

    description = (
        item.get(
            'description',
        )
        or annotations.get(
            'description',
        )
        or summary
    )

    return {
        'name': alert_name,
        'severity': str(
            severity or 'none',
        ).lower(),
        'status': str(
            status or 'active',
        ).lower(),
        'namespace': namespace,
        'target': target,
        'source': 'Alertmanager',
        'summary': summary,
        'description': description,
        'starts_at': starts_at or '-',
        'starts_at_display': format_alert_datetime(
            starts_at,
        ),
        'ends_at': ends_at or '-',
        'ends_at_display': format_alert_datetime(
            ends_at,
        ),
        'labels': labels,
        'annotations': annotations,
        'generator_url': item.get(
            'generatorURL',
        )
        or item.get(
            'generator_url',
        )
        or '',
        'fingerprint': item.get(
            'fingerprint',
            '',
        ),
        'receiver': item.get(
            'receiver',
            '-',
        ),
        'owner': extract_alert_owner_from_payload(
            labels=labels,
            annotations=annotations,
            fallback_namespace=namespace,
        ),
        'runbook_url': extract_alert_runbook_from_payload(
            annotations=annotations,
        ),
        'contact': extract_alert_contact_from_payload(
            labels=labels,
            annotations=annotations,
        ),
        'silenced': bool(
            item.get(
                'silenced',
                False,
            )
        )
        or bool(
            status_payload.get(
                'silencedBy',
                [],
            )
        ),
        'inhibited': bool(
            item.get(
                'inhibited',
                False,
            )
        )
        or bool(
            status_payload.get(
                'inhibitedBy',
                [],
            )
        ),
        'silenced_by': item.get(
            'silenced_by',
            status_payload.get(
                'silencedBy',
                [],
            ),
        ),
        'inhibited_by': item.get(
            'inhibited_by',
            status_payload.get(
                'inhibitedBy',
                [],
            ),
        ),
    }


def normalize_prometheus_alert(
    item: dict[str, Any],
) -> dict[str, Any]:
    metric = get_metric_labels(
        item,
    )

    alert_value = '-'

    value = item.get(
        'value',
        [],
    )

    if (
        isinstance(
            value,
            list,
        )
        and len(
            value,
        )
        >= 2
    ):
        alert_value = str(
            value[1],
        )

    alert_name = metric.get(
        'alertname',
        'Unknown Alert',
    )

    severity = metric.get(
        'severity',
        'none',
    )

    status = metric.get(
        'alertstate',
        'firing',
    )

    namespace = metric.get(
        'namespace',
        '-',
    )

    target = (
        metric.get(
            'pod',
        )
        or metric.get(
            'node',
        )
        or metric.get(
            'instance',
        )
        or metric.get(
            'job',
        )
        or '-'
    )

    return {
        'name': alert_name,
        'severity': str(
            severity or 'none',
        ).lower(),
        'status': str(
            status or 'firing',
        ).lower(),
        'namespace': namespace,
        'target': target,
        'source': 'Prometheus',
        'summary': metric.get(
            'alertname',
            alert_name,
        ),
        'description': 'Alert loaded from Prometheus ALERTS metric.',
        'starts_at': '-',
        'starts_at_display': '-',
        'ends_at': '-',
        'ends_at_display': '-',
        'labels': metric,
        'annotations': {},
        'owner': extract_alert_owner_from_payload(
            labels=metric,
            annotations={},
            fallback_namespace=namespace,
        ),
        'runbook_url': '',
        'contact': extract_alert_contact_from_payload(
            labels=metric,
            annotations={},
        ),
        'generator_url': '',
        'fingerprint': '',
        'value': alert_value,
    }


def load_alertmanager_alerts(
    *,
    cluster: Cluster,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started_at = perf_counter()

    result = get_alertmanager_alerts(
        cluster_id=cluster.id,
    )

    elapsed_ms = int((perf_counter() - started_at) * 1000)

    alerts = [
        normalize_alertmanager_item(
            item,
        )
        for item in result.get(
            'alerts',
            [],
        )
        if isinstance(
            item,
            dict,
        )
    ]

    status = get_alertmanager_status(
        cluster_id=cluster.id,
    )

    connected = bool(
        result.get(
            'connected',
        )
    )

    source_status = {
        'source': 'alertmanager',
        'selected_source': 'alertmanager',
        'resolved_source': 'alertmanager' if connected else 'none',
        'label': 'Alertmanager Connected'
        if connected
        else status.get(
            'label',
            'Alertmanager Unavailable',
        ),
        'configured': bool(
            status.get(
                'configured',
            )
        )
        or connected,
        'connected': connected,
        'fallback_used': False,
        'fallback_reason': None,
        'error': result.get(
            'error',
        ),
        'response_time_ms': elapsed_ms,
        'last_checked_at': datetime.now(
            UTC,
        ),
    }

    return alerts, source_status


def load_prometheus_alerts(
    *,
    cluster: Cluster,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        service = PrometheusService(
            cluster,
        )

        started_at = perf_counter()

        result = service.instant_query(
            PROMETHEUS_ALERTS_QUERY,
        )

        elapsed_ms = int((perf_counter() - started_at) * 1000)

        raw_items = result.get(
            'data',
            {},
        ).get(
            'result',
            [],
        )

        if not isinstance(
            raw_items,
            list,
        ):
            raw_items = []

        alerts = [
            normalize_prometheus_alert(
                item,
            )
            for item in raw_items
            if isinstance(
                item,
                dict,
            )
        ]

        return alerts, {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'prometheus',
            'label': 'Prometheus Connected',
            'configured': True,
            'connected': True,
            'fallback_used': False,
            'fallback_reason': None,
            'error': None,
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(
                UTC,
            ),
        }

    except PrometheusError as exc:
        return [], {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'none',
            'label': 'Prometheus Unavailable',
            'configured': False,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': str(
                exc,
            ),
            'response_time_ms': None,
            'last_checked_at': None,
        }
    except Exception as exc:
        return [], {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'none',
            'label': 'Prometheus Error',
            'configured': True,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': str(
                exc,
            ),
            'response_time_ms': None,
            'last_checked_at': None,
        }


def get_source_status_message(
    status: dict[str, Any],
    *,
    default: str,
) -> str:
    error = status.get(
        'error',
    )

    if (
        isinstance(
            error,
            str,
        )
        and error
    ):
        return error

    label = status.get(
        'label',
    )

    if (
        isinstance(
            label,
            str,
        )
        and label
    ):
        return label

    return default


def load_alerts_by_source(
    *,
    cluster: Cluster | None,
    source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if cluster is None:
        return [], build_empty_source_status(
            source=source,
            message='No cluster available.',
        )

    if source == 'alertmanager':
        return load_alertmanager_alerts(
            cluster=cluster,
        )

    if source == 'prometheus':
        return load_prometheus_alerts(
            cluster=cluster,
        )

    alertmanager_alerts, alertmanager_status = load_alertmanager_alerts(
        cluster=cluster,
    )

    alertmanager_status['selected_source'] = 'auto'

    if alertmanager_status.get(
        'connected',
    ):
        alertmanager_status['fallback_used'] = False
        alertmanager_status['fallback_reason'] = None

        return alertmanager_alerts, alertmanager_status

    prometheus_alerts, prometheus_status = load_prometheus_alerts(
        cluster=cluster,
    )

    alertmanager_reason = get_source_status_message(
        alertmanager_status,
        default='Alertmanager is unavailable.',
    )

    prometheus_status['selected_source'] = 'auto'
    prometheus_status['fallback_used'] = True
    prometheus_status['fallback_reason'] = (
        f'Alertmanager unavailable: {alertmanager_reason}. Using Prometheus ALERTS fallback.'
    )

    if prometheus_status.get(
        'connected',
    ):
        prometheus_status['label'] = 'Prometheus Fallback Connected'
        prometheus_status['error'] = None

        return prometheus_alerts, prometheus_status

    prometheus_reason = get_source_status_message(
        prometheus_status,
        default='Prometheus fallback is unavailable.',
    )

    return [], {
        'source': 'auto',
        'selected_source': 'auto',
        'resolved_source': 'none',
        'label': 'Alert Sources Unavailable',
        'configured': bool(
            alertmanager_status.get(
                'configured',
                False,
            )
        )
        or bool(
            prometheus_status.get(
                'configured',
                False,
            )
        ),
        'connected': False,
        'fallback_used': True,
        'fallback_reason': (f'Alertmanager unavailable: {alertmanager_reason}. Prometheus fallback also unavailable.'),
        'error': f'{alertmanager_reason} | {prometheus_reason}',
        'response_time_ms': None,
        'last_checked_at': datetime.now(
            UTC,
        ),
    }


def filter_items(
    items: list[dict[str, Any]],
    *,
    severity: str,
    status: str,
    namespace: str,
    search: str,
) -> list[dict[str, Any]]:
    filtered = items

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

    if status != 'all':
        filtered = [
            item
            for item in filtered
            if str(
                item.get(
                    'status',
                    '',
                )
            ).lower()
            == status
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


def build_summary(
    *,
    alerts: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    source_status: dict[str, Any],
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
    source_status: dict[str, Any],
) -> dict[str, Any]:
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

    connected = source_status.get(
        'resolved_source',
    ) == 'prometheus' and source_status.get(
        'connected',
    )

    return {
        'configured': True,
        'connected': bool(
            connected,
        ),
        'label': 'Prometheus Connected' if connected else 'Prometheus Configured',
        'status': 'connected' if connected else 'configured',
        'response_time_ms': source_status.get(
            'response_time_ms',
        )
        if connected
        else None,
    }


def build_alertmanager_integration_status(
    *,
    cluster: Cluster | None,
    source_status: dict[str, Any],
) -> dict[str, Any]:
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
    source_status: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        'prometheus': build_prometheus_status(
            cluster=cluster,
            source_status=source_status,
        ),
        'alertmanager': build_alertmanager_integration_status(
            cluster=cluster,
            source_status=source_status,
        ),
    }


def build_source_health(
    *,
    cluster: Cluster | None,
    source_status: dict[str, Any],
    integration_status: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if cluster is None:
        return {
            'score': 0,
            'level': 'unavailable',
            'label': 'No Cluster Selected',
            'description': 'Select a cluster before evaluating alert source health.',
            'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
            'icon': 'circle-off',
            'checks': [
                {
                    'label': 'Cluster selected',
                    'status': 'fail',
                    'description': 'No cluster is selected for alert analysis.',
                }
            ],
        }

    alertmanager_status = integration_status.get(
        'alertmanager',
        {},
    )
    prometheus_status = integration_status.get(
        'prometheus',
        {},
    )

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

    if connected and resolved_source == 'alertmanager' and not fallback_used:
        score = 100
        level = 'healthy'
        label = 'Alertmanager Healthy'
        description = 'Alertmanager is connected and used as the primary alert source.'
        icon = 'shield-check'
        class_name = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
    elif connected and resolved_source == 'prometheus' and fallback_used:
        score = 60 if alertmanager_configured else 80
        level = 'fallback'
        label = 'Prometheus Fallback Active'
        description = 'Alertmanager is unavailable, but Prometheus ALERTS fallback is connected.'
        icon = 'route'
        class_name = 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
    elif connected and resolved_source == 'prometheus':
        score = 75
        level = 'degraded'
        label = 'Prometheus Alerts Only'
        description = 'Prometheus ALERTS is connected, but Alertmanager routing, grouping, silence, and inhibition context is not the active source.'
        icon = 'activity'
        class_name = 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
    elif alertmanager_configured or prometheus_configured:
        score = 40
        level = 'unavailable'
        label = 'Alert Source Unavailable'
        description = 'At least one alert source is configured, but no alert source is currently connected.'
        icon = 'circle-alert'
        class_name = 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-300'
    else:
        score = 20
        level = 'unavailable'
        label = 'Alert Sources Not Configured'
        description = (
            'Configure Alertmanager as the primary source and Prometheus as fallback before relying on alert analysis.'
        )
        icon = 'plug-zap'
        class_name = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'

    checks = [
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
            'label': 'Prometheus fallback connected',
            'status': 'pass' if prometheus_connected else ('warning' if prometheus_configured else 'fail'),
            'description': 'Prometheus ALERTS fallback is connected.'
            if prometheus_connected
            else 'Prometheus fallback is not currently connected.',
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
        'class': class_name,
        'icon': icon,
        'checks': checks,
        'selected_source': selected_source,
        'resolved_source': resolved_source,
        'fallback_used': fallback_used,
    }


def normalize_alert_receiver(
    alert: dict[str, Any],
) -> str:
    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    receiver = (
        alert.get(
            'receiver',
        )
        or alert.get(
            'route',
        )
        or labels.get(
            'receiver',
        )
        or labels.get(
            'alertmanager_receiver',
        )
        or labels.get(
            'route',
        )
        or labels.get(
            'team',
        )
        or labels.get(
            'owner',
        )
        or 'Receiver Unknown'
    )

    return str(
        receiver or 'Receiver Unknown',
    )


def build_alert_group_key(
    alert: dict[str, Any],
) -> str:
    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    group_parts = [
        str(
            labels.get(
                'alertname',
                alert.get(
                    'name',
                    'Unknown Alert',
                ),
            )
            or 'Unknown Alert'
        ),
        str(
            labels.get(
                'namespace',
                alert.get(
                    'namespace',
                    '-',
                ),
            )
            or '-'
        ),
        str(
            labels.get(
                'severity',
                alert.get(
                    'severity',
                    'none',
                ),
            )
            or 'none'
        ),
        str(
            labels.get(
                'job',
                labels.get(
                    'service',
                    '-',
                ),
            )
            or '-'
        ),
    ]

    return ' / '.join(
        group_parts,
    )


def build_count_groups(
    alerts: list[dict[str, Any]],
    *,
    key_name: str,
    label_default: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}

    for alert in alerts:
        if not isinstance(
            alert,
            dict,
        ):
            continue

        value = str(
            alert.get(
                key_name,
                label_default,
            )
            or label_default
        )

        if key_name == 'receiver':
            value = normalize_alert_receiver(
                alert,
            )

        if key_name == 'group_key':
            value = build_alert_group_key(
                alert,
            )

        counts[value] = (
            counts.get(
                value,
                0,
            )
            + 1
        )

    total = sum(
        counts.values(),
    )

    grouped_rows = [
        {
            'label': label,
            'count': count,
            'percent': round(
                (count / total) * 100,
                1,
            )
            if total > 0
            else 0,
        }
        for label, count in counts.items()
    ]

    return sorted(
        grouped_rows,
        key=lambda item: (
            item.get(
                'count',
                0,
            ),
            item.get(
                'label',
                '',
            ),
        ),
        reverse=True,
    )[:limit]


def build_routing_summary(
    *,
    alerts: list[dict[str, Any]],
    source_status: dict[str, Any],
) -> dict[str, Any]:
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

    alert_rows = [
        alert
        for alert in alerts
        if isinstance(
            alert,
            dict,
        )
    ]

    receiver_groups = build_count_groups(
        alert_rows,
        key_name='receiver',
        label_default='Receiver Unknown',
    )
    severity_groups = build_count_groups(
        alert_rows,
        key_name='severity',
        label_default='none',
    )
    namespace_groups = build_count_groups(
        alert_rows,
        key_name='namespace',
        label_default='-',
    )
    grouping_keys = build_count_groups(
        alert_rows,
        key_name='group_key',
        label_default='Unknown Alert / - / none / -',
    )

    receiver_count = len(
        {
            normalize_alert_receiver(
                alert,
            )
            for alert in alert_rows
        }
    )
    group_count = len(
        {
            build_alert_group_key(
                alert,
            )
            for alert in alert_rows
        }
    )
    fingerprint_count = sum(
        1
        for alert in alert_rows
        if str(
            alert.get(
                'fingerprint',
                '',
            )
            or ''
        )
    )
    namespace_count = len(
        {
            str(
                alert.get(
                    'namespace',
                    '',
                )
                or ''
            )
            for alert in alert_rows
            if str(
                alert.get(
                    'namespace',
                    '',
                )
                or ''
            )
            and str(
                alert.get(
                    'namespace',
                    '',
                )
                or ''
            )
            != '-'
        }
    )

    if resolved_source == 'alertmanager' and connected:
        enabled = True
        level = 'available'
        label = 'Alertmanager Routing Context Available'
        description = 'Alertmanager context is available.'
        icon = 'route'
        class_name = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
    elif resolved_source == 'prometheus' and connected:
        enabled = False
        level = 'limited'
        label = 'Routing Context Limited'
        description = 'Prometheus fallback is active; Alertmanager context is limited.'
        icon = 'activity'
        class_name = 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
    else:
        enabled = False
        level = 'unavailable'
        label = 'Routing Context Unavailable'
        description = 'Alert routing cannot be evaluated because no alert source is currently connected.'
        icon = 'circle-alert'
        class_name = 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-300'

    return {
        'enabled': enabled,
        'level': level,
        'label': label,
        'description': description,
        'class': class_name,
        'icon': icon,
        'source': resolved_source,
        'alert_count': len(
            alert_rows,
        ),
        'receiver_count': receiver_count,
        'group_count': group_count,
        'fingerprint_count': fingerprint_count,
        'namespace_count': namespace_count,
        'severity_groups': severity_groups,
        'receiver_groups': receiver_groups,
        'namespace_groups': namespace_groups,
        'grouping_keys': grouping_keys,
    }


def build_empty_routing_summary() -> dict[str, Any]:
    return {
        'enabled': False,
        'level': 'unavailable',
        'label': 'Routing Context Unavailable',
        'description': 'Alert routing cannot be evaluated because no alert source is currently connected.',
        'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
        'icon': 'circle-off',
        'source': 'none',
        'alert_count': 0,
        'receiver_count': 0,
        'group_count': 0,
        'fingerprint_count': 0,
        'namespace_count': 0,
        'severity_groups': [],
        'receiver_groups': [],
        'namespace_groups': [],
        'grouping_keys': [],
    }


def load_alertmanager_silences(
    *,
    cluster: Cluster | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if cluster is None:
        return [], {
            'connected': False,
            'error': 'No cluster selected.',
        }

    result = get_alertmanager_silences(
        cluster_id=cluster.id,
    )

    silences = [
        item
        for item in result.get(
            'silences',
            [],
        )
        if isinstance(
            item,
            dict,
        )
    ]

    return silences, {
        'connected': bool(
            result.get(
                'connected',
                False,
            )
        ),
        'error': result.get(
            'error',
        ),
    }


def parse_alertmanager_datetime(
    value: Any,
) -> datetime | None:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                'Z',
                '+00:00',
            )
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(
            tzinfo=UTC,
        )

    return parsed.astimezone(
        UTC,
    )


def format_silence_datetime(
    value: Any,
) -> str:
    parsed = parse_alertmanager_datetime(
        value,
    )

    if parsed is None:
        return '-'

    return parsed.strftime(
        '%Y-%m-%d %H:%M UTC',
    )


def normalize_silence_state(
    silence: dict[str, Any],
) -> str:
    status = silence.get(
        'status',
        {},
    )

    if isinstance(
        status,
        dict,
    ):
        state = str(
            status.get(
                'state',
                '',
            )
            or ''
        ).lower()

        if state:
            return state

    now = datetime.now(
        UTC,
    )
    starts_at = parse_alertmanager_datetime(
        silence.get(
            'startsAt',
        )
        or silence.get(
            'starts_at',
        )
    )
    ends_at = parse_alertmanager_datetime(
        silence.get(
            'endsAt',
        )
        or silence.get(
            'ends_at',
        )
    )

    if starts_at is not None and starts_at > now:
        return 'pending'

    if ends_at is not None and ends_at <= now:
        return 'expired'

    return 'active'


def normalize_silence_matchers(
    silence: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_matchers = silence.get(
        'matchers',
        [],
    )

    if not isinstance(
        raw_matchers,
        list,
    ):
        return []

    matchers: list[dict[str, Any]] = []

    for matcher in raw_matchers:
        if not isinstance(
            matcher,
            dict,
        ):
            continue

        name = str(
            matcher.get(
                'name',
                '',
            )
            or ''
        )
        value = str(
            matcher.get(
                'value',
                '',
            )
            or ''
        )

        if not name:
            continue

        matchers.append(
            {
                'name': name,
                'value': value,
                'is_regex': bool(
                    matcher.get(
                        'isRegex',
                        matcher.get(
                            'is_regex',
                            False,
                        ),
                    )
                ),
                'is_equal': bool(
                    matcher.get(
                        'isEqual',
                        matcher.get(
                            'is_equal',
                            True,
                        ),
                    )
                ),
                'label': f'{name}{"=~" if matcher.get("isRegex") else "="}{value}',
            }
        )

    return matchers


def silence_matches_alert(
    *,
    silence: dict[str, Any],
    alert: dict[str, Any],
) -> bool:
    matchers = normalize_silence_matchers(
        silence,
    )

    if not matchers:
        return False

    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    for matcher in matchers:
        name = str(
            matcher.get(
                'name',
                '',
            )
            or ''
        )
        expected_value = str(
            matcher.get(
                'value',
                '',
            )
            or ''
        )
        actual_value = str(
            labels.get(
                name,
                alert.get(
                    name,
                    '',
                ),
            )
            or ''
        )
        is_equal = bool(
            matcher.get(
                'is_equal',
                True,
            )
        )
        is_regex = bool(
            matcher.get(
                'is_regex',
                False,
            )
        )

        if is_regex:
            try:
                matched = (
                    re.search(
                        expected_value,
                        actual_value,
                    )
                    is not None
                )
            except re.error:
                matched = expected_value in actual_value
        else:
            matched = actual_value == expected_value

        if is_equal and not matched:
            return False

        if not is_equal and matched:
            return False

    return True


def build_silence_summary(
    *,
    cluster: Cluster | None,
    alerts: list[dict[str, Any]],
    source_status: dict[str, Any],
) -> dict[str, Any]:
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

    if cluster is None:
        return build_empty_silence_summary(
            label='Silence Visibility Unavailable',
            description='Select a cluster before evaluating Alertmanager silences.',
        )

    if resolved_source != 'alertmanager' or not connected:
        return {
            **build_empty_silence_summary(
                label='Silence Visibility Limited',
                description='Silence visibility needs Alertmanager as the active source.',
            ),
            'level': 'limited' if resolved_source == 'prometheus' and connected else 'unavailable',
            'source': resolved_source,
        }

    silences, silence_status = load_alertmanager_silences(
        cluster=cluster,
    )

    if not silence_status.get(
        'connected',
        False,
    ):
        return {
            **build_empty_silence_summary(
                label='Silence API Unavailable',
                description=str(
                    silence_status.get(
                        'error',
                        'Alertmanager silence API could not be queried.',
                    )
                    or 'Alertmanager silence API could not be queried.'
                ),
            ),
            'level': 'unavailable',
            'source': resolved_source,
        }

    active_items: list[dict[str, Any]] = []
    pending_count = 0
    expired_count = 0
    silenced_namespaces: set[str] = set()
    silenced_matchers: set[str] = set()
    matched_alert_fingerprints: set[str] = set()

    for silence in silences:
        state = normalize_silence_state(
            silence,
        )
        matchers = normalize_silence_matchers(
            silence,
        )
        matcher_labels = [
            str(
                matcher.get(
                    'label',
                    '',
                )
            )
            for matcher in matchers
            if matcher.get(
                'label',
            )
        ]

        if state == 'pending':
            pending_count += 1
        elif state == 'expired':
            expired_count += 1

        matched_alerts = [
            alert
            for alert in alerts
            if isinstance(
                alert,
                dict,
            )
            and state == 'active'
            and silence_matches_alert(
                silence=silence,
                alert=alert,
            )
        ]

        for matcher in matchers:
            if (
                matcher.get(
                    'name',
                )
                == 'namespace'
            ):
                silenced_namespaces.add(
                    str(
                        matcher.get(
                            'value',
                            '',
                        )
                        or ''
                    )
                )

            if matcher.get(
                'label',
            ):
                silenced_matchers.add(
                    str(
                        matcher.get(
                            'label',
                        )
                    )
                )

        for alert in matched_alerts:
            fingerprint = str(
                alert.get(
                    'fingerprint',
                    '',
                )
                or f'{alert.get("name", "")}/{alert.get("namespace", "")}/{alert.get("target", "")}'
            )

            if fingerprint:
                matched_alert_fingerprints.add(
                    fingerprint,
                )

        if state == 'active':
            active_items.append(
                {
                    'id': str(
                        silence.get(
                            'id',
                            '-',
                        )
                        or '-'
                    ),
                    'state': state,
                    'created_by': str(
                        silence.get(
                            'createdBy',
                            silence.get(
                                'created_by',
                                '-',
                            ),
                        )
                        or '-'
                    ),
                    'comment': str(
                        silence.get(
                            'comment',
                            '-',
                        )
                        or '-'
                    ),
                    'starts_at': format_silence_datetime(
                        silence.get(
                            'startsAt',
                        )
                        or silence.get(
                            'starts_at',
                        )
                    ),
                    'ends_at': format_silence_datetime(
                        silence.get(
                            'endsAt',
                        )
                        or silence.get(
                            'ends_at',
                        )
                    ),
                    'matchers': matcher_labels,
                    'matched_alerts': len(
                        matched_alerts,
                    ),
                }
            )

    active_count = len(
        active_items,
    )

    return {
        'enabled': True,
        'level': 'available',
        'label': 'Alertmanager Silence Context Available',
        'description': ('Active, pending, and expired Alertmanager silences are visible for the selected cluster.'),
        'class': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
        'icon': 'volume-x',
        'source': resolved_source,
        'active_silences': active_count,
        'pending_silences': pending_count,
        'expired_silences': expired_count,
        'matched_alerts': len(
            matched_alert_fingerprints,
        ),
        'silenced_namespaces': sorted(namespace for namespace in silenced_namespaces if namespace)[:6],
        'silenced_matchers': sorted(matcher for matcher in silenced_matchers if matcher)[:8],
        'items': active_items[:5],
    }


def build_empty_silence_summary(
    *,
    label: str = 'Silence Visibility Unavailable',
    description: str = 'Alertmanager silence context is not available.',
) -> dict[str, Any]:
    return {
        'enabled': False,
        'level': 'unavailable',
        'label': label,
        'description': description,
        'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
        'icon': 'volume-x',
        'source': 'none',
        'active_silences': 0,
        'pending_silences': 0,
        'expired_silences': 0,
        'matched_alerts': 0,
        'silenced_namespaces': [],
        'silenced_matchers': [],
        'items': [],
    }


def build_inhibition_summary(
    *,
    alerts: list[dict[str, Any]],
    source_status: dict[str, Any],
) -> dict[str, Any]:
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

    if resolved_source != 'alertmanager' or not connected:
        return {
            'enabled': False,
            'level': 'limited' if resolved_source == 'prometheus' and connected else 'unavailable',
            'label': 'Inhibition Visibility Limited'
            if resolved_source == 'prometheus' and connected
            else 'Inhibition Visibility Unavailable',
            'description': (
                'Inhibition visibility requires Alertmanager alert lifecycle metadata. '
                'Prometheus fallback does not include inhibitedBy context.'
            ),
            'class': 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
            if resolved_source == 'prometheus' and connected
            else 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
            'icon': 'shield-alert',
            'source': resolved_source,
            'rules_detected': 0,
            'matched_alerts': 0,
            'source_equal_labels': [],
            'target_matchers': [],
            'items': [],
        }

    inhibited_alerts: list[dict[str, Any]] = []

    for alert in alerts:
        if not isinstance(
            alert,
            dict,
        ):
            continue

        if bool(
            alert.get(
                'inhibited',
                False,
            )
        ) or bool(
            alert.get(
                'inhibited_by',
                [],
            )
        ):
            inhibited_alerts.append(
                alert,
            )

    source_equal_labels = sorted(
        {
            label
            for alert in inhibited_alerts
            for label in [
                'namespace',
                'alertname',
                'severity',
                'job',
            ]
            if label
            in (
                alert.get(
                    'labels',
                    {},
                )
                if isinstance(
                    alert.get(
                        'labels',
                        {},
                    ),
                    dict,
                )
                else {}
            )
        }
    )

    items = [
        {
            'name': str(
                alert.get(
                    'name',
                    'Unknown Alert',
                )
                or 'Unknown Alert'
            ),
            'namespace': str(
                alert.get(
                    'namespace',
                    '-',
                )
                or '-'
            ),
            'target': str(
                alert.get(
                    'target',
                    '-',
                )
                or '-'
            ),
            'severity': str(
                alert.get(
                    'severity',
                    'none',
                )
                or 'none'
            ),
            'inhibited_by': alert.get(
                'inhibited_by',
                [],
            ),
        }
        for alert in inhibited_alerts[:5]
    ]

    matched_alerts = len(
        inhibited_alerts,
    )

    return {
        'enabled': True,
        'level': 'available',
        'label': 'Alertmanager Inhibition Context Available',
        'description': ('Inhibition visibility is derived from Alertmanager alert lifecycle metadata.'),
        'class': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
        'icon': 'shield-alert',
        'source': resolved_source,
        'rules_detected': len(
            {
                str(item)
                for alert in inhibited_alerts
                for item in (
                    alert.get(
                        'inhibited_by',
                        [],
                    )
                    if isinstance(
                        alert.get(
                            'inhibited_by',
                            [],
                        ),
                        list,
                    )
                    else []
                )
            }
        ),
        'matched_alerts': matched_alerts,
        'source_equal_labels': source_equal_labels[:6],
        'target_matchers': [
            'severity',
            'alertname',
            'namespace',
        ]
        if matched_alerts
        else [],
        'items': items,
    }


def _get_first_string_value(
    mapping: dict[str, Any],
    keys: list[str],
    *,
    default: str = '',
) -> str:
    for key in keys:
        value = mapping.get(
            key,
        )

        if value is None:
            continue

        text = str(
            value,
        ).strip()

        if text:
            return text

    return default


def extract_alert_owner_from_payload(
    *,
    labels: dict[str, Any],
    annotations: dict[str, Any],
    fallback_namespace: Any = '-',
) -> str:
    owner = _get_first_string_value(
        labels,
        [
            'owner',
            'team',
            'service',
            'app',
            'application',
        ],
    )

    if owner:
        return owner

    owner = _get_first_string_value(
        annotations,
        [
            'owner',
            'team',
            'service',
            'app',
            'application',
        ],
    )

    if owner:
        return owner

    namespace = str(
        fallback_namespace or '',
    ).strip()

    if namespace and namespace != '-':
        return namespace

    return '-'


def extract_alert_runbook_from_payload(
    *,
    annotations: dict[str, Any],
) -> str:
    return _get_first_string_value(
        annotations,
        [
            'runbook_url',
            'runbook',
            'runbook_link',
            'runbookURL',
            'dashboard_url',
            'dashboard',
        ],
    )


def extract_alert_contact_from_payload(
    *,
    labels: dict[str, Any],
    annotations: dict[str, Any],
) -> str:
    keys = [
        'contact',
        'contact_point',
        'pager',
        'pagerduty',
        'slack',
        'email',
        'escalation',
    ]

    contact = _get_first_string_value(
        labels,
        keys,
    )

    if contact:
        return contact

    return _get_first_string_value(
        annotations,
        keys,
    )


def get_alert_owner(
    alert: dict[str, Any],
) -> str:
    explicit_owner = str(
        alert.get(
            'owner',
            '',
        )
        or ''
    ).strip()

    if explicit_owner and explicit_owner != '-':
        return explicit_owner

    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    annotations = alert.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    return extract_alert_owner_from_payload(
        labels=labels,
        annotations=annotations,
        fallback_namespace=alert.get(
            'namespace',
            '-',
        ),
    )


def get_alert_runbook(
    alert: dict[str, Any],
) -> str:
    explicit_runbook = str(
        alert.get(
            'runbook_url',
            '',
        )
        or ''
    ).strip()

    if explicit_runbook:
        return explicit_runbook

    annotations = alert.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    return extract_alert_runbook_from_payload(
        annotations=annotations,
    )


def get_alert_contact(
    alert: dict[str, Any],
) -> str:
    explicit_contact = str(
        alert.get(
            'contact',
            '',
        )
        or ''
    ).strip()

    if explicit_contact:
        return explicit_contact

    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    annotations = alert.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    return extract_alert_contact_from_payload(
        labels=labels,
        annotations=annotations,
    )


def build_ownership_summary(
    *,
    alerts: list[dict[str, Any]],
    source_status: dict[str, Any],
) -> dict[str, Any]:
    alert_rows = [
        alert
        for alert in alerts
        if isinstance(
            alert,
            dict,
        )
    ]

    total_alerts = len(
        alert_rows,
    )

    if total_alerts == 0:
        return {
            **build_empty_ownership_summary(),
            'label': 'No Alert Metadata Required',
            'description': 'No active alert matched the selected source and filters, so ownership and runbook readiness cannot be evaluated yet.',
            'level': 'unknown',
        }

    owner_groups: dict[str, int] = {}
    runbook_items: list[dict[str, Any]] = []
    missing_metadata_items: list[dict[str, Any]] = []
    owner_count = 0
    runbook_count = 0
    contact_count = 0

    for alert in alert_rows:
        owner = get_alert_owner(
            alert,
        )
        runbook = get_alert_runbook(
            alert,
        )
        contact = get_alert_contact(
            alert,
        )

        has_owner = bool(
            owner and owner != '-',
        )
        has_runbook = bool(
            runbook,
        )
        has_contact = bool(
            contact,
        )

        if has_owner:
            owner_count += 1
            owner_groups[owner] = (
                owner_groups.get(
                    owner,
                    0,
                )
                + 1
            )

        if has_runbook:
            runbook_count += 1
            runbook_items.append(
                {
                    'name': str(
                        alert.get(
                            'name',
                            'Unknown Alert',
                        )
                        or 'Unknown Alert'
                    ),
                    'namespace': str(
                        alert.get(
                            'namespace',
                            '-',
                        )
                        or '-'
                    ),
                    'url': runbook,
                    'owner': owner if has_owner else '-',
                }
            )

        if has_contact:
            contact_count += 1

        missing_parts: list[str] = []

        if not has_owner:
            missing_parts.append(
                'owner',
            )

        if not has_runbook:
            missing_parts.append(
                'runbook',
            )

        if not has_contact:
            missing_parts.append(
                'contact',
            )

        if missing_parts:
            missing_metadata_items.append(
                {
                    'name': str(
                        alert.get(
                            'name',
                            'Unknown Alert',
                        )
                        or 'Unknown Alert'
                    ),
                    'namespace': str(
                        alert.get(
                            'namespace',
                            '-',
                        )
                        or '-'
                    ),
                    'severity': str(
                        alert.get(
                            'severity',
                            'none',
                        )
                        or 'none'
                    ),
                    'missing': missing_parts,
                }
            )

    missing_owner_count = total_alerts - owner_count
    missing_runbook_count = total_alerts - runbook_count
    missing_contact_count = total_alerts - contact_count

    score = round(
        ((owner_count + runbook_count + contact_count) / (total_alerts * 3)) * 100,
    )

    if score >= 85:
        level = 'ready'
        label = 'Ownership Metadata Ready'
        description = 'Most active alerts include owner, runbook, and contact metadata for operational response.'
        class_name = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
        icon = 'book-open'
    elif score >= 60:
        level = 'partial'
        label = 'Ownership Metadata Partial'
        description = 'Some alerts have owner or runbook context, but response metadata coverage is not complete.'
        class_name = 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
        icon = 'clipboard-check'
    elif score >= 30:
        level = 'weak'
        label = 'Ownership Metadata Weak'
        description = 'Many alerts are missing owner, runbook, or contact metadata. Response readiness is weak.'
        class_name = 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
        icon = 'triangle-alert'
    else:
        level = 'unknown'
        label = 'Ownership Metadata Missing'
        description = 'Most alerts do not include owner, runbook, or contact metadata.'
        class_name = 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-300'
        icon = 'user-x'

    owner_group_rows = [
        {
            'label': owner,
            'count': count,
            'percent': round(
                (count / total_alerts) * 100,
                1,
            ),
        }
        for owner, count in owner_groups.items()
    ]

    owner_group_rows = sorted(
        owner_group_rows,
        key=lambda item: (
            item.get(
                'count',
                0,
            ),
            item.get(
                'label',
                '',
            ),
        ),
        reverse=True,
    )[:6]

    return {
        'score': score,
        'level': level,
        'label': label,
        'description': description,
        'class': class_name,
        'icon': icon,
        'source': str(
            source_status.get(
                'resolved_source',
                'none',
            )
            or 'none'
        ),
        'alert_count': total_alerts,
        'owner_count': owner_count,
        'runbook_count': runbook_count,
        'contact_count': contact_count,
        'missing_owner_count': missing_owner_count,
        'missing_runbook_count': missing_runbook_count,
        'missing_contact_count': missing_contact_count,
        'owner_groups': owner_group_rows,
        'runbook_items': runbook_items[:5],
        'missing_metadata_items': missing_metadata_items[:6],
    }


def build_empty_ownership_summary() -> dict[str, Any]:
    return {
        'score': 0,
        'level': 'unknown',
        'label': 'Ownership Metadata Unknown',
        'description': 'No alert ownership metadata is available yet.',
        'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
        'icon': 'search',
        'source': 'none',
        'alert_count': 0,
        'owner_count': 0,
        'runbook_count': 0,
        'contact_count': 0,
        'missing_owner_count': 0,
        'missing_runbook_count': 0,
        'missing_contact_count': 0,
        'owner_groups': [],
        'runbook_items': [],
        'missing_metadata_items': [],
    }


def safe_int(
    value: Any,
    *,
    default: int = 0,
) -> int:
    try:
        return int(
            value or default,
        )
    except (
        TypeError,
        ValueError,
    ):
        return default


def clamp_score(
    value: int,
) -> int:
    return max(
        min(
            value,
            100,
        ),
        0,
    )


def build_incident_readiness(
    *,
    signal_overview: dict[str, Any],
    source_health: dict[str, Any],
    routing_summary: dict[str, Any],
    silence_summary: dict[str, Any],
    inhibition_summary: dict[str, Any],
    ownership_summary: dict[str, Any],
) -> dict[str, Any]:
    critical_signals = safe_int(
        signal_overview.get(
            'critical_alerts',
            0,
        )
    )
    warning_signals = safe_int(
        signal_overview.get(
            'warning_alerts',
            0,
        )
    )
    anomaly_signals = safe_int(
        signal_overview.get(
            'anomalies',
            0,
        )
    )
    source_score = clamp_score(
        safe_int(
            source_health.get(
                'score',
                0,
            )
        )
    )
    ownership_score = clamp_score(
        safe_int(
            ownership_summary.get(
                'score',
                0,
            )
        )
    )
    matched_silenced_alerts = safe_int(
        silence_summary.get(
            'matched_alerts',
            0,
        )
    )
    inhibited_alerts = safe_int(
        inhibition_summary.get(
            'matched_alerts',
            0,
        )
    )
    routing_ready = bool(
        routing_summary.get(
            'enabled',
            False,
        )
    )

    score = 100

    if critical_signals > 0:
        score -= 25

    if warning_signals > 0:
        score -= 10

    if anomaly_signals > 0:
        score -= 10

    if source_score < 80:
        score -= 15

    if not routing_ready:
        score -= 10

    if ownership_score < 60:
        score -= 15

    if matched_silenced_alerts > 0:
        score -= 10

    if inhibited_alerts > 0:
        score -= 5

    score = clamp_score(
        score,
    )

    if score >= 80:
        level = 'ready'
        label = 'Incident Ready'
        description = (
            'Alert source, routing, ownership, and current signal posture are ready for normal operational monitoring.'
        )
        recommended_action = (
            'Continue monitoring. No immediate incident escalation is required from the current alert posture.'
        )
        icon = 'shield-check'
        class_name = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
    elif score >= 60:
        level = 'watch'
        label = 'Watch Required'
        description = 'Some warning signals or readiness gaps exist. Keep the cluster under closer observation.'
        recommended_action = 'Review warning alerts, confirm ownership metadata, and validate that Alertmanager remains the primary source.'
        icon = 'radar'
        class_name = 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
    elif score >= 40:
        level = 'degraded'
        label = 'Incident Readiness Degraded'
        description = (
            'Alert readiness is degraded because one or more source, routing, metadata, or signal checks are weak.'
        )
        recommended_action = 'Triage active alerts, verify Alertmanager routing, and complete owner/runbook/contact metadata for affected services.'
        icon = 'alert-triangle'
        class_name = 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
    else:
        level = 'incident_risk'
        label = 'Incident Risk'
        description = (
            'Current alert posture has critical signals or significant readiness gaps that may require escalation.'
        )
        recommended_action = 'Escalate critical alerts, assign owner, validate runbook coverage, and inspect muted or inhibited alerts immediately.'
        icon = 'siren'
        class_name = 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-300'

    checks = [
        {
            'label': 'Critical signals',
            'status': 'fail' if critical_signals > 0 else 'pass',
            'description': f'{critical_signals} critical alert signal(s) detected.'
            if critical_signals > 0
            else 'No critical alert signal detected.',
        },
        {
            'label': 'Warning signals',
            'status': 'warning' if warning_signals > 0 else 'pass',
            'description': f'{warning_signals} warning alert signal(s) detected.'
            if warning_signals > 0
            else 'No warning alert signal detected.',
        },
        {
            'label': 'Anomaly signals',
            'status': 'warning' if anomaly_signals > 0 else 'pass',
            'description': f'{anomaly_signals} anomaly candidate(s) detected.'
            if anomaly_signals > 0
            else 'No anomaly candidate detected.',
        },
        {
            'label': 'Alert source health',
            'status': 'pass' if source_score >= 80 else ('warning' if source_score >= 60 else 'fail'),
            'description': f'Source health score is {source_score}/100.',
        },
        {
            'label': 'Routing context',
            'status': 'pass' if routing_ready else 'warning',
            'description': 'Alertmanager routing context is available.'
            if routing_ready
            else 'Routing context is limited or unavailable.',
        },
        {
            'label': 'Ownership readiness',
            'status': 'pass' if ownership_score >= 80 else ('warning' if ownership_score >= 60 else 'fail'),
            'description': f'Ownership and runbook readiness score is {ownership_score}/100.',
        },
        {
            'label': 'Silence impact',
            'status': 'warning' if matched_silenced_alerts > 0 else 'pass',
            'description': f'{matched_silenced_alerts} alert(s) may be affected by active silences.'
            if matched_silenced_alerts > 0
            else 'No active silence currently matches loaded alerts.',
        },
        {
            'label': 'Inhibition impact',
            'status': 'warning' if inhibited_alerts > 0 else 'pass',
            'description': f'{inhibited_alerts} inhibited alert(s) detected.'
            if inhibited_alerts > 0
            else 'No inhibited alert detected from Alertmanager metadata.',
        },
    ]

    return {
        'score': score,
        'level': level,
        'label': label,
        'description': description,
        'class': class_name,
        'icon': icon,
        'critical_signals': critical_signals,
        'warning_signals': warning_signals,
        'anomaly_signals': anomaly_signals,
        'ownership_score': ownership_score,
        'source_score': source_score,
        'silence_risk': matched_silenced_alerts,
        'inhibition_risk': inhibited_alerts,
        'routing_ready': routing_ready,
        'recommended_action': recommended_action,
        'checks': checks,
    }


def build_empty_incident_readiness() -> dict[str, Any]:
    return {
        'score': 0,
        'level': 'incident_risk',
        'label': 'Incident Readiness Unknown',
        'description': 'Incident readiness cannot be evaluated because no alert context is available.',
        'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
        'icon': 'circle-off',
        'critical_signals': 0,
        'warning_signals': 0,
        'anomaly_signals': 0,
        'ownership_score': 0,
        'source_score': 0,
        'silence_risk': 0,
        'inhibition_risk': 0,
        'routing_ready': False,
        'recommended_action': 'Select a cluster and verify alert source configuration before evaluating incident readiness.',
        'checks': [],
    }


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
    alerts: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    source_status: dict[str, Any],
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


def get_alerts_context(
    *,
    cluster_id: str | None,
    source: str | None,
    severity: str | None,
    status: str | None,
    namespace: str | None,
    search: str | None,
    page: str | int | None,
    alerts_per_page: str | int | None,
    anomalies_per_page: str | int | None,
) -> dict[str, Any]:
    clusters = get_clusters_for_filter()

    selected_cluster = get_selected_cluster(
        cluster_id=cluster_id,
    )

    selected_source = normalize_option(
        source,
        allowed=SOURCE_OPTIONS,
        default='auto',
    )

    selected_severity = normalize_option(
        severity,
        allowed=SEVERITY_OPTIONS,
        default='all',
    )

    selected_status = normalize_option(
        status,
        allowed=STATUS_OPTIONS,
        default='all',
    )

    selected_namespace = normalize_string(
        namespace,
    )

    selected_search = normalize_string(
        search,
    )

    selected_page = normalize_page(
        page,
    )

    selected_alerts_per_page = normalize_per_page(
        alerts_per_page,
    )

    selected_anomalies_per_page = normalize_per_page(
        anomalies_per_page,
    )

    namespace_options = get_namespace_options(
        cluster=selected_cluster,
    )

    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    raw_alerts, source_status = load_alerts_by_source(
        cluster=selected_cluster,
        source=selected_source,
    )

    filtered_alerts = filter_items(
        raw_alerts,
        severity=selected_severity,
        status=selected_status,
        namespace=selected_namespace,
        search=selected_search,
    )

    paginated_alerts, pagination = paginate_items(
        filtered_alerts,
        page=selected_page,
        per_page=selected_alerts_per_page,
    )

    raw_anomalies = (
        load_prometheus_anomaly_metrics(
            cluster=selected_cluster,
        )
        if selected_cluster is not None
        else []
    )

    anomalies = filter_anomalies(
        raw_anomalies,
        severity=selected_severity,
        namespace=selected_namespace,
        search=selected_search,
    )

    anomaly_rows, anomaly_pagination = paginate_items(
        anomalies,
        page=1,
        per_page=selected_anomalies_per_page,
    )

    summary = build_summary(
        alerts=filtered_alerts,
        anomalies=anomalies,
        source_status=source_status,
    )

    actionable_payload = {
        'alerts': filtered_alerts,
        'all_alerts': filtered_alerts,
        'anomalies': anomalies,
        'all_anomalies': anomalies,
        'summary': summary,
        'source_status': source_status,
        'selected_cluster_signal_overview': build_selected_cluster_signal_overview(
            cluster=selected_cluster,
            alerts=raw_alerts,
            anomalies=raw_anomalies,
            source_status=source_status,
        ),
    }

    actionable_recommendations = build_alerts_actionable_recommendations(
        actionable_payload,
    )
    recommendation_cards = format_recommendation_cards(
        actionable_recommendations,
        default_title='Continue alert and anomaly monitoring',
        default_description=(
            'No actionable alert or anomaly recommendation was generated. '
            'Continue monitoring alert source health, active signals, and anomaly candidates.'
        ),
        default_source='alerts',
        default_action_type='alert_review',
    )

    selected_cluster_signal_overview = actionable_payload['selected_cluster_signal_overview']

    integration_status = build_integration_status(
        cluster=selected_cluster,
        source_status=source_status,
    )

    dependency_blocker = cluster_required_blocker() if selected_cluster is None else None

    if selected_cluster is not None and not source_status.get('connected', False):
        if source_status.get('configured', False):
            dependency_blocker = alert_source_connection_blocker(
                selected_cluster,
                source=selected_source,
                detail=str(source_status.get('error') or ''),
            )
        else:
            dependency_blocker = alert_source_setup_blocker(
                selected_cluster,
                source=selected_source,
            )

    source_health = build_source_health(
        cluster=selected_cluster,
        source_status=source_status,
        integration_status=integration_status,
    )

    routing_summary = build_routing_summary(
        alerts=raw_alerts,
        source_status=source_status,
    )

    silence_summary = build_silence_summary(
        cluster=selected_cluster,
        alerts=raw_alerts,
        source_status=source_status,
    )

    inhibition_summary = build_inhibition_summary(
        alerts=raw_alerts,
        source_status=source_status,
    )

    ownership_summary = build_ownership_summary(
        alerts=raw_alerts,
        source_status=source_status,
    )

    incident_readiness = build_incident_readiness(
        signal_overview=selected_cluster_signal_overview,
        source_health=source_health,
        routing_summary=routing_summary,
        silence_summary=silence_summary,
        inhibition_summary=inhibition_summary,
        ownership_summary=ownership_summary,
    )

    return {
        'clusters': clusters,
        'selected_cluster': selected_cluster,
        'selected_cluster_id': selected_cluster.id if selected_cluster else '',
        'selected_source': selected_source,
        'selected_severity': selected_severity,
        'selected_status': selected_status,
        'selected_namespace': selected_namespace,
        'selected_search': selected_search,
        'selected_alerts_per_page': selected_alerts_per_page,
        'selected_anomalies_per_page': selected_anomalies_per_page,
        'selected_per_page': selected_alerts_per_page,
        'source_options': SOURCE_OPTIONS,
        'severity_options': SEVERITY_OPTIONS,
        'status_options': STATUS_OPTIONS,
        'per_page_options': PER_PAGE_OPTIONS,
        'namespace_options': namespace_options,
        'alerts': paginated_alerts,
        'all_alerts': filtered_alerts,
        'alerts_pagination': pagination,
        'anomalies': anomaly_rows,
        'all_anomalies': anomalies,
        'anomalies_pagination': anomaly_pagination,
        'summary': summary,
        'source_status': source_status,
        'integration_status': integration_status,
        'dependency_blocker': dependency_blocker,
        'source_health': source_health,
        'routing_summary': routing_summary,
        'silence_summary': silence_summary,
        'inhibition_summary': inhibition_summary,
        'ownership_summary': ownership_summary,
        'incident_readiness': incident_readiness,
        'resource_links': build_resource_links(
            cluster=selected_cluster,
        ),
        'selected_cluster_signal_overview': selected_cluster_signal_overview,
        'actionable_recommendations': actionable_recommendations,
        'recommendation_cards': recommendation_cards,
        'recommendation_count': count_actionable_recommendations(
            actionable_recommendations,
        ),
        'recommendations': recommendation_cards,
        'generated_at': datetime.now(
            UTC,
        ),
    }


def get_alerts_snapshot(
    cluster_id: str,
) -> dict[str, Any]:
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


def _empty_alerts_snapshot() -> dict[str, Any]:
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
    alerts: list[dict[str, Any]],
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
    alerts: list[dict[str, Any]],
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
    alerts: list[dict[str, Any]],
) -> dict[str, Any] | None:
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
    highest_alert: dict[str, Any] | None,
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
