from __future__ import annotations

from collections.abc import Iterable

from app.integrations.contracts import HealthFactor, HealthState


def calculate_health(factors: Iterable[HealthFactor]) -> HealthState:
    rows = tuple(factors)
    total_weight = sum(max(row.weight, 0) for row in rows) or 1
    score = round(sum(max(row.weight, 0) * max(0, min(row.score, 100)) for row in rows) / total_weight)
    if any(row.status == 'failed' and row.weight >= 25 for row in rows) or score < 50:
        status = 'unhealthy'
    elif score < 85 or any(row.status in {'warning', 'unknown'} for row in rows):
        status = 'degraded'
    else:
        status = 'healthy'
    summary = {
        'healthy': 'Runtime checks are healthy.',
        'degraded': 'Runtime is usable but one or more factors require attention.',
        'unhealthy': 'Runtime is unavailable or unsafe for normal consumption.',
    }[status]
    return HealthState(status=status, score=score, factors=rows, summary=summary)
