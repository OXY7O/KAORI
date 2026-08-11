from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from app.analytics.common.coercion import as_dict as _as_dict
from app.analytics.common.coercion import as_list as _as_list
from app.analytics.common.coercion import safe_float as _safe_float
from app.analytics.common.coercion import safe_int as _safe_int
from app.analytics.common.params import get_query_value
from app.analytics.forecast.calculation import (
    _build_chart_payload,
    _build_no_forecast_data_message,
    _build_summary,
    _calculate_forecast,
    _get_forecast_method_meta,
    _normalize_option,
    _parse_days,
)
from app.analytics.forecast.contracts import (
    CRITICAL_THRESHOLD,
    FORECAST_HORIZON_OPTIONS,
    FORECAST_METHOD_OPTIONS,
    FORECAST_TABS,
    HISTORY_WINDOW_OPTIONS,
    WARNING_THRESHOLD,
    ForecastPoint,
    ForecastResourceDefinition,
)
from app.analytics.forecast.resource import build_resource_forecast_payload
from app.intelligence.recommendation_engine import (
    build_forecast_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
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
            'total_resources': 4,
            'warning_count': 0,
            'critical_count': 0,
            'highest_projected_label': 'N/A',
            'forecasted_resources': 0,
            'unavailable_resources': 4,
            'limited_resources': 0,
            'highest_projected_percent': None,
            'posture': 'unknown',
            'posture_label': 'Evidence Unavailable',
            'posture_tone': 'unknown',
            'evidence_complete': False,
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
            'labels': [],
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
    actionable_recommendations = [
        _as_dict(item)
        for item in _as_list(forecast_payload.get('actionable_recommendations'))
        if isinstance(item, dict)
    ]
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
            if risk_count > 0
            else (
                'Forecast evidence is unavailable for the selected time range.'
                if forecast_risk == 'Unknown'
                else 'No threshold breach is projected from the available evidence.'
            )
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
        'recommendation_count': count_actionable_recommendations(actionable_recommendations),
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


def _build_forecast_snapshot_series(items: list[Any]) -> list[dict[str, Any]]:
    item_map = _build_forecast_item_map(items)
    resources = (('cpu', 'CPU'), ('memory', 'Memory'), ('storage', 'Storage'), ('pods', 'Pods'))
    return [
        series
        for key, label in resources
        if (series := _snapshot_series_item(key=key, label=label, item=item_map.get(key, {})))
    ]


def _snapshot_series_item(
    *,
    key: str,
    label: str,
    item: dict[str, Any],
) -> dict[str, Any] | None:
    if not item:
        return None
    historical = _sample_forecast_values(
        _extract_percent_values(item.get('historical_points', [])),
        limit=12,
    )
    forecast = _sample_forecast_values(
        _extract_percent_values(item.get('forecast_points', [])),
        limit=12,
    )
    if not historical and not forecast:
        current = _safe_float(item.get('latest_daily_average_percent', 0))
        projected = _safe_float(item.get('projected_percent', 0))
        if current <= 0 and projected <= 0:
            return None
        historical = [current]
        forecast = [projected]

    total_points = max(len(historical) + len(forecast), 2)
    forecast_line = ([historical[-1]] if historical else []) + forecast
    latest = historical[-1] if historical else _safe_float(item.get('latest_daily_average_percent', 0))
    projected = forecast[-1] if forecast else _safe_float(item.get('projected_percent', 0))
    return {
        'key': key,
        'label': label,
        'historical_points': _build_svg_polyline_points(values=historical, total_points=total_points, start_index=0),
        'forecast_points': _build_svg_polyline_points(
            values=forecast_line,
            total_points=total_points,
            start_index=max(len(historical) - 1, 0),
        ),
        'latest_percent': _safe_int(latest),
        'projected_percent': _safe_int(projected),
        'trend': _get_forecast_trend_label(item),
    }


def _extract_percent_values(
    points: Any,
) -> list[float]:
    values: list[float] = []
    for point in _as_list(points):
        point_dict = _as_dict(point)
        raw_percent = point_dict.get('percent')
        if raw_percent is None:
            continue
        percent = _safe_float(raw_percent)
        if not isfinite(percent):
            continue
        values.append(max(percent, 0.0))
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
    historical_points = _parse_historical_points(item.get('historical_points'))
    result = _calculate_forecast(
        values=historical_points,
        horizon_days=horizon_days,
        method=method,
    )
    definition = ForecastResourceDefinition(
        key=str(item.get('key') or ''),
        label=str(item.get('label') or ''),
        unit=str(item.get('unit') or ''),
        icon=str(item.get('icon') or ''),
        description=str(item.get('description') or ''),
        scope_label=str(item.get('scope_label') or ''),
        comparison_label=str(item.get('comparison_label') or ''),
        capacity_label=str(item.get('capacity_label') or ''),
        usage_query='',
        capacity_query='',
    )
    return build_resource_forecast_payload(
        definition=definition,
        daily_points=historical_points,
        capacity=_safe_float(item.get('capacity')),
        forecast_result=result,
        horizon_days=horizon_days,
        method=method,
        fallback_time=historical_points[-1].timestamp if historical_points else datetime.now(UTC),
    )


def _parse_historical_points(value: Any) -> list[ForecastPoint]:
    points: list[ForecastPoint] = []
    for point in _as_list(value):
        point_dict = _as_dict(point)
        try:
            timestamp = datetime.strptime(str(point_dict.get('date') or ''), '%Y-%m-%d').replace(tzinfo=UTC)
            number = _safe_float(point_dict.get('value'))
        except (TypeError, ValueError):
            continue
        if isfinite(number):
            points.append(ForecastPoint(timestamp=timestamp, value=number))
    return points


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
        set(FORECAST_TABS),
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
    items = [_present_forecast_item(item, horizon_days=horizon_days, method=selected_method) for item in source_items]
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
