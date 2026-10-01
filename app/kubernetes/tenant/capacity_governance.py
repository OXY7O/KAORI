from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from kubernetes.utils.quantity import parse_quantity
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.analytics.materialization.service import SnapshotResult, read_snapshot
from app.kubernetes.tenant.capacity import (
    AllocationPreflightDecision,
    CapacityVector,
    TenantAllocationBudget,
    build_tenant_allocation_budget,
    classify_allocation_change,
    classify_capacity_state,
    evaluate_allocation_preflight,
    quota_request_vector,
)
from app.models import Cluster
from app.models.tenant import (
    Tenant,
    TenantCapacityDecision,
    TenantCapacityPolicy,
    TenantEnvironment,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantResourceProfile,
)
from app.models.tenant_advanced import (
    TenantAdvancedCapabilityIntent,
    TenantAdvancedCapabilityStatus,
)

_GIB = Decimal(1024**3)
_ZERO = Decimal('0')


class TenantCapacityBlockedError(ValueError):
    """Tenant allocation was denied before any provider reconciliation."""


class TenantCapacityStateConflictError(RuntimeError):
    """Tenant capacity policy persistence failed before provider reconciliation."""


@dataclass(frozen=True, slots=True)
class _DecisionEvidenceContext:
    policy: TenantCapacityPolicy | None
    budget: TenantAllocationBudget | None
    committed_before: CapacityVector
    current: CapacityVector
    proposed: CapacityVector
    committed_count: int
    snapshot_result: SnapshotResult


def upsert_capacity_policy(source: Mapping[str, Any]) -> TenantCapacityPolicy:
    cluster_id = _text(source, 'capacity_cluster_id')
    cluster = db.session.get(Cluster, cluster_id)
    if cluster is None:
        raise ValueError('Select a valid Kubernetes cluster for Tenant Capacity Governance.')

    reserve_cpu = _nonnegative_quantity(source.get('platform_reserve_cpu'), label='Platform reserve CPU')
    reserve_memory = _nonnegative_quantity(source.get('platform_reserve_memory'), label='Platform reserve memory')
    reserve_pods = _nonnegative_integer(source.get('platform_reserve_pods'), label='Platform reserve Pods')
    unmanaged_cpu = _nonnegative_quantity(
        source.get('unmanaged_commitment_cpu'),
        label='Unmanaged commitment CPU',
    )
    unmanaged_memory = _nonnegative_quantity(
        source.get('unmanaged_commitment_memory'),
        label='Unmanaged commitment memory',
    )
    unmanaged_pods = _nonnegative_integer(source.get('unmanaged_commitment_pods'), label='Unmanaged commitment Pods')
    tenant_storage_budget = _optional_positive_quantity(
        source.get('tenant_storage_budget'),
        label='Tenant Storage Budget',
    )
    safety_headroom_percent = _percent(source.get('safety_headroom_percent'))

    policy = TenantCapacityPolicy.query.filter_by(cluster_id=cluster.id).first()
    if policy is None:
        policy = TenantCapacityPolicy()
        policy.cluster_id = cluster.id
        db.session.add(policy)

    policy.platform_reserve_cpu = reserve_cpu
    policy.platform_reserve_memory = reserve_memory
    policy.platform_reserve_pods = reserve_pods
    policy.safety_headroom_percent = safety_headroom_percent
    policy.unmanaged_commitment_cpu = unmanaged_cpu
    policy.unmanaged_commitment_memory = unmanaged_memory
    policy.unmanaged_commitment_pods = unmanaged_pods
    policy.tenant_storage_budget = tenant_storage_budget
    db.session.flush()
    return policy


def upsert_capacity_policy_committed(source: Mapping[str, Any]) -> TenantCapacityPolicy:
    try:
        policy = upsert_capacity_policy(source)
        db.session.commit()
        return policy
    except ValueError:
        db.session.rollback()
        raise
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise TenantCapacityStateConflictError(
            'Tenant Capacity Governance policy changed while this request was being applied. Refresh and retry.'
        ) from exc


