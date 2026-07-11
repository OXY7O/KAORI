from __future__ import annotations

from typing import Any, cast

from flask import current_app, render_template, request

from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.utilization.service import (
    UtilizationService,
    get_selected_cluster,
    get_utilization_clusters,
)
from app.common.dependencies import (
    DependencyBlocker,
    cluster_required_blocker,
    prometheus_connection_blocker,
    prometheus_setup_blocker,
    render_dependency_blocker,
)
from app.intelligence.recommendation_engine import (
    build_utilization_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.prometheus.exceptions import PrometheusError
from app.prometheus.service import PrometheusService
from app.rbac.decorators import permission_required

ALLOWED_TREND_HOURS = [
    1,
    6,
    12,
    24,
    168,
    720,
    1440,
]

TREND_STEP_MAP = {
    1: '5m',
    6: '15m',
    12: '30m',
    24: '1h',
    168: '6h',
    720: '12h',
    1440: '1d',
}


def _empty_recommendation_context() -> dict[str, Any]:
    return {
        'actionable_recommendations': [],
        'recommendation_cards': [],
        'recommendation_count': 0,
        'top_cpu_consumers': [],
        'top_memory_consumers': [],
    }


def _build_recommendation_context(
    risk_assessment: dict[str, dict[str, int | float | str]],
    top_cpu_consumers: list[dict[str, str | float]],
    top_memory_consumers: list[dict[str, str | float]],
) -> dict[str, Any]:
    recommendation_payload = {
        'risk_assessment': risk_assessment,
        'top_cpu_consumers': top_cpu_consumers,
        'top_memory_consumers': top_memory_consumers,
    }

    actionable_recommendations = build_utilization_actionable_recommendations(
        recommendation_payload,
    )

    return {
        'actionable_recommendations': actionable_recommendations,
        'recommendation_cards': format_recommendation_cards(
            actionable_recommendations,
            default_title='Continue utilization monitoring',
            default_description=(
                'No actionable utilization recommendation was generated from the current risk signals. '
                'Continue monitoring CPU, memory, storage, pods, and recurring hotspots.'
            ),
            default_source='utilization',
            default_action_type='utilization_review',
        ),
        'recommendation_count': count_actionable_recommendations(
            actionable_recommendations,
        ),
        'top_cpu_consumers': top_cpu_consumers,
        'top_memory_consumers': top_memory_consumers,
    }


def _get_trend_hours() -> int:
    try:
        trend_hours = int(
            request.args.get(
                'trend_hours',
                1,
            )
        )
    except ValueError:
        return 1

    if trend_hours not in ALLOWED_TREND_HOURS:
        return 1

    return trend_hours


@permission_required('analytics.view')
def utilization_trend() -> str:
    _, cluster, service, dependency_context = build_analysis_utilization_context(
        request.args,
    )
    dependency_blocker = dependency_context.get('dependency_blocker')

    if dependency_blocker:
        return render_dependency_blocker(
            dependency_blocker,
        )

    if cluster is None or service is None:
        return render_dependency_blocker(
            cluster_required_blocker(),
        )

    trend_hours = _get_trend_hours()
    trend_step = TREND_STEP_MAP[trend_hours]
    selected_trend_node = request.args.get(
        'trend_node',
        '',
        type=str,
    )

    summary = _empty_summary()
    trends: dict[str, list[dict[str, float]]] = {
        'cpu': [],
        'memory': [],
        'pods': [],
    }
    available_worker_nodes: list[str] = []

    try:
        available_worker_nodes = service.get_worker_node_names()

        if selected_trend_node not in available_worker_nodes:
            selected_trend_node = ''

        if selected_trend_node:
            summary = service.get_detail_summary(
                node_name=selected_trend_node,
            )
        else:
            summary = service.get_summary()

        trends = service.get_trends(
            hours=trend_hours,
            step=trend_step,
            node_name=selected_trend_node or None,
        )
    except PrometheusError as exc:
        return render_dependency_blocker(
            prometheus_connection_blocker(
                cluster,
                detail=str(exc),
            )
        )
    except Exception as exc:
        current_app.logger.exception(
            'Unable to retrieve utilization trend for cluster %s.',
            cluster.name,
        )
        return render_dependency_blocker(
            prometheus_connection_blocker(
                cluster,
                detail=str(exc),
            )
        )

    return render_template(
        'analytics/utilization/partials/_trend.html',
        cluster=cluster,
        summary=summary,
        trends=trends,
        trend_hours=trend_hours,
        allowed_trend_hours=ALLOWED_TREND_HOURS,
        available_worker_nodes=available_worker_nodes,
        selected_trend_node=selected_trend_node,
        error=None,
    )


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
        'cpu': {
            'status': 'Normal',
            'reason': 'No utilization data available',
            'pressure_nodes': 0,
            'utilization': 0,
        },
        'memory': {
            'status': 'Normal',
            'reason': 'No utilization data available',
            'pressure_nodes': 0,
            'utilization': 0,
        },
        'storage': {
            'status': 'Normal',
            'reason': 'No utilization data available',
            'pressure_nodes': 0,
            'utilization': 0,
        },
        'pods': {
            'status': 'Normal',
            'reason': 'No utilization data available',
            'pressure_nodes': 0,
            'utilization': 0,
        },
    }


