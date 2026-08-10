# app/analytics/common/context.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app

from app.analytics.common.clusters import get_selected_cluster
from app.analytics.common.params import get_query_value, get_selected_time_range
from app.analytics.common.presentation import present_prometheus_status
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import (
    cluster_required_blocker,
    prometheus_capability_blocker,
    prometheus_connection_blocker,
    prometheus_setup_blocker,
)
from app.integrations.prometheus.capabilities import definition as capability_definition
from app.integrations.prometheus.exceptions import PrometheusError
from app.models import Cluster
from app.prometheus.repository import KUBERNETES_CLUSTER_SCOPE, resolve_instance_for_cluster
from app.prometheus.resolver import resolve_prometheus_sources
from app.prometheus.service import PrometheusService


def get_default_prometheus_status() -> dict[str, Any]:
    return present_prometheus_status(
        {
            'configured': False,
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Not Configured',
            'error': None,
        }
    )


def build_analysis_utilization_context(
    query_args: Mapping[str, Any],
    *,
    check_prometheus_connection: bool = True,
) -> tuple[list[Cluster], Cluster | None, UtilizationService | None, dict[str, Any]]:
    clusters = Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
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
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Waiting for Cluster',
                'error': None,
            }
        )
        base_context['dependency_blocker'] = cluster_required_blocker()
        return clusters, None, None, base_context

    prometheus_config = resolve_instance_for_cluster(cluster.id)

    if prometheus_config is None or not prometheus_config.endpoint.strip():
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Not Configured',
                'error': None,
            }
        )
        base_context['dependency_blocker'] = prometheus_setup_blocker(cluster)
        return clusters, cluster, None, base_context

    if not check_prometheus_connection:
        resolution = resolve_prometheus_sources(
            scope_type=KUBERNETES_CLUSTER_SCOPE,
            scope_key=str(cluster.id),
            required_binding_capabilities=('metrics',),
            required_technical_capabilities=('instant_query',),
        )
        selected = resolution.selected
        if selected is None:
            if not resolution.candidates:
                base_context['dependency_blocker'] = prometheus_setup_blocker(cluster)
            else:
                candidate = resolution.candidates[0]
                if candidate.missing_technical_capabilities:
                    labels = []
                    for key in candidate.missing_technical_capabilities:
                        capability = capability_definition(key)
                        labels.append(capability.label if capability else key)
                    base_context['dependency_blocker'] = prometheus_capability_blocker(
                        cluster,
                        capability_labels=labels,
                        feature_label='Kubernetes Analytics Query Transport',
                    )
                else:
                    base_context['dependency_blocker'] = prometheus_connection_blocker(
                        cluster,
                        detail=candidate.decision_reason,
                    )
            return clusters, cluster, None, base_context

        try:
            prometheus = PrometheusService(cluster)
            utilization_service = UtilizationService(prometheus)
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
            base_context['prometheus_status'] = present_prometheus_status(
                {
                    'configured': True,
                    'connected': False,
                    'response_time_ms': None,
                    'label': 'Prometheus Error',
                    'error': message,
                }
            )
            return clusters, cluster, None, base_context

        observation_degraded = selected.operational_state in {
            'unhealthy',
            'ready_not_connected',
            'degraded_not_connected',
        }
        base_context['prometheus_connected'] = True
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': True,
                'connected': True,
                'response_time_ms': selected.instance.last_response_time_ms,
                'last_checked_at': selected.instance.last_checked_at,
                'label': 'Prometheus Query Ready',
                'description': (
                    'The source is eligible for analytics queries; the previous runtime observation '
                    'was degraded and remains advisory until the dataset query runs.'
                    if observation_degraded
                    else 'The source is eligible for analytics queries.'
                ),
                'error': selected.instance.last_error if observation_degraded else None,
                'tone': 'warning' if observation_degraded else 'normal',
                'icon': 'triangle-alert' if observation_degraded else 'circle-check',
                'observation_degraded': observation_degraded,
            }
        )
        return clusters, cluster, utilization_service, base_context

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
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Not Configured',
                'error': message,
            }
        )
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
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Error',
                'error': message,
            }
        )
        return clusters, cluster, None, base_context

    utilization_service = UtilizationService(
        prometheus,
    )

    try:
        prometheus_status = utilization_service.get_prometheus_status()
    except PrometheusError as exc:
        message = str(exc) or 'Prometheus health check failed for the selected cluster.'
        base_context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Unavailable',
                'error': message,
            }
        )
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
        base_context['prometheus_status'] = present_prometheus_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Unavailable',
                'error': message,
            }
        )
        return clusters, cluster, None, base_context

    base_context['prometheus_status'] = present_prometheus_status(prometheus_status)
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
