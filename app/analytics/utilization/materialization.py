from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app

from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import (
    cluster_required_blocker,
    prometheus_capability_blocker,
    prometheus_connection_blocker,
)
from app.integrations.prometheus.exceptions import PrometheusError

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


def get_utilization_trend_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    _, cluster, service, dependency_context = build_analysis_utilization_context(query_args)
    dependency_blocker = dependency_context.get('dependency_blocker')
    if dependency_blocker:
        return {'dependency_blocker': dependency_blocker}
    if cluster is None or service is None:
        return {'dependency_blocker': cluster_required_blocker()}
    if not isinstance(service, UtilizationService):
        return {'dependency_blocker': prometheus_connection_blocker(cluster, detail='Utilization service unavailable.')}

    requirements = service.requirements()
    if not requirements.ok:
        missing = list((requirements.payload or {}).get('missing_capabilities', []))
        return {
            'dependency_blocker': prometheus_capability_blocker(
                cluster,
                feature_label='Utilization Analytics',
                missing_capabilities=missing,
            )
        }

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
            service.get_detail_summary(node_name=selected_trend_node)
            if selected_trend_node
            else service.get_summary()
        )
        trends = service.get_trends(
            hours=trend_hours,
            step=TREND_STEP_MAP[trend_hours],
            node_name=selected_trend_node or None,
        )
    except PrometheusError as exc:
        return {'dependency_blocker': prometheus_connection_blocker(cluster, detail=str(exc))}
    except Exception as exc:
        current_app.logger.exception('Unable to materialize utilization trend for cluster %s.', cluster.name)
        return {'dependency_blocker': prometheus_connection_blocker(cluster, detail=str(exc))}

    return {
        'cluster': cluster,
        'summary': summary,
        'trends': trends,
        'trend_hours': trend_hours,
        'allowed_trend_hours': list(ALLOWED_TREND_HOURS),
        'available_worker_nodes': available_worker_nodes,
        'selected_trend_node': selected_trend_node,
        'error': None,
        'dependency_blocker': None,
    }