def _empty_prometheus_status() -> dict[str, bool | int | str | None]:
    return {
        'connected': False,
        'response_time_ms': None,
        'label': 'Prometheus Disconnected',
        'description': 'No successful Prometheus response.',
    }


@permission_required('analytics.view')
def utilization() -> str:
    clusters = get_utilization_clusters()

    cluster_id = request.args.get(
        'cluster_id',
    )

    cluster = get_selected_cluster(
        cluster_id,
    )

    trend_hours = _get_trend_hours()
    trend_step = TREND_STEP_MAP[trend_hours]

    selected_node = request.args.get(
        'node',
        '',
        type=str,
    )

    selected_filesystem_instance = request.args.get(
        'filesystem_instance',
        '',
        type=str,
    )

    selected_trend_node = request.args.get(
        'trend_node',
        '',
        type=str,
    )

    summary = _empty_summary()
    detail_summary = _empty_summary()
    cluster_info = _empty_cluster_info()
    summary_table: list[dict[str, str | float]] = []

    trends: dict[str, list[dict[str, float]]] = {
        'cpu': [],
        'memory': [],
        'pods': [],
    }

    available_nodes: list[str] = []
    available_worker_nodes: list[str] = []
    available_filesystem_instances: list[str] = []

    risk_assessment = _empty_risk_assessment()
    detail_risk_assessment = _empty_risk_assessment()
    prometheus_status = _empty_prometheus_status()
    recommendation_context = _empty_recommendation_context()

    error = None
    dependency_blocker: DependencyBlocker | None = None

    if not cluster:
        return render_template(
            'analytics/utilization/index.html',
            cluster=None,
            clusters=[],
            summary=summary,
            summary_table=summary_table,
            detail_summary=detail_summary,
            trends=trends,
            error=None,
            dependency_blocker=cluster_required_blocker(),
            prometheus_status={
                'connected': False,
                'response_time_ms': None,
                'label': 'Waiting for Cluster',
                'description': 'Prometheus checks start after a Kubernetes cluster is added.',
            },
            cluster_info=cluster_info,
            risk_assessment=risk_assessment,
            detail_risk_assessment=detail_risk_assessment,
            trend_hours=trend_hours,
            allowed_trend_hours=ALLOWED_TREND_HOURS,
            available_nodes=[],
            available_worker_nodes=[],
            available_filesystem_instances=[],
            selected_node='',
            selected_filesystem_instance='',
            selected_trend_node='',
            cluster_query_endpoint='analytics.utilization',
            cluster_query_hidden_params={},
            **_empty_recommendation_context(),
        )

    prometheus_config = cluster.prometheus_config

    if prometheus_config is None or not prometheus_config.endpoint.strip():
        dependency_blocker = prometheus_setup_blocker(cluster)

        return render_template(
            'analytics/utilization/index.html',
            cluster=cluster,
            clusters=clusters,
            summary=summary,
            summary_table=summary_table,
            detail_summary=detail_summary,
            trends=trends,
            error=None,
            dependency_blocker=dependency_blocker,
            prometheus_status={
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Not Configured',
                'description': 'Configure Prometheus after the cluster is available.',
            },
            cluster_info=cluster_info,
            risk_assessment=risk_assessment,
            detail_risk_assessment=detail_risk_assessment,
            trend_hours=trend_hours,
            allowed_trend_hours=ALLOWED_TREND_HOURS,
            available_nodes=[],
            available_worker_nodes=[],
            available_filesystem_instances=[],
            selected_node='',
            selected_filesystem_instance='',
            selected_trend_node='',
            cluster_query_endpoint='analytics.utilization',
            cluster_query_hidden_params={},
            **_empty_recommendation_context(),
        )

    try:
        prometheus = PrometheusService(
            cluster,
        )

        service = UtilizationService(
            prometheus,
        )

        prometheus_status = service.get_prometheus_status()

        if not prometheus_status.get('connected', False):
            raise PrometheusError(
                str(
                    prometheus_status.get('error')
                    or prometheus_status.get('description')
                    or 'Prometheus did not report a healthy connection.'
                )
            )

        available_nodes = service.get_node_names()
        available_worker_nodes = service.get_worker_node_names()
        available_filesystem_instances = service.get_filesystem_instances()

        if selected_node not in available_nodes:
            selected_node = ''

        if selected_trend_node not in available_worker_nodes:
            selected_trend_node = ''

        if selected_filesystem_instance not in available_filesystem_instances:
            selected_filesystem_instance = ''

        summary = service.get_summary()

        cluster_info = service.get_cluster_info(
            summary,
        )

        summary_table = service.get_summary_table(
            summary,
        )

        detail_summary = service.get_detail_summary(
            node_name=selected_node or None,
            filesystem_instance=selected_filesystem_instance or None,
        )

        trends = service.get_trends(
            hours=trend_hours,
            step=trend_step,
            node_name=selected_trend_node or None,
        )

        risk_assessment = service.get_capacity_pressure_risk(
            cast(
                dict[str, int | float],
                summary,
            ),
        )

        detail_risk_assessment = service.get_capacity_pressure_risk(
            cast(
                dict[str, int | float],
                detail_summary,
            ),
            selected_node or None,
        )

        top_cpu_consumers = service.get_top_cpu_consumers()[:5]
        top_memory_consumers = service.get_top_memory_consumers()[:5]

        recommendation_context = _build_recommendation_context(
            risk_assessment=risk_assessment,
            top_cpu_consumers=top_cpu_consumers,
            top_memory_consumers=top_memory_consumers,
        )

    except PrometheusError as exc:
        message = str(exc) or 'Prometheus is not configured for the selected cluster.'
        prometheus_status = {
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Unavailable',
            'description': message,
        }
        dependency_blocker = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
    except Exception as exc:
        current_app.logger.exception(
            exc,
        )

        dependency_blocker = prometheus_connection_blocker(
            cluster,
            detail=str(exc),
        )

    return render_template(
        'analytics/utilization/index.html',
        cluster=cluster,
        clusters=clusters,
        summary=summary,
        summary_table=summary_table,
        detail_summary=detail_summary,
        trends=trends,
        error=error,
        dependency_blocker=dependency_blocker,
        prometheus_status=prometheus_status,
        cluster_info=cluster_info,
        risk_assessment=risk_assessment,
        detail_risk_assessment=detail_risk_assessment,
        trend_hours=trend_hours,
        allowed_trend_hours=ALLOWED_TREND_HOURS,
        available_nodes=available_nodes,
        available_worker_nodes=available_worker_nodes,
        available_filesystem_instances=available_filesystem_instances,
        selected_node=selected_node,
        selected_filesystem_instance=selected_filesystem_instance,
        selected_trend_node=selected_trend_node,
        cluster_query_endpoint='analytics.utilization',
        cluster_query_hidden_params={
            'trend_hours': trend_hours,
            'trend_node': selected_trend_node,
            'node': selected_node,
            'filesystem_instance': selected_filesystem_instance,
        },
        **recommendation_context,
    )


