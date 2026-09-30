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
    unmanaged_cpu = _nonnegative_quantity(
        source.get('unmanaged_commitment_cpu'),
        label='Unmanaged commitment CPU',
    )
    unmanaged_memory = _nonnegative_quantity(
        source.get('unmanaged_commitment_memory'),
        label='Unmanaged commitment memory',
    )
    safety_headroom_percent = _percent(source.get('safety_headroom_percent'))

    policy = TenantCapacityPolicy.query.filter_by(cluster_id=cluster.id).first()
    if policy is None:
        policy = TenantCapacityPolicy()
        policy.cluster_id = cluster.id
        db.session.add(policy)

    policy.platform_reserve_cpu = reserve_cpu
    policy.platform_reserve_memory = reserve_memory
    policy.safety_headroom_percent = safety_headroom_percent
    policy.unmanaged_commitment_cpu = unmanaged_cpu
    policy.unmanaged_commitment_memory = unmanaged_memory
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
    commitment_reason = _committed_evidence_reason(committed, unbounded_namespaces)
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
        current=CapacityVector(cpu=_ZERO, memory_bytes=_ZERO),
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
    tenant_environment: TenantEnvironment,
    profile: TenantResourceProfile,
    current_quota_hard: Mapping[str, object],
    proposed_quota_hard: Mapping[str, object],
) -> TenantCapacityDecision:
    """Evaluate one Tenant-level shared quota exactly once across its namespaces."""

    tenant = tenant_environment.tenant
    current = quota_request_vector(current_quota_hard)
    proposed = quota_request_vector(proposed_quota_hard)
    operation = classify_allocation_change(current=current, proposed=proposed)
    committed_state = _committed_tenant_allocation(
        tenant.cluster_id,
        shared_overrides={tenant.id: current_quota_hard},
    )
    return _enforce_allocation_preflight(
        tenant_environment=tenant_environment,
        profile=profile,
        namespace=f'@tenant:{tenant.slug}',
        current=current,
        proposed=proposed,
        operation=operation,
        committed_state=committed_state,
        allocation_scope='tenant_shared',
    )


def _enforce_allocation_preflight(
    *,
    tenant_environment: TenantEnvironment,
    profile: TenantResourceProfile,
    namespace: str,
    current: CapacityVector,
    proposed: CapacityVector,
    operation: str,
    committed_state: tuple[CapacityVector, int, list[str]] | None = None,
    allocation_scope: str = 'namespace',
) -> TenantCapacityDecision:
    cluster_id = tenant_environment.tenant.cluster_id
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
        if committed.cpu is None or committed.memory_bytes is None:
            pure = _unknown_evidence_decision(
                reason=_committed_evidence_reason(committed, unbounded_namespaces)
                or 'Committed Tenant allocation is incomplete; positive allocation cannot be proven safe.',
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
    tenant_environment: TenantEnvironment,
    profile: TenantResourceProfile,
    namespace: str,
    operation: str,
    pure: AllocationPreflightDecision,
    evidence: _DecisionEvidenceContext,
    allocation_scope: str,
) -> TenantCapacityDecision:
    record = TenantCapacityDecision()
    record.cluster_id = cluster_id
    record.tenant_environment_id = tenant_environment.id
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
        'tenant_id': tenant_environment.tenant_id,
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
    if not isinstance(cpu, dict) or not isinstance(memory, dict):
        return None, 'Committed Capacity Analytics evidence is missing CPU or memory capacity.'

    if cpu.get('capacity_evidence_available') is not True or memory.get('capacity_evidence_available') is not True:
        return (
            None,
            'Committed Capacity Analytics evidence does not contain Ready-worker CPU and memory allocatable capacity.',
        )

    try:
        cpu_value = Decimal(str(cpu['capacity']))
        memory_value = Decimal(str(memory['capacity'])) * _GIB
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return None, 'Committed Capacity Analytics CPU or memory capacity is invalid.'
    if cpu_value <= _ZERO or memory_value <= _ZERO:
        return None, 'Committed Capacity Analytics CPU or memory allocatable capacity is not positive.'

    return CapacityVector(cpu=cpu_value, memory_bytes=memory_value), ''


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
    return selected, sorted(ambiguous)


