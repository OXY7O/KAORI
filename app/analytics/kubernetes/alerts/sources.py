from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from app.alertmanager.service import get_alertmanager_alerts, get_alertmanager_status
from app.analytics.kubernetes.alerts.contracts import AlertLoadResult, AlertSourceStatus
from app.analytics.kubernetes.alerts.records import deduplicate_alerts, normalize_alertmanager_item, normalize_prometheus_alert
from app.analytics.kubernetes.alerts.source_messages import (
    friendly_alert_fallback_reason,
    friendly_alert_source_error,
    friendly_combined_alert_error,
)
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.models import Cluster
from app.prometheus.repository import resolve_instance_for_cluster
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


def load_prometheus_alerts(
    *,
    cluster: Cluster,
) -> AlertLoadResult:
    started_at = perf_counter()
    configured = resolve_instance_for_cluster(cluster.id) is not None
    try:
        service = PrometheusService(cluster)
        result = service.instant_query(PROMETHEUS_ALERTS_QUERY)
        elapsed_ms = max(int((perf_counter() - started_at) * 1000), 0)

        raw_items = result.get('data', {}).get('result', [])
        if not isinstance(raw_items, list):
            raw_items = []

        alerts = deduplicate_alerts(normalize_prometheus_alert(item) for item in raw_items if isinstance(item, dict))

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
            'last_checked_at': datetime.now(UTC),
        }

    except PrometheusError as exc:
        elapsed_ms = max(int((perf_counter() - started_at) * 1000), 0)
        logger.warning('Prometheus alert loading failed for cluster %s: %s', cluster.id, exc)
        return [], {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'none',
            'label': 'Prometheus Unavailable' if configured else 'Prometheus Not Configured',
            'configured': configured,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(exc, source_label='Prometheus'),
            'response_time_ms': elapsed_ms,
            'last_checked_at': datetime.now(UTC),
        }
    except Exception as exc:
        elapsed_ms = max(int((perf_counter() - started_at) * 1000), 0)
        logger.exception('Unexpected Prometheus alert loading failure for cluster %s.', cluster.id)
        return [], {
            'source': 'prometheus',
            'selected_source': 'prometheus',
            'resolved_source': 'none',
            'label': 'Prometheus Error',
            'configured': configured,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': friendly_alert_source_error(exc, source_label='Prometheus'),
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
