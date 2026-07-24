# app/analytics/forecast/service.py

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from statistics import mean
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.coercion import (
    as_dict as _as_dict,
    as_list as _as_list,
    safe_float as _safe_float,
    safe_int as _safe_int,
)
from app.analytics.common.params import get_query_value
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_connection_blocker
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.intelligence.recommendation_engine import (
    build_forecast_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster
from app.prometheus.service import PrometheusService

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


RESOURCE_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'all',
        'label': 'All Resources',
    },
    {
        'value': 'cpu',
        'label': 'CPU',
    },
    {
        'value': 'memory',
        'label': 'Memory',
    },
    {
        'value': 'storage',
        'label': 'Storage',
    },
    {
        'value': 'pods',
        'label': 'Pods',
    },
]


FORECAST_METHOD_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'linear',
        'label': 'Linear Trend',
        'description': 'Projects future usage from the historical growth rate.',
    },
    {
        'value': 'moving_average',
        'label': 'Moving Average',
        'description': 'Smooths short-term noise using recent historical averages.',
    },
    {
        'value': 'conservative',
        'label': 'Conservative',
        'description': 'Adds safety buffer for capacity planning and operational review.',
    },
]


@dataclass(frozen=True)
class ForecastResourceDefinition:
    key: str
    label: str
    unit: str
    icon: str
    description: str
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
        self.prometheus = PrometheusService(cluster)

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
        resource: str,
        method: str = 'linear',
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
            'linear',
            {item['value'] for item in FORECAST_METHOD_OPTIONS},
        )
        method_meta = _get_forecast_method_meta(method)

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=history_days)
        step = _select_range_step(history_days)

        definitions = _get_resource_definitions(namespace)

        if resource != 'all':
            definitions = [definition for definition in definitions if definition.key == resource]

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
            'namespace': namespace or 'All Namespaces',
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
            default_title='Continue forecast monitoring',
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
        method: str = 'linear',
    ) -> dict[str, Any]:
        raw_points = self._query_range(
            query=definition.usage_query,
            start_time=start_time,
            end_time=end_time,
            step=step,
        )
        daily_points = _daily_average(raw_points)

        capacity = self._query_instant(
            query=definition.capacity_query,
        )

        forecast_result = _calculate_forecast(
            values=daily_points,
            horizon_days=horizon_days,
            method=method,
        )

        current_value = forecast_result['current_value']
        projected_value = forecast_result['projected_value']
        slope_per_day = forecast_result['slope_per_day']

        current_percent = _percentage(
            current_value,
            capacity,
        )
        projected_percent = _percentage(
            projected_value,
            capacity,
        )

        warning_eta = _calculate_eta(
            current_value=current_value,
            slope_per_day=slope_per_day,
            capacity=capacity,
            threshold=WARNING_THRESHOLD,
        )
        critical_eta = _calculate_eta(
            current_value=current_value,
            slope_per_day=slope_per_day,
            capacity=capacity,
            threshold=CRITICAL_THRESHOLD,
        )

        status = _resolve_status(projected_percent)

        history_points_count = len(daily_points)
        has_data = history_points_count >= 2 and capacity > 0

        return {
            'key': definition.key,
            'label': definition.label,
            'unit': definition.unit,
            'icon': definition.icon,
            'description': definition.description,
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
            'capacity': capacity,
            'capacity_display': _format_value(
                capacity,
                definition.unit,
            ),
            'current_value': current_value,
            'current_display': _format_value(
                current_value,
                definition.unit,
            ),
            'projected_value': projected_value,
            'projected_display': _format_value(
                projected_value,
                definition.unit,
            ),
            'growth_per_day': slope_per_day,
            'growth_per_week': slope_per_day * 7,
            'growth_display': _format_growth(
                slope_per_day,
                definition.unit,
            ),
            'current_percent': round(
                current_percent,
                2,
            ),
            'projected_percent': round(
                projected_percent,
                2,
            ),
            'warning_eta': warning_eta,
            'critical_eta': critical_eta,
            'confidence': forecast_result['confidence'],
            'confidence_reason': forecast_result['confidence_reason'],
            'historical_points': [
                {
                    'date': point.timestamp.strftime('%Y-%m-%d'),
                    'value': point.value,
                    'percent': round(
                        _percentage(
                            point.value,
                            capacity,
                        ),
                        2,
                    ),
                }
                for point in daily_points
            ],
            'forecast_points': [
                {
                    'date': point.timestamp.strftime('%Y-%m-%d'),
                    'value': point.value,
                    'percent': round(
                        _percentage(
                            point.value,
                            capacity,
                        ),
                        2,
                    ),
                }
                for point in forecast_result['forecast_points']
            ],
        }

    def _query_range(
        self,
        *,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
    ) -> list[ForecastPoint]:
        try:
            result = self.prometheus.range_query(
                query=query,
                start=_to_prometheus_time(start_time),
                end=_to_prometheus_time(end_time),
                step=step,
            )
        except Exception:
            return []

        return _extract_range_points(result)

    def _query_instant(
        self,
        *,
        query: str,
    ) -> float:
        try:
            result = self.prometheus.instant_query(
                query=query,
            )
        except Exception:
            return 0.0

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
    selected_resource = _normalize_option(
        get_query_value(
            query_args=query_args,
            name='resource',
            default='all',
        ),
        'all',
        {item['value'] for item in RESOURCE_OPTIONS},
    )
    selected_method = _normalize_option(
        get_query_value(
            query_args=query_args,
            name='method',
            default='linear',
        ),
        'linear',
        {item['value'] for item in FORECAST_METHOD_OPTIONS},
    )

    context.update(
        {
            'selected_namespace': selected_namespace,
            'selected_history_window': selected_history_window,
            'selected_forecast_horizon': selected_forecast_horizon,
            'selected_resource': selected_resource,
            'selected_method': selected_method,
            'history_window_options': HISTORY_WINDOW_OPTIONS,
            'forecast_horizon_options': FORECAST_HORIZON_OPTIONS,
            'resource_options': RESOURCE_OPTIONS,
            'forecast_method_options': FORECAST_METHOD_OPTIONS,
            'namespace_options': [],
            'forecast_payload': _empty_payload(
                message='No cluster available. Add a Kubernetes cluster first.',
            ),
        }
    )

    if utilization_service is None or cluster is None:
        return context

    try:
        prometheus_status = utilization_service.get_prometheus_status()
    except PrometheusError as exc:
        prometheus_status = {
            'connected': False,
            'label': 'Prometheus Disconnected',
            'response_time_ms': None,
            'error': str(exc),
        }
    except Exception as exc:
        prometheus_status = {
            'connected': False,
            'label': 'Prometheus Error',
            'response_time_ms': None,
            'error': str(exc),
        }

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

    try:
        forecast_service = ForecastAnalysisService(
            utilization_service=utilization_service,
            cluster=cluster,
        )
    except PrometheusError as exc:
        context['forecast_payload'] = _empty_payload(
            message=str(exc),
        )

        return context
    except Exception as exc:
        context['forecast_payload'] = _empty_payload(
            message=f'Forecast service initialization failed: {exc}',
        )

        return context

    try:
        namespace_options = forecast_service.get_namespace_options()
    except PrometheusError:
        namespace_options = []
    except Exception:
        namespace_options = []

    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    context['selected_namespace'] = selected_namespace
    context['namespace_options'] = namespace_options

    try:
        forecast_payload = forecast_service.get_forecast_analysis(
            namespace=selected_namespace,
            history_window=selected_history_window,
            forecast_horizon=selected_forecast_horizon,
            resource=selected_resource,
            method=selected_method,
        )
    except PrometheusError as exc:
        forecast_payload = _empty_payload(
            message=str(exc),
        )
    except Exception as exc:
        forecast_payload = _empty_payload(
            message=f'Forecast query failed: {exc}',
        )

    context['forecast_payload'] = forecast_payload

    return context


