from __future__ import annotations

from collections.abc import Sequence

from app.common.analytics.metrics import MetricPoint


def linear_forecast(points: Sequence[MetricPoint], *, capacity_bytes: float | None) -> dict[str, float | None]:
    if len(points) < 2:
        return {'growth_per_day': None, 'projected_7d': None, 'projected_30d': None, 'days_to_capacity': None}
    first = points[0]
    last = points[-1]
    elapsed_days = max((last['timestamp'] - first['timestamp']) / 86400.0, 1 / 1440)
    growth_per_day = (last['value'] - first['value']) / elapsed_days
    current = last['value']
    days_to_capacity: float | None = None
    if capacity_bytes is not None and growth_per_day > 0 and capacity_bytes > current:
        days_to_capacity = (capacity_bytes - current) / growth_per_day
    return {
        'growth_per_day': growth_per_day,
        'projected_7d': max(0.0, current + (growth_per_day * 7)),
        'projected_30d': max(0.0, current + (growth_per_day * 30)),
        'days_to_capacity': days_to_capacity,
    }
