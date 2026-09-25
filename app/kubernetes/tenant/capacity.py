from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from kubernetes.utils.quantity import parse_quantity

_GIB = Decimal(1024**3)
_HUNDRED = Decimal('100')


@dataclass(frozen=True, slots=True)
class CapacityVector:
    cpu_cores: Decimal | None
    memory_bytes: Decimal | None

    @property
    def complete(self) -> bool:
        return self.cpu_cores is not None and self.memory_bytes is not None


@dataclass(frozen=True, slots=True)
class CapacityPolicyValues:
    system_reserved: CapacityVector
    unmanaged_commitment: CapacityVector
    safety_headroom_percent: Decimal


@dataclass(frozen=True, slots=True)
class CapacityPreflightResult:
    allowed: bool
    state: str
    budget: CapacityVector
    committed: CapacityVector
    current: CapacityVector
    proposed: CapacityVector
    projected: CapacityVector
    remaining: CapacityVector
    shortfall: CapacityVector
    reason: str


def parse_cpu_quantity(value: object | None) -> Decimal | None:
    return _parse_quantity(value)


def parse_memory_quantity(value: object | None) -> Decimal | None:
    return _parse_quantity(value)


def _parse_quantity(value: object | None) -> Decimal | None:
    if value is None:
        return None
    rendered = str(value).strip()
    if not rendered:
        return None
    try:
        parsed = Decimal(parse_quantity(rendered))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def quota_requests(quota: dict[str, Any] | None) -> CapacityVector:
    values = quota or {}
    return CapacityVector(
        cpu_cores=parse_cpu_quantity(values.get('requests.cpu')),
        memory_bytes=parse_memory_quantity(values.get('requests.memory')),
    )


def decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    return format(normalized, 'f')


def bytes_to_gib_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value / _GIB


def calculate_budget(
    allocatable: CapacityVector,
    policy: CapacityPolicyValues,
) -> CapacityVector:
    if not allocatable.complete or not policy.system_reserved.complete or not policy.unmanaged_commitment.complete:
        return CapacityVector(None, None)

    assert allocatable.cpu_cores is not None
    assert allocatable.memory_bytes is not None
    assert policy.system_reserved.cpu_cores is not None
    assert policy.system_reserved.memory_bytes is not None
    assert policy.unmanaged_commitment.cpu_cores is not None
    assert policy.unmanaged_commitment.memory_bytes is not None

    headroom_ratio = policy.safety_headroom_percent / _HUNDRED
    cpu = (
        allocatable.cpu_cores
        - policy.system_reserved.cpu_cores
        - policy.unmanaged_commitment.cpu_cores
        - (allocatable.cpu_cores * headroom_ratio)
    )
    memory = (
        allocatable.memory_bytes
        - policy.system_reserved.memory_bytes
        - policy.unmanaged_commitment.memory_bytes
        - (allocatable.memory_bytes * headroom_ratio)
    )
    return CapacityVector(max(cpu, Decimal(0)), max(memory, Decimal(0)))


def evaluate_preflight(
    *,
    allocatable: CapacityVector,
    policy: CapacityPolicyValues,
    committed: CapacityVector,
    proposed: CapacityVector,
    current: CapacityVector | None = None,
) -> CapacityPreflightResult:
    current = current or CapacityVector(Decimal(0), Decimal(0))
    budget = calculate_budget(allocatable, policy)

    vectors = (budget, committed, current, proposed)
    if not all(vector.complete for vector in vectors):
        unknown = CapacityVector(None, None)
        return CapacityPreflightResult(
            allowed=False,
            state='unknown',
            budget=budget,
            committed=committed,
            current=current,
            proposed=proposed,
            projected=unknown,
            remaining=unknown,
            shortfall=unknown,
            reason='Required CPU or memory allocation evidence is missing or unbounded.',
        )

    assert budget.cpu_cores is not None and budget.memory_bytes is not None
    assert committed.cpu_cores is not None and committed.memory_bytes is not None
    assert current.cpu_cores is not None and current.memory_bytes is not None
    assert proposed.cpu_cores is not None and proposed.memory_bytes is not None

    projected = CapacityVector(
        max(committed.cpu_cores - current.cpu_cores + proposed.cpu_cores, Decimal(0)),
        max(committed.memory_bytes - current.memory_bytes + proposed.memory_bytes, Decimal(0)),
    )
    assert projected.cpu_cores is not None and projected.memory_bytes is not None

    remaining = CapacityVector(
        budget.cpu_cores - projected.cpu_cores,
        budget.memory_bytes - projected.memory_bytes,
    )
    assert remaining.cpu_cores is not None and remaining.memory_bytes is not None
    shortfall = CapacityVector(
        max(-remaining.cpu_cores, Decimal(0)),
        max(-remaining.memory_bytes, Decimal(0)),
    )

    positive_change = proposed.cpu_cores > current.cpu_cores or proposed.memory_bytes > current.memory_bytes
    if not positive_change:
        state = classify_capacity_state(budget, projected)
        return CapacityPreflightResult(
            allowed=True,
            state=state,
            budget=budget,
            committed=committed,
            current=current,
            proposed=proposed,
            projected=projected,
            remaining=remaining,
            shortfall=shortfall,
            reason='Allocation does not increase CPU or memory commitment.',
        )

    if projected.cpu_cores > budget.cpu_cores or projected.memory_bytes > budget.memory_bytes:
        return CapacityPreflightResult(
            allowed=False,
            state='overcommitted',
            budget=budget,
            committed=committed,
            current=current,
            proposed=proposed,
            projected=projected,
            remaining=remaining,
            shortfall=shortfall,
            reason='Projected Tenant commitment exceeds the governed CPU or memory allocation budget.',
        )

    state = classify_capacity_state(budget, projected)
    return CapacityPreflightResult(
        allowed=True,
        state=state,
        budget=budget,
        committed=committed,
        current=current,
        proposed=proposed,
        projected=projected,
        remaining=remaining,
        shortfall=shortfall,
        reason='Projected Tenant commitment remains within the governed allocation budget.',
    )


def classify_capacity_state(budget: CapacityVector, committed: CapacityVector) -> str:
    if not budget.complete or not committed.complete:
        return 'unknown'

    assert budget.cpu_cores is not None and budget.memory_bytes is not None
    assert committed.cpu_cores is not None and committed.memory_bytes is not None

    if committed.cpu_cores > budget.cpu_cores or committed.memory_bytes > budget.memory_bytes:
        return 'overcommitted'
    if committed.cpu_cores == budget.cpu_cores or committed.memory_bytes == budget.memory_bytes:
        return 'exhausted'

    ratios: list[Decimal] = []
    for total, used in (
        (budget.cpu_cores, committed.cpu_cores),
        (budget.memory_bytes, committed.memory_bytes),
    ):
        if total <= 0:
            return 'exhausted'
        ratios.append((total - used) / total)

    headroom = min(ratios)
    if headroom <= Decimal('0.15'):
        return 'critical'
    if headroom <= Decimal('0.40'):
        return 'near_capacity'
    return 'healthy'
