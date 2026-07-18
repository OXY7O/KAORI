from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    key: str
    label: str
    category: str
    status: str
    detail: str
    duration_ms: int | None = None
    severity: str = 'info'
    recommendation: str | None = None


@dataclass(frozen=True, slots=True)
class HealthFactor:
    key: str
    label: str
    status: str
    weight: int
    score: int
    detail: str = ''


@dataclass(frozen=True, slots=True)
class HealthState:
    status: str
    score: int
    factors: tuple[HealthFactor, ...] = ()
    summary: str = ''


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    profile: str | None
    compatibility_profile: str | None
    capabilities: tuple[str, ...]
    observed_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeState:
    provider: str
    instance_id: str
    instance_name: str
    observed_at: datetime
    readiness: str
    health: HealthState
    diagnostics: tuple[DiagnosticResult, ...]
    snapshot: CapabilitySnapshot
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    latency_ms: int | None = None
    message: str = ''


class RuntimeAdapter(Protocol):
    provider: str

    def refresh(self, instance: Any) -> Any: ...

    def get_state(self, instance: Any, *, validation_result: Any | None = None) -> RuntimeState: ...
