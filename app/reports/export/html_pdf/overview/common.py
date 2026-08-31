from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

TONE_MAP = {
    'green': 'normal',
    'normal': 'normal',
    'healthy': 'normal',
    'ready': 'normal',
    'current': 'normal',
    'amber': 'warning',
    'orange': 'warning',
    'warning': 'warning',
    'review': 'warning',
    'attention': 'warning',
    'red': 'critical',
    'critical': 'critical',
    'failed': 'critical',
    'blue': 'info',
    'purple': 'info',
    'info': 'info',
    'gray': 'neutral',
    'unknown': 'neutral',
    'neutral': 'neutral',
}


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def text(value: Any, fallback: str = 'Not Available') -> str:
    return sanitize_text(value, fallback=fallback)


def number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, str):
        value = value.replace('%', '').replace(',', '').strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: int = 0) -> int:
    return int(round(number(value, float(default))))


def tone(value: Any) -> str:
    normalized = str(value or 'neutral').strip().lower()
    return TONE_MAP.get(normalized, 'neutral')


def status(value: Any, fallback: str = 'Unknown') -> str:
    if isinstance(value, Mapping):
        value = value.get('label') or value.get('status') or value.get('value')
    return text(value, fallback)


def percent(card: Mapping[str, Any]) -> float | None:
    for key in (
        'percent',
        'value',
        'usage_percent',
        'utilization_percent',
        'current_percent',
        'p95_percent',
        'current',
        'p95',
    ):
        raw = card.get(key)
        if isinstance(raw, Mapping):
            raw = raw.get('percent') or raw.get('value') or raw.get('current')
        if raw is not None and str(raw).strip() != '':
            return max(0.0, min(number(raw), 100.0))
    for key in ('metric', 'usage', 'utilization', 'current_value'):
        nested = mapping(card.get(key))
        if nested:
            value = percent(nested)
            if value is not None:
                return value
    return None


def display_percent(value: float | None) -> str:
    if value is None:
        return 'Not Available'
    return f'{value:.1f}%'


def nested_number(source: Mapping[str, Any], *paths: tuple[str, ...]) -> float | None:
    for path in paths:
        value: Any = source
        for key in path:
            if not isinstance(value, Mapping):
                value = None
                break
            value = value.get(key)
        if value is None or str(value).strip() == '':
            continue
        if isinstance(value, Mapping):
            value = value.get('percent') or value.get('value') or value.get('current')
        if value is None or str(value).strip() == '':
            continue
        return number(value)
    return None
