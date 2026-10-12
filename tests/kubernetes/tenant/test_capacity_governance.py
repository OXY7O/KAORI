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


def test_capacity_policy_persists_explicit_gib_and_optional_blank(monkeypatch) -> None:
    policy = SimpleNamespace(cluster_id='cluster-1', tenant_storage_budget=None)
    commits = []

    class FakeSession:
        def get(self, model, cluster_id):
            return SimpleNamespace(id=cluster_id)

        def flush(self):
            pass

        def commit(self):
            commits.append(policy.tenant_storage_budget)

    session = FakeSession()
    monkeypatch.setattr(capacity_governance, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(
        capacity_governance,
        'TenantCapacityPolicy',
        SimpleNamespace(query=SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: policy),
        )),
    )

    form = {
        'capacity_cluster_id': 'cluster-1',
        'platform_reserve_cpu': '1',
        'platform_reserve_memory': '1Gi',
        'platform_reserve_pods': '1',
        'safety_headroom_percent': '10',
        'unmanaged_commitment_cpu': '0',
        'unmanaged_commitment_memory': '0',
        'unmanaged_commitment_pods': '0',
        'tenant_storage_budget_gib': '2048',
    }
    saved = capacity_governance.upsert_capacity_policy_committed(form)
    assert saved.tenant_storage_budget == '2048Gi'
    assert capacity_governance._policy_json(saved)['tenant_storage_budget_gib'] == '2048'

    # Empty is an explicitly optional, ungoverned policy input; no default.
    capacity_governance.upsert_capacity_policy_committed({**form, 'tenant_storage_budget_gib': ''})
    assert policy.tenant_storage_budget is None
    assert commits == ['2048Gi', None]


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
        capacity_governance,
        'TenantCapacityPolicy',
        SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: policy))),
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


def test_fleet_capacity_summary_batches_snapshot_reads(monkeypatch) -> None:
    class _Field:
        @staticmethod
        def in_(values):
            return tuple(values)

    monkeypatch.setattr(
        capacity_governance,
        'TenantCapacityPolicy',
        SimpleNamespace(
            cluster_id=_Field(),
            query=SimpleNamespace(
                filter=lambda *_args: SimpleNamespace(all=lambda: []),
            ),
        ),
    )
    committed_state = (
        CapacityVector(
            cpu=Decimal('0'),
            memory_bytes=Decimal('0'),
            pods=Decimal('0'),
            storage_bytes=Decimal('0'),
        ),
        0,
        [],
    )
    monkeypatch.setattr(
        capacity_governance,
        '_committed_tenant_allocations',
        lambda cluster_ids: {cluster_id: committed_state for cluster_id in cluster_ids},
    )

    batch_calls: list[list[str]] = []
    snapshot = SnapshotResult(context=None, snapshot=None, state='missing', stale=False)

    def _snapshots(cluster_ids: list[str]) -> dict[str, SnapshotResult]:
        batch_calls.append(cluster_ids)
        return {cluster_id: snapshot for cluster_id in cluster_ids}

    monkeypatch.setattr(capacity_governance, '_read_capacity_snapshots', _snapshots)
    monkeypatch.setattr(
        capacity_governance,
        '_build_capacity_governance_summary_from_inputs',
        lambda cluster_id, **kwargs: {
            'cluster_id': cluster_id,
            'snapshot_is_batched': kwargs['snapshot_result'] is snapshot,
        },
    )

    summaries = capacity_governance.build_capacity_governance_summaries(['cluster-1', 'cluster-2', 'cluster-1'])

    assert batch_calls == [['cluster-1', 'cluster-2']]
    assert list(summaries) == ['cluster-1', 'cluster-2']
    assert all(summary['snapshot_is_batched'] for summary in summaries.values())


