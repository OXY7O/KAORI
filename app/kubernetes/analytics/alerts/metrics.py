from __future__ import annotations

from typing import Any


def get_metric_value(
    item: dict[str, Any],
) -> float:
    value = item.get(
        'value',
        [],
    )

    if not isinstance(
        value,
        list,
    ):
        return 0.0

    if (
        len(
            value,
        )
        < 2
    ):
        return 0.0

    try:
        return float(
            value[1],
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def get_metric_labels(
    item: dict[str, Any],
) -> dict[str, Any]:
    metric = item.get(
        'metric',
        {},
    )

    if isinstance(
        metric,
        dict,
    ):
        return metric

    return {}