def build_capacity_governance_summary(cluster_id: str) -> dict[str, Any]:
    policy = TenantCapacityPolicy.query.filter_by(cluster_id=cluster_id).first()
    snapshot_result = _read_capacity_snapshot(cluster_id)
    committed, committed_count, unbounded_namespaces = _committed_tenant_allocation(cluster_id)

    if policy is None:
        return {
            'cluster_id': cluster_id,
            'state': 'Unknown',
            'reason': 'Tenant Capacity Governance policy is not configured.',
            'policy': None,
            'snapshot_state': snapshot_result.state,
            'data_cutoff': _snapshot_cutoff(snapshot_result),
            'committed_namespace_count': committed_count,
            'committed': _vector_json(committed),
            'budget': None,
            'headroom': None,
            'display': {
                'committed': _vector_display(committed),
                'budget': _vector_display(CapacityVector(cpu=None, memory_bytes=None)),
                'headroom': _vector_display(CapacityVector(cpu=None, memory_bytes=None)),
            },
        }

    capacity, capacity_reason = _capacity_vector(snapshot_result)
    if capacity is None:
        return {
            'cluster_id': cluster_id,
            'state': 'Unknown',
            'reason': capacity_reason,
            'policy': _policy_json(policy),
            'snapshot_state': snapshot_result.state,
            'data_cutoff': _snapshot_cutoff(snapshot_result),
            'committed_namespace_count': committed_count,
            'committed': _vector_json(committed),
            'budget': None,
            'headroom': None,
            'display': {
                'committed': _vector_display(committed),
                'budget': _vector_display(CapacityVector(cpu=None, memory_bytes=None)),
                'headroom': _vector_display(CapacityVector(cpu=None, memory_bytes=None)),
            },
        }

    budget = _budget(policy, capacity)
    commitment_reason = _committed_evidence_reason(
        committed,
        unbounded_namespaces,
        budget=budget.available,
    )
    state = 'Unknown' if commitment_reason else classify_capacity_state(budget=budget.available, committed=committed)
    return {
        'cluster_id': cluster_id,
        'state': state,
        'reason': commitment_reason or _state_reason(state),
        'policy': _policy_json(policy),
        'snapshot_state': snapshot_result.state,
        'data_cutoff': _snapshot_cutoff(snapshot_result),
        'committed_namespace_count': committed_count,
        'committed': _vector_json(committed),
        'budget': _budget_json(budget),
        'headroom': _vector_json(_headroom(budget.available, committed)),
        'display': {
            'committed': _vector_display(committed),
            'budget': _vector_display(budget.available),
            'headroom': _vector_display(_headroom(budget.available, committed)),
        },
    }


def enforce_namespace_allocation_preflight(
    *,
    tenant_environment: TenantEnvironment,
    profile: TenantResourceProfile,
    namespace: str,
    quota_hard: Mapping[str, object],
) -> TenantCapacityDecision:
    return _enforce_allocation_preflight(
        tenant_environment=tenant_environment,
        profile=profile,
        namespace=namespace,
        current=CapacityVector(cpu=_ZERO, memory_bytes=_ZERO, pods=_ZERO, storage_bytes=_ZERO),
        proposed=quota_request_vector(quota_hard),
        operation='create',
    )


def enforce_existing_namespace_allocation_preflight(
    *,
    record: TenantNamespace,
    profile: TenantResourceProfile,
    quota_hard: Mapping[str, object],
) -> TenantCapacityDecision:
    current = quota_request_vector(record.allocation_quota_json or {})
    proposed = quota_request_vector(quota_hard)
    operation = classify_allocation_change(current=current, proposed=proposed)
    return _enforce_allocation_preflight(
        tenant_environment=record.environment,
        profile=profile,
        namespace=record.namespace,
        current=current,
        proposed=proposed,
        operation=operation,
    )


def enforce_observed_namespace_allocation_preflight(
    *,
    record: TenantNamespace,
    profile: TenantResourceProfile,
    current_quota_hard: Mapping[str, object],
    proposed_quota_hard: Mapping[str, object],
) -> TenantCapacityDecision:
    current = quota_request_vector(current_quota_hard)
    proposed = quota_request_vector(proposed_quota_hard)
    operation = classify_allocation_change(current=current, proposed=proposed)
    return _enforce_allocation_preflight(
        tenant_environment=record.environment,
        profile=profile,
        namespace=record.namespace,
        current=current,
        proposed=proposed,
        operation=operation,
    )


