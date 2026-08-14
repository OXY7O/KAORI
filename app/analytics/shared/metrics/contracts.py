from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypedDict


class MetricPoint(TypedDict):
    timestamp: float
    value: float


class MetricsSourceFailureKind(StrEnum):
    CONFIGURATION = 'configuration'
    TRANSPORT = 'transport'
    AUTHENTICATION = 'authentication'
    QUERY = 'query'


class MetricReadinessState(StrEnum):
    READY = 'ready'
    PARTIAL = 'partial'
    NO_DATA = 'no_data'
    UNSUPPORTED = 'unsupported'
    BLOCKED = 'blocked'
    NOT_VALIDATED = 'not_validated'


@dataclass(frozen=True, slots=True)
class MetricsSourceIdentity:
    provider: str
    provider_label: str
    instance_name: str
    detail: str


@dataclass(frozen=True, slots=True)
class MetricReadinessItem:
    key: str
    label: str
    domain: str
    tier: str
    state: MetricReadinessState
    detail: str


@dataclass(frozen=True, slots=True)
class MetricsReadinessSnapshot:
    profile: str
    profile_label: str
    state: MetricReadinessState
    checked_at: str | None
    items: tuple[MetricReadinessItem, ...]

    @property
    def total_count(self) -> int:
        return len(self.items)

    def count(self, state: MetricReadinessState) -> int:
        return sum(item.state == state for item in self.items)


class MetricsSourceError(RuntimeError):
    """Provider-neutral failure raised at the Analytics metrics-source boundary."""

    def __init__(
        self,
        message: str,
        *,
        kind: MetricsSourceFailureKind,
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.provider = provider

    @property
    def source_wide(self) -> bool:
        """Whether later queries to the same source should be skipped in this request."""
        return self.kind in {
            MetricsSourceFailureKind.TRANSPORT,
            MetricsSourceFailureKind.AUTHENTICATION,
        }


class MetricsSource(Protocol):
    @property
    def identity(self) -> MetricsSourceIdentity: ...

    @property
    def readiness(self) -> MetricsReadinessSnapshot: ...

    def scalar(self, metric_key: str) -> float | None: ...

    def vector(self, metric_key: str, label: str) -> dict[str, float]: ...

    def trend(self, metric_key: str, time_range: str) -> list[MetricPoint]: ...
