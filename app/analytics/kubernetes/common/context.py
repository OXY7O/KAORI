# app/analytics/kubernetes/common/context.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app

from app.analytics.kubernetes.common.clusters import get_selected_cluster
from app.analytics.kubernetes.common.presentation import present_metrics_source_status
from app.analytics.kubernetes.utilization.service import UtilizationService
from app.analytics.shared.params import get_query_value, get_selected_time_range
from app.common.dependencies import (
    cluster_required_blocker,
    metrics_source_capability_blocker,
    metrics_source_connection_blocker,
    metrics_source_setup_blocker,
)
from app.integrations.metrics.capabilities import definition as capability_definition
from app.integrations.metrics.exceptions import MetricsSourceError
from app.metrics.repository import KUBERNETES_CLUSTER_SCOPE, resolve_instance_for_cluster
from app.metrics.resolver import resolve_metrics_sources
from app.metrics.service import MetricsService
from app.models import Cluster


def get_default_metrics_source_status() -> dict[str, Any]:
    return present_metrics_source_status(
        {
            'configured': False,
            'connected': False,
            'response_time_ms': None,
            'label': 'Metrics Source Not Configured',
            'error': None,
        }
    )


def build_analysis_utilization_context(
    query_args: Mapping[str, Any],
    *,
    check_metrics_source_connection: bool = True,
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
        'metrics_source_connected': False,
        'metrics_source_status': get_default_metrics_source_status(),
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
        base_context['metrics_source_status'] = present_metrics_source_status(
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

    metrics_source_config = resolve_instance_for_cluster(cluster.id)

    if metrics_source_config is None or not metrics_source_config.endpoint.strip():
        base_context['metrics_source_status'] = present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Metrics Source Not Configured',
                'error': None,
            }
        )
        base_context['dependency_blocker'] = metrics_source_setup_blocker(cluster)
        return clusters, cluster, None, base_context

    if not check_metrics_source_connection:
        resolution = resolve_metrics_sources(
            scope_type=KUBERNETES_CLUSTER_SCOPE,
            scope_key=str(cluster.id),
            required_binding_capabilities=('metrics',),
            required_technical_capabilities=('instant_query',),
        )
        selected = resolution.selected
        if selected is None:
            if not resolution.candidates:
                base_context['dependency_blocker'] = metrics_source_setup_blocker(cluster)
            else:
                candidate = resolution.candidates[0]
                if candidate.missing_technical_capabilities:
                    labels = []
                    for key in candidate.missing_technical_capabilities:
                        capability = capability_definition(key)
                        labels.append(capability.label if capability else key)
                    base_context['dependency_blocker'] = metrics_source_capability_blocker(
                        cluster,
                        capability_labels=labels,
                        feature_label='Kubernetes Analytics Query Transport',
                    )
                else:
                    base_context['dependency_blocker'] = metrics_source_connection_blocker(
                        cluster,
                        detail=candidate.decision_reason,
                    )
            return clusters, cluster, None, base_context

        try:
            metrics_source = MetricsService(cluster)
            utilization_service = UtilizationService(metrics_source)
        except Exception as exc:
            current_app.logger.exception(
                'Metrics Source service initialization failed for cluster %s.',
                cluster.name,
            )
            message = str(exc) or 'Metrics Source service initialization failed.'
            base_context['dependency_blocker'] = metrics_source_connection_blocker(
                cluster,
                detail=message,
            )
            base_context['metrics_source_status'] = present_metrics_source_status(
                {
                    'configured': True,
                    'connected': False,
                    'response_time_ms': None,
                    'label': 'Metrics Source Error',
                    'error': message,
                }
            )
            return clusters, cluster, None, base_context

        observation_degraded = selected.operational_state in {
            'unhealthy',
            'ready_not_connected',
            'degraded_not_connected',
        }
        base_context['metrics_source_connected'] = True
        base_context['metrics_source_status'] = present_metrics_source_status(
            {
                'configured': True,
                'connected': True,
                'response_time_ms': selected.instance.last_response_time_ms,
                'last_checked_at': selected.instance.last_checked_at,
                'label': 'Metrics Source Query Ready',
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
        metrics_source = MetricsService(
            cluster,
        )
    except MetricsSourceError as exc:
        message = str(exc) or 'Metrics Source is not configured for the selected cluster.'
        base_context['dependency_blocker'] = metrics_source_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['metrics_source_status'] = present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Metrics Source Not Configured',
                'error': message,
            }
        )
        return clusters, cluster, None, base_context
    except Exception as exc:
        current_app.logger.exception(
            'Metrics Source service initialization failed for cluster %s.',
            cluster.name,
        )
        message = str(exc) or 'Metrics Source service initialization failed.'
        base_context['dependency_blocker'] = metrics_source_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['metrics_source_status'] = present_metrics_source_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Metrics Source Error',
                'error': message,
            }
        )
        return clusters, cluster, None, base_context

    utilization_service = UtilizationService(
        metrics_source,
    )

    try:
        metrics_source_status = utilization_service.get_metrics_source_status()
    except MetricsSourceError as exc:
        message = str(exc) or 'Metrics Source health check failed for the selected cluster.'
        base_context['dependency_blocker'] = metrics_source_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['metrics_source_status'] = present_metrics_source_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Metrics Source Unavailable',
                'error': message,
            }
        )
        return clusters, cluster, None, base_context
    except Exception as exc:
        current_app.logger.exception(
            'Metrics Source health check failed for cluster %s.',
            cluster.name,
        )
        message = str(exc) or 'Metrics Source health check failed.'
        base_context['dependency_blocker'] = metrics_source_connection_blocker(
            cluster,
            detail=message,
        )
        base_context['metrics_source_status'] = present_metrics_source_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Metrics Source Unavailable',
                'error': message,
            }
        )
        return clusters, cluster, None, base_context

    base_context['metrics_source_status'] = present_metrics_source_status(metrics_source_status)
    base_context['metrics_source_connected'] = bool(metrics_source_status.get('connected', False))

    if not base_context['metrics_source_connected']:
        message = str(
            metrics_source_status.get('error')
            or metrics_source_status.get('description')
            or 'Metrics Source did not report a healthy connection.'
        )
        base_context['dependency_blocker'] = metrics_source_connection_blocker(
            cluster,
            detail=message,
        )
        return clusters, cluster, None, base_context

    return clusters, cluster, utilization_service, base_context
