# app/analytics/forecast/service.py

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from statistics import mean
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.coercion import (
    as_dict as _as_dict,
)
from app.analytics.common.coercion import (
    as_list as _as_list,
)
from app.analytics.common.coercion import (
    safe_float as _safe_float,
)
from app.analytics.common.coercion import (
    safe_int as _safe_int,
)
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import get_query_value
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_connection_blocker
from app.integrations.prometheus.query_profiles import get_query_expression
from app.intelligence.recommendation_engine import (
    build_forecast_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster

CPU_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.CPU_USAGE_BY_NAMESPACE_QUERY')
CPU_USAGE_QUERY = get_query_expression('analytics.forecast.queries.CPU_USAGE_QUERY')
CPU_WORKER_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY')
MEMORY_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.MEMORY_USAGE_BY_NAMESPACE_QUERY')
MEMORY_USAGE_QUERY = get_query_expression('analytics.forecast.queries.MEMORY_USAGE_QUERY')
MEMORY_WORKER_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY')
NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.forecast.queries.NAMESPACE_ACTIVE_QUERY')
POD_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.POD_USAGE_BY_NAMESPACE_QUERY')
POD_USAGE_QUERY = get_query_expression('analytics.forecast.queries.POD_USAGE_QUERY')
POD_WORKER_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.POD_WORKER_CAPACITY_QUERY')
STORAGE_CAPACITY_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.forecast.queries.STORAGE_CAPACITY_BY_NAMESPACE_QUERY'
)
STORAGE_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_CAPACITY_QUERY')
STORAGE_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_USAGE_BY_NAMESPACE_QUERY')
STORAGE_USAGE_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_USAGE_QUERY')

WARNING_THRESHOLD = 75.0
CRITICAL_THRESHOLD = 90.0


HISTORY_WINDOW_OPTIONS: list[dict[str, str]] = [
    {
        'value': '7d',
        'label': '7 Days',
    },
    {
        'value': '30d',
        'label': '30 Days',
    },
    {
        'value': '90d',
        'label': '90 Days',
    },
]


FORECAST_HORIZON_OPTIONS: list[dict[str, str]] = [
    {
        'value': '7d',
        'label': '7 Days',
    },
    {
        'value': '30d',
        'label': '30 Days',
    },
    {
        'value': '90d',
        'label': '90 Days',
    },
    {
        'value': '180d',
        'label': '180 Days',
    },
    {
        'value': '365d',
        'label': '365 Days',
    },
]



FORECAST_METHOD_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'holt_winters',
        'label': 'Holt-Winters',
        'description': 'Projects the selected horizon from level, trend, and weekly seasonal signals.',
    },
    {
        'value': 'linear',
        'label': 'Linear Trend',
        'description': 'Projects future usage from a simple historical trend baseline.',
    },
    {
        'value': 'conservative',
        'label': 'Conservative Trend',
        'description': 'Applies a planning buffer to positive Holt-Winters growth for capacity review.',
    },
]


@dataclass(frozen=True)
class ForecastResourceDefinition:
    key: str
    label: str
    unit: str
    icon: str
    description: str
    scope_label: str
    comparison_label: str
    capacity_label: str
    usage_query: str
    capacity_query: str


@dataclass(frozen=True)
class ForecastPoint:
    timestamp: datetime
    value: float


