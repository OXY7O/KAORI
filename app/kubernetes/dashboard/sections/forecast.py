from __future__ import annotations

from typing import Any

from app.kubernetes.dashboard.schema import ForecastItem, ForecastSnapshot
from app.kubernetes.dashboard.utils import forecast_insight

_WARNING_RISKS = {'warning', 'medium'}
_CRITICAL_RISKS = {'critical', 'high'}
_RESOURCE_KEYS = ('cpu', 'memory', 'storage', 'pods')


def build_forecast_snapshot(*, context: dict[str, Any] | None, unavailable_reason: str) -> ForecastSnapshot:
    if not context:
        return ForecastSnapshot(
            insight=unavailable_reason,
            source_status='Unavailable',
        )

    payload = context.get('forecast_payload') or {}
    if not isinstance(payload, dict):
        return ForecastSnapshot(
            insight='Committed forecast snapshot has an invalid payload.',
            source_status='Unavailable',
        )

    horizon_days = _safe_int(payload.get('horizon_days'), default=90)
    raw_items = payload.get('items', [])
    items: list[ForecastItem] = []
    if isinstance(raw_items, list):
        for position, item in enumerate(raw_items[:4]):
            if not isinstance(item, dict):
                continue

            status = str(item.get('status_label') or item.get('status') or 'Unknown').title()
            projected = _optional_float(item.get('projected_percent'))
            current = _optional_float(item.get('latest_daily_average_percent'))
            resource_key = _resource_key(item=item, position=position)
            historical_values = _extract_percent_values(item.get('historical_points'), item.get('capacity'))
            forecast_values = _extract_percent_values(item.get('forecast_points'), item.get('capacity'))
            if item.get('has_data') is False:
                continue
            historical_points, forecast_points = _build_chart_points(
                historical_values=historical_values,
                forecast_values=forecast_values,
                latest_daily_average_percent=current,
                projected_percent=projected,
            )
            trend = str(item.get('trend_label') or item.get('trend') or _trend_label(current, projected)).title()
            items.append(
                ForecastItem(
                    key=resource_key,
                    label=str(item.get('label') or _resource_label(resource_key)),
                    risk=status,
                    icon=str(item.get('icon') or _resource_icon(resource_key)),
                    projected_percent=projected,
                    latest_daily_average_percent=current,
                    trend=trend,
                    historical_points=historical_points,
                    forecast_points=forecast_points,
                )
            )

    has_data = bool(payload.get('has_data')) and bool(items)
    raw_summary = payload.get('summary')
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    at_risk_count = sum(item.risk.lower() in _WARNING_RISKS | _CRITICAL_RISKS for item in items)
    critical_count = sum(item.risk.lower() in _CRITICAL_RISKS for item in items)
    highest_item = max(
        (item for item in items if item.projected_percent is not None),
        key=lambda item: item.projected_percent or 0,
        default=None,
    )
    highest_label = str(summary.get('highest_projected_label') or (highest_item.label if highest_item else 'N/A'))
    highest_percent = _optional_float(summary.get('highest_projected_percent'))
    if highest_percent is None and highest_item is not None:
        highest_percent = highest_item.projected_percent

    return ForecastSnapshot(
        items=items,
        insight=(
            forecast_insight(payload)
            if has_data
            else str(payload.get('message') or 'Insufficient trend data for reliable forecasting.')
        ),
        source_status='Available' if has_data else 'Unavailable',
        horizon_days=horizon_days,
        item_count=len(items),
        at_risk_count=at_risk_count,
        critical_count=critical_count,
        highest_projected_label=highest_label,
        highest_projected_percent=highest_percent,
        has_historical_series=any(bool(item.historical_points) for item in items),
    )


def _resource_key(*, item: dict[str, Any], position: int) -> str:
    explicit = str(item.get('key') or '').strip().lower()
    if explicit in _RESOURCE_KEYS:
        return explicit

    label = str(item.get('label') or '').strip().lower()
    for key in _RESOURCE_KEYS:
        if key in label:
            return key
    return _RESOURCE_KEYS[position] if position < len(_RESOURCE_KEYS) else 'resource'


def _resource_label(key: str) -> str:
    return {
        'cpu': 'CPU Growth',
        'memory': 'Memory Growth',
        'storage': 'Storage Growth',
        'pods': 'Pod Growth',
    }.get(key, 'Resource Growth')


def _resource_icon(key: str) -> str:
    return {
        'cpu': 'cpu',
        'memory': 'memory-stick',
        'storage': 'hard-drive',
        'pods': 'container',
    }.get(key, 'activity')


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _extract_percent_values(points: Any, capacity_value: Any) -> list[float]:
    if not isinstance(points, list):
        return []

    capacity = _optional_float(capacity_value)
    values: list[float] = []
    for point in points:
        if isinstance(point, dict):
            percent = _optional_float(point.get('percent'))
            if percent is None:
                raw_value = _optional_float(point.get('value'))
                if raw_value is not None and capacity is not None and capacity > 0:
                    percent = raw_value / capacity * 100
        else:
            percent = _optional_float(point)

        if percent is not None:
            values.append(_clamp_percent(percent))
    return values


def _sample(values: list[float], *, limit: int) -> list[float]:
    if len(values) <= limit:
        return values
    if limit <= 1:
        return [values[-1]]

    last_index = len(values) - 1
    indexes = [round(index * last_index / (limit - 1)) for index in range(limit)]
    return [values[index] for index in indexes]


def _build_chart_points(
    *,
    historical_values: list[float],
    forecast_values: list[float],
    latest_daily_average_percent: float | None,
    projected_percent: float | None,
) -> tuple[str, str]:
    history = _sample(historical_values, limit=8)
    forecast = _sample(forecast_values, limit=6)

    if history:
        historical_points = _polyline_points(history, start_x=2, end_x=56)
        forecast_line = [history[-1], *forecast]
        if len(forecast_line) == 1 and projected_percent is not None:
            forecast_line.append(projected_percent)
        if len(forecast_line) == 1:
            forecast_line.append(forecast_line[0])
        return historical_points, _polyline_points(forecast_line, start_x=56, end_x=98)

    baseline = latest_daily_average_percent if latest_daily_average_percent is not None else projected_percent
    forecast_line: list[float] = []
    if baseline is not None:
        forecast_line.append(baseline)
    forecast_line.extend(forecast)
    if projected_percent is not None and (not forecast_line or abs(forecast_line[-1] - projected_percent) > 0.01):
        forecast_line.append(projected_percent)
    if len(forecast_line) == 1:
        forecast_line.append(forecast_line[0])

    return '', _polyline_points(forecast_line, start_x=2, end_x=98)


def _polyline_points(values: list[float], *, start_x: float, end_x: float) -> str:
    if not values:
        return ''
    denominator = max(len(values) - 1, 1)
    points = []
    for index, value in enumerate(values):
        x_value = start_x + ((end_x - start_x) * index / denominator)
        points.append(f'{x_value:.2f},{_chart_y(value):.2f}')
    return ' '.join(points)


def _chart_y(value: float | None) -> float:
    return max(2.0, min(98.0, 100.0 - _clamp_percent(value or 0.0)))


def _clamp_percent(value: float) -> float:
    return max(0.0, min(float(value), 100.0))


def _trend_label(current: float | None, projected: float | None) -> str:
    if current is None or projected is None:
        return 'Unknown'
    delta = projected - current
    if delta > 1:
        return 'Increasing'
    if delta < -1:
        return 'Decreasing'
    return 'Stable'
