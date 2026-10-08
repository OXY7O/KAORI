from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.analytics.materialization.service import SnapshotResult, read_snapshot, read_snapshots
from app.kubernetes.tenant.capacity import (
    AllocationPreflightDecision,
    CapacityVector,
    TenantAllocationBudget,
    classify_allocation_change,
    classify_capacity_state,
    evaluate_allocation_preflight,
    quota_request_vector,
)
from app.kubernetes.tenant.capacity_allocation_state import (
    _aggregate_committed_allocation,
    _canonical_shared_allocation_quota,
    _committed_tenant_allocation,
    _committed_tenant_allocations,
)
from app.kubernetes.tenant.capacity_governance_support import (
    _GIB,
    _budget,
    _budget_json,
    _committed_evidence_reason,
    _datetime_text,
    _headroom,
    _logical_storage_budget_vector,
    _nonnegative_integer,
    _nonnegative_quantity,
    _optional_positive_gib_quantity,
    _optional_positive_quantity,
    _percent,
    _policy_json,
    _snapshot_cutoff,
    _state_reason,
    _text,
    _unknown_evidence_decision,
    _vector_display,
    _vector_json,
)
from app.kubernetes.tenant.capacity_governance_support import (
    _quantity_gib_text as _quantity_gib_text,
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


@dataclass(frozen=True, slots=True)
class _AllocationRequest:
    profile: TenantResourceProfile
    namespace: str
    current: CapacityVector
    proposed: CapacityVector
    operation: str
    allocation_scope: str = 'namespace'


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
    if 'tenant_storage_budget_gib' in source:
        tenant_storage_budget = _optional_positive_gib_quantity(
            source.get('tenant_storage_budget_gib'),
            label='Tenant Storage Budget',
        )
    else:
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


def _build_capacity_governance_summary_from_inputs(
    cluster_id: str,
    *,
    policy: TenantCapacityPolicy | None,
    snapshot_result: SnapshotResult,
    committed_state: tuple[CapacityVector, int, list[str]],
) -> dict[str, Any]:
    committed, committed_count, unbounded_namespaces = committed_state

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
        logical_budget = _logical_storage_budget_vector(policy)
        logical_headroom = _headroom(logical_budget, committed)
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
            'headroom': _vector_json(logical_headroom),
            'display': {
                'committed': _vector_display(committed),
                'budget': _vector_display(logical_budget),
                'headroom': _vector_display(logical_headroom),
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


def build_capacity_governance_summary(cluster_id: str) -> dict[str, Any]:
    return _build_capacity_governance_summary_from_inputs(
        cluster_id,
        policy=TenantCapacityPolicy.query.filter_by(cluster_id=cluster_id).first(),
        snapshot_result=_read_capacity_snapshot(cluster_id),
        committed_state=_committed_tenant_allocation(cluster_id),
    )


def build_capacity_governance_summaries(cluster_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Build read-only fleet summaries while batching KAORI-owned committed evidence."""

    normalized_ids = list(dict.fromkeys(str(cluster_id) for cluster_id in cluster_ids if str(cluster_id)))
    if not normalized_ids:
        return {}

    policies = {
        str(policy.cluster_id): policy
        for policy in TenantCapacityPolicy.query.filter(TenantCapacityPolicy.cluster_id.in_(normalized_ids)).all()
    }
    committed_states = _committed_tenant_allocations(normalized_ids)
    snapshots = _read_capacity_snapshots(normalized_ids)
    return {
        cluster_id: _build_capacity_governance_summary_from_inputs(
            cluster_id,
            policy=policies.get(cluster_id),
            snapshot_result=snapshots[cluster_id],
            committed_state=committed_states[cluster_id],
        )
        for cluster_id in normalized_ids
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
        request=_AllocationRequest(
            profile=profile,
            namespace=namespace,
            current=CapacityVector(cpu=_ZERO, memory_bytes=_ZERO, pods=_ZERO, storage_bytes=_ZERO),
            proposed=quota_request_vector(quota_hard),
            operation='create',
        ),
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
        request=_AllocationRequest(
            profile=profile,
            namespace=record.namespace,
            current=current,
            proposed=proposed,
            operation=operation,
        ),
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
        request=_AllocationRequest(
            profile=profile,
            namespace=record.namespace,
            current=current,
            proposed=proposed,
            operation=operation,
        ),
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
        request=_AllocationRequest(
            profile=profile,
            namespace=f'@tenant:{tenant.slug}',
            current=current,
            proposed=proposed,
            operation=operation,
            allocation_scope='tenant_shared',
        ),
        committed_state=committed_state,
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
    if any(value is None for value in (override.cpu, override.memory_bytes, override.pods)):
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
        request=_AllocationRequest(
            profile=profile,
            namespace=f'@tenant:{tenant.slug}:resource-quotas',
            current=current,
            proposed=proposed,
            operation=operation,
            allocation_scope=(
                'tenant_shared' if str(proposed_scope or 'Tenant') == 'Tenant' else 'tenant_namespace_template'
            ),
        ),
        committed_state=committed_state,
    )


def _enforce_allocation_preflight(
    *,
    tenant_environment: TenantEnvironment | None,
    request: _AllocationRequest,
    tenant: Tenant | None = None,
    committed_state: tuple[CapacityVector, int, list[str]] | None = None,
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
    positive_change = request.operation in {'create', 'increase'}

    budget: TenantAllocationBudget | None = None
    if policy is None:
        pure = _unknown_evidence_decision(
            reason='Tenant Capacity Governance policy is not configured for the selected cluster.',
            committed=committed,
            current=request.current,
            proposed=request.proposed,
            positive_change=positive_change,
        )
    elif capacity is None:
        pure = _unknown_evidence_decision(
            reason=capacity_reason,
            committed=committed,
            current=request.current,
            proposed=request.proposed,
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
                current=request.current,
                proposed=request.proposed,
                positive_change=positive_change,
            )
        else:
            pure = evaluate_allocation_preflight(
                budget=budget.available,
                committed_before=committed,
                current_allocation=request.current,
                proposed_allocation=request.proposed,
                capacity_evidence_available=True,
            )

    decision = _persist_decision(
        cluster_id=cluster_id,
        tenant_environment=tenant_environment,
        tenant=resolved_tenant,
        request=request,
        pure=pure,
        evidence=_DecisionEvidenceContext(
            policy=policy,
            budget=budget,
            committed_before=committed,
            current=request.current,
            proposed=request.proposed,
            committed_count=committed_count,
            snapshot_result=snapshot_result,
        ),
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
    request: _AllocationRequest,
    pure: AllocationPreflightDecision,
    evidence: _DecisionEvidenceContext,
) -> TenantCapacityDecision:
    record = TenantCapacityDecision()
    record.cluster_id = cluster_id
    record.tenant_environment_id = tenant_environment.id if tenant_environment is not None else None
    record.resource_profile_id = request.profile.id
    record.resource_profile_version = request.profile.version
    record.namespace = request.namespace
    record.operation = request.operation
    record.decision = pure.decision
    record.capacity_state = pure.state
    record.data_cutoff = _snapshot_cutoff(evidence.snapshot_result)
    record.evidence_json = {
        'version': 1,
        'authority': 'tenant_capacity_governance',
        'allocation_scope': request.allocation_scope,
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


def _read_capacity_snapshots(cluster_ids: list[str]) -> dict[str, SnapshotResult]:
    return read_snapshots(
        dataset_key='analytics.capacity',
        parameters_by_cluster={
            str(cluster_id): {'cluster_id': str(cluster_id), 'time_range': '24h'} for cluster_id in cluster_ids
        },
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

    if any(resource.get('capacity_evidence_available') is not True for resource in (cpu, memory, pods)):
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
