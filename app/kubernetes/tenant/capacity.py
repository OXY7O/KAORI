from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from kubernetes.utils.quantity import parse_quantity

_ZERO = Decimal('0')
_HUNDRED = Decimal('100')


@dataclass(frozen=True, slots=True)
class CapacityVector:
    cpu: Decimal | None
    memory_bytes: Decimal | None
    pods: Decimal | None = None
    storage_bytes: Decimal | None = None


@dataclass(frozen=True, slots=True)
class TenantAllocationBudget:
    allocatable: CapacityVector
    reserve: CapacityVector
    safety_headroom: CapacityVector
    unmanaged: CapacityVector
    available: CapacityVector
    logical_storage_budget: Decimal | None = None


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
        pods=_quantity_or_none(quota.get('pods')),
        storage_bytes=_quantity_or_none(quota.get('requests.storage')),
    )


def build_tenant_allocation_budget(
    *,
    allocatable: CapacityVector,
    reserve: CapacityVector,
    safety_headroom_percent: Decimal,
    unmanaged: CapacityVector,
    logical_storage_budget: Decimal | None = None,
) -> TenantAllocationBudget:
    if safety_headroom_percent < _ZERO or safety_headroom_percent >= _HUNDRED:
        raise ValueError('Tenant capacity safety headroom must be between 0 and 100 percent.')

    safety_headroom = CapacityVector(
        cpu=_percentage(allocatable.cpu, safety_headroom_percent),
        memory_bytes=_percentage(allocatable.memory_bytes, safety_headroom_percent),
        pods=_percentage(allocatable.pods, safety_headroom_percent),
        storage_bytes=None,
    )
    available = CapacityVector(
        cpu=_budget_dimension(allocatable.cpu, reserve.cpu, safety_headroom.cpu, unmanaged.cpu),
        memory_bytes=_budget_dimension(
            allocatable.memory_bytes,
            reserve.memory_bytes,
            safety_headroom.memory_bytes,
            unmanaged.memory_bytes,
        ),
        pods=_budget_dimension(
            allocatable.pods,
            reserve.pods,
            safety_headroom.pods,
            unmanaged.pods,
        ),
        storage_bytes=logical_storage_budget,
    )
    return TenantAllocationBudget(
        allocatable=allocatable,
        reserve=reserve,
        safety_headroom=safety_headroom,
        unmanaged=unmanaged,
        available=available,
        logical_storage_budget=logical_storage_budget,
    )


def classify_capacity_state(*, budget: CapacityVector, committed: CapacityVector) -> str:
    dimensions = _governed_dimensions(budget, committed)
    if not dimensions:
        return 'Unknown'
    if any(used is None for _, used in dimensions):
        return 'Unknown'

    typed = [(limit, used) for limit, used in dimensions if used is not None]
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


def classify_allocation_change(*, current: CapacityVector, proposed: CapacityVector) -> str:
    changes = tuple(
        _dimension_change(current_value, proposed_value)
        for current_value, proposed_value in _paired_dimensions(current, proposed)
    )
    if 'increase' in changes:
        return 'increase'
    if 'decrease' in changes:
        return 'decrease'
    return 'no_change'