def enforce_shared_tenant_allocation_preflight(
    *,
    tenant: Tenant,
    profile: TenantResourceProfile,
    current_quota_hard: Mapping[str, object],
    proposed_quota_hard: Mapping[str, object],
) -> TenantCapacityDecision:
    """Evaluate one Tenant-level shared quota exactly once across its namespaces."""

    current = quota_request_vector(current_quota_hard)
    proposed = quota_request_vector(proposed_quota_hard)
    operation = classify_allocation_change(current=current, proposed=proposed)
    committed_state = _committed_tenant_allocation(
        tenant.cluster_id,
        shared_overrides={tenant.id: current_quota_hard},
    )
    return _enforce_allocation_preflight(
        tenant_environment=None,
        tenant=tenant,
        profile=profile,
        namespace=f'@tenant:{tenant.slug}',
        current=current,
        proposed=proposed,
        operation=operation,
        committed_state=committed_state,
        allocation_scope='tenant_shared',
    )


def _scale_capacity_vector(vector: CapacityVector, factor: int) -> CapacityVector:
    if factor <= 0:
        return CapacityVector(cpu=_ZERO, memory_bytes=_ZERO, pods=_ZERO, storage_bytes=_ZERO)
    return CapacityVector(
        cpu=vector.cpu * factor if vector.cpu is not None else None,
        memory_bytes=vector.memory_bytes * factor if vector.memory_bytes is not None else None,
        pods=vector.pods * factor if vector.pods is not None else None,
        storage_bytes=vector.storage_bytes * factor if vector.storage_bytes is not None else None,
    )


def _add_capacity_vectors(left: CapacityVector, right: CapacityVector) -> CapacityVector:
    return CapacityVector(
        cpu=(left.cpu + right.cpu) if left.cpu is not None and right.cpu is not None else None,
        memory_bytes=(
            left.memory_bytes + right.memory_bytes
            if left.memory_bytes is not None and right.memory_bytes is not None
            else None
        ),
        pods=(left.pods + right.pods) if left.pods is not None and right.pods is not None else None,
        storage_bytes=(
            left.storage_bytes + right.storage_bytes
            if left.storage_bytes is not None and right.storage_bytes is not None
            else None
        ),
    )


def _capsule_tenant_quota_vector(
    quota_hard: Mapping[str, object],
    *,
    scope: str,
    namespace_count: int,
) -> CapacityVector:
    normalized_scope = str(scope or 'Tenant')
    if normalized_scope not in {'Tenant', 'Namespace'}:
        raise ValueError('Capsule Tenant resource quota scope must be Tenant or Namespace.')
    factor = 1 if normalized_scope == 'Tenant' else max(int(namespace_count), 0)
    return _scale_capacity_vector(quota_request_vector(quota_hard), factor)