class ForecastAnalysisService(AnalyticsBaseService):
    def __init__(
        self,
        utilization_service: UtilizationService,
        cluster: Cluster,
    ) -> None:
        self.utilization_service = utilization_service
        self.cluster = cluster
        self.consumer = utilization_service.consumer

    def get_prometheus_status(
        self,
    ) -> dict[str, Any]:
        return self.utilization_service.get_prometheus_status()

    def get_namespace_options(
        self,
    ) -> list[str]:
        result = self.get_prometheus_result(
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
        raw_points = self._query_range(
            query=definition.usage_query,
            start_time=start_time,
            end_time=end_time,
            step=step,
        )
        daily_points = _daily_average(raw_points)
        capacity = self._query_instant(query=definition.capacity_query)
        forecast_result = _calculate_forecast(
            values=daily_points,
            horizon_days=horizon_days,
            method=method,
        )

        history_points_count = len(daily_points)
        has_data = history_points_count >= 2 and capacity > 0
        latest_daily_average = forecast_result['latest_daily_average'] if has_data else None
        projected_value = forecast_result['projected_value'] if has_data else None
        slope_per_day = forecast_result['slope_per_day'] if has_data else 0.0
        latest_daily_average_percent = (
            _percentage(latest_daily_average, capacity) if latest_daily_average is not None else None
        )
        projected_percent = _percentage(projected_value, capacity) if projected_value is not None else None
        status = _resolve_status(projected_percent) if projected_percent is not None else 'unknown'
        warning_eta = (
            _calculate_eta(
                current_value=latest_daily_average,
                slope_per_day=slope_per_day,
                capacity=capacity,
                threshold=WARNING_THRESHOLD,
            )
            if latest_daily_average is not None
            else _unavailable_eta()
        )
        critical_eta = (
            _calculate_eta(
                current_value=latest_daily_average,
                slope_per_day=slope_per_day,
                capacity=capacity,
                threshold=CRITICAL_THRESHOLD,
            )
            if latest_daily_average is not None
            else _unavailable_eta()
        )

        return {
            'key': definition.key,
            'label': definition.label,
            'unit': definition.unit,
            'icon': definition.icon,
            'description': definition.description,
            'scope_label': definition.scope_label,
            'comparison_label': definition.comparison_label,
            'capacity_label': definition.capacity_label,
            'forecast_method': method,
            'method_label': forecast_result['method_label'],
            'method_description': forecast_result['method_description'],
            'has_data': has_data,
            'history_points_count': history_points_count,
            'capacity_missing': capacity <= 0,
            'empty_reason': _resolve_forecast_empty_reason(
                history_points_count=history_points_count,
                capacity=capacity,
            ),
            'status': status,
            'status_label': status.title(),
            'capacity': capacity if capacity > 0 else None,
            'capacity_display': _format_value(capacity, definition.unit) if capacity > 0 else 'N/A',
            'latest_daily_average': latest_daily_average,
            'latest_daily_average_display': (
                _format_value(latest_daily_average, definition.unit)
                if latest_daily_average is not None
                else 'N/A'
            ),
            'projected_value': projected_value,
            'projected_display': (
                _format_value(projected_value, definition.unit) if projected_value is not None else 'N/A'
            ),
            'weekly_trend': slope_per_day * 7,
            'weekly_trend_display': (
                _format_weekly_trend(slope_per_day, definition.unit) if has_data else 'N/A'
            ),
            'latest_daily_average_percent': (
                round(latest_daily_average_percent, 2)
                if latest_daily_average_percent is not None
                else None
            ),
            'projected_percent': round(projected_percent, 2) if projected_percent is not None else None,
            'warning_eta': warning_eta,
            'critical_eta': critical_eta,
            'signal_quality': forecast_result['signal_quality'] if has_data else 'Unavailable',
            'signal_quality_reason': (
                forecast_result['signal_quality_reason']
                if has_data
                else 'Forecast requires at least two daily samples and a non-zero capacity baseline.'
            ),
            'historical_points': [
                {
                    'date': point.timestamp.strftime('%Y-%m-%d'),
                    'value': point.value,
                    'percent': round(_percentage(point.value, capacity), 2) if capacity > 0 else None,
                }
                for point in daily_points
            ],
            'forecast_points': [
                {
                    'date': point.timestamp.strftime('%Y-%m-%d'),
                    'value': point.value,
                    'percent': round(_percentage(point.value, capacity), 2) if capacity > 0 else None,
                }
                for point in forecast_result['forecast_points']
            ] if has_data else [],
        }

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
            _to_prometheus_time(start_time),
            _to_prometheus_time(end_time),
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

    prometheus_status = utilization_service.get_prometheus_status()

    context['prometheus_status'] = prometheus_status
    context['prometheus_connected'] = bool(
        prometheus_status.get(
            'connected',
            False,
        )
    )

    if not prometheus_status.get(
        'connected',
        False,
    ):
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=_safe_message(
                value=prometheus_status.get('error'),
                default='Prometheus health check did not complete successfully.',
            ),
        )
        context['forecast_payload'] = _empty_payload(
            message=_safe_message(
                value=prometheus_status.get(
                    'error',
                ),
                default='Prometheus is not connected for the selected cluster.',
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
    cluster_capacity = 'Ready-worker cluster capacity'
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
            description='Projected PVC usage compared with the selected PVC claim-capacity baseline.',
            scope_label=namespace_scope,
            comparison_label=(
                'Namespace PVC Usage vs Namespace Claim Capacity'
                if namespace
                else 'PVC Usage vs Claim Capacity'
            ),
            capacity_label=(f'Namespace {namespace} claim capacity' if namespace else 'All PVC claim capacity'),
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
            description='Projected running-pod demand compared with worker-node pod capacity.',
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


def _calculate_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
    method: str = 'holt_winters',
) -> dict[str, Any]:
    method = _normalize_option(
        method,
        'holt_winters',
        {item['value'] for item in FORECAST_METHOD_OPTIONS},
    )
    method_meta = _get_forecast_method_meta(method)

    if len(values) < 2:
        latest = values[-1].value if values else 0.0
        return {
            'latest_daily_average': latest,
            'projected_value': latest,
            'slope_per_day': 0.0,
            'forecast_points': [],
            'signal_quality': 'Low' if values else 'Unavailable',
            'signal_quality_reason': 'Not enough historical daily samples.',
            'method_label': method_meta['label'],
            'method_description': method_meta['description'],
        }

    if method == 'linear':
        result = _calculate_linear_forecast(values=values, horizon_days=horizon_days)
    elif method == 'conservative':
        result = _calculate_conservative_forecast(values=values, horizon_days=horizon_days)
    else:
        result = _calculate_holt_winters_forecast(values=values, horizon_days=horizon_days)

    result['method_label'] = method_meta['label']
    result['method_description'] = method_meta['description']
    return result


def _calculate_linear_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
) -> dict[str, Any]:
    start = values[0].timestamp
    x_values = [max((point.timestamp - start).total_seconds() / 86400, 0.0) for point in values]
    y_values = [point.value for point in values]
    slope, intercept = _linear_regression(x_values=x_values, y_values=y_values)
    latest = max(y_values[-1], 0.0)
    forecast_points = _build_forecast_points(
        last_timestamp=values[-1].timestamp,
        current_value=latest,
        slope_per_day=slope,
        horizon_days=horizon_days,
        intercept=intercept,
        last_x=x_values[-1],
    )
    quality, reason = _calculate_signal_quality(values=y_values, points=values)
    return {
        'latest_daily_average': latest,
        'projected_value': forecast_points[-1].value if forecast_points else latest,
        'slope_per_day': slope,
        'forecast_points': forecast_points,
        'signal_quality': quality,
        'signal_quality_reason': reason,
    }


