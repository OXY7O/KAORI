from decimal import Decimal
from types import SimpleNamespace

import app.kubernetes.tenant.capacity_governance as capacity_governance
from app.kubernetes.analytics.materialization.service import SnapshotResult
from app.kubernetes.tenant.capacity import (
    CapacityVector,
    build_tenant_allocation_budget,
    classify_allocation_change,
    classify_capacity_state,
    evaluate_allocation_preflight,
    quota_request_vector,
)
from app.kubernetes.tenant.capacity_governance import (
    _aggregate_committed_allocation,
    _capacity_vector,
    _capsule_tenant_quota_vector,
    _committed_evidence_reason,
    _logical_storage_budget_vector,
    _optional_positive_gib_quantity,
    _quantity_gib_text,
    _unknown_evidence_decision,
    build_capacity_governance_summary,
)


def test_quota_request_vector_preserves_unbounded_dimensions() -> None:
    vector = quota_request_vector({'requests.cpu': '1500m'})

    assert vector.cpu == Decimal('1.500')
    assert vector.memory_bytes is None


def test_incomplete_active_commitment_remains_unknown_instead_of_zero() -> None:
    reason = _committed_evidence_reason(CapacityVector(cpu=None, memory_bytes=Decimal('1024')))

    assert reason is not None
    assert 'unbounded or missing' in reason
    assert 'cannot be proven' in reason


def test_bounded_active_commitment_has_no_unknown_reason() -> None:
    assert _committed_evidence_reason(CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('4096'))) is None


def test_incomplete_commitment_reason_names_blocking_namespaces() -> None:
    reason = _committed_evidence_reason(
        CapacityVector(cpu=None, memory_bytes=None),
        ['legacy-a', 'adopted-b'],
    )

    assert reason is not None
    assert 'legacy-a, adopted-b' in reason
    assert 'Apply a bounded Resource Profile allocation before positive changes.' in reason


def test_budget_subtracts_reserve_headroom_and_unmanaged_commitments() -> None:
    gib = Decimal(1024**3)

    budget = build_tenant_allocation_budget(
        allocatable=CapacityVector(
            cpu=Decimal('100'),
            memory_bytes=Decimal('200') * gib,
            pods=Decimal('500'),
        ),
        reserve=CapacityVector(
            cpu=Decimal('10'),
            memory_bytes=Decimal('20') * gib,
            pods=Decimal('25'),
        ),
        safety_headroom_percent=Decimal('10'),
        unmanaged=CapacityVector(
            cpu=Decimal('5'),
            memory_bytes=Decimal('10') * gib,
            pods=Decimal('15'),
        ),
        logical_storage_budget=Decimal('2000') * gib,
    )

    assert budget.allocatable.cpu == Decimal('100')
    assert budget.safety_headroom.cpu == Decimal('10')
    assert budget.safety_headroom.pods == Decimal('50')
    assert budget.available.cpu == Decimal('75')
    assert budget.available.memory_bytes == Decimal('150') * gib
    assert budget.available.pods == Decimal('410')
    assert budget.available.storage_bytes == Decimal('2000') * gib


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
                'pods': {'capacity_evidence_available': True, 'capacity': 440},
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
    assert vector.pods == Decimal('440')
    assert vector.storage_bytes is None


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


def test_unknown_evidence_allows_non_increasing_existing_allocation_change() -> None:
    decision = _unknown_evidence_decision(
        reason='Committed capacity evidence is stale.',
        committed=CapacityVector(cpu=Decimal('8'), memory_bytes=Decimal('80')),
        current=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40')),
        proposed=CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('20')),
        positive_change=False,
    )

    assert decision.allowed is True
    assert decision.decision == 'allow'
    assert decision.state == 'Unknown'
    assert decision.projected_committed.cpu == Decimal('6')
    assert decision.projected_committed.memory_bytes == Decimal('60')


def test_unknown_evidence_blocks_positive_existing_allocation_change() -> None:
    decision = _unknown_evidence_decision(
        reason='Committed capacity evidence is stale.',
        committed=CapacityVector(cpu=Decimal('8'), memory_bytes=Decimal('80')),
        current=CapacityVector(cpu=Decimal('2'), memory_bytes=Decimal('20')),
        proposed=CapacityVector(cpu=Decimal('4'), memory_bytes=Decimal('40')),
        positive_change=True,
    )

    assert decision.allowed is False
    assert decision.decision == 'block'
    assert decision.state == 'Unknown'


