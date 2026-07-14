# app/analytics/common/context.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app

from app.analytics.common.clusters import get_selected_cluster
from app.analytics.common.params import (
    get_query_value,
    get_selected_time_range,
)
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import (
    cluster_required_blocker,
    prometheus_connection_blocker,
    prometheus_setup_blocker,
)
from app.models import Cluster
from app.prometheus.exceptions import PrometheusError
from app.prometheus.service import PrometheusService


def get_default_prometheus_status() -> dict[str, Any]:
    return {
        'connected': False,
        'response_time_ms': None,
        'label': 'Prometheus Disconnected',
        'description': 'Prometheus is unavailable for the selected cluster.',
        'error': None,
    }


def build_analysis_utilization_context(
    query_args: Mapping[str, Any],
    *,
    check_prometheus_connection: bool = True,
) -> tuple[list[Cluster], Cluster | None, UtilizationService | None, dict[str, Any]]:
    clusters = Cluster.query.order_by(
        Cluster.name,
    ).all()

    cluster_id = get_query_value(
        query_args=query_args,
        name='cluster_id',
        default='',
    )

    cluster = get_selected_cluster(
        clusters=clusters,
        cluster_id=cluster_id,
    )

    base_context: dict[str, Any] = {
        'clusters': clusters,
        'cluster': cluster,
        'error': None,
        'prometheus_connected': False,
        'prometheus_status': get_default_prometheus_status(),
        'dependency_blocker': None,
        'selected_namespace': get_query_value(
            query_args=query_args,
            name='namespace',
            default='',
        ),
        'selected_time_range': get_selected_time_range(
            query_args=query_args,
        ),
    }

    if cluster is None:
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Waiting for Cluster',
            'description': 'Prometheus checks start after a Kubernetes cluster is added.',
            'error': None,
        }
        base_context['dependency_blocker'] = cluster_required_blocker()
        return clusters, None, None, base_context

    prometheus_config = cluster.prometheus_config

    if prometheus_config is None or not prometheus_config.endpoint.strip():
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Not Configured',
            'description': 'Configure Prometheus after the cluster is available.',
            'error': None,
        }
        base_context['dependency_blocker'] = prometheus_setup_blocker(cluster)
        return clusters, cluster, None, base_context

    try:
        prometheus = PrometheusService(
            cluster,
        )
    except PrometheusError as exc:
        message = str(exc) or 'Prometheus is not configured for the selected cluster.'
        base_context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Not Configured',
            'description': message,
            'error': message,
        }
        return clusters, cluster, None, base_context
    except Exception as exc:
        current_app.logger.exception(
            'Prometheus service initialization failed for cluster %s.',
            cluster.name,
        )
        message = str(exc) or 'Prometheus service initialization failed.'
        base_context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Error',
            'description': message,
            'error': message,
        }
        return clusters, cluster, None, base_context

    utilization_service = UtilizationService(
        prometheus,
    )

    if not check_prometheus_connection:
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus check pending',
            'description': 'Connection health is loaded by the dedicated Prometheus status section.',
            'error': None,
        }
        return clusters, cluster, utilization_service, base_context

    try:
        prometheus_status = utilization_service.get_prometheus_status()
    except PrometheusError as exc:
        message = str(exc) or 'Prometheus health check failed for the selected cluster.'
        base_context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Unavailable',
            'description': message,
            'error': message,
        }
        return clusters, cluster, None, base_context
    except Exception as exc:
        current_app.logger.exception(
            'Prometheus health check failed for cluster %s.',
            cluster.name,
        )
        message = str(exc) or 'Prometheus health check failed.'
        base_context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['prometheus_status'] = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Unavailable',
            'description': message,
            'error': message,
        }
        return clusters, cluster, None, base_context

    base_context['prometheus_status'] = prometheus_status
    base_context['prometheus_connected'] = bool(prometheus_status.get('connected', False))

    if not base_context['prometheus_connected']:
        message = str(
            prometheus_status.get('error')
            or prometheus_status.get('description')
            or 'Prometheus did not report a healthy connection.'
        )
        base_context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
        return clusters, cluster, None, base_context

    return clusters, cluster, utilization_service, base_context
