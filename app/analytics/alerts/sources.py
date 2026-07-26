from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.alertmanager.service import get_alertmanager_alerts, get_alertmanager_status
from app.analytics.alerts.contracts import AlertLoadResult, AlertSourceStatus, NormalizedAlert
from app.analytics.alerts.metrics import get_metric_labels
from app.analytics.alerts.ownership import (
    extract_alert_contact_from_payload,
    extract_alert_owner_from_payload,
    extract_alert_runbook_from_payload,
)
from app.analytics.alerts.source_messages import (
    friendly_alert_fallback_reason,
    friendly_alert_source_error,
    friendly_combined_alert_error,
)
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.models import Cluster
from app.prometheus.service import PrometheusService

logger = logging.getLogger(__name__)


PROMETHEUS_ALERTS_QUERY = get_query_expression('analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY')


def build_empty_source_status(
    *,
    source: str,
    message: str,
) -> AlertSourceStatus:
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
) -> NormalizedAlert:
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
) -> NormalizedAlert:
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
) -> AlertLoadResult:
    started_at = perf_counter()

    try:
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

        raw_error = result.get('error')
        if raw_error and not connected:
            logger.warning(
                'Alertmanager alert loading failed for cluster %s: %s',
                cluster.id,
                raw_error,
            )
        source_status: AlertSourceStatus = {
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
            'error': (
                friendly_alert_source_error(raw_error, source_label='Alertmanager')
                if raw_error and not connected
                else None
            ),
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(
                UTC,
            ),
        }

        return alerts, source_status
    except Exception as exc:
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        error_message = str(exc).strip() or exc.__class__.__name__

        logger.exception(
            'Unexpected Alertmanager alert loading failure for cluster %s.',
            cluster.id,
        )

        return [], {
            'source': 'alertmanager',
            'selected_source': 'alertmanager',
            'resolved_source': 'none',
            'label': 'Alertmanager Error',
            'configured': True,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(error_message, source_label='Alertmanager'),
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(
                UTC,
            ),
        }


def load_prometheus_alerts(
    *,
    cluster: Cluster,
) -> AlertLoadResult:
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
        logger.warning('Prometheus alert loading failed for cluster %s: %s', cluster.id, exc)
        return [], {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'none',
            'label': 'Prometheus Unavailable',
            'configured': False,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(exc, source_label='Prometheus'),
            'response_time_ms': None,
            'last_checked_at': None,
        }
    except Exception as exc:
        logger.exception('Unexpected Prometheus alert loading failure for cluster %s.', cluster.id)
        return [], {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'none',
            'label': 'Prometheus Error',
            'configured': True,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(exc, source_label='Prometheus'),
            'response_time_ms': None,
            'last_checked_at': None,
        }


def get_source_status_message(
    status: AlertSourceStatus,
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
) -> AlertLoadResult:
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
    prometheus_status['fallback_reason'] = friendly_alert_fallback_reason(
        primary_available=False,
        fallback_available=bool(prometheus_status.get('connected')),
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
    logger.warning(
        'All alert sources are unavailable for cluster %s. Alertmanager: %s Prometheus: %s',
        cluster.id,
        alertmanager_reason,
        prometheus_reason,
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
        'fallback_reason': friendly_alert_fallback_reason(
            primary_available=False,
            fallback_available=False,
        ),
        'error': friendly_combined_alert_error(),
        'response_time_ms': None,
        'last_checked_at': datetime.now(
            UTC,
        ),
    }


def filter_items(
    items: list[NormalizedAlert],
    *,
    severity: str,
    status: str,
    namespace: str,
    search: str,
) -> list[NormalizedAlert]:
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
