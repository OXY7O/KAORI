from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from kubernetes.utils.quantity import parse_quantity

_ZERO = Decimal('0')
_HUNDRED = Decimal('100')


@dataclass(frozen=True, slots=True)
class CapacityVector:
    cpu: Decimal | None
    memory_bytes: Decimal | None


@dataclass(frozen=True, slots=True)
class TenantAllocationBudget:
    allocatable: CapacityVector
    reserve: CapacityVector
    safety_headroom: CapacityVector
    unmanaged: CapacityVector
    available: CapacityVector


@dataclass(frozen=True, slots=True)
class AllocationPreflightDecision:
    allowed: bool
    decision: str
    state: str
    reason: str
    projected_committed: CapacityVector
    projected_headroom: CapacityVector
    shortfall: CapacityVector
    positive_change: bool


def quota_request_vector(quota: Mapping[str, object]) -> CapacityVector:
    return CapacityVector(
        cpu=_quantity_or_none(quota.get('requests.cpu')),
        memory_bytes=_quantity_or_none(quota.get('requests.memory')),
    )


def build_tenant_allocation_budget(
    *,
    allocatable: CapacityVector,
    reserve: CapacityVector,
    safety_headroom_percent: Decimal,
    unmanaged: CapacityVector,
) -> TenantAllocationBudget:
    if safety_headroom_percent < _ZERO or safety_headroom_percent >= _HUNDRED:
        raise ValueError('Tenant capacity safety headroom must be between 0 and 100 percent.')

    safety_headroom = CapacityVector(
        cpu=_percentage(allocatable.cpu, safety_headroom_percent),
        memory_bytes=_percentage(allocatable.memory_bytes, safety_headroom_percent),
    )
    available = CapacityVector(
        cpu=_budget_dimension(allocatable.cpu, reserve.cpu, safety_headroom.cpu, unmanaged.cpu),
        memory_bytes=_budget_dimension(
            allocatable.memory_bytes,
            reserve.memory_bytes,
            safety_headroom.memory_bytes,
            unmanaged.memory_bytes,
        ),
    )
    return TenantAllocationBudget(
        allocatable=allocatable,
        reserve=reserve,
        safety_headroom=safety_headroom,
        unmanaged=unmanaged,
        available=available,
    )


def classify_capacity_state(*, budget: CapacityVector, committed: CapacityVector) -> str:
    dimensions = (
        (budget.cpu, committed.cpu),
        (budget.memory_bytes, committed.memory_bytes),
    )
    if any(limit is None or used is None for limit, used in dimensions):
        return 'Unknown'

    typed = [(limit, used) for limit, used in dimensions if limit is not None and used is not None]
    if any(used > limit for limit, used in typed):
        return 'Overcommitted'

    if any(limit <= _ZERO for limit, _ in typed):
        return 'Exhausted'

    remaining_percent = [((limit - used) / limit) * _HUNDRED for limit, used in typed]
    if any(value <= _ZERO for value in remaining_percent):
        return 'Exhausted'
    if any(value <= Decimal('15') for value in remaining_percent):
        return 'Critical'
    if any(value <= Decimal('40') for value in remaining_percent):
        return 'Near Capacity'
    return 'Healthy'


def evaluate_allocation_preflight(
    *,
    budget: CapacityVector,
    committed_before: CapacityVector,
    current_allocation: CapacityVector,
    proposed_allocation: CapacityVector,
    capacity_evidence_available: bool,
) -> AllocationPreflightDecision:
    positive_change = _has_positive_change(current_allocation, proposed_allocation)

    if not capacity_evidence_available:
        return _decision(
            allowed=not positive_change,
            state='Unknown',
            reason=(
                'Required committed capacity evidence is unavailable or stale; positive allocation changes fail closed.'
                if positive_change
                else 'Capacity evidence is unavailable, but this change does not increase committed allocation.'
            ),
            budget=budget,
            committed=committed_before,
            current=current_allocation,
            proposed=proposed_allocation,
            positive_change=positive_change,
        )

    if positive_change and _has_unbounded_dimension(proposed_allocation):
        return _decision(
            allowed=False,
            state='Unknown',
            reason='Positive allocation changes require bounded CPU and memory request dimensions; an unbounded request was proposed.',
            budget=budget,
            committed=committed_before,
            current=current_allocation,
            proposed=proposed_allocation,
            positive_change=True,
        )

    current_state = classify_capacity_state(budget=budget, committed=committed_before)
    if positive_change and current_state == 'Overcommitted':
        return _decision(
            allowed=False,
            state='Overcommitted',
            reason='The cluster is already overcommitted; positive allocation changes are blocked until commitments are reduced or capacity increases.',
            budget=budget,
            committed=committed_before,
            current=current_allocation,
            proposed=proposed_allocation,
            positive_change=True,
        )

    result = _decision(
        allowed=True,
        state='Unknown',
        reason='Allocation is within the governed Tenant Allocation Budget.',
        budget=budget,
        committed=committed_before,
        current=current_allocation,
        proposed=proposed_allocation,
        positive_change=positive_change,
    )

    if _exceeds_budget(result.projected_committed, budget):
        return AllocationPreflightDecision(
            allowed=False,
            decision='block',
            state='Overcommitted',
            reason='Projected committed allocation exceeds the governed Tenant Allocation Budget.',
            projected_committed=result.projected_committed,
            projected_headroom=result.projected_headroom,
            shortfall=_shortfall(result.projected_committed, budget),
            positive_change=positive_change,
        )

    state = classify_capacity_state(budget=budget, committed=result.projected_committed)
    reason = (
        'Allocation reduction is permitted because it does not increase committed Tenant capacity.'
        if not positive_change
        else 'Projected allocation remains within the governed Tenant Allocation Budget.'
    )
    return AllocationPreflightDecision(
        allowed=True,
        decision='allow',
        state=state,
        reason=reason,
        projected_committed=result.projected_committed,
        projected_headroom=result.projected_headroom,
        shortfall=CapacityVector(cpu=_ZERO, memory_bytes=_ZERO),
        positive_change=positive_change,
    )