def _committed_allocation_with_tenant_override(
    *,
    tenant: Tenant,
    quota_hard: Mapping[str, object],
    scope: str,
    namespace_count: int,
) -> tuple[CapacityVector, int, list[str]]:
    rows = (
        TenantNamespace.query.filter(
            TenantNamespace.cluster_id == tenant.cluster_id,
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .order_by(TenantNamespace.namespace.asc())
        .all()
    )
    tenant_id = str(tenant.id)
    other_rows = [row for row in rows if str(row.environment.tenant_id) != tenant_id]
    shared, ambiguous = _canonical_shared_allocation_quota(tenant.cluster_id)
    shared.pop(tenant_id, None)
    ambiguous = [item for item in ambiguous if item != tenant_id]
    committed, unbounded = _aggregate_committed_allocation(
        other_rows,
        shared_quota_by_tenant=shared,
        ambiguous_shared_tenants=ambiguous,
    )
    override = _capsule_tenant_quota_vector(
        quota_hard,
        scope=scope,
        namespace_count=namespace_count,
    )
    committed = _add_capacity_vectors(committed, override)
    if any(
        value is None
        for value in (override.cpu, override.memory_bytes, override.pods, override.storage_bytes)
    ):
        unbounded.append(f'Tenant/{tenant.id} Capsule resourceQuotas scope={scope}')
    return committed, len(rows), unbounded


def enforce_capsule_tenant_resource_quota_preflight(
    *,
    tenant: Tenant,
    profile: TenantResourceProfile,
    current_quota_hard: Mapping[str, object],
    proposed_quota_hard: Mapping[str, object],
    current_scope: str,
    proposed_scope: str,
    namespace_count: int,
) -> TenantCapacityDecision:
    """Evaluate Capsule Tenant.spec.resourceQuotas using its actual scope semantics."""

    current = _capsule_tenant_quota_vector(
        current_quota_hard,
        scope=current_scope,
        namespace_count=namespace_count,
    )
    proposed = _capsule_tenant_quota_vector(
        proposed_quota_hard,
        scope=proposed_scope,
        namespace_count=namespace_count,
    )
    operation = classify_allocation_change(current=current, proposed=proposed)
    committed_state = _committed_allocation_with_tenant_override(
        tenant=tenant,
        quota_hard=current_quota_hard,
        scope=current_scope,
        namespace_count=namespace_count,
    )
    return _enforce_allocation_preflight(
        tenant_environment=None,
        tenant=tenant,
        profile=profile,
        namespace=f'@tenant:{tenant.slug}:resource-quotas',
        current=current,
        proposed=proposed,
        operation=operation,
        committed_state=committed_state,
        allocation_scope=(
            'tenant_shared'
            if str(proposed_scope or 'Tenant') == 'Tenant'
            else 'tenant_namespace_template'
        ),
    )


def _enforce_allocation_preflight(
    *,
    tenant_environment: TenantEnvironment | None,
    profile: TenantResourceProfile,
    namespace: str,
    current: CapacityVector,
    proposed: CapacityVector,
    operation: str,
    tenant: Tenant | None = None,
    committed_state: tuple[CapacityVector, int, list[str]] | None = None,
    allocation_scope: str = 'namespace',
) -> TenantCapacityDecision:
    resolved_tenant = tenant or (tenant_environment.tenant if tenant_environment is not None else None)
    if resolved_tenant is None:
        raise ValueError('Tenant capacity preflight requires a Tenant authority.')
    cluster_id = resolved_tenant.cluster_id
    committed, committed_count, unbounded_namespaces = (
        committed_state if committed_state is not None else _committed_tenant_allocation(cluster_id)
    )
    policy = TenantCapacityPolicy.query.filter_by(cluster_id=cluster_id).first()
    snapshot_result = _read_capacity_snapshot(cluster_id)
    capacity, capacity_reason = _capacity_vector(snapshot_result)
    positive_change = operation in {'create', 'increase'}

    budget: TenantAllocationBudget | None = None
    if policy is None:
        pure = _unknown_evidence_decision(
            reason='Tenant Capacity Governance policy is not configured for the selected cluster.',
            committed=committed,
            current=current,
            proposed=proposed,
            positive_change=positive_change,
        )
    elif capacity is None:
        pure = _unknown_evidence_decision(
            reason=capacity_reason,
            committed=committed,
            current=current,
            proposed=proposed,
            positive_change=positive_change,
        )
    else:
        budget = _budget(policy, capacity)
        commitment_reason = _committed_evidence_reason(
            committed,
            unbounded_namespaces,
            budget=budget.available,
        )
        if commitment_reason:
            pure = _unknown_evidence_decision(
                reason=commitment_reason,
                committed=committed,
                current=current,
                proposed=proposed,
                positive_change=positive_change,
            )
        else:
            pure = evaluate_allocation_preflight(
                budget=budget.available,
                committed_before=committed,
                current_allocation=current,
                proposed_allocation=proposed,
                capacity_evidence_available=True,
            )

    decision = _persist_decision(
        cluster_id=cluster_id,
        tenant_environment=tenant_environment,
        tenant=resolved_tenant,
        profile=profile,
        namespace=namespace,
        operation=operation,
        pure=pure,
        evidence=_DecisionEvidenceContext(
            policy=policy,
            budget=budget,
            committed_before=committed,
            current=current,
            proposed=proposed,
            committed_count=committed_count,
            snapshot_result=snapshot_result,
        ),
        allocation_scope=allocation_scope,
    )
    if not pure.allowed:
        db.session.commit()
        raise TenantCapacityBlockedError(pure.reason)
    return decision


def _persist_decision(
    *,
    cluster_id: str,
    tenant_environment: TenantEnvironment | None,
    tenant: Tenant,
    profile: TenantResourceProfile,
    namespace: str,
    operation: str,
    pure: AllocationPreflightDecision,
    evidence: _DecisionEvidenceContext,
    allocation_scope: str,
) -> TenantCapacityDecision:
    record = TenantCapacityDecision()
    record.cluster_id = cluster_id
    record.tenant_environment_id = tenant_environment.id if tenant_environment is not None else None
    record.resource_profile_id = profile.id
    record.resource_profile_version = profile.version
    record.namespace = namespace
    record.operation = operation
    record.decision = pure.decision
    record.capacity_state = pure.state
    record.data_cutoff = _snapshot_cutoff(evidence.snapshot_result)
    record.evidence_json = {
        'version': 1,
        'authority': 'tenant_capacity_governance',
        'allocation_scope': allocation_scope,
        'tenant_id': tenant.id,
        'decision': pure.decision,
        'state': pure.state,
        'reason': pure.reason,
        'positive_change': pure.positive_change,
        'capacity_source': {
            'dataset_key': 'analytics.capacity',
            'snapshot_id': evidence.snapshot_result.snapshot.id
            if evidence.snapshot_result.snapshot is not None
            else None,
            'snapshot_state': evidence.snapshot_result.state,
            'stale': evidence.snapshot_result.stale,
            'data_cutoff': _datetime_text(_snapshot_cutoff(evidence.snapshot_result)),
        },
        'policy': _policy_json(evidence.policy) if evidence.policy is not None else None,
        'allocation': {
            'committed_namespace_count': evidence.committed_count,
            'committed_before': _vector_json(evidence.committed_before),
            'current': _vector_json(evidence.current),
            'proposed': _vector_json(evidence.proposed),
            'projected_committed': _vector_json(pure.projected_committed),
            'projected_headroom': _vector_json(pure.projected_headroom),
            'shortfall': _vector_json(pure.shortfall),
        },
        'budget': _budget_json(evidence.budget) if evidence.budget is not None else None,
    }
    db.session.add(record)
    db.session.flush()
    return record


def _read_capacity_snapshot(cluster_id: str) -> SnapshotResult:
    return read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.capacity',
        parameters={'cluster_id': str(cluster_id), 'time_range': '24h'},
    )


