from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from app.analytics.kubernetes.common.base_service import AnalyticsBaseService
from app.analytics.kubernetes.common.context import build_analysis_utilization_context
from app.analytics.kubernetes.forecast.calculation import (
    _build_chart_payload,
    _build_no_forecast_data_message,
    _build_summary,
    _calculate_forecast,
    _daily_average,
    _extract_instant_value,
    _extract_range_points,
    _get_forecast_method_meta,
    _normalize_option,
    _parse_days,
    _safe_message,
    _select_range_step,
    _to_metrics_time,
)
from app.analytics.kubernetes.forecast.contracts import (
    FORECAST_HORIZON_OPTIONS,
    FORECAST_METHOD_OPTIONS,
    HISTORY_WINDOW_OPTIONS,
    ForecastPoint,
    ForecastResourceDefinition,
)
from app.analytics.kubernetes.forecast.presentation import _empty_payload
from app.analytics.kubernetes.forecast.resource import build_resource_forecast_payload
from app.analytics.kubernetes.utilization.service import UtilizationService
from app.analytics.shared.params import get_query_value
from app.common.dependencies import metrics_source_connection_blocker
from app.integrations.metrics.query_profiles import get_kubernetes_query_expression
from app.intelligence.recommendation_engine import (
    build_forecast_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster

CPU_USAGE_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.forecast.queries.CPU_USAGE_BY_NAMESPACE_QUERY'
)
CPU_USAGE_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.CPU_USAGE_QUERY')
CPU_WORKER_CAPACITY_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY')
MEMORY_USAGE_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.forecast.queries.MEMORY_USAGE_BY_NAMESPACE_QUERY'
)
MEMORY_USAGE_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.MEMORY_USAGE_QUERY')
MEMORY_WORKER_CAPACITY_QUERY = get_kubernetes_query_expression(
    'analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY'
)
NAMESPACE_ACTIVE_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.NAMESPACE_ACTIVE_QUERY')
POD_USAGE_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.forecast.queries.POD_USAGE_BY_NAMESPACE_QUERY'
)
POD_USAGE_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.POD_USAGE_QUERY')
POD_WORKER_CAPACITY_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.POD_WORKER_CAPACITY_QUERY')
STORAGE_CAPACITY_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.forecast.queries.STORAGE_CAPACITY_BY_NAMESPACE_QUERY'
)
STORAGE_CAPACITY_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.STORAGE_CAPACITY_QUERY')
STORAGE_USAGE_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.forecast.queries.STORAGE_USAGE_BY_NAMESPACE_QUERY'
)
STORAGE_USAGE_QUERY = get_kubernetes_query_expression('analytics.forecast.queries.STORAGE_USAGE_QUERY')


