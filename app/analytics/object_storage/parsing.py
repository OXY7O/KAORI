from __future__ import annotations

from typing import Any


def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data')
    if not isinstance(data, dict):
        return []
    result = data.get('result')
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _number(value: object) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def vector_scalar(payload: dict[str, Any]) -> float | None:
    for item in _results(payload):
        value = item.get('value')
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return _number(value[1])
    return None


def vector_by_label(payload: dict[str, Any], label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in _results(payload):
        metric = item.get('metric')
        value = item.get('value')
        if not isinstance(metric, dict) or not isinstance(value, (list, tuple)) or len(value) < 2:
            continue
        key = str(metric.get(label) or '').strip()
        number = _number(value[1])
        if key and number is not None:
            values[key] = number
    return values


def matrix_points(payload: dict[str, Any]) -> list[dict[str, float]]:
    rows = _results(payload)
    if not rows:
        return []
    values = rows[0].get('values')
    if not isinstance(values, list):
        return []
    points: list[dict[str, float]] = []
    for value in values:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            continue
        timestamp = _number(value[0])
        number = _number(value[1])
        if timestamp is not None and number is not None:
            points.append({'timestamp': timestamp, 'value': number})
    return points
