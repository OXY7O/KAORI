from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from flask import has_request_context
from flask_login import current_user

from app.common.timezone import (
    format_user_datetime,
    normalize_date_format,
    normalize_locale,
    normalize_time_format,
    normalize_timezone_name,
)


@dataclass(frozen=True, slots=True)
class UserPresentationPreferences:
    timezone_name: str = 'UTC'
    locale: str = 'en-US'
    date_format: str = 'day_month_year'
    time_format: str = '24h'


def current_user_presentation_preferences() -> UserPresentationPreferences:
    if not has_request_context() or not current_user.is_authenticated:
        return UserPresentationPreferences()

    return UserPresentationPreferences(
        timezone_name=normalize_timezone_name(getattr(current_user, 'timezone', 'UTC')),
        locale=normalize_locale(getattr(current_user, 'locale', 'en-US')),
        date_format=normalize_date_format(getattr(current_user, 'date_format', 'day_month_year')),
        time_format=normalize_time_format(getattr(current_user, 'time_format', '24h')),
    )


def present_user_datetime(
    value: datetime | str | None,
    *,
    empty: str = '-',
    include_seconds: bool = False,
    include_timezone: bool = True,
    preferences: UserPresentationPreferences | None = None,
) -> str:
    selected = preferences or current_user_presentation_preferences()
    return format_user_datetime(
        value,
        selected.timezone_name,
        date_format=selected.date_format,
        time_format=selected.time_format,
        locale=selected.locale,
        include_seconds=include_seconds,
        include_timezone=include_timezone,
        empty=empty,
    )


def present_key_label(value: str | None, *, empty: str = '-') -> str:
    """Convert a canonical snake-case key into a presentation label in Python."""
    if not value:
        return empty
    return str(value).replace('_', ' ').strip().title()


def present_count(value: int | None, singular: str, plural: str | None = None) -> str:
    count = int(value or 0)
    noun = singular if count == 1 else (plural or f'{singular}s')
    return f'{count} {noun}'


def present_milliseconds(value: int | float | None, *, empty: str = 'Not observed') -> str:
    if value is None:
        return empty
    return f'{int(value)} ms'


def pretty_structured_json(value: object) -> str | None:
    """Pretty-print valid JSON objects/arrays for read-only metadata; leave other values unchanged."""
    if not isinstance(value, str) or not value.lstrip().startswith(('{', '[')):
        return None

    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, RecursionError):
        return None

    if not isinstance(parsed, (dict, list)):
        return None
    return json.dumps(parsed, indent=2, ensure_ascii=False)
