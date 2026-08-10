from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from flask import current_app

from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import (
    cluster_required_blocker,
    prometheus_capability_blocker,
    prometheus_connection_blocker,
)
from app.integrations.prometheus.exceptions import PrometheusError
from app.intelligence.recommendation_engine import (
    build_utilization_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)

ALLOWED_TREND_HOURS = (1, 6, 12, 24, 168, 720, 1440)
TREND_STEP_MAP = {
    1: '5m',
    6: '15m',
    12: '30m',
    24: '1h',
    168: '6h',
    720: '12h',
    1440: '1d',
}


def _trend_hours(query_args: Mapping[str, Any]) -> int:
    try:
        value = int(str(query_args.get('trend_hours', 24)))
    except (TypeError, ValueError):
        return 24
    return value if value in ALLOWED_TREND_HOURS else 24


def build_utilization_trend_summary(
    trends: Mapping[str, list[dict[str, float]]],
) -> dict[str, Any]:
    """Build one stable operational summary for trend presentation."""
    resources: dict[str, dict[str, float | int]] = {}
    peak_resource = 'None'
    peak_value = 0.0
    sample_count = 0

    for resource in ('cpu', 'memory', 'pods'):
        values = [float(point.get('value', 0) or 0) for point in trends.get(resource, []) if isinstance(point, Mapping)]
        if not values:
            resources[resource] = {
                'current': 0.0,
                'average': 0.0,
                'peak': 0.0,
                'sample_count': 0,
            }
            continue

        resource_peak = max(values)
        resources[resource] = {
            'current': round(values[-1], 2),
            'average': round(sum(values) / len(values), 2),
            'peak': round(max(values), 2),
            'sample_count': len(values),
        }
        sample_count = max(sample_count, len(values))
        if resource_peak > peak_value:
            peak_resource = resource.upper() if resource != 'pods' else 'Pods'
            peak_value = resource_peak

    if peak_value >= 90:
        posture, tone = 'Critical Pressure', 'critical'
    elif peak_value >= 75:
        posture, tone = 'Capacity Watch', 'warning'
    elif sample_count:
        posture, tone = 'Stable', 'normal'
    else:
        posture, tone = 'No Data', 'unknown'

    return {
        'resources': resources,
        'sample_count': sample_count,
        'peak_resource': peak_resource,
        'peak_value': round(peak_value, 2),
        'posture': posture,
        'tone': tone,
    }


def _empty_summary() -> dict[str, int | float]:
    return {
        'cpu_capacity': 0,
        'cpu_usage': 0,
        'cpu_utilization': 0,
        'memory_capacity': 0,
        'memory_usage': 0,
        'memory_utilization': 0,
        'storage_capacity': 0,
        'storage_usage': 0,
        'storage_available': 0,
        'storage_utilization': 0,
        'storage_capacity_gib': 0,
        'storage_usage_gib': 0,
        'storage_available_gib': 0,
        'pod_count': 0,
        'pod_capacity': 0,
        'pod_utilization': 0,
    }


def _empty_cluster_info() -> dict[str, int | float | str]:
    return {
        'kubernetes_version': '-',
        'total_nodes': 0,
        'ready_nodes': 0,
        'not_ready_nodes': 0,
        'worker_nodes': 0,
        'master_nodes': 0,
        'cpu_capacity': 0,
        'memory_capacity': 0,
        'pod_capacity': 0,
    }


def _empty_risk_assessment() -> dict[str, dict[str, int | float | str]]:
    return {
        resource: {
            'status': 'Unknown',
            'reason': 'Capacity evidence unavailable',
            'pressure_nodes': 0,
            'utilization': 0,
        }
        for resource in ('cpu', 'memory', 'storage', 'pods')
    }


def _recommendation_context(
    risk_assessment: dict[str, dict[str, int | float | str]],
    top_cpu_consumers: list[dict[str, Any]],
    top_memory_consumers: list[dict[str, Any]],
) -> dict[str, Any]:
    recommendations = build_utilization_actionable_recommendations(
        {
            'risk_assessment': risk_assessment,
            'top_cpu_consumers': top_cpu_consumers,
            'top_memory_consumers': top_memory_consumers,
        }
    )
    return {
        'actionable_recommendations': recommendations,
        'recommendation_cards': format_recommendation_cards(
            recommendations,
            default_title='Continue Utilization Monitoring',
            default_description=(
                'No actionable utilization recommendation was generated from the current risk signals. '
                'Continue monitoring CPU, memory, storage, pods, and recurring hotspots.'
            ),
            default_source='utilization',
            default_action_type='utilization_review',
        ),
        'recommendation_count': count_actionable_recommendations(recommendations),
        'top_cpu_consumers': top_cpu_consumers,
        'top_memory_consumers': top_memory_consumers,
    }


def _dependency_context(query_args: Mapping[str, Any]) -> tuple[Any, UtilizationService | None, dict[str, Any]]:
    _, cluster, service, context = build_analysis_utilization_context(
        query_args,
        check_prometheus_connection=False,
    )
    blocker = context.get('dependency_blocker')
    if blocker:
        return cluster, None, context
    if cluster is None:
        context['dependency_blocker'] = cluster_required_blocker()
        return None, None, context
    if not isinstance(service, UtilizationService):
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail='Utilization service unavailable.',
        )
        return cluster, None, context
    requirements = service.requirements()
    if not requirements.ok:
        missing = list((requirements.payload or {}).get('missing_capabilities', []))
        context['dependency_blocker'] = prometheus_capability_blocker(
            cluster,
            feature_label='Utilization Analytics',
            missing_capabilities=missing,
        )
        return cluster, None, context
    return cluster, service, context


