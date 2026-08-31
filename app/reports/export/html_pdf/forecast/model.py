from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.kubernetes.analytics.forecast.contracts import (
    CRITICAL_THRESHOLD as FORECAST_CRITICAL_THRESHOLD,
    WARNING_THRESHOLD as FORECAST_WARNING_THRESHOLD,
)
from app.reports.export.html_pdf.normalization import sanitize_text

from .charts import combined_chart_svg, single_chart_svg

FORECAST_PAGE_TITLES = (
    'Cover',
    'Executive Forecast Brief',
    'Forecast Portfolio',
    'CPU Forecast',
    'Memory Forecast',
    'Pod and Storage Forecast',
    'Threshold Exposure and Confidence',
    'Recommendation Plan',
    'Methodology and Evidence Boundary',
)

RESOURCE_META = {
    'cpu': {'label': 'CPU', 'color': '#2563EB'},
    'memory': {'label': 'Memory', 'color': '#7C3AED'},
    'pods': {'label': 'Pods', 'color': '#15803D'},
    'storage': {'label': 'Storage', 'color': '#D97706'},
}
WARNING_THRESHOLD = FORECAST_WARNING_THRESHOLD
CRITICAL_THRESHOLD = FORECAST_CRITICAL_THRESHOLD


@dataclass(frozen=True, slots=True)
class ForecastState:
    payload: Mapping[str, Any]
    cluster: dict[str, Any]
    forecast_payload: dict[str, Any]
    resources: dict[str, dict[str, Any]]
    available: list[dict[str, Any]]
    highest: dict[str, Any] | None
    warning_count: int
    critical_count: int
    coverage_count: int
    method: str
    history_window: str
    horizon: str
    horizon_days: int | None
    combined_chart: str
    highest_value: str
    highest_status: str
    forecast_status: str
    forecast_tone: str


def build_forecast_state(payload: Mapping[str, Any]) -> ForecastState:
    cluster = mapping(payload.get('cluster'))
    forecast_payload = mapping(payload.get('forecast_payload'))
    items = resource_map(forecast_payload)
    resources = {key: resource_presentation(key, mapping(items.get(key))) for key in RESOURCE_META}
    available = [item for item in resources.values() if item['available']]
    highest = (
        max(available, key=lambda item: float_value(item.get('peak_projected_percent')) or 0.0)
        if available
        else None
    )
    warning_count = sum(
        1
        for item in available
        if (float_value(item.get('peak_projected_percent')) or 0.0) >= WARNING_THRESHOLD
    )
    critical_count = sum(
        1
        for item in available
        if (float_value(item.get('peak_projected_percent')) or 0.0) >= CRITICAL_THRESHOLD
    )
    coverage_count = len(available)
    method = sanitize_text(
        forecast_payload.get('method_label')
        or forecast_payload.get('forecast_method_label')
        or forecast_payload.get('forecast_method'),
        fallback='Not Available',
    )
    history_window = sanitize_text(
        forecast_payload.get('history_window') or payload.get('history_window'),
        fallback='Not Available',
    )
    horizon = sanitize_text(
        forecast_payload.get('forecast_horizon') or payload.get('forecast_horizon'),
        fallback='Not Available',
    )
    horizon_days = int_value(forecast_payload.get('horizon_days')) or days_from_label(horizon)
    combined_chart = combined_chart_svg(resources)
    highest_value = percent(highest['peak_projected_percent']) if highest else 'Not Available'
    highest_status = highest['label'] if highest else 'No Forecast Evidence'
    forecast_status = executive_status(warning_count, critical_count, coverage_count)
    forecast_tone = executive_tone(warning_count, critical_count, coverage_count)
    return ForecastState(
        payload=payload,
        cluster=cluster,
        forecast_payload=forecast_payload,
        resources=resources,
        available=available,
        highest=highest,
        warning_count=warning_count,
        critical_count=critical_count,
        coverage_count=coverage_count,
        method=method,
        history_window=history_window,
        horizon=horizon,
        horizon_days=horizon_days,
        combined_chart=combined_chart,
        highest_value=highest_value,
        highest_status=highest_status,
        forecast_status=forecast_status,
        forecast_tone=forecast_tone,
    )