def evaluate_allocation_preflight(
    *,
    budget: CapacityVector,
    committed_before: CapacityVector,
    current_allocation: CapacityVector,
    proposed_allocation: CapacityVector,
    capacity_evidence_available: bool,
) -> AllocationPreflightDecision:
    positive_change = _has_positive_change(current_allocation, proposed_allocation, budget=budget)

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

    if positive_change and _has_unbounded_dimension(proposed_allocation, budget=budget):
        return _decision(
            allowed=False,
            state='Unknown',
            reason=(
                'Positive allocation changes require bounded values for every governed capacity dimension; '
                'an unbounded request was proposed.'
            ),
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
            reason=(
                'The cluster is already overcommitted; positive allocation changes are blocked until commitments '
                'are reduced or capacity increases.'
            ),
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
        shortfall=_zero_vector_for_budget(budget),
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


def _dimension_change(current: Decimal | None, proposed: Decimal | None) -> str:
    if current is None and proposed is None:
        return 'no_change'
    if current is None:
        return 'decrease'
    if proposed is None:
        return 'increase'
    if proposed > current:
        return 'increase'
    if proposed < current:
        return 'decrease'
    return 'no_change'


def _dimension_positive_change(current: Decimal | None, proposed: Decimal | None) -> bool:
    if current is None:
        return False
    if proposed is None:
        return True
    return proposed > current


def _has_positive_change(
    current: CapacityVector,
    proposed: CapacityVector,
    *,
    budget: CapacityVector,
) -> bool:
    return any(
        limit is not None and _dimension_positive_change(current_value, proposed_value)
        for (current_value, proposed_value), limit in zip(
            _paired_dimensions(current, proposed),
            _vector_dimensions(budget),
            strict=True,
        )
    )


def _has_unbounded_dimension(vector: CapacityVector, *, budget: CapacityVector) -> bool:
    return any(
        limit is not None and value is None
        for value, limit in zip(_vector_dimensions(vector), _vector_dimensions(budget), strict=True)
    )


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
    values = [
        _project_dimension(committed_value, current_value, proposed_value)
        for committed_value, current_value, proposed_value in zip(
            _vector_dimensions(committed),
            _vector_dimensions(current),
            _vector_dimensions(proposed),
            strict=True,
        )
    ]
    return CapacityVector(
        cpu=values[0],
        memory_bytes=values[1],
        pods=values[2],
        storage_bytes=values[3],
    )


def _headroom(budget: CapacityVector, committed: CapacityVector) -> CapacityVector:
    values = [
        _remaining(limit, used)
        for limit, used in zip(_vector_dimensions(budget), _vector_dimensions(committed), strict=True)
    ]
    return CapacityVector(
        cpu=values[0],
        memory_bytes=values[1],
        pods=values[2],
        storage_bytes=values[3],
    )


def _remaining(limit: Decimal | None, used: Decimal | None) -> Decimal | None:
    if limit is None or used is None:
        return None
    return limit - used


def _exceeds_budget(committed: CapacityVector, budget: CapacityVector) -> bool:
    return any(
        used is not None and limit is not None and used > limit
        for used, limit in zip(_vector_dimensions(committed), _vector_dimensions(budget), strict=True)
    )


def _shortfall(committed: CapacityVector, budget: CapacityVector) -> CapacityVector:
    values = [
        _shortfall_dimension(used, limit)
        for used, limit in zip(_vector_dimensions(committed), _vector_dimensions(budget), strict=True)
    ]
    return CapacityVector(
        cpu=values[0],
        memory_bytes=values[1],
        pods=values[2],
        storage_bytes=values[3],
    )


def _shortfall_dimension(committed: Decimal | None, budget: Decimal | None) -> Decimal | None:
    if committed is None or budget is None:
        return None
    return max(committed - budget, _ZERO)


def _governed_dimensions(
    budget: CapacityVector,
    committed: CapacityVector,
) -> list[tuple[Decimal, Decimal | None]]:
    return [
        (limit, used)
        for limit, used in zip(_vector_dimensions(budget), _vector_dimensions(committed), strict=True)
        if limit is not None
    ]


def _paired_dimensions(
    left: CapacityVector,
    right: CapacityVector,
) -> tuple[tuple[Decimal | None, Decimal | None], ...]:
    return tuple(zip(_vector_dimensions(left), _vector_dimensions(right), strict=True))


def _vector_dimensions(vector: CapacityVector) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    return vector.cpu, vector.memory_bytes, vector.pods, vector.storage_bytes


def _zero_vector_for_budget(budget: CapacityVector) -> CapacityVector:
    values = [_ZERO if value is not None else None for value in _vector_dimensions(budget)]
    return CapacityVector(
        cpu=values[0],
        memory_bytes=values[1],
        pods=values[2],
        storage_bytes=values[3],
    )