def test_committed_allocation_queries_exclude_terminal_generations_in_all_paths() -> None:
    """Single/batched #654 and Capsule shared query paths use one lifecycle boundary."""
    from pathlib import Path

    from app.kubernetes.tenant.capacity_allocation_state import (
        _TERMINAL_NAMESPACE_ALLOCATION_STATUSES,
        _TERMINAL_TENANT_ALLOCATION_LIFECYCLES,
    )

    source = (
        Path(__file__).resolve().parents[3] / "app/kubernetes/tenant/capacity_allocation_state.py"
    ).read_text(encoding="utf-8")
    overview = (
        Path(__file__).resolve().parents[3] / "app/kubernetes/tenant/allocation_overview.py"
    ).read_text(encoding="utf-8")
    assert set(_TERMINAL_NAMESPACE_ALLOCATION_STATUSES) == {"released", "deprovisioned"}
    assert set(_TERMINAL_TENANT_ALLOCATION_LIFECYCLES) == {"released", "decommissioned"}
    assert source.count("_active_namespace_allocation_query()") == 3  # definition + two readers
    assert source.count("Tenant.lifecycle_status.notin_(_TERMINAL_TENANT_ALLOCATION_LIFECYCLES)") == 5
    assert source.count("TenantNamespace.provisioning_status.notin_(_TERMINAL_NAMESPACE_ALLOCATION_STATUSES)") == 1
    assert overview.count("_active_namespace_allocation_query()") == 1
    assert "Tenant.lifecycle_status.notin_(_TERMINAL_TENANT_ALLOCATION_LIFECYCLES)" in overview
    assert "resource_profile_id is None" not in source


def _replacement_row(tenant_id: str, namespace: str, row_id: int, quota: dict[str, str]):
    return SimpleNamespace(
        id=row_id,
        cluster_id='cluster-1',
        namespace=namespace,
        environment=SimpleNamespace(tenant_id=tenant_id),
        allocation_quota_json=quota,
    )


def test_atomic_replacement_excludes_only_the_exact_active_native_namespace() -> None:
    from app.kubernetes.tenant.capacity_allocation_state import _other_committed_for_namespace_replacement

    target = _replacement_row(
        'tenant-native', 'tenant-adopt-quota-uat', 8,
        {'limits.cpu': '4', 'limits.memory': '8Gi', 'pods': '10', 'requests.storage': '1Gi'},
    )
    other = _replacement_row(
        'tenant-other', 'payments', 9,
        {'requests.cpu': '2', 'requests.memory': '4Gi', 'pods': '20', 'requests.storage': '100Gi'},
    )
    capsule = _replacement_row('tenant-shared', 'capsule-a', 10, {})
    shared = {
        'tenant-shared': {
            'requests.cpu': '3', 'requests.memory': '6Gi',
            'pods': '15', 'requests.storage': '25Gi',
        },
    }
    committed, count, unknown = _other_committed_for_namespace_replacement(
        [target, other, capsule],
        target=target, shared_quota_by_tenant=shared, ambiguous_shared_tenants=[],
    )
    gib = Decimal(1024**3)
    assert count == 3
    assert unknown == []
    assert committed == CapacityVector(
        cpu=Decimal('5'), memory_bytes=Decimal('10') * gib,
        pods=Decimal('35'), storage_bytes=Decimal('125') * gib,
    )


def test_atomic_replacement_rejects_absent_duplicate_and_shared_authority() -> None:
    import pytest

    from app.kubernetes.tenant.capacity_allocation_state import _other_committed_for_namespace_replacement

    target = _replacement_row('tenant-native', 'adopted-a', 1, {})
    other = _replacement_row('tenant-other', 'unrelated-b', 2, {})
    call = lambda rows, **kw: _other_committed_for_namespace_replacement(
        rows, target=target, shared_quota_by_tenant=kw.get('shared', {}),
        ambiguous_shared_tenants=kw.get('ambiguous', []),
    )
    with pytest.raises(ValueError, match='exactly one active matching'):
        call([other])
    with pytest.raises(ValueError, match='multiple active generations'):
        call([target, _replacement_row('tenant-other', 'adopted-a', 3, {})])
    with pytest.raises(ValueError, match='shared or ambiguous Tenant authority'):
        call([target], shared={'tenant-native': {'requests.cpu': '2'}})
    with pytest.raises(ValueError, match='shared or ambiguous Tenant authority'):
        call([target], ambiguous=['tenant-native'])


