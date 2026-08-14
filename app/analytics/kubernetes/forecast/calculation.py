from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil, isfinite, sqrt
from statistics import mean
from typing import Any

from app.analytics.kubernetes.forecast.contracts import (
    CRITICAL_THRESHOLD,
    FORECAST_METHOD_OPTIONS,
    WARNING_THRESHOLD,
    ForecastPoint,
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
            f'{fallback["signal_quality_reason"]} Holt-Winters used a linear fallback because fewer than '
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
    latest = result['latest_daily_average']
    baseline_points = list(result['forecast_points'])
    forecast_points = [
        ForecastPoint(
            timestamp=point.timestamp,
            value=(latest + ((point.value - latest) * 1.15) if point.value > latest else point.value),
        )
        for point in baseline_points
    ]
    projected = forecast_points[-1].value if forecast_points else latest
    adjusted_slope = (projected - latest) / horizon_days if horizon_days > 0 else 0.0
    result['slope_per_day'] = adjusted_slope
    result['forecast_points'] = forecast_points
    result['projected_value'] = projected
    result['signal_quality_reason'] = (
        f'{result["signal_quality_reason"]} Conservative Trend applies a 15% uplift '
        'to positive Holt-Winters projection growth while preserving seasonal shape.'
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


def _unavailable_eta(label: str = 'N/A') -> dict[str, Any]:
    return {'label': label, 'days': None, 'date': None}


def _calculate_threshold_eta(
    *,
    current_value: float,
    forecast_points: list[ForecastPoint],
    capacity: float,
    threshold: float,
    base_time: datetime,
    horizon_days: int,
) -> dict[str, Any]:
    if capacity <= 0:
        return _unavailable_eta()

    threshold_value = capacity * (threshold / 100)
    if current_value >= threshold_value:
        return {
            'label': 'Reached',
            'days': 0,
            'date': base_time.strftime('%Y-%m-%d'),
        }

    for point in forecast_points:
        if point.value < threshold_value:
            continue
        days = max(ceil((point.timestamp - base_time).total_seconds() / 86400), 0)
        if days > horizon_days:
            break
        return {
            'label': f'{days} days',
            'days': days,
            'date': point.timestamp.strftime('%Y-%m-%d'),
        }

    return _unavailable_eta(f'Beyond {horizon_days}d horizon')


def _resolve_summary_posture(
    *,
    available_items: list[dict[str, Any]],
    unavailable_items: list[dict[str, Any]],
    warning_items: list[dict[str, Any]],
    critical_items: list[dict[str, Any]],
) -> tuple[str, str, str]:
    if critical_items:
        return 'critical', 'Critical Projection', 'critical'
    if warning_items:
        return 'warning', 'Capacity Watch', 'warning'
    if not available_items:
        return 'unknown', 'Evidence Unavailable', 'unknown'
    if unavailable_items or any(not item.get('planning_ready') for item in available_items):
        return 'limited', 'Limited Evidence', 'warning'
    return 'healthy', 'Within Capacity', 'normal'


def _build_summary(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    available_items = [
        item for item in items if item.get('has_data') and item.get('peak_projected_percent') is not None
    ]
    unavailable_items = [item for item in items if not item.get('has_data')]
    warning_items = [item for item in available_items if item['status'] == 'warning']
    critical_items = [item for item in available_items if item['status'] == 'critical']
    highest_projected = (
        max(available_items, key=lambda item: float(item['peak_projected_percent'])) if available_items else None
    )
    posture, posture_label, posture_tone = _resolve_summary_posture(
        available_items=available_items,
        unavailable_items=unavailable_items,
        warning_items=warning_items,
        critical_items=critical_items,
    )
    return {
        'total_resources': len(items),
        'forecasted_resources': len(available_items),
        'unavailable_resources': len(unavailable_items),
        'limited_resources': sum(1 for item in available_items if not item.get('planning_ready')),
        'warning_count': len(warning_items),
        'critical_count': len(critical_items),
        'highest_projected_label': highest_projected['label'] if highest_projected else 'N/A',
        'highest_projected_percent': (highest_projected['peak_projected_percent'] if highest_projected else None),
        'nearest_warning': _find_nearest_eta(items=available_items, eta_key='warning_eta'),
        'nearest_critical': _find_nearest_eta(items=available_items, eta_key='critical_eta'),
        'posture': posture,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'evidence_complete': posture not in {'unknown', 'limited'},
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
    available_items = [item for item in items if item.get('has_data')]
    all_dates = sorted(
        {
            str(point.get('date'))
            for item in available_items
            for collection in ('historical_points', 'forecast_points')
            for point in item.get(collection, [])
            if point.get('date')
        }
    )
    datasets = []

    for item in available_items:
        historical_map = {
            str(point['date']): point.get('percent') for point in item.get('historical_points', []) if point.get('date')
        }
        forecast_map = {
            str(point['date']): point.get('percent') for point in item.get('forecast_points', []) if point.get('date')
        }
        historical_dates = sorted(historical_map)
        if historical_dates:
            boundary_date = historical_dates[-1]
            forecast_map.setdefault(boundary_date, historical_map[boundary_date])

        datasets.append(
            {
                'key': item['key'],
                'label': item['label'],
                'labels': all_dates,
                'historical': [historical_map.get(date) for date in all_dates],
                'forecast': [forecast_map.get(date) for date in all_dates],
            }
        )

    return {
        'labels': all_dates,
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
            if not isfinite(value):
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
            parsed = float(value[1])
        except (TypeError, ValueError):
            continue
        if isfinite(parsed):
            total += parsed

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