def _get_resource_definitions(
    namespace: str,
) -> list[ForecastResourceDefinition]:
    return [
        ForecastResourceDefinition(
            key='cpu',
            label='CPU',
            unit='cores',
            icon='cpu',
            description='Projected CPU usage growth compared with worker-node allocatable CPU.',
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
            description='Projected memory working set growth compared with worker-node allocatable memory.',
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
            description='Projected PVC storage growth compared with PVC capacity.',
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
            description='Projected running pod growth compared with worker-node pod capacity.',
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
    method: str = 'linear',
) -> dict[str, Any]:
    method = _normalize_option(
        method,
        'linear',
        {item['value'] for item in FORECAST_METHOD_OPTIONS},
    )
    method_meta = _get_forecast_method_meta(method)

    if len(values) < 2:
        current_value = values[-1].value if values else 0.0

        return {
            'current_value': current_value,
            'projected_value': current_value,
            'slope_per_day': 0.0,
            'forecast_points': [],
            'confidence': 'Low',
            'confidence_reason': 'Not enough historical data points.',
            'method_label': method_meta['label'],
            'method_description': method_meta['description'],
        }

    if method == 'moving_average':
        result = _calculate_moving_average_forecast(
            values=values,
            horizon_days=horizon_days,
        )
    elif method == 'conservative':
        result = _calculate_conservative_forecast(
            values=values,
            horizon_days=horizon_days,
        )
    else:
        result = _calculate_linear_forecast(
            values=values,
            horizon_days=horizon_days,
        )

    result['method_label'] = method_meta['label']
    result['method_description'] = method_meta['description']

    return result


def _calculate_linear_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
) -> dict[str, Any]:
    start = values[0].timestamp

    x_values = [
        max(
            (point.timestamp - start).total_seconds() / 86400,
            0.0,
        )
        for point in values
    ]
    y_values = [point.value for point in values]

    slope, intercept = _linear_regression(
        x_values=x_values,
        y_values=y_values,
    )

    current_value = max(
        y_values[-1],
        0.0,
    )
    last_x = x_values[-1]

    forecast_points = _build_forecast_points(
        last_timestamp=values[-1].timestamp,
        current_value=current_value,
        slope_per_day=slope,
        horizon_days=horizon_days,
        intercept=intercept,
        last_x=last_x,
    )
    projected_value = forecast_points[-1].value if forecast_points else current_value

    confidence, confidence_reason = _calculate_confidence(
        values=y_values,
        points_count=len(values),
    )

    return {
        'current_value': current_value,
        'projected_value': projected_value,
        'slope_per_day': slope,
        'forecast_points': forecast_points,
        'confidence': confidence,
        'confidence_reason': confidence_reason,
    }


