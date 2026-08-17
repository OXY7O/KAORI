from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from app.alertmanager.service import get_alertmanager_alerts, get_alertmanager_status
from app.analytics.kubernetes.alerts.contracts import AlertLoadResult, AlertSourceStatus
from app.analytics.kubernetes.alerts.records import (
    deduplicate_alerts,
    normalize_alertmanager_item,
    normalize_metrics_source_alert,
)
from app.analytics.kubernetes.alerts.source_messages import (
    friendly_alert_fallback_reason,
    friendly_alert_source_error,
    friendly_combined_alert_error,
)
from app.integrations.metrics.exceptions import MetricsSourceError
from app.integrations.metrics.query_profiles import get_kubernetes_query_expression
from app.metrics.repository import resolve_instance_for_cluster
from app.metrics.service import MetricsService
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

        alerts = deduplicate_alerts(
            normalize_alertmanager_item(item) for item in result.get('alerts', []) if isinstance(item, dict)
        )

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

        raw_items = result.get('data', {}).get('result', [])
        if not isinstance(raw_items, list):
            raw_items = []

        alerts = deduplicate_alerts(
            normalize_metrics_source_alert(item) for item in raw_items if isinstance(item, dict)
        )

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
