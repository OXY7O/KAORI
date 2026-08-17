from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from app.common.automation_execution import build_idempotency_key as _build_idempotency_key


def build_idempotency_key(*, decision_id: str, action_key: str, evidence_hash: str) -> str:
    """Preserve the resolver contract API while using the shared execution identity."""
    return _build_idempotency_key(
        decision_id=decision_id,
        action_key=action_key,
        evidence_hash=evidence_hash,
    )


class ResolverError(RuntimeError):
    """Raised when a remediation request violates the resolver boundary."""


class ResolverResultStatus(StrEnum):
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    NOOP = 'noop'


class VerificationStatus(StrEnum):
    VERIFIED = 'verified'
    PENDING = 'pending'
    FAILED = 'failed'


@dataclass(frozen=True, slots=True)
class ResolverContext:
    decision_id: str
    journal_id: str
    action_key: str
    evidence_hash: str
    idempotency_key: str
    cluster_id: str | None
    namespace: str | None
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class DryRunResult:
    allowed: bool
    summary: str
    planned_changes: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    rollback_plan: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: VerificationStatus
    summary: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResolverResult:
    status: ResolverResultStatus
    summary: str
    result: Mapping[str, Any] = field(default_factory=dict)
    rollback_reference: str | None = None
    retryable: bool = False


class ResolverAdapter(Protocol):
    action_key: str

    def dry_run(self, context: ResolverContext) -> DryRunResult: ...

    def execute(self, context: ResolverContext, dry_run: DryRunResult) -> ResolverResult: ...

    def verify(self, context: ResolverContext, result: ResolverResult) -> VerificationResult: ...
