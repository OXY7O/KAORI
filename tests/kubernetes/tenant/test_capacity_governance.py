from decimal import Decimal

from app.kubernetes.tenant.capacity import (
    CapacityPolicyValues,
    CapacityVector,
    calculate_budget,
    classify_capacity_state,
    evaluate_preflight,
    quota_requests,
)


def _vector(cpu: str, memory_gib: str) -> CapacityVector:
    return CapacityVector(Decimal(cpu), Decimal(memory_gib) * Decimal(1024**3))


def _policy(
    *,
    reserved_cpu: str = '0',
    reserved_memory_gib: str = '0',
    unmanaged_cpu: str = '0',
    unmanaged_memory_gib: str = '0',
    headroom: str = '10',
) -> CapacityPolicyValues:
    return CapacityPolicyValues(
        system_reserved=_vector(reserved_cpu, reserved_memory_gib),
        unmanaged_commitment=_vector(unmanaged_cpu, unmanaged_memory_gib),
        safety_headroom_percent=Decimal(headroom),
    )


def test_capacity_budget_subtracts_reserve_headroom_and_unmanaged_commitment() -> None:
    budget = calculate_budget(
        _vector('20', '64'),
        _policy(
            reserved_cpu='2',
            reserved_memory_gib='4',
            unmanaged_cpu='1',
            unmanaged_memory_gib='2',
            headroom='10',
        ),
    )

    assert budget.cpu_cores == Decimal('15')
    assert budget.memory_bytes == Decimal('51.6') * Decimal(1024**3)


def test_capacity_preflight_allows_bounded_create_with_projected_headroom() -> None:
    result = evaluate_preflight(
        allocatable=_vector('20', '64'),
        policy=_policy(),
        committed=_vector('5', '10'),
        proposed=_vector('2', '4'),
    )

    assert result.allowed is True
    assert result.state == 'healthy'
    assert result.projected == _vector('7', '14')


def test_capacity_preflight_blocks_positive_allocation_beyond_budget() -> None:
    result = evaluate_preflight(
        allocatable=_vector('10', '20'),
        policy=_policy(headroom='10'),
        committed=_vector('8', '15'),
        proposed=_vector('2', '4'),
    )

    assert result.allowed is False
    assert result.state == 'overcommitted'
    assert result.shortfall.cpu_cores == Decimal('1')
    assert result.shortfall.memory_bytes == Decimal('1') * Decimal(1024**3)


def test_capacity_preflight_fails_safe_for_unbounded_request_dimension() -> None:
    proposed = quota_requests({'requests.cpu': '2'})

    result = evaluate_preflight(
        allocatable=_vector('10', '20'),
        policy=_policy(),
        committed=_vector('2', '4'),
        proposed=proposed,
    )

    assert result.allowed is False
    assert result.state == 'unknown'


def test_capacity_reduction_remains_allowed_while_cluster_is_overcommitted() -> None:
    result = evaluate_preflight(
        allocatable=_vector('10', '20'),
        policy=_policy(headroom='10'),
        committed=_vector('12', '24'),
        current=_vector('4', '8'),
        proposed=_vector('2', '4'),
    )

    assert result.allowed is True
    assert result.state == 'overcommitted'
    assert result.projected == _vector('10', '20')


def test_capacity_state_thresholds_use_worst_cpu_or_memory_headroom() -> None:
    budget = _vector('10', '20')

    assert classify_capacity_state(budget, _vector('4', '8')) == 'healthy'
    assert classify_capacity_state(budget, _vector('6', '12')) == 'near_capacity'
    assert classify_capacity_state(budget, _vector('8.5', '17')) == 'critical'
    assert classify_capacity_state(budget, _vector('10', '18')) == 'exhausted'
    assert classify_capacity_state(budget, _vector('10.1', '18')) == 'overcommitted'
