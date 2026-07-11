from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

DEFAULT_TIMEZONE = 'UTC'

_PRIORITY_TIMEZONES = (
    'UTC',
    'Asia/Jakarta',
    'Asia/Makassar',
    'Asia/Jayapura',
    'Asia/Singapore',
    'Asia/Kuala_Lumpur',
    'Asia/Tokyo',
    'Asia/Seoul',
    'Australia/Sydney',
    'Europe/London',
    'Europe/Berlin',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
)


def timezone_choices() -> list[str]:
    known_timezones = available_timezones()
    priority = [name for name in _PRIORITY_TIMEZONES if name in known_timezones]
    remaining = sorted(name for name in known_timezones if name not in priority and not name.startswith('Etc/'))
    return [*priority, *remaining]


def normalize_timezone_name(value: str | None) -> str:
    timezone_name = (value or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return DEFAULT_TIMEZONE

    return timezone_name


def localize_datetime(value: datetime | None, timezone_name: str | None) -> datetime | None:
    if value is None:
        return None

    normalized_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized_value.astimezone(ZoneInfo(normalize_timezone_name(timezone_name)))


def format_datetime(
    value: datetime | None,
    timezone_name: str | None,
    pattern: str = '%d %b %Y %H:%M %Z',
    empty: str = '-',
) -> str:
    localized = localize_datetime(value, timezone_name)
    return localized.strftime(pattern) if localized is not None else empty


def format_date(
    value: datetime | None,
    timezone_name: str | None,
    pattern: str = '%d %b %Y',
    empty: str = '-',
) -> str:
    return format_datetime(value, timezone_name, pattern, empty)