class ForecastAnalysisService(AnalyticsBaseService):
    def __init__(
        self,
        utilization_service: UtilizationService,
        cluster: Cluster,
    ) -> None:
        self.utilization_service = utilization_service
        self.cluster = cluster
        self.consumer = utilization_service.consumer

    def get_metrics_source_status(
        self,
    ) -> dict[str, Any]:
        return self.utilization_service.get_metrics_source_status()

    def get_namespace_options(
        self,
    ) -> list[str]:
        result = self.get_metrics_result(
            NAMESPACE_ACTIVE_QUERY,
        )

        namespaces: set[str] = set()

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            namespace = metric.get(
                'namespace',
                '',
            )

            if (
                isinstance(
                    namespace,
                    str,
                )
                and namespace
            ):
                namespaces.add(
                    namespace,
                )

        return sorted(
            namespaces,
        )

    def get_forecast_analysis(
        self,
        *,
        namespace: str,
        history_window: str,
        forecast_horizon: str,
        method: str = 'holt_winters',
    ) -> dict[str, Any]:
        history_days = _parse_days(
            history_window,
            default=30,
        )
        horizon_days = _parse_days(
            forecast_horizon,
            default=90,
        )
        method = _normalize_option(
            method,
            'holt_winters',
            {item['value'] for item in FORECAST_METHOD_OPTIONS},
        )
        method_meta = _get_forecast_method_meta(method)

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=history_days)
        step = _select_range_step(history_days)

        definitions = _get_resource_definitions(namespace)

        items: list[dict[str, Any]] = []

        for definition in definitions:
            items.append(
                self._build_resource_forecast(
                    definition=definition,
                    start_time=start_time,
                    end_time=end_time,
                    step=step,
                    horizon_days=horizon_days,
                    method=method,
                ),
            )

        summary = _build_summary(items)

        actionable_payload = {
            'namespace': namespace,
            'history_window': history_window,
            'forecast_horizon': forecast_horizon,
            'history_days': history_days,
            'horizon_days': horizon_days,
            'forecast_method': method,
            'forecast_method_label': method_meta['label'],
            'items': items,
            'summary': summary,
        }

        actionable_recommendations = build_forecast_actionable_recommendations(
            actionable_payload,
        )

        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Continue Forecast Monitoring',
            default_description=(
                'No actionable forecast recommendation was generated from the current projection. '
                'Continue monitoring forecast trend and threshold ETA.'
            ),
            default_source='forecast',
            default_action_type='forecast_review',
        )

        has_data = any(item['has_data'] for item in items)

        return {
            'has_data': has_data,
            'message': None if has_data else _build_no_forecast_data_message(items),
            'namespace': namespace,
            'history_window': history_window,
            'forecast_horizon': forecast_horizon,
            'history_days': history_days,
            'horizon_days': horizon_days,
            'forecast_method': method,
            'method_label': method_meta['label'],
            'method_description': method_meta['description'],
            'generated_at': end_time,
            'items': items,
            'summary': summary,
            'chart': _build_chart_payload(items),
            'actionable_recommendations': actionable_recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': count_actionable_recommendations(
                actionable_recommendations,
            ),
        }

    def _build_resource_forecast(
        self,
        *,
        definition: ForecastResourceDefinition,
        start_time: datetime,
        end_time: datetime,
        step: str,
        horizon_days: int,
        method: str = 'holt_winters',
    ) -> dict[str, Any]:
        daily_points = _daily_average(
            self._query_range(
                query=definition.usage_query,
                start_time=start_time,
                end_time=end_time,
                step=step,
            )
        )
        capacity = self._query_instant(query=definition.capacity_query)
        forecast_result = _calculate_forecast(
            values=daily_points,
            horizon_days=horizon_days,
            method=method,
        )
        return build_resource_forecast_payload(
            definition=definition,
            daily_points=daily_points,
            capacity=capacity,
            forecast_result=forecast_result,
            horizon_days=horizon_days,
            method=method,
            fallback_time=end_time,
        )

    def _query_range(
        self,
        *,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
    ) -> list[ForecastPoint]:
        result = self.consumer.query_range(
            query,
            _to_metrics_time(start_time),
            _to_metrics_time(end_time),
            step,
            required_capabilities=('range_query',),
        )
        return _extract_range_points(result)

    def _query_instant(
        self,
        *,
        query: str,
    ) -> float:
        result = self.consumer.query(
            query,
            required_capabilities=('instant_query',),
        )
        return _extract_instant_value(result)


def get_forecast_analysis_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, selected_cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
    )

    cluster = selected_cluster or context.get(
        'cluster',
    )

    selected_namespace = get_query_value(
        query_args=query_args,
        name='namespace',
        default='',
    )
    selected_history_window = _normalize_option(
        get_query_value(
            query_args=query_args,
            name='history_window',
            default='30d',
        ),
        '30d',
        {item['value'] for item in HISTORY_WINDOW_OPTIONS},
    )
    selected_forecast_horizon = _normalize_option(
        get_query_value(
            query_args=query_args,
            name='forecast_horizon',
            default='90d',
        ),
        '90d',
        {item['value'] for item in FORECAST_HORIZON_OPTIONS},
    )
    selected_tab = _normalize_option(
        get_query_value(query_args=query_args, name='tab', default='cpu'),
        'cpu',
        {'cpu', 'memory', 'storage', 'pods', 'trend', 'recommendations'},
    )
    selected_method = _normalize_option(
        get_query_value(
            query_args=query_args,
            name='method',
            default='holt_winters',
        ),
        'holt_winters',
        {item['value'] for item in FORECAST_METHOD_OPTIONS},
    )

    context.update(
        {
            'selected_namespace': selected_namespace,
            'selected_history_window': selected_history_window,
            'selected_forecast_horizon': selected_forecast_horizon,
            'selected_tab': selected_tab,
            'selected_method': selected_method,
            'history_window_options': HISTORY_WINDOW_OPTIONS,
            'forecast_horizon_options': FORECAST_HORIZON_OPTIONS,
            'forecast_method_options': FORECAST_METHOD_OPTIONS,
            'namespace_options': [],
            'forecast_payload': _empty_payload(
                message='No cluster available. Add a Kubernetes cluster first.',
            ),
        }
    )

    if utilization_service is None or cluster is None:
        return context

    metrics_source_status = utilization_service.get_metrics_source_status()

    context['metrics_source_status'] = metrics_source_status
    context['metrics_source_connected'] = bool(
        metrics_source_status.get(
            'connected',
            False,
        )
    )

    if not metrics_source_status.get(
        'connected',
        False,
    ):
        context['dependency_blocker'] = metrics_source_connection_blocker(
            cluster,
            detail=_safe_message(
                value=metrics_source_status.get('error'),
                default='Metrics Source health check did not complete successfully.',
            ),
        )
        context['forecast_payload'] = _empty_payload(
            message=_safe_message(
                value=metrics_source_status.get(
                    'error',
                ),
                default='Metrics Source is not connected for the selected cluster.',
            ),
        )

        return context

    forecast_service = ForecastAnalysisService(
        utilization_service=utilization_service,
        cluster=cluster,
    )
    namespace_options = forecast_service.get_namespace_options()

    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    context['selected_namespace'] = selected_namespace
    context['namespace_options'] = namespace_options

    forecast_payload = forecast_service.get_forecast_analysis(
        namespace=selected_namespace,
        history_window=selected_history_window,
        forecast_horizon=selected_forecast_horizon,
        method=selected_method,
    )

    context['forecast_payload'] = forecast_payload

    return context