def _capacity_vector(result: SnapshotResult) -> tuple[CapacityVector | None, str]:
    if not result.available:
        return (
            None,
            'Committed Capacity Analytics evidence is unavailable; refresh capacity materialization before allocation.',
        )
    if result.stale:
        return (
            None,
            'Committed Capacity Analytics evidence is stale; refresh capacity materialization before allocation.',
        )

    context = result.context or {}
    summary = context.get('capacity_summary')
    if not isinstance(summary, dict):
        return None, 'Committed Capacity Analytics evidence does not contain a capacity summary.'

    cpu = summary.get('cpu')
    memory = summary.get('memory')
    pods = summary.get('pods')
    if not isinstance(cpu, dict) or not isinstance(memory, dict) or not isinstance(pods, dict):
        return None, 'Committed Capacity Analytics evidence is missing CPU, memory, or Pod capacity.'

    if any(
        resource.get('capacity_evidence_available') is not True
        for resource in (cpu, memory, pods)
    ):
        return (
            None,
            'Committed Capacity Analytics evidence does not contain Ready-worker CPU, memory, and Pod allocatable capacity.',
        )

    try:
        cpu_value = Decimal(str(cpu['capacity']))
        memory_value = Decimal(str(memory['capacity'])) * _GIB
        pods_value = Decimal(str(pods['capacity']))
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return None, 'Committed Capacity Analytics CPU, memory, or Pod capacity is invalid.'
    if cpu_value <= _ZERO or memory_value <= _ZERO or pods_value <= _ZERO:
        return None, 'Committed Capacity Analytics CPU, memory, or Pod allocatable capacity is not positive.'

    return CapacityVector(
        cpu=cpu_value,
        memory_bytes=memory_value,
        pods=pods_value,
        storage_bytes=None,
    ), ''