def _calculate_moving_average_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
) -> dict[str, Any]:
    start = values[0].timestamp
    x_values = [max((point.timestamp - start).total_seconds() / 86400, 0.0) for point in values]
    raw_values = [point.value for point in values]
    window = min(
        7,
        len(raw_values),
    )
    smoothed_values = [mean(raw_values[max(index - window + 1, 0) : index + 1]) for index in range(len(raw_values))]

    current_value = max(
        smoothed_values[-1],
        0.0,
    )
    day_span = max(
        x_values[-1] - x_values[0],
        1.0,
    )
    slope = (smoothed_values[-1] - smoothed_values[0]) / day_span

    forecast_points = _build_forecast_points(
        last_timestamp=values[-1].timestamp,
        current_value=current_value,
        slope_per_day=slope,
        horizon_days=horizon_days,
    )
    projected_value = forecast_points[-1].value if forecast_points else current_value

    confidence, confidence_reason = _calculate_confidence(
        values=smoothed_values,
        points_count=len(values),
    )

    return {
        'current_value': current_value,
        'projected_value': projected_value,
        'slope_per_day': slope,
        'forecast_points': forecast_points,
        'confidence': confidence,
        'confidence_reason': f'{confidence_reason} Moving average uses a {window}-day smoothing window.',
    }