def _install_atomic_replacement_test_evidence(
    monkeypatch, *,
    other_cpu='2', other_memory_gib='4', other_pods='20', other_storage_gib='100',
    other_unknown=None, snapshot_stale=False, has_policy=True,
):
    """Set up the same contracted admission components, without a provider write."""
    gib = Decimal(1024**3)
    policy = SimpleNamespace(
        platform_reserve_cpu='0', platform_reserve_memory='0', platform_reserve_pods=0,
        safety_headroom_percent=10, unmanaged_commitment_cpu='0',
        unmanaged_commitment_memory='0', unmanaged_commitment_pods=0,
        tenant_storage_budget='2048Gi',
    )
    monkeypatch.setattr(
        capacity_governance, 'TenantCapacityPolicy',
        SimpleNamespace(query=SimpleNamespace(filter_by=lambda **_k: SimpleNamespace(
            first=lambda: policy if has_policy else None,
        ))),
    )
    snapshot = SnapshotResult(
        context={'capacity_summary': {
            'cpu': {'capacity_evidence_available': True, 'capacity': 12},
            'memory': {'capacity_evidence_available': True, 'capacity': 32},
            'pods': {'capacity_evidence_available': True, 'capacity': 200},
        }},
        snapshot=None, state='stale' if snapshot_stale else 'fresh',
        stale=snapshot_stale,
    )
    monkeypatch.setattr(capacity_governance, '_read_capacity_snapshot', lambda _id: snapshot)
    unknown = CapacityVector(cpu=None, memory_bytes=None, pods=Decimal('30'), storage_bytes=Decimal('101') * gib)
    other = CapacityVector(
        cpu=Decimal(other_cpu) if other_cpu is not None else None,
        memory_bytes=Decimal(other_memory_gib) * gib if other_memory_gib is not None else None,
        pods=Decimal(other_pods) if other_pods is not None else None,
        storage_bytes=Decimal(other_storage_gib) * gib if other_storage_gib is not None else None,
    )
    reads = []

    def fake_committed(cluster_id, *, replace_namespace=None):
        assert cluster_id == 'cluster-1'
        reads.append(replace_namespace is not None)
        return (other, 2, list(other_unknown or [])) if replace_namespace else (
            unknown, 2, ['tenant-adopt-quota-uat'],
        )

    monkeypatch.setattr(capacity_governance, '_committed_tenant_allocation', fake_committed)
    decisions = []
    monkeypatch.setattr(
        capacity_governance, '_persist_decision',
        lambda **kwargs: decisions.append(kwargs) or SimpleNamespace(id=32),
    )
    commits = []
    monkeypatch.setattr(
        capacity_governance, 'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append(True))),
    )
    return reads, decisions, commits


def _atomic_native_request(*, proposed_cpu='1', proposed_storage='50Gi'):
    from app.kubernetes.tenant.capacity_governance import _AllocationRequest

    target = _replacement_row('tenant-native', 'tenant-adopt-quota-uat', 8, {})
    tenant = SimpleNamespace(id='tenant-native', cluster_id='cluster-1')
    target.environment.tenant = tenant
    current = {
        'limits.cpu': '4', 'limits.memory': '8Gi',
        'pods': '10', 'requests.storage': '1Gi',
    }
    proposed = {
        'limits.cpu': '2', 'requests.memory': '2Gi',
        'limits.memory': '4Gi', 'pods': '10',
        'requests.storage': proposed_storage,
    }
    if proposed_cpu is not None:
        proposed['requests.cpu'] = proposed_cpu
    return SimpleNamespace(tenant=tenant), _AllocationRequest(
        profile=SimpleNamespace(id=5, version=2),
        namespace=target.namespace,
        current=quota_request_vector(current),
        proposed=quota_request_vector(proposed),
        operation='increase',
        replacement_namespace=target,
    )


