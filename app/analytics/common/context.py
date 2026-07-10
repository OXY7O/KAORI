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
            'label': 'No Cluster',
            'description': 'Add at least one Kubernetes cluster to load Prometheus-backed analytics.',
            'error': None,
        }
        return clusters, None, None, base_context

    try:
        prometheus = PrometheusService(
            cluster,
        )
    except PrometheusError as exc:
        message = str(exc) or 'Prometheus is not configured for the selected cluster.'
        base_context['error'] = (
            'Prometheus is not configured or available for the selected cluster. '
            'Configure the integration to load live analytics data.'
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
        base_context['error'] = (
            'KAORI could not initialize Prometheus for the selected cluster. '
            'Review the endpoint, credentials, TLS settings, and network connectivity.'
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

    return clusters, cluster, utilization_service, base_context
