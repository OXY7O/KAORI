from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from app.integrations.observability.alert_source.providers.alertmanager.application.service import (
    get_alertmanager_alerts,
    get_alertmanager_status,
)
from app.integrations.observability.metrics_source.application.repository import resolve_instance_for_cluster
from app.integrations.observability.metrics_source.application.service import MetricsService
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles import get_kubernetes_query_expression
from app.kubernetes.analytics.alerts.contracts import AlertLoadResult, AlertSourceStatus
from app.kubernetes.analytics.alerts.records import (
    deduplicate_alerts,
    normalize_alertmanager_item,
    normalize_metrics_source_alert,
)
from app.kubernetes.analytics.alerts.source_messages import (
    friendly_alert_fallback_reason,
    friendly_alert_source_error,
    friendly_combined_alert_error,
)
from app.models import Cluster

logger = logging.getLogger(__name__)


ACTIVE_ALERT_STATE_QUERY = get_kubernetes_query_expression('analytics.alerts.queries.ACTIVE_ALERTS_EXPRESSION')


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


def _validated_alertmanager_items(result: object) -> list[dict]:
    """Only a complete Alertmanager list can prove an observed zero-alert state."""
    if not isinstance(result, dict):
        raise ValueError('Alertmanager returned an invalid alert response.')
    if not result.get('connected'):
        return []
    if result.get('error'):
        raise ValueError('Alertmanager returned inconsistent alert source evidence.')
    items = result.get('alerts')
    if not isinstance(items, list):
        raise ValueError('Alertmanager did not return an alerts list.')
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Alertmanager returned a malformed alert record.')
        labels = item.get('labels', {})
        if not isinstance(labels, dict) or not str(
            item.get('alertname') or item.get('name') or labels.get('alertname') or ''
        ).strip():
            raise ValueError('Alertmanager returned an alert without valid identity.')
    return items


def _validated_metrics_source_items(result: object) -> list[dict]:
    """Reject partial Prometheus responses rather than fabricating no alerts."""
    if not isinstance(result, dict) or result.get('error') or result.get('status', 'success') != 'success':
        raise ValueError('Metrics Source returned an invalid alert query response.')
    data = result.get('data')
    if not isinstance(data, dict) or data.get('resultType', 'vector') != 'vector':
        raise ValueError('Metrics Source did not return vector alert evidence.')
    items = data.get('result')
    if not isinstance(items, list):
        raise ValueError('Metrics Source did not return an alert result list.')
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Metrics Source returned a malformed alert series.')
        metric = item.get('metric')
        value = item.get('value')
        if (
            not isinstance(metric, dict)
            or not str(metric.get('alertname') or '').strip()
            or not isinstance(value, (list, tuple))
            or len(value) < 2
        ):
            raise ValueError('Metrics Source returned incomplete alert series evidence.')
    return items


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

        items = _validated_alertmanager_items(result)
        alerts = deduplicate_alerts(normalize_alertmanager_item(item) for item in items)

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


def load_metrics_source_alerts(
    *,
    cluster: Cluster,
) -> AlertLoadResult:
    started_at = perf_counter()
    configured = resolve_instance_for_cluster(cluster.id) is not None
    try:
        service = MetricsService(cluster)
        result = service.instant_query(ACTIVE_ALERT_STATE_QUERY)
        elapsed_ms = max(int((perf_counter() - started_at) * 1000), 0)

        raw_items = _validated_metrics_source_items(result)
        alerts = deduplicate_alerts(normalize_metrics_source_alert(item) for item in raw_items)

        return alerts, {
            'source': 'metrics_source',
            'selected_source': 'metrics_source',
            'resolved_source': 'metrics_source',
            'label': 'Metrics Source Connected',
            'configured': True,
            'connected': True,
            'fallback_used': False,
            'fallback_reason': None,
            'error': None,
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(UTC),
        }

    except MetricsSourceError as exc:
        elapsed_ms = max(int((perf_counter() - started_at) * 1000), 0)
        logger.warning('Metrics Source alert loading failed for cluster %s: %s', cluster.id, exc)
        return [], {
            'source': 'metrics_source',
            'selected_source': 'metrics_source',
            'resolved_source': 'none',
            'label': 'Metrics Source Unavailable' if configured else 'Metrics Source Not Configured',
            'configured': configured,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(exc, source_label='Metrics Source'),
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(UTC),
        }
    except Exception as exc:
        elapsed_ms = max(int((perf_counter() - started_at) * 1000), 0)
        logger.exception('Unexpected Metrics Source alert loading failure for cluster %s.', cluster.id)
        return [], {
            'source': 'metrics_source',
            'selected_source': 'metrics_source',
            'resolved_source': 'none',
            'label': 'Metrics Source Error',
            'configured': configured,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(exc, source_label='Metrics Source'),
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(UTC),
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

    if source == 'metrics_source':
        return load_metrics_source_alerts(
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

    metrics_source_alerts, metrics_source_status = load_metrics_source_alerts(
        cluster=cluster,
    )

    alertmanager_reason = get_source_status_message(
        alertmanager_status,
        default='Alertmanager is unavailable.',
    )

    metrics_source_status['selected_source'] = 'auto'
    metrics_source_status['fallback_used'] = True
    metrics_source_status['fallback_reason'] = friendly_alert_fallback_reason(
        primary_available=False,
        fallback_available=bool(metrics_source_status.get('connected')),
    )

    if metrics_source_status.get(
        'connected',
    ):
        metrics_source_status['label'] = 'Metrics Source Fallback Connected'
        metrics_source_status['error'] = None

        return metrics_source_alerts, metrics_source_status

    metrics_source_reason = get_source_status_message(
        metrics_source_status,
        default='Metrics Source fallback is unavailable.',
    )
    logger.warning(
        'All alert sources are unavailable for cluster %s. Alertmanager: %s Metrics Source: %s',
        cluster.id,
        alertmanager_reason,
        metrics_source_reason,
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
            metrics_source_status.get(
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
