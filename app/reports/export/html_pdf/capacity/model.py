from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_RESOURCE_UNITS = {
    'cpu': 'cores',
    'memory': 'GiB',
    'pods': 'pods',
    'storage': 'GiB',
}
_RESOURCE_LABELS = {
    'cpu': 'CPU',
    'memory': 'Memory',
    'pods': 'Pods',
    'storage': 'Storage',
}


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def ratio_percent(numerator: int, denominator: int) -> float:
    return numerator / denominator * 100 if denominator > 0 else 0.0


def percent(value: float) -> str:
    return f'{max(0.0, value):.1f}%'


def optional_percent(value: float | None) -> str:
    return percent(value) if value is not None else 'Not Available'


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def risk_metric(label: str, count: int, tone: str) -> dict[str, str]:
    return metric(
        label,
        str(count),
        'Open' if count else 'Clear',
        tone if count else 'normal',
    )


def capacity_resource(item: Mapping[str, Any], key: str) -> dict[str, Any]:
    evidence_available = bool(item.get('evidence_available')) or to_float(item.get('capacity')) > 0
    capacity = max(0.0, to_float(item.get('capacity')))
    used = max(0.0, to_float(item.get('used')))
    available = max(0.0, to_float(item.get('available')))
    headroom = to_float(item.get('headroom')) if evidence_available else None
    if evidence_available and headroom is not None and headroom <= 0 and capacity > 0:
        headroom = max(0.0, min(100.0, available / capacity * 100))
    used_percent = max(0.0, min(100.0, 100.0 - headroom)) if headroom is not None else 0.0
    status, tone = headroom_status(headroom)
    unit = _RESOURCE_UNITS[key]
    return {
        'key': key,
        'label': _RESOURCE_LABELS[key],
        'unit': unit,
        'evidence_available': evidence_available,
        'capacity': capacity,
        'used': used,
        'available': available,
        'headroom': headroom,
        'used_percent': used_percent,
        'used_display': percent(used_percent) if evidence_available else 'Not Available',
        'headroom_display': percent(headroom) if headroom is not None else 'Not Available',
        'capacity_display': quantity(capacity, unit) if evidence_available else 'Not Available',
        'available_display': quantity(available, unit) if evidence_available else 'Not Available',
        'used_value_display': quantity(used, unit) if evidence_available else 'Not Available',
        'capacity_value_display': (quantity(capacity, unit) if evidence_available else 'Not Available'),
        'status': status,
        'tone': tone,
    }


def quantity(value: float, unit: str) -> str:
    if unit == 'pods':
        return f'{int(round(value))} Pods'
    if unit == 'cores':
        return f'{value:.2f} Cores'
    return f'{value:.2f} GiB'


def headroom_status(headroom: float | None) -> tuple[str, str]:
    if headroom is None:
        return 'Not Available', 'muted'
    if headroom < 15:
        return 'Critical', 'critical'
    if headroom < 40:
        return 'Watch', 'warning'
    return 'Healthy', 'normal'


def allocation_resource(section: Mapping[str, Any], key: str) -> dict[str, Any]:
    status = mapping(section.get('status'))
    rows = []
    for item in sequence(section.get('items')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'label': sanitize_text(item.get('label'), fallback='Capacity Signal'),
                'display': sanitize_text(item.get('display'), fallback='Not Available'),
                'percent': max(0.0, min(to_float(item.get('percent')), 100.0)),
                'tone': sanitize_text(item.get('tone'), fallback='muted'),
            }
        )
    return {
        'key': key,
        'title': sanitize_text(section.get('title'), fallback=_RESOURCE_LABELS[key]),
        'available': bool(section.get('available')),
        'unit': sanitize_text(section.get('unit'), fallback=_RESOURCE_UNITS[key]),
        'status': sanitize_text(status.get('label'), fallback='Unknown'),
        'tone': sanitize_text(status.get('tone'), fallback='muted'),
        'items': tuple(rows),
    }
