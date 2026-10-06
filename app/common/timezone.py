from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

DEFAULT_TIMEZONE = 'UTC'
DEFAULT_TIMEZONE_MODE = 'manual'
DEFAULT_LOCALE = 'en-US'
DEFAULT_DATE_FORMAT = 'day_month_year'
DEFAULT_TIME_FORMAT = '24h'

TIMEZONE_MODES = ('automatic', 'manual')
SUPPORTED_LOCALES = ('en-US', 'id-ID')
SUPPORTED_DATE_FORMATS = (
    'day_month_year',
    'year_month_day',
    'day_month_numeric',
    'month_day_numeric',
)
SUPPORTED_TIME_FORMATS = ('24h', '12h')

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

_MONTH_ABBREVIATIONS = {
    'en-US': ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'),
    'id-ID': ('Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'),
}


def timezone_choices() -> list[str]:
    known_timezones = available_timezones()
    priority = [name for name in _PRIORITY_TIMEZONES if name in known_timezones]
    remaining = sorted(name for name in known_timezones if name not in priority and not name.startswith('Etc/'))
    return [*priority, *remaining]


def timezone_choice_groups() -> list[tuple[str, list[str]]]:
    all_choices = timezone_choices()
    priority = [name for name in _PRIORITY_TIMEZONES if name in all_choices]
    remaining = [name for name in all_choices if name not in priority]
    return [('Recommended', priority), ('All IANA timezones', remaining)]


def locale_choices() -> list[tuple[str, str]]:
    return [
        ('en-US', 'English (United States)'),
        ('id-ID', 'Bahasa Indonesia (Indonesia)'),
    ]


def date_format_choices() -> list[tuple[str, str]]:
    return [
        ('day_month_year', '17 Jul 2026'),
        ('year_month_day', '2026-07-17'),
        ('day_month_numeric', '17/07/2026'),
        ('month_day_numeric', '07/17/2026'),
    ]


def time_format_choices() -> list[tuple[str, str]]:
    return [('24h', '24-hour · 15:04'), ('12h', '12-hour · 03:04 PM')]


def normalize_timezone_name(value: str | None) -> str:
    timezone_name = (value or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return DEFAULT_TIMEZONE

    return timezone_name


def is_valid_timezone_name(value: str | None) -> bool:
    timezone_name = (value or '').strip()
    if not timezone_name:
        return False

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return False

    return True


def normalize_timezone_mode(value: str | None) -> str:
    candidate = (value or DEFAULT_TIMEZONE_MODE).strip().lower()
    return candidate if candidate in TIMEZONE_MODES else DEFAULT_TIMEZONE_MODE


def normalize_locale(value: str | None) -> str:
    candidate = (value or DEFAULT_LOCALE).strip()
    return candidate if candidate in SUPPORTED_LOCALES else DEFAULT_LOCALE


def normalize_date_format(value: str | None) -> str:
    candidate = (value or DEFAULT_DATE_FORMAT).strip()
    return candidate if candidate in SUPPORTED_DATE_FORMATS else DEFAULT_DATE_FORMAT


def normalize_time_format(value: str | None) -> str:
    candidate = (value or DEFAULT_TIME_FORMAT).strip()
    return candidate if candidate in SUPPORTED_TIME_FORMATS else DEFAULT_TIME_FORMAT


def localize_datetime(value: datetime | str | None, timezone_name: str | None) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate or candidate == '-':
            return None
        try:
            value = datetime.fromisoformat(candidate.replace('Z', '+00:00'))
        except ValueError:
            return None

    normalized_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized_value.astimezone(ZoneInfo(normalize_timezone_name(timezone_name)))


def _format_preferred_date(value: datetime, date_format: str, locale: str) -> str:
    normalized_date_format = normalize_date_format(date_format)
    normalized_locale = normalize_locale(locale)

    if normalized_date_format == 'year_month_day':
        return f'{value.year:04d}-{value.month:02d}-{value.day:02d}'
    if normalized_date_format == 'day_month_numeric':
        return f'{value.day:02d}/{value.month:02d}/{value.year:04d}'
    if normalized_date_format == 'month_day_numeric':
        return f'{value.month:02d}/{value.day:02d}/{value.year:04d}'

    month = _MONTH_ABBREVIATIONS[normalized_locale][value.month - 1]
    return f'{value.day:02d} {month} {value.year:04d}'


def _format_preferred_time(value: datetime, time_format: str, include_seconds: bool) -> str:
    normalized_time_format = normalize_time_format(time_format)

    if normalized_time_format == '12h':
        pattern = '%I:%M:%S %p' if include_seconds else '%I:%M %p'
        return value.strftime(pattern).lstrip('0')

    pattern = '%H:%M:%S' if include_seconds else '%H:%M'
    return value.strftime(pattern)


def format_user_datetime(
    value: datetime | str | None,
    timezone_name: str | None,
    *,
    date_format: str | None = None,
    time_format: str | None = None,
    locale: str | None = None,
    include_seconds: bool = False,
    include_timezone: bool = True,
    empty: str = '-',
) -> str:
    localized = localize_datetime(value, timezone_name)
    if localized is None:
        return empty

    date_text = _format_preferred_date(
        localized,
        normalize_date_format(date_format),
        normalize_locale(locale),
    )
    time_text = _format_preferred_time(localized, normalize_time_format(time_format), include_seconds)
    timezone_text = f' {localized.tzname() or normalize_timezone_name(timezone_name)}' if include_timezone else ''
    return f'{date_text} {time_text}{timezone_text}'


def format_user_date(
    value: datetime | str | None,
    timezone_name: str | None,
    *,
    date_format: str | None = None,
    locale: str | None = None,
    empty: str = '-',
) -> str:
    localized = localize_datetime(value, timezone_name)
    if localized is None:
        return empty

    return _format_preferred_date(
        localized,
        normalize_date_format(date_format),
        normalize_locale(locale),
    )


def format_user_time(
    value: datetime | str | None,
    timezone_name: str | None,
    *,
    time_format: str | None = None,
    include_seconds: bool = False,
    include_timezone: bool = True,
    empty: str = '-',
) -> str:
    localized = localize_datetime(value, timezone_name)
    if localized is None:
        return empty

    time_text = _format_preferred_time(localized, normalize_time_format(time_format), include_seconds)
    timezone_text = f' {localized.tzname() or normalize_timezone_name(timezone_name)}' if include_timezone else ''
    return f'{time_text}{timezone_text}'


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