def _get_resource_definitions(
    namespace: str,
) -> list[ForecastResourceDefinition]:
    namespace_scope = f'Namespace {namespace}' if namespace else 'All Namespaces'
    cluster_capacity = 'Ready-worker allocatable capacity'
    return [
        ForecastResourceDefinition(
            key='cpu',
            label='CPU',
            unit='cores',
            icon='cpu',
            description='Projected CPU demand compared with worker-node allocatable CPU.',
            scope_label=namespace_scope,
            comparison_label=(
                'Namespace Demand vs Cluster Capacity' if namespace else 'Cluster Demand vs Cluster Capacity'
            ),
            capacity_label=cluster_capacity,
            usage_query=_render_namespace_query(
                namespace=namespace,
                all_query=CPU_USAGE_QUERY,
                namespace_query=CPU_USAGE_BY_NAMESPACE_QUERY,
            ),
            capacity_query=CPU_WORKER_CAPACITY_QUERY,
        ),
        ForecastResourceDefinition(
            key='memory',
            label='Memory',
            unit='bytes',
            icon='memory-stick',
            description='Projected memory working-set demand compared with worker-node allocatable memory.',
            scope_label=namespace_scope,
            comparison_label=(
                'Namespace Demand vs Cluster Capacity' if namespace else 'Cluster Demand vs Cluster Capacity'
            ),
            capacity_label=cluster_capacity,
            usage_query=_render_namespace_query(
                namespace=namespace,
                all_query=MEMORY_USAGE_QUERY,
                namespace_query=MEMORY_USAGE_BY_NAMESPACE_QUERY,
            ),
            capacity_query=MEMORY_WORKER_CAPACITY_QUERY,
        ),
        ForecastResourceDefinition(
            key='storage',
            label='Storage',
            unit='bytes',
            icon='database',
            description='Projected PVC usage compared with the observed mounted-volume capacity baseline.',
            scope_label=namespace_scope,
            comparison_label=(
                'Namespace PVC Usage vs Namespace Observed Capacity' if namespace else 'PVC Usage vs Observed Capacity'
            ),
            capacity_label=(
                f'Namespace {namespace} observed volume capacity' if namespace else 'All observed volume capacity'
            ),
            usage_query=_render_namespace_query(
                namespace=namespace,
                all_query=STORAGE_USAGE_QUERY,
                namespace_query=STORAGE_USAGE_BY_NAMESPACE_QUERY,
            ),
            capacity_query=_render_namespace_query(
                namespace=namespace,
                all_query=STORAGE_CAPACITY_QUERY,
                namespace_query=STORAGE_CAPACITY_BY_NAMESPACE_QUERY,
            ),
        ),
        ForecastResourceDefinition(
            key='pods',
            label='Pods',
            unit='count',
            icon='boxes',
            description='Projected active Pod demand compared with Ready-worker allocatable Pod capacity.',
            scope_label=namespace_scope,
            comparison_label=(
                'Namespace Demand vs Cluster Capacity' if namespace else 'Cluster Demand vs Cluster Capacity'
            ),
            capacity_label=cluster_capacity,
            usage_query=_render_namespace_query(
                namespace=namespace,
                all_query=POD_USAGE_QUERY,
                namespace_query=POD_USAGE_BY_NAMESPACE_QUERY,
            ),
            capacity_query=POD_WORKER_CAPACITY_QUERY,
        ),
    ]


def _render_namespace_query(
    *,
    namespace: str,
    all_query: str,
    namespace_query: str,
) -> str:
    if not namespace:
        return all_query

    escaped_namespace = namespace.replace(
        '\\',
        '\\\\',
    ).replace(
        '"',
        '\\"',
    )

    return namespace_query.replace(
        '$namespace',
        escaped_namespace,
    )
