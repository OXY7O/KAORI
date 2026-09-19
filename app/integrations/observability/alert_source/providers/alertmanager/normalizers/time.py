from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def human_duration(starts_at: datetime | None, ends_at: datetime | None) -> str:
    if starts_at is None:
        return '-'
    end_time = ends_at or datetime.now(UTC)
    if end_time <= starts_at:
        end_time = datetime.now(UTC)
    total_seconds = int((end_time - starts_at).total_seconds())
    if total_seconds < 60:
        return f'{total_seconds}s'
    total_minutes = total_seconds // 60
    if total_minutes < 60:
        return f'{total_minutes}m'
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours < 24:
        return f'{hours}h {minutes}m'
    days = hours // 24
    return f'{days}d {hours % 24}h'
