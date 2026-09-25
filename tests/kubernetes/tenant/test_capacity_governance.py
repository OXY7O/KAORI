from decimal import Decimal

from app.kubernetes.tenant.capacity import (
    CapacityVector,
    build_tenant_allocation_budget,
    classify_capacity_state,
    evaluate_allocation_preflight,
    quota_request_vector,
)


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
