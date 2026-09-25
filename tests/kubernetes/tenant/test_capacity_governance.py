from decimal import Decimal

from app.kubernetes.analytics.materialization.service import SnapshotResult
from app.kubernetes.tenant.capacity import (
    CapacityVector,
    build_tenant_allocation_budget,
    classify_allocation_change,
    classify_capacity_state,
    evaluate_allocation_preflight,
    quota_request_vector,
)
from app.kubernetes.tenant.capacity_governance import _capacity_vector


def test_quota_request_vector_preserves_unbounded_dimensions() -> None:
    vector = quota_request_vector({'requests.cpu': '1500m'})

    assert vector.cpu == Decimal('1.500')
    assert vector.memory_bytes is None


def test_budget_subtracts_reserve_headroom_and_unmanaged_commitments() -> None:
    gib = Decimal(1024**3)

    budget = build_tenant_allocation_budget(
        allocatable=CapacityVector(cpu=Decimal('100'), memory_bytes=Decimal('200') * gib),
        reserve=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('20') * gib),
        safety_headroom_percent=Decimal('10'),
        unmanaged=CapacityVector(cpu=Decimal('5'), memory_bytes=Decimal('10') * gib),
    )

    assert budget.allocatable.cpu == Decimal('100')
    assert budget.safety_headroom.cpu == Decimal('10')
    assert budget.available.cpu == Decimal('75')
    assert budget.available.memory_bytes == Decimal('150') * gib


def test_capacity_state_uses_governed_headroom_thresholds() -> None:
    assert (
        classify_capacity_state(
            budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('10')),
            committed=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('4')),
        )
        == 'Healthy'
    )
    assert (
        classify_capacity_state(
            budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('10')),
            committed=CapacityVector(cpu=Decimal('7'), memory_bytes=Decimal('7')),
        )
        == 'Near Capacity'
    )
    assert (
        classify_capacity_state(
            budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('10')),
            committed=CapacityVector(cpu=Decimal('9'), memory_bytes=Decimal('9')),
        )
        == 'Critical'
    )
    assert (
        classify_capacity_state(
            budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('10')),
            committed=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('10')),
        )
        == 'Exhausted'
    )
    assert (
        classify_capacity_state(
            budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('10')),
            committed=CapacityVector(cpu=Decimal('11'), memory_bytes=Decimal('9')),
        )
        == 'Overcommitted'
    )


def test_create_preflight_allows_allocation_inside_budget() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('100')),
        committed_before=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40')),
        current_allocation=CapacityVector(cpu=Decimal('0'), memory_bytes=Decimal('0')),
        proposed_allocation=CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('20')),
        capacity_evidence_available=True,
    )

    assert decision.allowed is True
    assert decision.decision == 'allow'
    assert decision.projected_committed.cpu == Decimal('6')
    assert decision.projected_headroom.cpu == Decimal('4')
    assert decision.state == 'Near Capacity'


def test_preflight_blocks_projected_shortfall() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('100')),
        committed_before=CapacityVector(cpu=Decimal('9'), memory_bytes=Decimal('90')),
        current_allocation=CapacityVector(cpu=Decimal('0'), memory_bytes=Decimal('0')),
        proposed_allocation=CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('20')),
        capacity_evidence_available=True,
    )

    assert decision.allowed is False
    assert decision.decision == 'block'
    assert decision.state == 'Overcommitted'
    assert decision.shortfall.cpu == Decimal('1')
    assert decision.shortfall.memory_bytes == Decimal('10')


def test_positive_change_fails_closed_without_current_capacity_evidence() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(cpu=None, memory_bytes=None),
        committed_before=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40')),
        current_allocation=CapacityVector(cpu=Decimal('0'), memory_bytes=Decimal('0')),
        proposed_allocation=CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('20')),
        capacity_evidence_available=False,
    )

    assert decision.allowed is False
    assert decision.state == 'Unknown'
    assert 'capacity evidence' in decision.reason.lower()


def test_unbounded_positive_request_dimension_is_blocked() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('100')),
        committed_before=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40')),
        current_allocation=CapacityVector(cpu=Decimal('0'), memory_bytes=Decimal('0')),
        proposed_allocation=CapacityVector(cpu=None, memory_bytes=Decimal('20')),
        capacity_evidence_available=True,
    )

    assert decision.allowed is False
    assert decision.state == 'Unknown'
    assert 'unbounded' in decision.reason.lower()


def test_reduction_is_allowed_while_cluster_is_overcommitted() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('100')),
        committed_before=CapacityVector(cpu=Decimal('12'), memory_bytes=Decimal('110')),
        current_allocation=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40')),
        proposed_allocation=CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('20')),
        capacity_evidence_available=True,
    )

    assert decision.allowed is True
    assert decision.projected_committed.cpu == Decimal('10')
    assert decision.projected_committed.memory_bytes == Decimal('90')
    assert decision.state == 'Exhausted'


def test_positive_change_is_blocked_while_cluster_is_already_overcommitted() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(cpu=Decimal('10'), memory_bytes=Decimal('100')),
        committed_before=CapacityVector(cpu=Decimal('12'), memory_bytes=Decimal('90')),
        current_allocation=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('20')),
        proposed_allocation=CapacityVector(cpu=Decimal('3'), memory_bytes=Decimal('30')),
        capacity_evidence_available=True,
    )

    assert decision.allowed is False
    assert decision.state == 'Overcommitted'
    assert 'positive allocation' in decision.reason.lower()


def test_committed_capacity_snapshot_uses_ready_worker_allocatable_units() -> None:
    result = SnapshotResult(
        context={
            'capacity_summary': {
                'cpu': {'capacity_evidence_available': True, 'capacity': 12.5},
                'memory': {'capacity_evidence_available': True, 'capacity': 32},
            }
        },
        snapshot=None,
        state='fresh',
        stale=False,
    )

    vector, reason = _capacity_vector(result)

    assert reason == ''
    assert vector is not None
    assert vector.cpu == Decimal('12.5')
    assert vector.memory_bytes == Decimal(32 * 1024**3)


def test_stale_committed_capacity_snapshot_fails_closed() -> None:
    result = SnapshotResult(
        context={
            'capacity_summary': {
                'cpu': {'capacity_evidence_available': True, 'capacity': 12.5},
                'memory': {'capacity_evidence_available': True, 'capacity': 32},
            }
        },
        snapshot=None,
        state='stale',
        stale=True,
    )

    vector, reason = _capacity_vector(result)

    assert vector is None
    assert 'stale' in reason.lower()


def test_allocation_change_classifies_increase_decrease_and_no_change() -> None:
    bounded = CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40'))
    increased = CapacityVector(cpu=Decimal('5'), memory_bytes=Decimal('40'))
    decreased = CapacityVector(cpu=Decimal('3'), memory_bytes=Decimal('30'))

    assert classify_allocation_change(current=bounded, proposed=increased) == 'increase'
    assert classify_allocation_change(current=bounded, proposed=decreased) == 'decrease'
    assert classify_allocation_change(current=bounded, proposed=bounded) == 'no_change'


def test_allocation_change_treats_unbounded_proposal_as_increase() -> None:
    current = CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40'))
    proposed = CapacityVector(cpu=None, memory_bytes=Decimal('40'))

    assert classify_allocation_change(current=current, proposed=proposed) == 'increase'


def test_allocation_change_treats_bounding_an_unbounded_dimension_as_decrease() -> None:
    current = CapacityVector(cpu=None, memory_bytes=Decimal('40'))
    proposed = CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40'))

    assert classify_allocation_change(current=current, proposed=proposed) == 'decrease'
