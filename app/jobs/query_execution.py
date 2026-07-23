from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from time import time

from app.jobs.execution import JobExecutionContext
from app.jobs.query_planning import QueryBudgetPolicy, QueryChunk, build_query_chunks
from app.jobs.resource_limits import acquire_resource_slot, release_resource_slot


class QueryResourceBusy(RuntimeError):
    """Raised when a provider source has exhausted its external-query budget."""


@dataclass(frozen=True)
class LargeQueryExecutionPlan:
    """Bounded execution plan for long-range Prometheus or Thanos queries."""

    chunks: tuple[QueryChunk, ...]
    resource_group: str
    maximum_concurrent_queries: int
    slot_ttl_seconds: int

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)


def prepare_large_query_execution(
    *,
    start: datetime,
    end: datetime,
    requested_step_seconds: int,
    resource_group: str,
    policy: QueryBudgetPolicy | None = None,
    slot_ttl_seconds: int = 900,
) -> LargeQueryExecutionPlan:
    selected = policy or QueryBudgetPolicy()
    chunks = build_query_chunks(
        start=start,
        end=end,
        requested_step_seconds=requested_step_seconds,
        policy=selected,
    )
    return LargeQueryExecutionPlan(
        chunks=tuple(chunks),
        resource_group=resource_group,
        maximum_concurrent_queries=selected.maximum_concurrent_queries_per_source,
        slot_ttl_seconds=max(int(slot_ttl_seconds), 60),
    )


@contextmanager
def external_query_slot(
    *,
    plan: LargeQueryExecutionPlan,
    task_id: str,
) -> Iterator[None]:
    """Reserve one external-provider query slot and always release it.

    Heavy analytics tasks should reserve the slot only around remote query work,
    not around local model execution. The slot TTL limits damage if a worker is
    killed before the finally block runs.
    """
    acquired = acquire_resource_slot(
        resource_group=plan.resource_group,
        task_id=task_id,
        limit=plan.maximum_concurrent_queries,
        ttl_seconds=plan.slot_ttl_seconds,
        now_epoch=int(time()),
    )
    if not acquired:
        raise QueryResourceBusy(f'External query budget is busy for resource group {plan.resource_group!r}.')
    try:
        yield
    finally:
        release_resource_slot(resource_group=plan.resource_group, task_id=task_id)


def checkpoint_query_chunk(
    *,
    job: JobExecutionContext,
    plan: LargeQueryExecutionPlan,
    chunk: QueryChunk,
    completed: bool = False,
) -> None:
    """Refresh slot TTL, heartbeat, progress, and cancellation per chunk."""
    renewed = acquire_resource_slot(
        resource_group=plan.resource_group,
        task_id=job.task_id,
        limit=plan.maximum_concurrent_queries,
        ttl_seconds=plan.slot_ttl_seconds,
        now_epoch=int(time()),
    )
    if not renewed:
        raise QueryResourceBusy(f'External query budget was lost for resource group {plan.resource_group!r}.')
    current = chunk.sequence if completed else chunk.sequence - 1
    phase = 'Completed' if completed else 'Querying'
    job.checkpoint(
        current=current,
        total=chunk.total,
        message=(
            f'{phase} chunk {chunk.sequence} of {chunk.total}: '
            f'{chunk.start.isoformat()} to {chunk.end.isoformat()} '
            f'at {chunk.step_seconds}s resolution'
        ),
    )