def _calculate_conservative_forecast(
    *,
    values: list[ForecastPoint],
    horizon_days: int,
) -> dict[str, Any]:
    result = _calculate_linear_forecast(
        values=values,
        horizon_days=horizon_days,
    )
    slope = result['slope_per_day']

    if slope > 0:
        adjusted_slope = slope * 1.15
    else:
        adjusted_slope = slope

    current_value = result['current_value']
    forecast_points = _build_forecast_points(
        last_timestamp=values[-1].timestamp,
        current_value=current_value,
        slope_per_day=adjusted_slope,
        horizon_days=horizon_days,
    )

    result['slope_per_day'] = adjusted_slope
    result['forecast_points'] = forecast_points
    result['projected_value'] = forecast_points[-1].value if forecast_points else current_value
    result['confidence_reason'] = (
        f'{result["confidence_reason"]} Conservative projection applies a 15% growth buffer when usage is trending upward.'
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


def _calculate_confidence(
    *,
    values: list[float],
    points_count: int,
) -> tuple[str, str]:
    if points_count < 7:
        return 'Low', 'Less than 7 daily data points available.'

    avg_value = mean(values)

    if avg_value <= 0:
        return 'Low', 'Average historical value is zero or unavailable.'

    variance = mean(
        [(value - avg_value) ** 2 for value in values],
    )
    std_dev = sqrt(variance)
    coefficient_of_variation = std_dev / avg_value

    if points_count >= 30 and coefficient_of_variation <= 0.25:
        return 'High', 'Historical data is sufficient and relatively stable.'

    if points_count >= 14 and coefficient_of_variation <= 0.60:
        return 'Medium', 'Historical data is usable with moderate variance.'

    return 'Low', 'Historical data is noisy or too limited.'


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
    warning_items = [item for item in items if item['status'] == 'warning']
    critical_items = [item for item in items if item['status'] == 'critical']

    highest_projected = None

    if items:
        highest_projected = max(
            items,
            key=lambda item: item['projected_percent'],
        )

    return {
        'total_resources': len(items),
        'warning_count': len(warning_items),
        'critical_count': len(critical_items),
        'highest_projected_label': (highest_projected['label'] if highest_projected is not None else 'N/A'),
        'highest_projected_percent': (highest_projected['projected_percent'] if highest_projected is not None else 0),
        'nearest_warning': _find_nearest_eta(
            items=items,
            eta_key='warning_eta',
        ),
        'nearest_critical': _find_nearest_eta(
            items=items,
            eta_key='critical_eta',
        ),
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


def _format_growth(
    slope_per_day: float,
    unit: str,
) -> str:
    weekly_growth = slope_per_day * 7

    if unit == 'bytes':
        return f'{_format_bytes(weekly_growth)} / week'

    if unit == 'cores':
        return f'{weekly_growth:.2f} cores / week'

    if unit == 'count':
        return f'{weekly_growth:.0f} pods / week'

    return f'{weekly_growth:.2f} / week'


def _format_bytes(
    value: float,
) -> str:
    if value <= 0:
        return '0 B'

    units = [
        'B',
        'KiB',
        'MiB',
        'GiB',
        'TiB',
        'PiB',
    ]
    size = float(value)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f'{size:.0f} {units[unit_index]}'

    return f'{size:.2f} {units[unit_index]}'


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
        'forecast_method': 'linear',
        'method_label': 'Linear Trend',
        'method_description': 'Projects future usage from the historical growth rate.',
        'history_days': 30,
        'horizon_days': 90,
        'generated_at': None,
        'items': [],
        'summary': {
            'total_resources': 0,
            'warning_count': 0,
            'critical_count': 0,
            'highest_projected_label': 'N/A',
            'highest_projected_percent': 0,
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
) -> dict[str, Any]:
    cluster = Cluster.query.filter_by(
        id=cluster_id,
    ).first()

    if not cluster:
        return _empty_forecast_snapshot()

    history_window = _normalize_forecast_history_window(
        time_range,
    )

    try:
        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        forecast_service = ForecastAnalysisService(
            utilization_service=utilization_service,
            cluster=cluster,
        )

        forecast_payload = forecast_service.get_forecast_analysis(
            namespace='',
            history_window=history_window,
            forecast_horizon='30d',
            resource='all',
            method='linear',
        )

        items = _as_list(
            forecast_payload.get(
                'items',
                [],
            )
        )

        summary = _as_dict(
            forecast_payload.get(
                'summary',
                {},
            )
        )

        item_map = _build_forecast_item_map(
            items,
        )

        cpu_item = item_map.get(
            'cpu',
            {},
        )
        memory_item = item_map.get(
            'memory',
            {},
        )
        storage_item = item_map.get(
            'storage',
            {},
        )
        pod_item = item_map.get(
            'pods',
            {},
        )

        forecast_risk = _resolve_forecast_risk(
            summary=summary,
            items=items,
        )

        warning_count = _safe_int(
            summary.get(
                'warning_count',
                0,
            )
        )
        critical_count = _safe_int(
            summary.get(
                'critical_count',
                0,
            )
        )
        risk_count = warning_count + critical_count

        risk_note = (
            f'{risk_count} metric(s) may breach warning thresholds in the forecast window.'
            if risk_count > 0
            else 'No forecast risk detected in the selected time range.'
        )

        actionable_recommendations = build_forecast_actionable_recommendations(
            forecast_payload,
        )

        return {
            'cpu_trend': _get_forecast_trend_label(
                cpu_item,
            ),
            'cpu_trend_value': _get_forecast_trend_value(
                cpu_item,
            ),
            'memory_trend': _get_forecast_trend_label(
                memory_item,
            ),
            'memory_trend_value': _get_forecast_trend_value(
                memory_item,
            ),
            'storage_trend': _get_forecast_trend_label(
                storage_item,
            ),
            'storage_trend_value': _get_forecast_trend_value(
                storage_item,
            ),
            'pod_trend': _get_forecast_trend_label(
                pod_item,
            ),
            'pod_trend_value': _get_forecast_trend_value(
                pod_item,
            ),
            'forecast_risk': forecast_risk,
            'forecast_horizon': '30 days',
            'risk_count': risk_count,
            'risk_note': risk_note,
            'highest_projected_resource': str(
                summary.get(
                    'highest_projected_label',
                    'N/A',
                )
            ),
            'highest_projected_percent': _safe_int(
                summary.get(
                    'highest_projected_percent',
                    0,
                )
            ),
            'nearest_warning': _as_dict(
                summary.get(
                    'nearest_warning',
                    {},
                )
            ),
            'nearest_critical': _as_dict(
                summary.get(
                    'nearest_critical',
                    {},
                )
            ),
            'series': _build_forecast_snapshot_series(
                items,
            ),
            'recommendation_count': count_actionable_recommendations(
                actionable_recommendations,
            ),
        }

    except Exception:
        return _empty_forecast_snapshot()


def _empty_forecast_snapshot() -> dict[str, Any]:
    return {
        'cpu_trend': 'Stable',
        'cpu_trend_value': 0,
        'memory_trend': 'Stable',
        'memory_trend_value': 0,
        'storage_trend': 'Stable',
        'storage_trend_value': 0,
        'pod_trend': 'Stable',
        'pod_trend_value': 0,
        'forecast_risk': 'Low',
        'forecast_horizon': '30 days',
        'risk_count': 0,
        'risk_note': 'No forecast risk detected in the selected time range.',
        'highest_projected_resource': 'N/A',
        'highest_projected_percent': 0,
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
        'series': [],
        'recommendation_count': 0,
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
) -> int:
    current_percent = _safe_float(
        item.get(
            'current_percent',
            0,
        )
    )
    projected_percent = _safe_float(
        item.get(
            'projected_percent',
            0,
        )
    )

    return _safe_int(
        projected_percent - current_percent,
    )


def _get_forecast_trend_label(
    item: dict[str, Any],
) -> str:
    trend_value = _get_forecast_trend_value(
        item,
    )

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

    for item in items:
        item_dict = _as_dict(
            item,
        )

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

    return 'Low'


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
                    'current_percent',
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
                    'current_percent',
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