def test_native_bounded_atomic_replacement_allows_proven_post_state(monkeypatch) -> None:
    reads, decisions, commits = _install_atomic_replacement_test_evidence(monkeypatch)
    environment, request = _atomic_native_request()

    result = capacity_governance._enforce_allocation_preflight(
        tenant_environment=environment, request=request,
    )

    gib = Decimal(1024**3)
    assert result.id == 32
    assert reads == [False, True]
    assert commits == []
    pure = decisions[0]['pure']
    context = decisions[0]['evidence']
    assert pure.allowed is True
    assert pure.positive_change is True
    assert pure.projected_committed.cpu == Decimal('3')
    assert pure.projected_committed.memory_bytes == Decimal('6') * gib
    assert pure.projected_committed.pods == Decimal('30')
    assert pure.projected_committed.storage_bytes == Decimal('150') * gib
    assert context.committed_before.cpu is None  # Original evidence remains unknown.
    assert context.replacement_other_committed.cpu == Decimal('2')
    assert request.current.cpu is None


def test_native_bounded_atomic_replacement_fails_closed_for_unprovable_or_over_budget(monkeypatch) -> None:
    import pytest

    from app.kubernetes.tenant.capacity_governance import TenantCapacityBlockedError

    for options, proposed_cpu, expected in (
        ({'other_unknown': ['another-namespace']}, '1', 'other active Tenant allocations'),
        ({'other_cpu': None, 'other_unknown': ['another-namespace']}, '1', 'Unbounded or missing'),
        ({'other_storage_gib': '2030'}, '1', 'Projected committed allocation exceeds'),
        ({'snapshot_stale': True}, '1', 'stale'),
        ({'has_policy': False}, '1', 'policy is not configured'),
        ({}, None, 'Unbounded or missing'),
    ):
        _reads, decisions, commits = _install_atomic_replacement_test_evidence(
            monkeypatch, **options,
        )
        environment, request = _atomic_native_request(proposed_cpu=proposed_cpu)
        with pytest.raises(TenantCapacityBlockedError, match=expected):
            capacity_governance._enforce_allocation_preflight(
                tenant_environment=environment, request=request,
            )
        assert len(decisions) == 1
        assert decisions[0]['pure'].allowed is False
        assert commits == [True]


def test_atomic_native_preflight_evidence_keeps_raw_unknown_and_other_committed(monkeypatch) -> None:
    from app.kubernetes.tenant.capacity_governance import _DecisionEvidenceContext, _persist_decision

    environment, request = _atomic_native_request()
    gib = Decimal(1024**3)
    current = request.current
    other = CapacityVector(
        cpu=Decimal('2'), memory_bytes=Decimal('4') * gib,
        pods=Decimal('20'), storage_bytes=Decimal('100') * gib,
    )
    projected = CapacityVector(
        cpu=Decimal('3'), memory_bytes=Decimal('6') * gib,
        pods=Decimal('30'), storage_bytes=Decimal('150') * gib,
    )
    class DummyDecision:
        pass

    monkeypatch.setattr(capacity_governance, 'TenantCapacityDecision', DummyDecision)
    monkeypatch.setattr(capacity_governance, '_policy_json', lambda _policy: {})
    monkeypatch.setattr(capacity_governance, '_budget_json', lambda _budget: {})
    saves = []
    monkeypatch.setattr(
        capacity_governance, 'db',
        SimpleNamespace(session=SimpleNamespace(add=saves.append, flush=lambda: None)),
    )
    from app.kubernetes.tenant.capacity import AllocationPreflightDecision
    pure = AllocationPreflightDecision(
        allowed=True, decision='allow', state='Healthy', reason='Projected bounded.',
        projected_committed=projected, projected_headroom=other,
        shortfall=CapacityVector(cpu=Decimal(0), memory_bytes=Decimal(0)),
        positive_change=True,
    )
    record = _persist_decision(
        cluster_id='cluster-1', tenant_environment=SimpleNamespace(id=17),
        tenant=environment.tenant, request=request, pure=pure,
        evidence=_DecisionEvidenceContext(
            policy=SimpleNamespace(), budget=SimpleNamespace(),
            committed_before=CapacityVector(cpu=None, memory_bytes=None),
            current=current, proposed=request.proposed,
            committed_count=2,
            snapshot_result=SnapshotResult(context=None, snapshot=None, state='fresh', stale=False),
            replacement_other_committed=other,
        ),
    )
    assert saves == [record]
    allocation = record.evidence_json['allocation']
    assert allocation['committed_before']['cpu'] is None
    assert allocation['current']['cpu'] is None
    assert allocation['projected_committed']['cpu'] == '3'
    assert allocation['atomic_replacement']['target_namespace_id'] == 8
    assert allocation['atomic_replacement']['other_committed']['cpu'] == '2'
    assert allocation['atomic_replacement']['projection'] == 'other_committed_plus_proposed'