def _capacity_row(
    tenant_id: str,
    namespace: str,
    cpu: str,
    memory: str,
    *,
    pods: str = '10',
    storage: str | None = None,
):
    quota = {
        'requests.cpu': cpu,
        'requests.memory': memory,
        'pods': pods,
    }
    if storage is not None:
        quota['requests.storage'] = storage
    return SimpleNamespace(
        namespace=namespace,
        environment=SimpleNamespace(tenant_id=tenant_id),
        allocation_quota_json=quota,
    )


def test_shared_tenant_allocation_is_counted_once_instead_of_per_namespace() -> None:
    rows = [
        _capacity_row('capsule-api', 'api-a', '4', '8Gi'),
        _capacity_row('capsule-api', 'api-b', '4', '8Gi'),
        _capacity_row('capsule-api', 'api-c', '4', '8Gi'),
    ]

    committed, unbounded = _aggregate_committed_allocation(
        rows,
        shared_quota_by_tenant={
            'capsule-api': {
                'requests.cpu': '4',
                'requests.memory': '8Gi',
                'pods': '10',
            }
        },
    )

    assert committed.cpu == Decimal('4')
    assert committed.memory_bytes == Decimal(8 * 1024**3)
    assert unbounded == []


def test_shared_and_namespace_commitments_can_coexist_without_double_counting() -> None:
    rows = [
        _capacity_row('capsule-api', 'api-a', '4', '8Gi'),
        _capacity_row('capsule-api', 'api-b', '4', '8Gi'),
        _capacity_row('native-payments', 'payments-prod', '2', '4Gi'),
    ]

    committed, unbounded = _aggregate_committed_allocation(
        rows,
        shared_quota_by_tenant={
            'capsule-api': {
                'requests.cpu': '4',
                'requests.memory': '8Gi',
                'pods': '10',
            }
        },
    )

    assert committed.cpu == Decimal('6')
    assert committed.memory_bytes == Decimal(12 * 1024**3)
    assert unbounded == []


def test_ambiguous_shared_authority_fails_capacity_evidence_closed() -> None:
    rows = [_capacity_row('capsule-api', 'api-a', '4', '8Gi')]

    committed, unbounded = _aggregate_committed_allocation(
        rows,
        shared_quota_by_tenant={},
        ambiguous_shared_tenants=['capsule-api'],
    )

    assert committed.cpu is None
    assert committed.memory_bytes is None
    assert 'Tenant/capsule-api ambiguous shared allocation' in unbounded


def test_capsule_tenant_scope_quota_is_counted_once() -> None:
    vector = _capsule_tenant_quota_vector(
        {
            'requests.cpu': '4',
            'requests.memory': '8Gi',
            'pods': '10',
        },
        scope='Tenant',
        namespace_count=3,
    )

    assert vector.cpu == Decimal('4')
    assert vector.memory_bytes == Decimal(8 * 1024**3)


def test_capsule_namespace_scope_quota_is_counted_per_correlated_namespace() -> None:
    vector = _capsule_tenant_quota_vector(
        {
            'requests.cpu': '4',
            'requests.memory': '8Gi',
            'pods': '10',
        },
        scope='Namespace',
        namespace_count=3,
    )

    assert vector.cpu == Decimal('12')
    assert vector.memory_bytes == Decimal(24 * 1024**3)

def test_quota_request_vector_includes_pods_and_storage_commitment() -> None:
    gib = Decimal(1024**3)

    vector = quota_request_vector(
        {
            'requests.cpu': '2',
            'requests.memory': '4Gi',
            'pods': '20',
            'requests.storage': '100Gi',
        }
    )

    assert vector.pods == Decimal('20')
    assert vector.storage_bytes == Decimal('100') * gib


def test_preflight_blocks_projected_pod_shortfall() -> None:
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(
            cpu=Decimal('10'),
            memory_bytes=Decimal('100'),
            pods=Decimal('100'),
        ),
        committed_before=CapacityVector(
            cpu=Decimal('4'),
            memory_bytes=Decimal('40'),
            pods=Decimal('95'),
        ),
        current_allocation=CapacityVector(
            cpu=Decimal('0'),
            memory_bytes=Decimal('0'),
            pods=Decimal('0'),
        ),
        proposed_allocation=CapacityVector(
            cpu=Decimal('1'),
            memory_bytes=Decimal('10'),
            pods=Decimal('10'),
        ),
        capacity_evidence_available=True,
    )

    assert decision.allowed is False
    assert decision.shortfall.pods == Decimal('5')