def _calculate_holt_winters_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
) -> dict[str, Any]:
    y_values = [max(point.value, 0.0) for point in values]
    season_length = 7
    alpha = 0.35
    beta = 0.15
    gamma = 0.20

    if len(y_values) < season_length * 2:
        fallback = _calculate_linear_forecast(values=values, horizon_days=horizon_days)
        fallback['signal_quality_reason'] = (
            f"{fallback['signal_quality_reason']} Holt-Winters used a linear fallback because fewer than "
            f'{season_length * 2} daily samples were available.'
        )
        return fallback

    first_season = y_values[:season_length]
    second_season = y_values[season_length : season_length * 2]
    level = mean(first_season)
    trend = (mean(second_season) - level) / season_length
    seasonals = [value - level for value in first_season]

    for index, value in enumerate(y_values):
        seasonal_index = index % season_length
        previous_level = level
        seasonal = seasonals[seasonal_index]
        level = alpha * (value - seasonal) + (1 - alpha) * (level + trend)
        trend = beta * (level - previous_level) + (1 - beta) * trend
        seasonals[seasonal_index] = gamma * (value - level) + (1 - gamma) * seasonal

    forecast_points = []
    for day in range(1, horizon_days + 1):
        seasonal = seasonals[(len(y_values) + day - 1) % season_length]
        forecast_points.append(
            ForecastPoint(
                timestamp=values[-1].timestamp + timedelta(days=day),
                value=max(level + day * trend + seasonal, 0.0),
            )
        )

    quality, reason = _calculate_signal_quality(values=y_values, points=values)
    return {
        'latest_daily_average': y_values[-1],
        'projected_value': forecast_points[-1].value if forecast_points else y_values[-1],
        'slope_per_day': trend,
        'forecast_points': forecast_points,
        'signal_quality': quality,
        'signal_quality_reason': f'{reason} Weekly additive seasonality was evaluated.',
    }


def _calculate_conservative_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
) -> dict[str, Any]:
    result = _calculate_holt_winters_forecast(values=values, horizon_days=horizon_days)
    slope = result['slope_per_day']
    adjusted_slope = slope * 1.15 if slope > 0 else slope
    latest = result['latest_daily_average']
    forecast_points = _build_forecast_points(
        last_timestamp=values[-1].timestamp,
        current_value=latest,
        slope_per_day=adjusted_slope,
        horizon_days=horizon_days,
    )
    result['slope_per_day'] = adjusted_slope
    result['forecast_points'] = forecast_points
    result['projected_value'] = forecast_points[-1].value if forecast_points else latest
    result['signal_quality_reason'] = (
        f"{result['signal_quality_reason']} Conservative Trend applies a 15% buffer to positive daily growth."
    )
    return result

def _build_forecast_points(
    *,
    last_timestamp: datetime,
    current_value: float,
    slope_per_day: float,
    horizon_days: int,
    intercept: float | None = None,
    last_x: float | None = None,
) -> list[ForecastPoint]:
    forecast_points: list[ForecastPoint] = []

    for day in range(1, horizon_days + 1):
        forecast_timestamp = last_timestamp + timedelta(days=day)

        if intercept is not None and last_x is not None:
            forecast_value = (slope_per_day * (last_x + day)) + intercept
        else:
            forecast_value = current_value + (slope_per_day * day)

        forecast_points.append(
            ForecastPoint(
                timestamp=forecast_timestamp,
                value=max(forecast_value, 0.0),
            ),
        )

    return forecast_points


def _get_forecast_method_meta(
    method: str,
) -> dict[str, str]:
    for item in FORECAST_METHOD_OPTIONS:
        if item['value'] == method:
            return item

    return FORECAST_METHOD_OPTIONS[0]


def _linear_regression(
    *,
    x_values: list[float],
    y_values: list[float],
) -> tuple[float, float]:
    x_avg = mean(x_values)
    y_avg = mean(y_values)

    numerator = sum(
        (x_value - x_avg) * (y_value - y_avg)
        for x_value, y_value in zip(
            x_values,
            y_values,
            strict=True,
        )
    )
    denominator = sum((x_value - x_avg) ** 2 for x_value in x_values)

    if denominator == 0:
        return 0.0, y_avg

    slope = numerator / denominator
    intercept = y_avg - (slope * x_avg)

    return slope, intercept


def _calculate_signal_quality(
    *,
    values: list[float],
    points: list[ForecastPoint],
) -> tuple[str, str]:
    points_count = len(values)
    if points_count < 7:
        return 'Low', 'Less than 7 daily samples are available.'

    expected_days = max((points[-1].timestamp.date() - points[0].timestamp.date()).days + 1, 1)
    completeness = min(points_count / expected_days, 1.0)
    average_value = mean(values)
    if average_value <= 0:
        return 'Low', 'The historical daily average is zero or unavailable.'

    variance = mean([(value - average_value) ** 2 for value in values])
    coefficient_of_variation = sqrt(variance) / average_value

    if points_count >= 30 and completeness >= 0.90 and coefficient_of_variation <= 0.25:
        return 'High', f'{points_count} daily samples, {completeness:.0%} completeness, and stable variation.'
    if points_count >= 14 and completeness >= 0.75 and coefficient_of_variation <= 0.60:
        return 'Medium', f'{points_count} daily samples, {completeness:.0%} completeness, and moderate variation.'
    return 'Low', f'{points_count} daily samples with {completeness:.0%} completeness or high variation.'

