from __future__ import annotations

from datetime import datetime


def format_bytes(value: float | int | None) -> str:
    if value is None:
        return 'N/A'
    size = float(value)
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            return f'{size:,.1f} {unit}' if unit != 'B' else f'{size:,.0f} {unit}'
        size /= 1024
    return 'N/A'


def format_number(value: float | int | None) -> str:
    return 'N/A' if value is None else f'{value:,.0f}'


def format_rate(value: float | int | None) -> str:
    return 'N/A' if value is None else f'{value:,.2f}/s'


def format_percent(value: float | int | None) -> str:
    return 'N/A' if value is None else f'{value:,.1f}%'


def utilization_percent(used: float | None, capacity: float | None) -> float | None:
    if used is None or capacity is None or capacity <= 0:
        return None
    return max(0.0, min(100.0, used / capacity * 100.0))


def utilization_tone(value: float | None) -> str:
    if value is None:
        return 'unknown'
    if value >= 95:
        return 'critical'
    if value >= 85:
        return 'warning'
    return 'normal'


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return 'Not Collected'
    return value.strftime('%Y-%m-%d %H:%M UTC')