def test_atomic_replacement_keeps_other_unbounded_sources_unknown() -> None:
    from app.kubernetes.tenant.capacity_allocation_state import _other_committed_for_namespace_replacement

    target = _replacement_row('native', 'target', 1, {})
    other = _replacement_row(
        'another-native', 'unbounded-other', 2,
        {'requests.memory': '2Gi', 'pods': '10', 'requests.storage': '1Gi'},
    )
    committed, count, unknown = _other_committed_for_namespace_replacement(
        [target, other], target=target,
        shared_quota_by_tenant={}, ambiguous_shared_tenants=[],
    )
    assert count == 2
    assert committed.cpu is None
    assert unknown == ['unbounded-other']


def test_atomic_replacement_is_not_used_for_bounded_or_observed_preflight(monkeypatch) -> None:
    import pytest

    from app.kubernetes.tenant.capacity_governance import TenantCapacityBlockedError

    reads, decisions, commits = _install_atomic_replacement_test_evidence(monkeypatch)
    environment, request = _atomic_native_request()
    bounded_request = capacity_governance._AllocationRequest(
        profile=request.profile,
        namespace=request.namespace,
        current=quota_request_vector({
            'requests.cpu': '1', 'requests.memory': '2Gi',
            'pods': '10', 'requests.storage': '1Gi',
        }),
        proposed=request.proposed,
        operation='increase',
        replacement_namespace=request.replacement_namespace,
    )
    with pytest.raises(TenantCapacityBlockedError, match='Unbounded or missing governed'):
        capacity_governance._enforce_allocation_preflight(
            tenant_environment=environment, request=bounded_request,
        )
    assert reads == [False]
    assert decisions[0]['evidence'].replacement_other_committed is None
    assert commits == [True]

    reads.clear()
    decisions.clear()
    commits.clear()
    observed_request = capacity_governance._AllocationRequest(
        profile=request.profile,
        namespace=request.namespace,
        current=request.current,
        proposed=request.proposed,
        operation='increase',
        # Observed initial cutover has no replacement-authority flag.
    )
    with pytest.raises(TenantCapacityBlockedError, match='Unbounded or missing governed'):
        capacity_governance._enforce_allocation_preflight(
            tenant_environment=environment, request=observed_request,
        )
    assert reads == [False]
    assert decisions[0]['evidence'].replacement_other_committed is None
    assert commits == [True]


def test_managed_native_service_wires_atomic_replacement_only_after_managed_checks() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    service = (root / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')
    governance = (root / 'app/kubernetes/tenant/capacity_governance.py').read_text(encoding='utf-8')
    state = (root / 'app/kubernetes/tenant/capacity_allocation_state.py').read_text(encoding='utf-8')
    assert "allocation_control_state(record) != 'kaori_managed'" in service
    assert "record.environment.tenant.provider_key != 'native_kubernetes'" in service
    assert "capacity_decision = enforce_existing_namespace_allocation_preflight(" in service
    assert "capacity_decision = enforce_observed_namespace_allocation_preflight(" not in service
    assert "replacement_namespace=record" in governance
    assert "replace_namespace=request.replacement_namespace" in governance
    assert "shared_overrides: Mapping[str, Mapping[str, object]] | None = None" in state
    assert "_canonical_shared_allocation_quota(cluster_id)" in state
    assert state.count("_active_namespace_allocation_query()") == 3