def _unavailable_eta() -> dict[str, Any]:
    return {'label': 'N/A', 'days': None, 'date': None}


def _calculate_eta(
    *,
    current_value: float,
    slope_per_day: float,
    capacity: float,
    threshold: float,
) -> dict[str, Any]:
    if capacity <= 0:
        return {
            'label': 'N/A',
            'days': None,
            'date': None,
        }

    threshold_value = capacity * (threshold / 100)

    if current_value >= threshold_value:
        return {
            'label': 'Reached',
            'days': 0,
            'date': datetime.now(UTC).strftime('%Y-%m-%d'),
        }

    if slope_per_day <= 0:
        return {
            'label': 'Not projected',
            'days': None,
            'date': None,
        }

    days = int((threshold_value - current_value) / slope_per_day)

    if days < 0:
        days = 0

    target_date = datetime.now(UTC) + timedelta(days=days)

    return {
        'label': f'{days} days',
        'days': days,
        'date': target_date.strftime('%Y-%m-%d'),
    }


def _build_summary(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    available_items = [item for item in items if item.get('has_data') and item.get('projected_percent') is not None]
    unavailable_items = [item for item in items if not item.get('has_data')]
    warning_items = [item for item in available_items if item['status'] == 'warning']
    critical_items = [item for item in available_items if item['status'] == 'critical']
    highest_projected = (
        max(available_items, key=lambda item: float(item['projected_percent']))
        if available_items
        else None
    )
    return {
        'total_resources': len(items),
        'forecasted_resources': len(available_items),
        'unavailable_resources': len(unavailable_items),
        'warning_count': len(warning_items),
        'critical_count': len(critical_items),
        'highest_projected_label': highest_projected['label'] if highest_projected else 'N/A',
        'highest_projected_percent': highest_projected['projected_percent'] if highest_projected else None,
        'nearest_warning': _find_nearest_eta(items=available_items, eta_key='warning_eta'),
        'nearest_critical': _find_nearest_eta(items=available_items, eta_key='critical_eta'),
    }

def _find_nearest_eta(
    *,
    items: list[dict[str, Any]],
    eta_key: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    for item in items:
        eta = item[eta_key]

        if eta['days'] is None:
            continue

        candidates.append(
            {
                'resource': item['label'],
                'label': eta['label'],
                'days': eta['days'],
                'date': eta['date'],
            },
        )

    if not candidates:
        return {
            'resource': None,
            'label': 'Not projected',
            'days': None,
            'date': None,
        }

    return min(
        candidates,
        key=lambda candidate: candidate['days'],
    )


def _build_no_forecast_data_message(
    items: list[dict[str, Any]],
) -> str:
    if not items:
        return 'No forecast resource was selected. Choose a resource scope and verify that Prometheus metrics are available.'

    missing_history = [item['label'] for item in items if item.get('history_points_count', 0) < 2]
    missing_capacity = [item['label'] for item in items if item.get('capacity_missing', False)]

    notes: list[str] = []

    if missing_history:
        notes.append(f'not enough historical daily points for {", ".join(missing_history)}')

    if missing_capacity:
        notes.append(f'missing capacity baseline for {", ".join(missing_capacity)}')

    if notes:
        return (
            'Forecast data is unavailable because Prometheus returned '
            + ' and '.join(notes)
            + '. Forecast requires at least two daily historical samples and a non-zero capacity baseline.'
        )

    return (
        'Forecast data is unavailable because the selected scope did not produce a usable historical series. '
        'Check Prometheus retention, kube-state-metrics, kubelet/cAdvisor metrics, and namespace/resource filters.'
    )


def _resolve_forecast_empty_reason(
    *,
    history_points_count: int,
    capacity: float,
) -> str:
    if history_points_count < 2 and capacity <= 0:
        return 'Not enough historical points and capacity baseline is missing.'

    if history_points_count < 2:
        return 'Not enough historical daily points.'

    if capacity <= 0:
        return 'Capacity baseline is missing or zero.'

    return 'Forecast data is available.'


def _build_chart_payload(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    datasets = []

    for item in items:
        if not item.get('has_data'):
            continue
        historical = item['historical_points']
        forecast = item['forecast_points']

        labels = [point['date'] for point in historical] + [point['date'] for point in forecast]

        historical_values = [point['percent'] for point in historical] + [None for _ in forecast]

        forecast_values = [None for _ in historical] + [point['percent'] for point in forecast]

        datasets.append(
            {
                'key': item['key'],
                'label': item['label'],
                'labels': labels,
                'historical': historical_values,
                'forecast': forecast_values,
            },
        )

    return {
        'datasets': datasets,
        'warning_threshold': WARNING_THRESHOLD,
        'critical_threshold': CRITICAL_THRESHOLD,
    }


def _extract_range_points(
    result: Any,
) -> list[ForecastPoint]:
    prometheus_result = _get_prometheus_result_list(result)
    aggregated: dict[int, float] = {}

    for series in prometheus_result:
        values = series.get('values', [])

        for item in values:
            if len(item) < 2:
                continue

            try:
                timestamp = int(float(item[0]))
                value = float(item[1])
            except (TypeError, ValueError):
                continue

            aggregated[timestamp] = (
                aggregated.get(
                    timestamp,
                    0.0,
                )
                + value
            )

    return [
        ForecastPoint(
            timestamp=datetime.fromtimestamp(
                timestamp,
                UTC,
            ),
            value=value,
        )
        for timestamp, value in sorted(aggregated.items())
    ]


def _extract_instant_value(
    result: Any,
) -> float:
    prometheus_result = _get_prometheus_result_list(result)
    total = 0.0

    for series in prometheus_result:
        value = series.get('value')

        if not value or len(value) < 2:
            continue

        try:
            total += float(value[1])
        except (TypeError, ValueError):
            continue

    return total


def _get_prometheus_result_list(
    result: Any,
) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return result

    if not isinstance(result, dict):
        return []

    data = result.get('data')

    if isinstance(data, dict):
        prometheus_result = data.get('result', [])

        if isinstance(prometheus_result, list):
            return prometheus_result

    prometheus_result = result.get('result', [])

    if isinstance(prometheus_result, list):
        return prometheus_result

    return []


def _daily_average(
    points: list[ForecastPoint],
) -> list[ForecastPoint]:
    grouped: dict[str, list[float]] = {}

    for point in points:
        date_key = point.timestamp.strftime('%Y-%m-%d')
        grouped.setdefault(
            date_key,
            [],
        ).append(point.value)

    daily_points: list[ForecastPoint] = []

    for date_key, values in sorted(grouped.items()):
        timestamp = datetime.strptime(
            date_key,
            '%Y-%m-%d',
        ).replace(tzinfo=UTC)

        daily_points.append(
            ForecastPoint(
                timestamp=timestamp,
                value=mean(values),
            ),
        )

    return daily_points


def _select_range_step(
    history_days: int,
) -> str:
    if history_days <= 7:
        return '1h'

    if history_days <= 30:
        return '6h'

    return '12h'


def _parse_days(
    value: str | None,
    *,
    default: int,
) -> int:
    if value is None:
        return default

    try:
        return int(value.replace('d', ''))
    except ValueError:
        return default


def _normalize_option(
    value: str | None,
    default: str,
    allowed_values: set[str],
) -> str:
    if value in allowed_values:
        return value

    return default


def _percentage(
    value: float,
    capacity: float,
) -> float:
    if capacity <= 0:
        return 0.0

    return max(
        (value / capacity) * 100,
        0.0,
    )


def _resolve_status(
    projected_percent: float,
) -> str:
    if projected_percent >= CRITICAL_THRESHOLD:
        return 'critical'

    if projected_percent >= WARNING_THRESHOLD:
        return 'warning'

    return 'normal'


def _format_value(
    value: float,
    unit: str,
) -> str:
    if unit == 'bytes':
        return _format_bytes(value)

    if unit == 'cores':
        return f'{value:.2f} cores'

    if unit == 'count':
        return f'{value:.0f}'

    return f'{value:.2f}'


def _format_weekly_trend(
    slope_per_day: float,
    unit: str,
) -> str:
    weekly_trend = slope_per_day * 7
    if abs(weekly_trend) < 1e-9:
        return 'Stable'
    sign = '+' if weekly_trend > 0 else '-'
    magnitude = abs(weekly_trend)
    if unit == 'bytes':
        return f'{sign}{_format_bytes(magnitude)} / Week'
    if unit == 'cores':
        return f'{sign}{magnitude:.2f} Cores / Week'
    if unit == 'count':
        return f'{sign}{magnitude:.0f} Pods / Week'
    return f'{sign}{magnitude:.2f} / Week'


def _format_bytes(
    value: float,
) -> str:
    if value == 0:
        return '0 B'
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    size = abs(float(value))
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f'{size:.0f} {units[unit_index]}' if unit_index == 0 else f'{size:.2f} {units[unit_index]}'

def _to_prometheus_time(
    value: datetime,
) -> str:
    return str(value.timestamp())


def _safe_message(
    *,
    value: Any,
    default: str,
) -> str:
    if (
        isinstance(
            value,
            str,
        )
        and value
    ):
        return value

    if value is None:
        return default

    return str(
        value,
    )


def _empty_payload(
    *,
    message: str,
) -> dict[str, Any]:
    return {
        'has_data': False,
        'message': message,
        'namespace': '',
        'history_window': '30d',
        'forecast_horizon': '90d',
        'forecast_method': 'holt_winters',
        'method_label': 'Holt-Winters',
        'method_description': 'Projects the selected horizon from level, trend, and weekly seasonal signals.',
        'history_days': 30,
        'horizon_days': 90,
        'generated_at': None,
        'items': [],
        'summary': {
            'total_resources': 0,
            'warning_count': 0,
            'critical_count': 0,
            'highest_projected_label': 'N/A',
            'forecasted_resources': 0,
            'unavailable_resources': 0,
            'highest_projected_percent': None,
            'nearest_warning': {
                'resource': None,
                'label': 'Not projected',
                'days': None,
                'date': None,
            },
            'nearest_critical': {
                'resource': None,
                'label': 'Not projected',
                'days': None,
                'date': None,
            },
        },
        'chart': {
            'datasets': [],
            'warning_threshold': WARNING_THRESHOLD,
            'critical_threshold': CRITICAL_THRESHOLD,
        },
        'actionable_recommendations': [],
        'recommendation_cards': [],
        'recommendation_count': 0,
    }


def get_forecast_snapshot(
    cluster_id: str,
    time_range: str = '30d',
) -> dict[str, Any] | None:
    from app.analytics.materialization.service import read_snapshot

    history_window = _normalize_forecast_history_window(time_range)
    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.forecast',
        parameters={
            'cluster_id': str(cluster_id),
            'history_window': history_window,
        },
    )
    context = result.context or {}
    forecast_payload = context.get('forecast_payload')
    if not isinstance(forecast_payload, dict):
        return None
    items = _as_list(forecast_payload.get('items', []))
    summary = _as_dict(forecast_payload.get('summary', {}))
    item_map = _build_forecast_item_map(items)
    cpu_item = item_map.get('cpu', {})
    memory_item = item_map.get('memory', {})
    storage_item = item_map.get('storage', {})
    pod_item = item_map.get('pods', {})
    forecast_risk = _resolve_forecast_risk(summary=summary, items=items)
    risk_count = _safe_int(summary.get('warning_count', 0)) + _safe_int(summary.get('critical_count', 0))
    return {
        'cpu_trend': _get_forecast_trend_label(cpu_item),
        'cpu_trend_value': _get_forecast_trend_value(cpu_item),
        'memory_trend': _get_forecast_trend_label(memory_item),
        'memory_trend_value': _get_forecast_trend_value(memory_item),
        'storage_trend': _get_forecast_trend_label(storage_item),
        'storage_trend_value': _get_forecast_trend_value(storage_item),
        'pod_trend': _get_forecast_trend_label(pod_item),
        'pod_trend_value': _get_forecast_trend_value(pod_item),
        'risk_count': risk_count,
        'risk_note': (
            f'{risk_count} metric(s) may breach warning thresholds in the forecast window.'
            if risk_count > 0 else 'No forecast risk detected in the selected time range.'
        ),
        'forecast_risk': forecast_risk,
        'forecast_horizon': str(forecast_payload.get('forecast_horizon') or '90d'),
        'highest_projected_resource': summary.get('highest_projected_label', 'N/A'),
        'highest_projected_percent': (
            _safe_float(summary.get('highest_projected_percent'))
            if summary.get('highest_projected_percent') is not None
            else None
        ),
        'nearest_warning': summary.get('nearest_warning', {}),
        'nearest_critical': summary.get('nearest_critical', {}),
        'series': _build_forecast_snapshot_series(items),
        'recommendation_count': count_actionable_recommendations(
            forecast_payload.get('actionable_recommendations')
            if isinstance(forecast_payload.get('actionable_recommendations'), list)
            else []
        ),
    }

def _normalize_forecast_history_window(
    time_range: str,
) -> str:
    if time_range in [
        '7d',
        '30d',
        '90d',
    ]:
        return time_range

    return '30d'


def _build_forecast_item_map(
    items: list[Any],
) -> dict[str, dict[str, Any]]:
    item_map: dict[str, dict[str, Any]] = {}

    for item in items:
        item_dict = _as_dict(
            item,
        )

        key = str(
            item_dict.get(
                'key',
                '',
            )
        )

        if not key:
            continue

        item_map[key] = item_dict

    return item_map


def _get_forecast_trend_value(
    item: dict[str, Any],
) -> int | None:
    latest_raw = item.get('latest_daily_average_percent')
    projected_raw = item.get('projected_percent')

    if latest_raw is None or projected_raw is None:
        return None

    return _safe_int(
        _safe_float(projected_raw) - _safe_float(latest_raw),
    )


def _get_forecast_trend_label(
    item: dict[str, Any],
) -> str:
    trend_value = _get_forecast_trend_value(
        item,
    )

    if trend_value is None:
        return 'Unknown'

    if trend_value >= 5:
        return 'Increasing'

    if trend_value <= -5:
        return 'Decreasing'

    return 'Stable'


def _resolve_forecast_risk(
    *,
    summary: dict[str, Any],
    items: list[Any],
) -> str:
    critical_count = _safe_int(
        summary.get(
            'critical_count',
            0,
        )
    )
    warning_count = _safe_int(
        summary.get(
            'warning_count',
            0,
        )
    )

    if critical_count > 0:
        return 'High'

    if warning_count > 0:
        return 'Medium'

    has_forecast_evidence = False

    for item in items:
        item_dict = _as_dict(
            item,
        )

        if item_dict.get('has_data') and item_dict.get('projected_percent') is not None:
            has_forecast_evidence = True

        status = str(
            item_dict.get(
                'status',
                '',
            )
        ).lower()

        if status == 'critical':
            return 'High'

        if status == 'warning':
            return 'Medium'

    return 'Low' if has_forecast_evidence else 'Unknown'


def _build_forecast_snapshot_series(
    items: list[Any],
) -> list[dict[str, Any]]:
    item_map = _build_forecast_item_map(
        items,
    )

    resource_order = [
        {
            'key': 'cpu',
            'label': 'CPU',
        },
        {
            'key': 'memory',
            'label': 'Memory',
        },
        {
            'key': 'storage',
            'label': 'Storage',
        },
        {
            'key': 'pods',
            'label': 'Pods',
        },
    ]

    series: list[dict[str, Any]] = []

    for resource in resource_order:
        key = resource['key']
        item = item_map.get(
            key,
            {},
        )

        if not item:
            continue

        historical_values = _extract_percent_values(
            item.get(
                'historical_points',
                [],
            )
        )
        forecast_values = _extract_percent_values(
            item.get(
                'forecast_points',
                [],
            )
        )

        historical_values = _sample_forecast_values(
            historical_values,
            limit=12,
        )
        forecast_values = _sample_forecast_values(
            forecast_values,
            limit=12,
        )

        if not historical_values and not forecast_values:
            current_percent = _safe_float(
                item.get(
                    'latest_daily_average_percent',
                    0,
                )
            )
            projected_percent = _safe_float(
                item.get(
                    'projected_percent',
                    0,
                )
            )

            if current_percent <= 0 and projected_percent <= 0:
                continue

            historical_values = [
                current_percent,
            ]
            forecast_values = [
                projected_percent,
            ]

        total_points = max(
            len(
                historical_values,
            )
            + len(
                forecast_values,
            ),
            2,
        )

        historical_points = _build_svg_polyline_points(
            values=historical_values,
            total_points=total_points,
            start_index=0,
        )

        forecast_line_values = []

        if historical_values:
            forecast_line_values.append(
                historical_values[-1],
            )

        forecast_line_values.extend(
            forecast_values,
        )

        forecast_points = _build_svg_polyline_points(
            values=forecast_line_values,
            total_points=total_points,
            start_index=max(
                len(
                    historical_values,
                )
                - 1,
                0,
            ),
        )

        latest_percent = (
            historical_values[-1]
            if historical_values
            else _safe_float(
                item.get(
                    'latest_daily_average_percent',
                    0,
                )
            )
        )
        projected_percent = (
            forecast_values[-1]
            if forecast_values
            else _safe_float(
                item.get(
                    'projected_percent',
                    0,
                )
            )
        )

        series.append(
            {
                'key': key,
                'label': resource['label'],
                'historical_points': historical_points,
                'forecast_points': forecast_points,
                'latest_percent': _safe_int(
                    latest_percent,
                ),
                'projected_percent': _safe_int(
                    projected_percent,
                ),
                'trend': _get_forecast_trend_label(
                    item,
                ),
            }
        )

    return series


def _extract_percent_values(
    points: Any,
) -> list[float]:
    values: list[float] = []

    for point in _as_list(
        points,
    ):
        point_dict = _as_dict(
            point,
        )

        percent = _safe_float(
            point_dict.get(
                'percent',
                0,
            )
        )

        values.append(
            _clamp_percent(
                percent,
            )
        )

    return values


def _sample_forecast_values(
    values: list[float],
    limit: int,
) -> list[float]:
    if (
        len(
            values,
        )
        <= limit
    ):
        return values

    if limit <= 1:
        return [
            values[-1],
        ]

    last_index = (
        len(
            values,
        )
        - 1
    )

    indexes = [
        round(
            index * last_index / (limit - 1),
        )
        for index in range(
            limit,
        )
    ]

    return [values[index] for index in indexes]


def _build_svg_polyline_points(
    *,
    values: list[float],
    total_points: int,
    start_index: int,
) -> str:
    if not values:
        return ''

    points: list[str] = []
    denominator = max(
        total_points - 1,
        1,
    )

    for index, value in enumerate(
        values,
    ):
        x_value = ((start_index + index) / denominator) * 100

        y_value = 100 - _clamp_percent(
            value,
        )

        points.append(
            f'{x_value:.2f},{y_value:.2f}',
        )

    return ' '.join(
        points,
    )


def _clamp_percent(
    value: float,
) -> float:
    return max(
        0.0,
        min(
            value,
            100.0,
        ),
    )


def _present_forecast_item(
    item: dict[str, Any],
    *,
    horizon_days: int,
    method: str,
) -> dict[str, Any]:
    from copy import deepcopy

    updated = deepcopy(item)
    historical_points: list[ForecastPoint] = []
    for point in item.get('historical_points') or []:
        try:
            timestamp = datetime.strptime(str(point.get('date') or ''), '%Y-%m-%d').replace(tzinfo=UTC)
            historical_points.append(ForecastPoint(timestamp=timestamp, value=_safe_float(point.get('value'))))
        except (TypeError, ValueError):
            continue

    result = _calculate_forecast(values=historical_points, horizon_days=horizon_days, method=method)
    capacity = _safe_float(item.get('capacity'))
    latest = _safe_float(result.get('latest_daily_average'))
    projected = _safe_float(result.get('projected_value'))
    slope = _safe_float(result.get('slope_per_day'))
    unit = str(item.get('unit') or '')
    history_count = len(historical_points)
    has_data = history_count >= 2 and capacity > 0
    latest_percent = _percentage(latest, capacity) if has_data else None
    projected_percent = _percentage(projected, capacity) if has_data else None
    status = _resolve_status(projected_percent) if projected_percent is not None else 'unknown'

    updated.update(
        {
            'forecast_method': method,
            'method_label': result['method_label'],
            'method_description': result['method_description'],
            'has_data': has_data,
            'history_points_count': history_count,
            'capacity_missing': capacity <= 0,
            'empty_reason': _resolve_forecast_empty_reason(history_points_count=history_count, capacity=capacity),
            'status': status,
            'status_label': status.title(),
            'capacity': capacity if capacity > 0 else None,
            'capacity_display': _format_value(capacity, unit) if capacity > 0 else 'N/A',
            'latest_daily_average': latest if has_data else None,
            'latest_daily_average_display': _format_value(latest, unit) if has_data else 'N/A',
            'projected_value': projected if has_data else None,
            'projected_display': _format_value(projected, unit) if has_data else 'N/A',
            'weekly_trend': slope * 7 if has_data else 0.0,
            'weekly_trend_display': _format_weekly_trend(slope, unit) if has_data else 'N/A',
            'latest_daily_average_percent': round(latest_percent, 2) if latest_percent is not None else None,
            'projected_percent': round(projected_percent, 2) if projected_percent is not None else None,
            'warning_eta': _calculate_eta(current_value=latest, slope_per_day=slope, capacity=capacity, threshold=WARNING_THRESHOLD) if has_data else _unavailable_eta(),
            'critical_eta': _calculate_eta(current_value=latest, slope_per_day=slope, capacity=capacity, threshold=CRITICAL_THRESHOLD) if has_data else _unavailable_eta(),
            'signal_quality': result['signal_quality'] if has_data else 'Unavailable',
            'signal_quality_reason': result['signal_quality_reason'] if has_data else 'Forecast evidence is unavailable.',
            'forecast_points': [
                {
                    'date': point.timestamp.strftime('%Y-%m-%d'),
                    'value': point.value,
                    'percent': round(_percentage(point.value, capacity), 2),
                }
                for point in result['forecast_points']
            ] if has_data else [],
        }
    )
    for legacy_key in (
        'current_value', 'current_display', 'current_percent', 'growth_per_day', 'growth_per_week',
        'growth_display', 'confidence', 'confidence_reason',
    ):
        updated.pop(legacy_key, None)
    return updated

def present_forecast_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproject a committed history snapshot without issuing a new Prometheus query."""
    from copy import deepcopy

    presented = deepcopy(context)
    selected_namespace = get_query_value(query_args=query_args, name='namespace', default='')
    selected_history_window = _normalize_option(
        get_query_value(query_args=query_args, name='history_window', default='30d'),
        '30d',
        {item['value'] for item in HISTORY_WINDOW_OPTIONS},
    )
    selected_horizon = _normalize_option(
        get_query_value(query_args=query_args, name='forecast_horizon', default='90d'),
        '90d',
        {item['value'] for item in FORECAST_HORIZON_OPTIONS},
    )
    selected_tab = _normalize_option(
        get_query_value(query_args=query_args, name='tab', default='cpu'),
        'cpu',
        {'cpu', 'memory', 'storage', 'pods', 'trend', 'recommendations'},
    )
    selected_method = _normalize_option(

        get_query_value(query_args=query_args, name='method', default='holt_winters'),
        'holt_winters',
        {item['value'] for item in FORECAST_METHOD_OPTIONS},
    )
    horizon_days = _parse_days(selected_horizon, default=90)
    method_meta = _get_forecast_method_meta(selected_method)

    namespace_options = list(presented.get('namespace_options') or [])
    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    payload = deepcopy(presented.get('forecast_payload') or {})
    source_items = list(payload.get('items') or [])
    items = [
        _present_forecast_item(item, horizon_days=horizon_days, method=selected_method)
        for item in source_items
    ]
    summary = _build_summary(items)
    recommendation_payload = {
        'namespace': selected_namespace,
        'history_window': selected_history_window,
        'forecast_horizon': selected_horizon,
        'history_days': _parse_days(selected_history_window, default=30),
        'horizon_days': horizon_days,
        'forecast_method': selected_method,
        'forecast_method_label': method_meta['label'],
        'items': items,
        'summary': summary,
    }
    recommendations = build_forecast_actionable_recommendations(recommendation_payload)
    recommendation_cards = format_recommendation_cards(
        recommendations,
        default_title='Continue Forecast Monitoring',
        default_description=(
            'No actionable forecast recommendation was generated from the current projection. '
            'Continue monitoring forecast trend and threshold ETA.'
        ),
        default_source='forecast',
        default_action_type='forecast_review',
    )
    has_data = any(item.get('has_data') for item in items)
    payload.update(
        {
            'has_data': has_data,
            'message': None if has_data else _build_no_forecast_data_message(items),
            'namespace': selected_namespace,
            'history_window': selected_history_window,
            'forecast_horizon': selected_horizon,
            'history_days': _parse_days(selected_history_window, default=30),
            'horizon_days': horizon_days,
            'forecast_method': selected_method,
            'method_label': method_meta['label'],
            'method_description': method_meta['description'],
            'items': items,
            'summary': summary,
            'chart': _build_chart_payload(items),
            'actionable_recommendations': recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': count_actionable_recommendations(recommendations),
        }
    )
    presented.update(
        {
            'selected_namespace': selected_namespace,
            'selected_history_window': selected_history_window,
            'selected_forecast_horizon': selected_horizon,
            'selected_tab': selected_tab,
            'selected_method': selected_method,
            'forecast_payload': payload,
        }
    )
    return presented
