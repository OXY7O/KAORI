from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ALLOWED_TIME_RANGE_VALUES = [
    '1h',
    '6h',
    '12h',
    '24h',
    '7d',
    '30d',
    '60d',
]

TIME_RANGE_LABELS = {
    '1h': 'Last 1h',
    '6h': 'Last 6h',
    '12h': 'Last 12h',
    '24h': 'Last 24 Hours',
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '60d': 'Last 60 Days',
}

ALLOWED_PER_PAGE_VALUES = [
    5,
    10,
    25,
    50,
]


def get_allowed_time_ranges() -> list[dict[str, str]]:
    return [
        {
            'value': value,
            'label': TIME_RANGE_LABELS.get(
                value,
                value,
            ),
        }
        for value in ALLOWED_TIME_RANGE_VALUES
    ]


def get_selected_time_range(
    query_args: Mapping[str, Any],
    name: str = 'time_range',
    default: str = '24h',
) -> str:
    value = get_query_value(
        query_args=query_args,
        name=name,
        default=default,
    )

    if value not in ALLOWED_TIME_RANGE_VALUES:
        return default

    return value


def get_query_value(
    query_args: Mapping[str, Any],
    name: str,
    default: str = '',
) -> str:
    value = query_args.get(
        name,
        default,
    )

    if value is None:
        return default

    return str(
        value,
    )


def get_positive_int_arg(
    query_args: Mapping[str, Any],
    name: str,
    default: int,
) -> int:
    raw_value = query_args.get(
        name,
        default,
    )

    try:
        value = int(
            raw_value,
        )
    except (
        TypeError,
        ValueError,
    ):
        return default

    if value < 1:
        return default

    return value


def get_per_page_arg(
    query_args: Mapping[str, Any],
    name: str,
    default: int = 5,
) -> int:
    value = get_positive_int_arg(
        query_args=query_args,
        name=name,
        default=default,
    )

    if value not in ALLOWED_PER_PAGE_VALUES:
        return default

    return value