def _decision(
    *,
    allowed: bool,
    state: str,
    reason: str,
    budget: CapacityVector,
    committed: CapacityVector,
    current: CapacityVector,
    proposed: CapacityVector,
    positive_change: bool,
) -> AllocationPreflightDecision:
    projected = _projected_committed(committed, current, proposed)
    return AllocationPreflightDecision(
        allowed=allowed,
        decision='allow' if allowed else 'block',
        state=state,
        reason=reason,
        projected_committed=projected,
        projected_headroom=_headroom(budget, projected),
        shortfall=_shortfall(projected, budget),
        positive_change=positive_change,
    )


def _quantity_or_none(value: object | None) -> Decimal | None:
    if value is None or not str(value).strip():
        return None
    try:
        parsed = Decimal(parse_quantity(str(value).strip()))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Tenant allocation contains an invalid Kubernetes resource quantity.') from exc
    return parsed


def _percentage(value: Decimal | None, percent: Decimal) -> Decimal | None:
    if value is None:
        return None
    return value * percent / _HUNDRED


def _budget_dimension(
    allocatable: Decimal | None,
    reserve: Decimal | None,
    safety_headroom: Decimal | None,
    unmanaged: Decimal | None,
) -> Decimal | None:
    if any(value is None for value in (allocatable, reserve, safety_headroom, unmanaged)):
        return None
    assert allocatable is not None
    assert reserve is not None
    assert safety_headroom is not None
    assert unmanaged is not None
    return max(allocatable - reserve - safety_headroom - unmanaged, _ZERO)


def _dimension_positive_change(current: Decimal | None, proposed: Decimal | None) -> bool:
    if current is None:
        return False
    if proposed is None:
        return True
    return proposed > current


def _has_positive_change(current: CapacityVector, proposed: CapacityVector) -> bool:
    return _dimension_positive_change(current.cpu, proposed.cpu) or _dimension_positive_change(
        current.memory_bytes, proposed.memory_bytes
    )


def _has_unbounded_dimension(vector: CapacityVector) -> bool:
    return vector.cpu is None or vector.memory_bytes is None


def _project_dimension(
    committed: Decimal | None,
    current: Decimal | None,
    proposed: Decimal | None,
) -> Decimal | None:
    if committed is None or current is None or proposed is None:
        return None
    return max(committed - current + proposed, _ZERO)


def _projected_committed(
    committed: CapacityVector,
    current: CapacityVector,
    proposed: CapacityVector,
) -> CapacityVector:
    return CapacityVector(
        cpu=_project_dimension(committed.cpu, current.cpu, proposed.cpu),
        memory_bytes=_project_dimension(committed.memory_bytes, current.memory_bytes, proposed.memory_bytes),
    )


def _headroom(budget: CapacityVector, committed: CapacityVector) -> CapacityVector:
    return CapacityVector(
        cpu=_remaining(budget.cpu, committed.cpu),
        memory_bytes=_remaining(budget.memory_bytes, committed.memory_bytes),
    )


def _remaining(limit: Decimal | None, used: Decimal | None) -> Decimal | None:
    if limit is None or used is None:
        return None
    return limit - used


def _exceeds_budget(committed: CapacityVector, budget: CapacityVector) -> bool:
    dimensions = (
        (committed.cpu, budget.cpu),
        (committed.memory_bytes, budget.memory_bytes),
    )
    return any(used is not None and limit is not None and used > limit for used, limit in dimensions)


def _shortfall(committed: CapacityVector, budget: CapacityVector) -> CapacityVector:
    return CapacityVector(
        cpu=_shortfall_dimension(committed.cpu, budget.cpu),
        memory_bytes=_shortfall_dimension(committed.memory_bytes, budget.memory_bytes),
    )


def _shortfall_dimension(committed: Decimal | None, budget: Decimal | None) -> Decimal | None:
    if committed is None or budget is None:
        return None
    return max(committed - budget, _ZERO)