def resource_map(forecast_payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in sequence(forecast_payload.get('items')):
        if not isinstance(item, Mapping):
            continue
        key = text(item.get('key'), '').lower()
        if key == 'pod':
            key = 'pods'
        if key in RESOURCE_META:
            result[key] = item
    return result


def resource_presentation(key: str, item: Mapping[str, Any]) -> dict[str, Any]:
    meta = RESOURCE_META[key]
    capacity = float_value(item.get('capacity'))
    current = first_float(
        item.get('latest_daily_average_percent'),
        item.get('current_percent'),
        ratio(item.get('latest_daily_average'), capacity),
        ratio(item.get('current_value'), capacity),
    )
    projected = first_float(
        item.get('projected_percent'),
        ratio(item.get('projected_value'), capacity),
    )
    history = point_percentages(item.get('historical_points'), capacity)
    projection = point_percentages(item.get('forecast_points'), capacity)
    peak_projected = first_float(
        item.get('peak_projected_percent'),
        max(projection) if projection else None,
        projected,
    )
    available = bool(item.get('has_data')) and projected is not None
    if projected is not None and (history or projection):
        available = True
    if current is None and history:
        current = history[-1]
    if projected is None and projection:
        projected = projection[-1]
    if current is None:
        current = 0.0
    if projected is None:
        projected = 0.0
    if peak_projected is None:
        peak_projected = projected

    status = status_for_value(peak_projected) if available else 'Not Available'
    tone = tone_for_value(peak_projected) if available else 'warning'
    warning_eta = eta(item.get('warning_eta')) if available else 'Not Available'
    critical_eta = eta(item.get('critical_eta')) if available else 'Not Available'
    confidence = sanitize_text(
        item.get('signal_quality') or item.get('confidence'),
        fallback='Not Available' if not available else 'Review',
    )
    confidence_reason = sanitize_text(
        item.get('signal_quality_reason') or item.get('confidence_reason'),
        fallback='Committed forecast confidence metadata was not supplied.',
    )
    empty_reason = sanitize_text(
        item.get('empty_reason'),
        fallback='Committed forecast evidence is not available for this resource.',
    )
    chart_svg = single_chart_svg(
        label=meta['label'],
        color=meta['color'],
        history=history,
        projection=projection,
        current=current if available else None,
        projected=projected if available else None,
        empty_reason=empty_reason,
    )
    headroom = max(0.0, 100.0 - peak_projected) if available else None
    return {
        'key': key,
        'label': meta['label'],
        'color': meta['color'],
        'available': available,
        'current_percent': current,
        'projected_percent': projected,
        'peak_projected_percent': peak_projected,
        'current_display': percent(current) if available else 'Not Available',
        'projected_display': percent(projected) if available else 'Not Available',
        'peak_projected_display': percent(peak_projected) if available else 'Not Available',
        'headroom_percent': headroom,
        'headroom_display': percent(headroom) if headroom is not None else 'Not Available',
        'status': status,
        'tone': tone,
        'warning_eta': warning_eta,
        'critical_eta': critical_eta,
        'confidence': confidence,
        'confidence_reason': confidence_reason,
        'history': history,
        'projection': projection,
        'chart_svg': chart_svg,
        'empty_reason': empty_reason,
        'scope_label': sanitize_text(item.get('scope_label'), fallback='Selected report boundary'),
        'method': sanitize_text(item.get('method_label') or item.get('forecast_method'), fallback='Not Available'),
    }


def point_percentages(value: Any, capacity: float | None) -> list[float]:
    result: list[float] = []
    for item in sequence(value):
        if not isinstance(item, Mapping):
            continue
        point_percent = float_value(item.get('percent'))
        if point_percent is None and capacity:
            raw = float_value(item.get('value'))
            if raw is not None:
                point_percent = raw / capacity * 100.0
        if point_percent is not None:
            result.append(max(0.0, min(100.0, point_percent)))
    return result


def status_for_value(value: float) -> str:
    if value >= CRITICAL_THRESHOLD:
        return 'Critical'
    if value >= WARNING_THRESHOLD:
        return 'Warning'
    return 'Stable'


def tone_for_value(value: float) -> str:
    if value >= CRITICAL_THRESHOLD:
        return 'critical'
    if value >= WARNING_THRESHOLD:
        return 'warning'
    return 'normal'


def executive_status(warning_count: int, critical_count: int, coverage_count: int) -> str:
    if critical_count:
        return 'Critical Review'
    if warning_count or coverage_count < len(RESOURCE_META):
        return 'Review Required'
    if coverage_count:
        return 'Normal'
    return 'Not Available'


def executive_tone(warning_count: int, critical_count: int, coverage_count: int) -> str:
    if critical_count:
        return 'critical'
    if warning_count or coverage_count < len(RESOURCE_META):
        return 'warning'
    return 'normal' if coverage_count else 'muted'


def eta(value: Any) -> str:
    if isinstance(value, Mapping):
        return sanitize_text(value.get('label'), fallback='Not projected')
    return sanitize_text(value, fallback='Not projected')


def human_window(value: str) -> str:
    cleaned = sanitize_text(value, fallback='Not Available')
    lower = cleaned.lower()
    if lower.endswith('d') and lower[:-1].isdigit():
        return f'{int(lower[:-1])} Days'
    return cleaned


def days_from_label(value: str) -> int | None:
    cleaned = value.strip().lower()
    if cleaned.endswith('d') and cleaned[:-1].isdigit():
        return int(cleaned[:-1])
    return None


def ratio(value: Any, denominator: float | None) -> float | None:
    numerator = float_value(value)
    if numerator is None or not denominator:
        return None
    return numerator / denominator * 100.0


def first_float(*values: Any) -> float | None:
    for value in values:
        parsed = float_value(value)
        if parsed is not None:
            return parsed
    return None


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def reference(ref: str, title: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'title': title, 'description': description}


def percent(value: float | None) -> str:
    return 'Not Available' if value is None else f'{value:.1f}%'


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def float_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def int_value(value: Any) -> int | None:
    parsed = float_value(value)
    return int(parsed) if parsed is not None else None


def text(value: Any, fallback: str = '') -> str:
    return sanitize_text(value, fallback=fallback)
