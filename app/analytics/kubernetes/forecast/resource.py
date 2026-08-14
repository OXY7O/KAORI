from __future__ import annotations

from datetime import datetime
from typing import Any

from app.analytics.kubernetes.forecast.calculation import (
    _calculate_threshold_eta,
    _format_value,
    _format_weekly_trend,
    _percentage,
    _resolve_forecast_empty_reason,
    _resolve_status,
)
from app.analytics.kubernetes.forecast.contracts import (
    CRITICAL_THRESHOLD,
    WARNING_THRESHOLD,
    ForecastPoint,
    ForecastResourceDefinition,
)

_NA_ETA = {'label': 'N/A', 'days': None, 'date': None}


def build_resource_forecast_payload(
    *,
    definition: ForecastResourceDefinition,
    daily_points: list[ForecastPoint],
    capacity: float,
    forecast_result: dict[str, Any],
    horizon_days: int,
    method: str,
    fallback_time: datetime,
) -> dict[str, Any]:
    evidence = _resource_evidence(
        daily_points=daily_points,
        capacity=capacity,
        forecast_result=forecast_result,
        horizon_days=horizon_days,
        fallback_time=fallback_time,
    )
    return {
        **_identity_payload(definition=definition, method=method, forecast_result=forecast_result),
        **_status_payload(evidence),
        **_metric_payload(definition=definition, evidence=evidence),
        **_series_payload(daily_points=daily_points, evidence=evidence),
    }


def _resource_evidence(
    *,
    daily_points: list[ForecastPoint],
    capacity: float,
    forecast_result: dict[str, Any],
    horizon_days: int,
    fallback_time: datetime,
) -> dict[str, Any]:
    history_count = len(daily_points)
    has_data = history_count >= 2 and capacity > 0
    latest = forecast_result['latest_daily_average'] if has_data else None
    forecast_points = list(forecast_result['forecast_points']) if has_data else []
    projected = forecast_result['projected_value'] if has_data else None
    peak = max((point.value for point in forecast_points), default=projected)
    latest_percent = _optional_percentage(latest, capacity)
    projected_percent = _optional_percentage(projected, capacity)
    peak_percent = _optional_percentage(peak, capacity)
    status = _resolve_status(peak_percent) if peak_percent is not None else 'unknown'
    signal_quality = forecast_result['signal_quality'] if has_data else 'Unavailable'
    planning_ready = has_data and signal_quality in {'High', 'Medium'}
    latest_timestamp = daily_points[-1].timestamp if daily_points else fallback_time
    return {
        'history_count': history_count,
        'has_data': has_data,
        'capacity': capacity,
        'latest': latest,
        'forecast_points': forecast_points,
        'projected': projected,
        'peak': peak,
        'slope': forecast_result['slope_per_day'] if has_data else 0.0,
        'latest_percent': latest_percent,
        'projected_percent': projected_percent,
        'peak_percent': peak_percent,
        'status': status,
        'signal_quality': signal_quality,
        'planning_ready': planning_ready,
        'warning_eta': _threshold_eta(
            current=latest,
            forecast_points=forecast_points,
            capacity=capacity,
            threshold=WARNING_THRESHOLD,
            latest_timestamp=latest_timestamp,
            horizon_days=horizon_days,
        ),
        'critical_eta': _threshold_eta(
            current=latest,
            forecast_points=forecast_points,
            capacity=capacity,
            threshold=CRITICAL_THRESHOLD,
            latest_timestamp=latest_timestamp,
            horizon_days=horizon_days,
        ),
        'signal_quality_reason': (
            forecast_result['signal_quality_reason']
            if has_data
            else 'Forecast requires at least two daily samples and a non-zero capacity baseline.'
        ),
    }


def _identity_payload(
    *,
    definition: ForecastResourceDefinition,
    method: str,
    forecast_result: dict[str, Any],
) -> dict[str, Any]:
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
    }


def _status_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    status = evidence['status']
    limited = evidence['has_data'] and not evidence['planning_ready'] and status == 'normal'
    return {
        'has_data': evidence['has_data'],
        'planning_ready': evidence['planning_ready'],
        'history_points_count': evidence['history_count'],
        'capacity_missing': evidence['capacity'] <= 0,
        'empty_reason': _resolve_forecast_empty_reason(
            history_points_count=evidence['history_count'],
            capacity=evidence['capacity'],
        ),
        'status': status,
        'status_label': 'Limited Evidence' if limited else status.title(),
        'status_tone': 'warning' if limited else status,
        'warning_eta': evidence['warning_eta'],
        'critical_eta': evidence['critical_eta'],
        'signal_quality': evidence['signal_quality'],
        'signal_quality_reason': evidence['signal_quality_reason'],
    }


def _metric_payload(
    *,
    definition: ForecastResourceDefinition,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    capacity = evidence['capacity']
    latest = evidence['latest']
    projected = evidence['projected']
    peak = evidence['peak']
    has_data = evidence['has_data']
    return {
        'capacity': capacity if capacity > 0 else None,
        'capacity_display': _format_value(capacity, definition.unit) if capacity > 0 else 'N/A',
        'latest_daily_average': latest,
        'latest_daily_average_display': _display_value(latest, definition.unit),
        'projected_value': projected,
        'projected_display': _display_value(projected, definition.unit),
        'peak_projected_value': peak,
        'peak_projected_display': _display_value(peak, definition.unit),
        'weekly_trend': evidence['slope'] * 7,
        'weekly_trend_display': (_format_weekly_trend(evidence['slope'], definition.unit) if has_data else 'N/A'),
        'latest_daily_average_percent': _rounded(evidence['latest_percent']),
        'projected_percent': _rounded(evidence['projected_percent']),
        'peak_projected_percent': _rounded(evidence['peak_percent']),
    }


def _series_payload(
    *,
    daily_points: list[ForecastPoint],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    capacity = evidence['capacity']
    return {
        'historical_points': _point_payload(daily_points, capacity),
        'forecast_points': _point_payload(evidence['forecast_points'], capacity),
    }


def _point_payload(points: list[ForecastPoint], capacity: float) -> list[dict[str, Any]]:
    return [
        {
            'date': point.timestamp.strftime('%Y-%m-%d'),
            'value': point.value,
            'percent': _rounded(_optional_percentage(point.value, capacity)),
        }
        for point in points
    ]


def _threshold_eta(
    *,
    current: float | None,
    forecast_points: list[ForecastPoint],
    capacity: float,
    threshold: float,
    latest_timestamp: datetime,
    horizon_days: int,
) -> dict[str, Any]:
    if current is None:
        return dict(_NA_ETA)
    return _calculate_threshold_eta(
        current_value=current,
        forecast_points=forecast_points,
        capacity=capacity,
        threshold=threshold,
        base_time=latest_timestamp,
        horizon_days=horizon_days,
    )


def _optional_percentage(value: float | None, capacity: float) -> float | None:
    return _percentage(value, capacity) if value is not None and capacity > 0 else None


def _display_value(value: float | None, unit: str) -> str:
    return _format_value(value, unit) if value is not None else 'N/A'


def _rounded(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