@permission_required('analytics.view')
def utilization_node_detail() -> str:
    _, cluster, service, dependency_context = build_analysis_utilization_context(
        request.args,
    )
    dependency_blocker = dependency_context.get('dependency_blocker')

    if dependency_blocker:
        return render_dependency_blocker(
            dependency_blocker,
        )

    if cluster is None or service is None:
        return render_dependency_blocker(
            cluster_required_blocker(),
        )

    selected_node = request.args.get(
        'node',
        '',
        type=str,
    )
    selected_filesystem_instance = request.args.get(
        'filesystem_instance',
        '',
        type=str,
    )

    detail_summary = _empty_summary()
    detail_risk_assessment = _empty_risk_assessment()

    try:
        available_nodes = service.get_node_names()
        available_filesystem_instances = service.get_filesystem_instances()

        if selected_node not in available_nodes:
            selected_node = ''

        if selected_filesystem_instance not in available_filesystem_instances:
            selected_filesystem_instance = ''

        detail_summary = service.get_detail_summary(
            node_name=selected_node or None,
            filesystem_instance=selected_filesystem_instance or None,
        )

        detail_risk_assessment = service.get_capacity_pressure_risk(
            cast(
                dict[str, int | float],
                detail_summary,
            ),
            selected_node or None,
        )
    except PrometheusError as exc:
        return render_dependency_blocker(
            prometheus_connection_blocker(
                cluster,
                detail=str(exc),
            )
        )
    except Exception as exc:
        current_app.logger.exception(
            'Unable to retrieve utilization node detail for cluster %s.',
            cluster.name,
        )
        return render_dependency_blocker(
            prometheus_connection_blocker(
                cluster,
                detail=str(exc),
            )
        )

    return render_template(
        'analytics/utilization/partials/_node_detail.html',
        cluster=cluster,
        detail_summary=detail_summary,
        detail_risk_assessment=detail_risk_assessment,
        available_nodes=available_nodes,
        available_filesystem_instances=available_filesystem_instances,
        selected_node=selected_node,
        selected_filesystem_instance=selected_filesystem_instance,
        error=None,
    )