def test_preflight_blocks_projected_logical_storage_shortfall() -> None:
    gib = Decimal(1024**3)
    decision = evaluate_allocation_preflight(
        budget=CapacityVector(
            cpu=Decimal('10'),
            memory_bytes=Decimal('100'),
            pods=Decimal('100'),
            storage_bytes=Decimal('500') * gib,
        ),
        committed_before=CapacityVector(
            cpu=Decimal('4'),
            memory_bytes=Decimal('40'),
            pods=Decimal('40'),
            storage_bytes=Decimal('480') * gib,
        ),
        current_allocation=CapacityVector(
            cpu=Decimal('0'),
            memory_bytes=Decimal('0'),
            pods=Decimal('0'),
            storage_bytes=Decimal('0'),
        ),
        proposed_allocation=CapacityVector(
            cpu=Decimal('1'),
            memory_bytes=Decimal('10'),
            pods=Decimal('10'),
            storage_bytes=Decimal('50') * gib,
        ),
        capacity_evidence_available=True,
    )

    assert decision.allowed is False
    assert decision.shortfall.storage_bytes == Decimal('30') * gib


def test_storage_budget_is_optional_without_claiming_physical_capacity() -> None:
    gib = Decimal(1024**3)
    budget = build_tenant_allocation_budget(
        allocatable=CapacityVector(
            cpu=Decimal('10'),
            memory_bytes=Decimal('32') * gib,
            pods=Decimal('100'),
        ),
        reserve=CapacityVector(cpu=Decimal('1'), memory_bytes=Decimal('2') * gib, pods=Decimal('5')),
        safety_headroom_percent=Decimal('10'),
        unmanaged=CapacityVector(cpu=Decimal('0'), memory_bytes=Decimal('0'), pods=Decimal('0')),
        logical_storage_budget=None,
    )

    assert budget.available.storage_bytes is None
    assert budget.logical_storage_budget is None

def test_storage_budget_ui_accepts_numeric_gib_and_persists_canonical_quantity() -> None:
    assert _optional_positive_gib_quantity('2048', label='Tenant Storage Budget') == '2048Gi'
    assert _optional_positive_gib_quantity('1536.5', label='Tenant Storage Budget') == '1536.5Gi'
    assert _quantity_gib_text('2Ti') == '2048'
    assert _quantity_gib_text('2048Gi') == '2048'


def test_logical_storage_budget_remains_available_without_compute_capacity_snapshot() -> None:
    gib = Decimal(1024**3)
    policy = SimpleNamespace(tenant_storage_budget='2048Gi')

    budget = _logical_storage_budget_vector(policy)

    assert budget.cpu is None
    assert budget.memory_bytes is None
    assert budget.pods is None
    assert budget.storage_bytes == Decimal('2048') * gib

def test_missing_compute_snapshot_keeps_logical_storage_budget_visible(monkeypatch) -> None:
    gib = Decimal(1024**3)
    policy = SimpleNamespace(
        cluster_id='cluster-1',
        platform_reserve_cpu='0',
        platform_reserve_memory='0',
        platform_reserve_pods=0,
        safety_headroom_percent=10,
        unmanaged_commitment_cpu='0',
        unmanaged_commitment_memory='0',
        unmanaged_commitment_pods=0,
        tenant_storage_budget='2048Gi',
    )

    monkeypatch.setattr(
        capacity_governance.TenantCapacityPolicy,
        'query',
        SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: policy)),
    )
    monkeypatch.setattr(
        capacity_governance,
        '_read_capacity_snapshot',
        lambda cluster_id: SnapshotResult(
            context={},
            snapshot=None,
            state='missing',
            stale=False,
        ),
    )
    monkeypatch.setattr(
        capacity_governance,
        '_committed_tenant_allocation',
        lambda cluster_id: (
            CapacityVector(
                cpu=Decimal('0'),
                memory_bytes=Decimal('0'),
                pods=Decimal('0'),
                storage_bytes=Decimal('100') * gib,
            ),
            1,
            [],
        ),
    )

    summary = build_capacity_governance_summary('cluster-1')

    assert summary['state'] == 'Unknown'
    assert summary['display']['budget']['cpu'] == 'N/A'
    assert summary['display']['budget']['memory'] == 'N/A'
    assert summary['display']['budget']['pods'] == 'N/A'
    assert summary['display']['budget']['storage'] == '2048.00 GiB'
    assert summary['display']['headroom']['storage'] == '1948.00 GiB'