def get_utilization_summary_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    cluster, service, context = _dependency_context(query_args)
    summary = _empty_summary()
    cluster_info = _empty_cluster_info()
    risk_assessment = _empty_risk_assessment()
    base = {
        **context,
        'cluster': cluster,
        'summary': summary,
        'cluster_info': cluster_info,
        'risk_assessment': risk_assessment,
        'error': None,
        'prometheus_connected': False,
        'prometheus_status': context.get('prometheus_status')
        or {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Unavailable',
            'description': 'No successful Prometheus observation is available.',
        },
        **_recommendation_context(risk_assessment, [], []),
    }
    if cluster is None or service is None:
        return base

    try:
        prometheus_status = service.get_prometheus_status()
        if not prometheus_status.get('connected', False):
            raise PrometheusError(
                str(
                    prometheus_status.get('error')
                    or prometheus_status.get('description')
                    or 'Prometheus did not report a healthy connection.'
                )
            )
        summary = service.get_summary()
        cluster_info = service.get_cluster_info(summary)
        risk_assessment = service.get_capacity_pressure_risk(cast(dict[str, int | float], summary))
        top_cpu_consumers = service.get_top_cpu_consumers()[:5]
        top_memory_consumers = service.get_top_memory_consumers()[:5]
        base.update(
            {
                'summary': summary,
                'cluster_info': cluster_info,
                'risk_assessment': risk_assessment,
                'prometheus_status': prometheus_status,
                'prometheus_connected': True,
                'dependency_blocker': None,
                **_recommendation_context(
                    risk_assessment,
                    top_cpu_consumers,
                    top_memory_consumers,
                ),
            }
        )
    except PrometheusError as exc:
        base['dependency_blocker'] = prometheus_connection_blocker(cluster, detail=str(exc))
    except Exception as exc:
        current_app.logger.exception(
            'Unable to materialize utilization summary for cluster %s.',
            cluster.name,
        )
        base['dependency_blocker'] = prometheus_connection_blocker(cluster, detail=str(exc))
    return base


def get_utilization_trend_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    cluster, service, context = _dependency_context(query_args)
    dependency_blocker = context.get('dependency_blocker')
    if dependency_blocker:
        return {'cluster': cluster, 'dependency_blocker': dependency_blocker}
    if cluster is None or service is None:
        return {'dependency_blocker': cluster_required_blocker()}

    trend_hours = _trend_hours(query_args)
    selected_trend_node = str(query_args.get('trend_node', '') or '')
    summary = _empty_summary()
    trends: dict[str, list[dict[str, float]]] = {'cpu': [], 'memory': [], 'pods': []}
    available_worker_nodes: list[str] = []
    try:
        available_worker_nodes = service.get_worker_node_names()
        if selected_trend_node not in available_worker_nodes:
            selected_trend_node = ''
        summary = (
            service.get_detail_summary(node_name=selected_trend_node) if selected_trend_node else service.get_summary()
        )
        trends = service.get_trends(
            hours=trend_hours,
            step=TREND_STEP_MAP[trend_hours],
            node_name=selected_trend_node or None,
        )
    except PrometheusError as exc:
        return {'cluster': cluster, 'dependency_blocker': prometheus_connection_blocker(cluster, detail=str(exc))}
    except Exception as exc:
        current_app.logger.exception('Unable to materialize utilization trend for cluster %s.', cluster.name)
        return {'cluster': cluster, 'dependency_blocker': prometheus_connection_blocker(cluster, detail=str(exc))}

    return {
        'cluster': cluster,
        'summary': summary,
        'trends': trends,
        'trend_summary': build_utilization_trend_summary(trends),
        'trend_hours': trend_hours,
        'allowed_trend_hours': list(ALLOWED_TREND_HOURS),
        'available_worker_nodes': available_worker_nodes,
        'selected_trend_node': selected_trend_node,
        'error': None,
        'dependency_blocker': None,
    }


def get_utilization_node_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    cluster, service, context = _dependency_context(query_args)
    dependency_blocker = context.get('dependency_blocker')
    if dependency_blocker:
        return {'cluster': cluster, 'dependency_blocker': dependency_blocker}
    if cluster is None or service is None:
        return {'dependency_blocker': cluster_required_blocker()}

    selected_node = str(query_args.get('node', '') or '')
    try:
        available_nodes = service.get_node_names()
        if selected_node not in available_nodes:
            selected_node = ''
        detail_summary = service.get_detail_summary(node_name=selected_node or None)
        detail_risk_assessment = service.get_capacity_pressure_risk(
            cast(dict[str, int | float], detail_summary),
            selected_node or None,
        )
    except PrometheusError as exc:
        return {'cluster': cluster, 'dependency_blocker': prometheus_connection_blocker(cluster, detail=str(exc))}
    except Exception as exc:
        current_app.logger.exception(
            'Unable to materialize utilization node detail for cluster %s.',
            cluster.name,
        )
        return {'cluster': cluster, 'dependency_blocker': prometheus_connection_blocker(cluster, detail=str(exc))}

    return {
        'cluster': cluster,
        'detail_summary': detail_summary,
        'detail_risk_assessment': detail_risk_assessment,
        'available_nodes': available_nodes,
        'selected_node': selected_node,
        'error': None,
        'dependency_blocker': None,
    }