def _aggregate_committed_allocation(
    rows: list[TenantNamespace],
    *,
    shared_quota_by_tenant: Mapping[str, Mapping[str, object]],
    ambiguous_shared_tenants: list[str] | None = None,
) -> tuple[CapacityVector, list[str]]:
    cpu_total: Decimal | None = _ZERO
    memory_total: Decimal | None = _ZERO
    unbounded: list[str] = []
    shared_tenant_ids = set(shared_quota_by_tenant)

    for row in rows:
        tenant_id = str(row.environment.tenant_id)
        if tenant_id in shared_tenant_ids:
            continue
        vector = quota_request_vector(row.allocation_quota_json or {})
        if vector.cpu is None or vector.memory_bytes is None:
            unbounded.append(row.namespace)
        if cpu_total is not None:
            cpu_total = cpu_total + vector.cpu if vector.cpu is not None else None
        if memory_total is not None:
            memory_total = memory_total + vector.memory_bytes if vector.memory_bytes is not None else None

    for tenant_id, quota in shared_quota_by_tenant.items():
        vector = quota_request_vector(quota)
        if vector.cpu is None or vector.memory_bytes is None:
            unbounded.append(f'Tenant/{tenant_id} shared allocation')
        if cpu_total is not None:
            cpu_total = cpu_total + vector.cpu if vector.cpu is not None else None
        if memory_total is not None:
            memory_total = memory_total + vector.memory_bytes if vector.memory_bytes is not None else None

    for tenant_id in ambiguous_shared_tenants or []:
        unbounded.append(f'Tenant/{tenant_id} ambiguous shared allocation')
        cpu_total = None
        memory_total = None

    return CapacityVector(cpu=cpu_total, memory_bytes=memory_total), unbounded


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
) -> str | None:
    if committed.cpu is None or committed.memory_bytes is None:
        names = list(unbounded_namespaces or [])
        if names:
            visible = ', '.join(names[:3])
            suffix = f' +{len(names) - 3} more' if len(names) > 3 else ''
            return (
                'Unbounded or missing CPU/memory request commitment on active Namespace(s): '
                f'{visible}{suffix}. Apply a bounded Resource Profile allocation before positive changes.'
            )
        return (
            'At least one active Tenant namespace has an unbounded or missing CPU/memory request commitment; '
            'Committed and Headroom cannot be proven until the allocation contract is bounded.'
        )
    return None


def _budget(policy: TenantCapacityPolicy, capacity: CapacityVector) -> TenantAllocationBudget:
    return build_tenant_allocation_budget(
        allocatable=capacity,
        reserve=CapacityVector(
            cpu=_quantity(policy.platform_reserve_cpu),
            memory_bytes=_quantity(policy.platform_reserve_memory),
        ),
        safety_headroom_percent=Decimal(policy.safety_headroom_percent),
        unmanaged=CapacityVector(
            cpu=_quantity(policy.unmanaged_commitment_cpu),
            memory_bytes=_quantity(policy.unmanaged_commitment_memory),
        ),
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
        projected_headroom=CapacityVector(cpu=None, memory_bytes=None),
        shortfall=CapacityVector(cpu=None, memory_bytes=None),
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
        'safety_headroom_percent': policy.safety_headroom_percent,
        'unmanaged_commitment_cpu': policy.unmanaged_commitment_cpu,
        'unmanaged_commitment_memory': policy.unmanaged_commitment_memory,
    }


def _budget_json(budget: TenantAllocationBudget) -> dict[str, Any]:
    return {
        'allocatable': _vector_json(budget.allocatable),
        'reserve': _vector_json(budget.reserve),
        'safety_headroom': _vector_json(budget.safety_headroom),
        'unmanaged': _vector_json(budget.unmanaged),
        'available': _vector_json(budget.available),
    }


def _vector_json(vector: CapacityVector) -> dict[str, str | None]:
    return {
        'cpu': _decimal_text(vector.cpu),
        'memory_bytes': _decimal_text(vector.memory_bytes),
    }


def _vector_display(vector: CapacityVector) -> dict[str, str]:
    return {
        'cpu': _display_cpu(vector.cpu),
        'memory': _display_memory(vector.memory_bytes),
    }


def _display_cpu(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{value.quantize(Decimal("0.01"))} cores'


def _display_memory(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{(value / _GIB).quantize(Decimal("0.01"))} GiB'


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, 'f')


def _snapshot_cutoff(result: SnapshotResult) -> datetime | None:
    return result.snapshot.generated_at if result.snapshot is not None else None


def _datetime_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _state_reason(state: str) -> str:
    return {
        'Healthy': 'Governed Tenant allocation retains more than 40% request-budget headroom.',
        'Near Capacity': 'Governed Tenant allocation has 40% or less request-budget headroom.',
        'Critical': 'Governed Tenant allocation has 15% or less request-budget headroom.',
        'Exhausted': 'Governed Tenant allocation has no remaining request-budget headroom.',
        'Overcommitted': 'Committed Tenant allocation exceeds the governed request budget.',
        'Unknown': 'Required capacity or commitment evidence is incomplete.',
    }[state]


def _text(source: Mapping[str, Any], key: str) -> str:
    return str(source.get(key) or '').strip()