def _canonical_shared_allocation_quota(
    cluster_id: str,
) -> tuple[dict[str, Mapping[str, object]], list[str]]:
    candidates = (
        TenantAdvancedCapabilityIntent.query.join(
            Tenant,
            TenantAdvancedCapabilityIntent.tenant_id == Tenant.id,
        )
        .filter(
            Tenant.cluster_id == cluster_id,
            TenantAdvancedCapabilityIntent.resource_kind == 'global_resource_quota',
            TenantAdvancedCapabilityIntent.status.in_(
                (
                    TenantAdvancedCapabilityStatus.READY.value,
                    TenantAdvancedCapabilityStatus.DRIFTED.value,
                )
            ),
        )
        .order_by(
            TenantAdvancedCapabilityIntent.tenant_id.asc(),
            TenantAdvancedCapabilityIntent.updated_at.desc(),
        )
        .all()
    )
    selected: dict[str, Mapping[str, object]] = {}
    ambiguous: set[str] = set()
    for intent in candidates:
        evidence = intent.reconciliation_evidence_json or {}
        if evidence.get('allocation_governance_scope') != 'tenant_shared':
            continue
        tenant_id = str(intent.tenant_id)
        if tenant_id in selected:
            ambiguous.add(tenant_id)
            continue
        desired = intent.desired_spec_json or {}
        quota = desired.get('quota') if isinstance(desired, Mapping) else None
        hard = quota.get('hard') if isinstance(quota, Mapping) else None
        selected[tenant_id] = dict(hard) if isinstance(hard, Mapping) else {}
    for tenant_id in ambiguous:
        selected.pop(tenant_id, None)

    capsule_tenants = Tenant.query.filter(
        Tenant.cluster_id == cluster_id,
        Tenant.provider_key == 'capsule',
    ).all()
    for tenant in capsule_tenants:
        governance = (tenant.provider_evidence_json or {}).get('allocation_governance')
        if not isinstance(governance, Mapping):
            continue
        if governance.get('authority') != 'capsule_tenant_resource_quotas':
            continue
        if governance.get('control_state') not in {'kaori_managed', 'drifted'}:
            continue
        if governance.get('allocation_scope') != 'tenant_shared':
            continue
        tenant_id = str(tenant.id)
        quota = governance.get('desired_quota')
        if tenant_id in selected or not isinstance(quota, Mapping):
            ambiguous.add(tenant_id)
            selected.pop(tenant_id, None)
            continue
        selected[tenant_id] = dict(quota)

    for tenant_id in ambiguous:
        selected.pop(tenant_id, None)
    return selected, sorted(ambiguous)


def _aggregate_committed_allocation(
    rows: list[TenantNamespace],
    *,
    shared_quota_by_tenant: Mapping[str, Mapping[str, object]],
    ambiguous_shared_tenants: list[str] | None = None,
) -> tuple[CapacityVector, list[str]]:
    totals: list[Decimal | None] = [_ZERO, _ZERO, _ZERO, _ZERO]
    unbounded: list[str] = []
    shared_tenant_ids = set(shared_quota_by_tenant)

    def add_vector(vector: CapacityVector, label: str) -> None:
        values = (vector.cpu, vector.memory_bytes, vector.pods, vector.storage_bytes)
        if any(value is None for value in values):
            unbounded.append(label)
        for index, value in enumerate(values):
            if totals[index] is not None:
                totals[index] = totals[index] + value if value is not None else None

    for row in rows:
        tenant_id = str(row.environment.tenant_id)
        if tenant_id in shared_tenant_ids:
            continue
        add_vector(quota_request_vector(row.allocation_quota_json or {}), row.namespace)

    for tenant_id, quota in shared_quota_by_tenant.items():
        add_vector(
            quota_request_vector(quota),
            f'Tenant/{tenant_id} shared allocation',
        )

    for tenant_id in ambiguous_shared_tenants or []:
        unbounded.append(f'Tenant/{tenant_id} ambiguous shared allocation')
        totals = [None, None, None, None]

    return CapacityVector(
        cpu=totals[0],
        memory_bytes=totals[1],
        pods=totals[2],
        storage_bytes=totals[3],
    ), unbounded

