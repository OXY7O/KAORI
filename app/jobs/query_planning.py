from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class QueryBudgetPolicy:
    maximum_range_days: int = 366
    chunk_days: int = 30
    minimum_step_seconds: int = 3600
    maximum_samples_per_series: int = 10000
    maximum_concurrent_queries_per_source: int = 2


@dataclass(frozen=True)
class QueryChunk:
    start: datetime
    end: datetime
    step_seconds: int
    sequence: int
    total: int


def policy_from_config(config: dict[str, object]) -> QueryBudgetPolicy:
    return QueryBudgetPolicy(
        maximum_range_days=max(int(config.get('ANALYTICS_QUERY_MAXIMUM_RANGE_DAYS', 366)), 1),
        chunk_days=max(int(config.get('ANALYTICS_QUERY_CHUNK_DAYS', 30)), 1),
        minimum_step_seconds=max(int(config.get('ANALYTICS_QUERY_MINIMUM_STEP_SECONDS', 3600)), 1),
        maximum_samples_per_series=max(int(config.get('ANALYTICS_QUERY_MAXIMUM_SAMPLES_PER_SERIES', 10000)), 1),
        maximum_concurrent_queries_per_source=max(int(config.get('ANALYTICS_QUERY_MAX_CONCURRENT_PER_SOURCE', 2)), 1),
    )


def recommended_step_seconds(*, start: datetime, end: datetime, requested_step_seconds: int, policy: QueryBudgetPolicy) -> int:
    duration_seconds = max(int((end - start).total_seconds()), 1)
    sample_floor = math.ceil(duration_seconds / max(policy.maximum_samples_per_series, 1))
    return max(requested_step_seconds, policy.minimum_step_seconds, sample_floor)


def build_query_chunks(
    *,
    start: datetime,
    end: datetime,
    requested_step_seconds: int,
    policy: QueryBudgetPolicy | None = None,
) -> list[QueryChunk]:
    selected = policy or QueryBudgetPolicy()
    if end <= start:
        raise ValueError('Query end time must be after start time.')
    if end - start > timedelta(days=selected.maximum_range_days):
        raise ValueError('Requested query range exceeds the configured analytics limit.')
    step = recommended_step_seconds(
        start=start,
        end=end,
        requested_step_seconds=requested_step_seconds,
        policy=selected,
    )
    chunk_size = timedelta(days=max(selected.chunk_days, 1))
    boundaries: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + chunk_size, end)
        boundaries.append((cursor, chunk_end))
        cursor = chunk_end
    total = len(boundaries)
    return [
        QueryChunk(chunk_start, chunk_end, step, index + 1, total)
        for index, (chunk_start, chunk_end) in enumerate(boundaries)
    ]
