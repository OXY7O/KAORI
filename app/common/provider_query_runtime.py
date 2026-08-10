from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass(slots=True)
class ProviderQueryRuntime:
    """Per-dataset provider query telemetry kept inside one worker context.

    The state is process-local and request-independent. It is intentionally
    lightweight: PromQL text is never retained, only bounded fingerprints and
    aggregate timing/error counters that are safe to persist with a snapshot.
    """

    dataset_key: str
    cluster_id: str
    job_execution_id: int | None = None
    query_count: int = 0
    retry_count: int = 0
    failure_count: int = 0
    query_duration_ms: int = 0
    source_lock_wait_ms: int = 0
    last_error: str | None = None
    query_fingerprints: list[str] = field(default_factory=list)
    _started_at: float = field(default_factory=perf_counter)

    def record_query(
        self,
        *,
        fingerprint: str,
        duration_ms: int,
        success: bool,
        error: Exception | str | None = None,
    ) -> None:
        self.query_count += 1
        self.query_duration_ms += max(int(duration_ms), 0)
        if fingerprint and fingerprint not in self.query_fingerprints:
            self.query_fingerprints.append(fingerprint)
            del self.query_fingerprints[12:]
        if not success:
            self.failure_count += 1
            if error is not None:
                self.last_error = str(error)[:1000]

    def record_retry(self) -> None:
        self.retry_count += 1

    def summary(self) -> dict[str, Any]:
        return {
            'dataset_key': self.dataset_key,
            'cluster_id': self.cluster_id,
            'job_execution_id': self.job_execution_id,
            'query_count': self.query_count,
            'retry_count': self.retry_count,
            'failure_count': self.failure_count,
            'query_duration_ms': self.query_duration_ms,
            'source_lock_wait_ms': self.source_lock_wait_ms,
            'duration_ms': max(int((perf_counter() - self._started_at) * 1000), 0),
            'query_fingerprints': list(self.query_fingerprints),
            'last_error': self.last_error,
        }


_runtime: ContextVar[ProviderQueryRuntime | None] = ContextVar(
    'kaori_provider_query_runtime',
    default=None,
)


@contextmanager
def provider_query_runtime(
    *,
    dataset_key: str,
    cluster_id: str,
    job_execution_id: int | None = None,
) -> Iterator[ProviderQueryRuntime]:
    state = ProviderQueryRuntime(
        dataset_key=str(dataset_key),
        cluster_id=str(cluster_id),
        job_execution_id=job_execution_id,
    )
    token = _runtime.set(state)
    try:
        yield state
    finally:
        _runtime.reset(token)


def current_provider_query_runtime() -> ProviderQueryRuntime | None:
    return _runtime.get()


def record_provider_query(
    *,
    fingerprint: str,
    duration_ms: int,
    success: bool,
    error: Exception | str | None = None,
) -> None:
    state = current_provider_query_runtime()
    if state is not None:
        state.record_query(
            fingerprint=fingerprint,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )


def record_provider_retry() -> None:
    state = current_provider_query_runtime()
    if state is not None:
        state.record_retry()