def _committed_tenant_allocation(
    cluster_id: str,
    *,
    shared_overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[CapacityVector, int, list[str]]:
    rows = (
        TenantNamespace.query.filter(
            TenantNamespace.cluster_id == cluster_id,
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .order_by(TenantNamespace.namespace.asc())
        .all()
    )
    shared, ambiguous = _canonical_shared_allocation_quota(cluster_id)
    for tenant_id, quota in dict(shared_overrides or {}).items():
        shared[str(tenant_id)] = dict(quota)
        if str(tenant_id) in ambiguous:
            ambiguous.remove(str(tenant_id))

    committed, unbounded = _aggregate_committed_allocation(
        rows,
        shared_quota_by_tenant=shared,
        ambiguous_shared_tenants=ambiguous,
    )
    return committed, len(rows), unbounded


def _committed_evidence_reason(
    committed: CapacityVector,
    unbounded_namespaces: list[str] | None = None,
    *,
    budget: CapacityVector | None = None,
) -> str | None:
    governed = budget or CapacityVector(cpu=_ZERO, memory_bytes=_ZERO)
    required = (
        ('CPU', governed.cpu, committed.cpu),
        ('memory', governed.memory_bytes, committed.memory_bytes),
        ('Pods', governed.pods, committed.pods),
        ('storage', governed.storage_bytes, committed.storage_bytes),
    )
    missing = [label for label, limit, value in required if limit is not None and value is None]
    if not missing:
        return None

    names = list(unbounded_namespaces or [])
    dimensions = ', '.join(missing)
    if names:
        visible = ', '.join(names[:3])
        suffix = f' +{len(names) - 3} more' if len(names) > 3 else ''
        return (
            f'Unbounded or missing governed {dimensions} commitment on active Namespace(s): '
            f'{visible}{suffix}. Apply a bounded Resource Profile allocation before positive changes.'
        )
    return (
        f'At least one active Tenant allocation has unbounded or missing governed {dimensions} commitment; '
        'Committed and Headroom cannot be proven until the allocation contract is bounded.'
    )


def _budget(policy: TenantCapacityPolicy, capacity: CapacityVector) -> TenantAllocationBudget:
    storage_budget = (
        _quantity(policy.tenant_storage_budget)
        if policy.tenant_storage_budget not in (None, '')
        else None
    )
    return build_tenant_allocation_budget(
        allocatable=capacity,
        reserve=CapacityVector(
            cpu=_quantity(policy.platform_reserve_cpu),
            memory_bytes=_quantity(policy.platform_reserve_memory),
            pods=Decimal(policy.platform_reserve_pods),
        ),
        safety_headroom_percent=Decimal(policy.safety_headroom_percent),
        unmanaged=CapacityVector(
            cpu=_quantity(policy.unmanaged_commitment_cpu),
            memory_bytes=_quantity(policy.unmanaged_commitment_memory),
            pods=Decimal(policy.unmanaged_commitment_pods),
        ),
        logical_storage_budget=storage_budget,
    )

def _unknown_evidence_decision(
    *,
    reason: str,
    committed: CapacityVector,
    current: CapacityVector,
    proposed: CapacityVector,
    positive_change: bool,
) -> AllocationPreflightDecision:
    projected = _project(committed, current, proposed)
    return AllocationPreflightDecision(
        allowed=not positive_change,
        decision='block' if positive_change else 'allow',
        state='Unknown',
        reason=(
            reason
            if positive_change
            else f'{reason} This non-increasing allocation change is allowed because it does not add commitment.'
        ),
        projected_committed=projected,
        projected_headroom=CapacityVector(cpu=None, memory_bytes=None, pods=None, storage_bytes=None),
        shortfall=CapacityVector(cpu=None, memory_bytes=None, pods=None, storage_bytes=None),
        positive_change=positive_change,
    )


def _project(
    committed: CapacityVector,
    current: CapacityVector,
    proposed: CapacityVector,
) -> CapacityVector:
    return CapacityVector(
        cpu=_project_dimension(committed.cpu, current.cpu, proposed.cpu),
        memory_bytes=_project_dimension(committed.memory_bytes, current.memory_bytes, proposed.memory_bytes),
        pods=_project_dimension(committed.pods, current.pods, proposed.pods),
        storage_bytes=_project_dimension(
            committed.storage_bytes,
            current.storage_bytes,
            proposed.storage_bytes,
        ),
    )


def _project_dimension(
    committed: Decimal | None,
    current: Decimal | None,
    proposed: Decimal | None,
) -> Decimal | None:
    if committed is None or current is None or proposed is None:
        return None
    return max(committed - current + proposed, _ZERO)


def _headroom(budget: CapacityVector, committed: CapacityVector) -> CapacityVector:
    return CapacityVector(
        cpu=_difference(budget.cpu, committed.cpu),
        memory_bytes=_difference(budget.memory_bytes, committed.memory_bytes),
        pods=_difference(budget.pods, committed.pods),
        storage_bytes=_difference(budget.storage_bytes, committed.storage_bytes),
    )


def _difference(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


def _nonnegative_quantity(value: object | None, *, label: str) -> str:
    rendered = str(value or '0').strip() or '0'
    try:
        parsed = Decimal(parse_quantity(rendered))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be a valid Kubernetes resource quantity.') from exc
    if parsed < _ZERO:
        raise ValueError(f'{label} cannot be negative.')
    return rendered


def _optional_positive_quantity(value: object | None, *, label: str) -> str | None:
    rendered = str(value or '').strip()
    if not rendered:
        return None
    try:
        parsed = Decimal(parse_quantity(rendered))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be a valid Kubernetes resource quantity.') from exc
    if parsed <= _ZERO:
        raise ValueError(f'{label} must be greater than zero when configured.')
    return rendered


def _nonnegative_integer(value: object | None, *, label: str) -> int:
    rendered = str(value or '0').strip() or '0'
    if not rendered.isdigit():
        raise ValueError(f'{label} must be a non-negative integer.')
    return int(rendered)


def _quantity(value: object) -> Decimal:
    try:
        return Decimal(parse_quantity(str(value).strip()))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Stored Tenant Capacity Governance policy contains an invalid quantity.') from exc


def _percent(value: object | None) -> int:
    rendered = str(value or '').strip()
    if not rendered.isdigit():
        raise ValueError('Safety headroom must be a whole percentage from 0 to 99.')
    parsed = int(rendered)
    if parsed < 0 or parsed >= 100:
        raise ValueError('Safety headroom must be a whole percentage from 0 to 99.')
    return parsed


def _policy_json(policy: TenantCapacityPolicy) -> dict[str, Any]:
    return {
        'cluster_id': policy.cluster_id,
        'platform_reserve_cpu': policy.platform_reserve_cpu,
        'platform_reserve_memory': policy.platform_reserve_memory,
        'platform_reserve_pods': policy.platform_reserve_pods,
        'safety_headroom_percent': policy.safety_headroom_percent,
        'unmanaged_commitment_cpu': policy.unmanaged_commitment_cpu,
        'unmanaged_commitment_memory': policy.unmanaged_commitment_memory,
        'unmanaged_commitment_pods': policy.unmanaged_commitment_pods,
        'tenant_storage_budget': policy.tenant_storage_budget,
    }


def _budget_json(budget: TenantAllocationBudget) -> dict[str, Any]:
    return {
        'allocatable': _vector_json(budget.allocatable),
        'reserve': _vector_json(budget.reserve),
        'safety_headroom': _vector_json(budget.safety_headroom),
        'unmanaged': _vector_json(budget.unmanaged),
        'logical_storage_budget_bytes': _decimal_text(budget.logical_storage_budget),
        'available': _vector_json(budget.available),
    }


def _vector_json(vector: CapacityVector) -> dict[str, str | None]:
    return {
        'cpu': _decimal_text(vector.cpu),
        'memory_bytes': _decimal_text(vector.memory_bytes),
        'pods': _decimal_text(vector.pods),
        'storage_bytes': _decimal_text(vector.storage_bytes),
    }


def _vector_display(vector: CapacityVector) -> dict[str, str]:
    return {
        'cpu': _display_cpu(vector.cpu),
        'memory': _display_memory(vector.memory_bytes),
        'pods': _display_pods(vector.pods),
        'storage': _display_storage(vector.storage_bytes),
    }


def _display_cpu(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{value.quantize(Decimal("0.01"))} cores'


def _display_memory(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{(value / _GIB).quantize(Decimal("0.01"))} GiB'


def _display_pods(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{value.quantize(Decimal("1"))} pods'


def _display_storage(value: Decimal | None) -> str:
    return 'Not Governed' if value is None else f'{(value / _GIB).quantize(Decimal("0.01"))} GiB'


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, 'f')


def _snapshot_cutoff(result: SnapshotResult) -> datetime | None:
    return result.snapshot.generated_at if result.snapshot is not None else None


def _datetime_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _state_reason(state: str) -> str:
    return {
        'Healthy': 'Governed Tenant allocation retains more than 40% capacity-budget headroom.',
        'Near Capacity': 'Governed Tenant allocation has 40% or less capacity-budget headroom.',
        'Critical': 'Governed Tenant allocation has 15% or less capacity-budget headroom.',
        'Exhausted': 'Governed Tenant allocation has no remaining capacity-budget headroom.',
        'Overcommitted': 'Committed Tenant allocation exceeds the governed capacity budget.',
        'Unknown': 'Required capacity or commitment evidence is incomplete.',
    }[state]


def _text(source: Mapping[str, Any], key: str) -> str:
    return str(source.get(key) or '').strip()
