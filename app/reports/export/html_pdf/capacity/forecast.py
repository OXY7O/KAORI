from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .model import (
    RESOURCE_LABELS,
    CapacityState,
    mapping,
    number_float,
    optional_percent,
    percent,
    sequence,
)


@dataclass(frozen=True)
class CapacityForecastState:
    items: Mapping[str, Mapping[str, Any]]
    projections: Mapping[str, float | None]
    rows: tuple[dict[str, str], ...]
    available: bool
    method: str
    interpretation: str


def forecast_percent(item: Mapping[str, Any]) -> float | None:
    if not item:
        return None
    for key in ('projected_percent', 'projection_percent', 'projected_value'):
        if item.get(key) is not None:
            return max(0.0, number_float(item.get(key)))
    points = forecast_points_percent(item)
    return points[-1] if points else None


def history_percent(item: Mapping[str, Any]) -> list[float]:
    values = []
    for point in sequence(item.get('historical_points')):
        if isinstance(point, Mapping):
            value = point.get('percent', point.get('value'))
            if value is not None:
                values.append(max(0.0, number_float(value)))
    return values


def forecast_points_percent(item: Mapping[str, Any]) -> list[float]:
    values = []
    for point in sequence(item.get('forecast_points')):
        if isinstance(point, Mapping):
            value = point.get('percent', point.get('value'))
            if value is not None:
                values.append(max(0.0, number_float(value)))
    return values


def forecast_row(
    ref: str,
    key: str,
    current: float,
    projection: float | None,
) -> dict[str, str]:
    return {
        'ref': ref,
        'resource': RESOURCE_LABELS[key],
        'current': percent(current),
        'projection': optional_percent(projection),
        'assessment': projection_status(projection),
        'tone': projection_tone(projection),
    }


def projection_status(value: float | None) -> str:
    if value is None:
        return 'Not Available'
    if value >= 85:
        return 'Critical'
    if value >= 70:
        return 'Review'
    return 'Stable'


def projection_tone(value: float | None) -> str:
    if value is None:
        return 'muted'
    if value >= 85:
        return 'critical'
    if value >= 70:
        return 'warning'
    return 'normal'


def forecast_interpretation(projections: Mapping[str, float | None]) -> str:
    available = {key: value for key, value in projections.items() if value is not None}
    if not available:
        return 'Committed forecast evidence was not available; planning conclusions remain limited to current capacity.'
    constrained_key, constrained_value = max(available.items(), key=lambda item: item[1])
    if constrained_value >= 85:
        return (
            f'{RESOURCE_LABELS[constrained_key]} projects into the critical operating band '
            'and requires an approved response.'
        )
    if constrained_value >= 70:
        return (
            f'{RESOURCE_LABELS[constrained_key]} projects into the warning band '
            'and requires planning review.'
        )
    return 'No displayed resource is projected to enter the warning band within the committed planning horizon.'


def build_capacity_forecast_state(state: CapacityState) -> CapacityForecastState:
    items = {
        str(item.get('key') or '').lower(): item
        for item in sequence(state.forecast_payload.get('items'))
        if isinstance(item, Mapping)
    }
    projections = {
        key: forecast_percent(mapping(items.get(key)))
        for key in ('cpu', 'memory', 'pods')
    }
    rows = tuple(
        forecast_row(
            f'T{index}',
            key,
            state.resources[key]['used_percent'],
            projections[key],
        )
        for index, key in enumerate(('cpu', 'memory', 'pods'), start=1)
    )
    available = any(value is not None for value in projections.values())
    method = sanitize_text(
        state.forecast_payload.get('method_label')
        or state.forecast_payload.get('forecast_method'),
        fallback='Not Available',
    )
    return CapacityForecastState(
        items=items,
        projections=projections,
        rows=rows,
        available=available,
        method=method,
        interpretation=forecast_interpretation(projections),
    )
