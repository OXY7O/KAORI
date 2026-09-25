from __future__ import annotations

from collections.abc import Mapping
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
    classify_capacity_state,
    evaluate_allocation_preflight,
    quota_request_vector,
)
from app.models import Cluster
from app.models.tenant import (
    TenantCapacityDecision,
    TenantCapacityPolicy,
    TenantEnvironment,
    TenantNamespace,
    TenantResourceProfile,
)

_GIB = Decimal(1024**3)
_ZERO = Decimal('0')


class TenantCapacityBlockedError(ValueError):
    """Tenant allocation was denied before any provider reconciliation."""


class TenantCapacityStateConflictError(RuntimeError):
    """Tenant capacity policy persistence failed before provider reconciliation."""


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
    committed, committed_count = _committed_tenant_allocation(cluster_id)

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
    state = classify_capacity_state(budget=budget.available, committed=committed)
    return {
        'cluster_id': cluster_id,
        'state': state,
        'reason': _state_reason(state),
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
    cluster_id = tenant_environment.tenant.cluster_id
    proposed = quota_request_vector(quota_hard)
    current = CapacityVector(cpu=_ZERO, memory_bytes=_ZERO)
    committed, committed_count = _committed_tenant_allocation(cluster_id)
    policy = TenantCapacityPolicy.query.filter_by(cluster_id=cluster_id).first()
    snapshot_result = _read_capacity_snapshot(cluster_id)
    capacity, capacity_reason = _capacity_vector(snapshot_result)

    budget: TenantAllocationBudget | None = None
    if policy is None:
        pure = _blocked_decision(
            reason='Tenant Capacity Governance policy is not configured for the selected cluster.',
            committed=committed,
            current=current,
            proposed=proposed,
        )
    elif capacity is None:
        pure = _blocked_decision(
            reason=capacity_reason,
            committed=committed,
            current=current,
            proposed=proposed,
        )
    elif committed.cpu is None or committed.memory_bytes is None:
        pure = _blocked_decision(
            reason=(
                'Committed Tenant allocation contains an unbounded CPU or memory request dimension; '
                'positive allocation cannot be proven safe.'
            ),
            committed=committed,
            current=current,
            proposed=proposed,
        )
        budget = _budget(policy, capacity)
    else:
        budget = _budget(policy, capacity)
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
        operation='create',
        pure=pure,
        policy=policy,
        budget=budget,
        committed_before=committed,
        current=current,
        proposed=proposed,
        committed_count=committed_count,
        snapshot_result=snapshot_result,
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
    policy: TenantCapacityPolicy | None,
    budget: TenantAllocationBudget | None,
    committed_before: CapacityVector,
    current: CapacityVector,
    proposed: CapacityVector,
    committed_count: int,
    snapshot_result: SnapshotResult,
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
    record.data_cutoff = _snapshot_cutoff(snapshot_result)
    record.evidence_json = {
        'version': 1,
        'authority': 'tenant_capacity_governance',
        'decision': pure.decision,
        'state': pure.state,
        'reason': pure.reason,
        'positive_change': pure.positive_change,
        'capacity_source': {
            'dataset_key': 'analytics.capacity',
            'snapshot_id': snapshot_result.snapshot.id if snapshot_result.snapshot is not None else None,
            'snapshot_state': snapshot_result.state,
            'stale': snapshot_result.stale,
            'data_cutoff': _datetime_text(_snapshot_cutoff(snapshot_result)),
        },
        'policy': _policy_json(policy) if policy is not None else None,
        'allocation': {
            'committed_namespace_count': committed_count,
            'committed_before': _vector_json(committed_before),
            'current': _vector_json(current),
            'proposed': _vector_json(proposed),
            'projected_committed': _vector_json(pure.projected_committed),
            'projected_headroom': _vector_json(pure.projected_headroom),
            'shortfall': _vector_json(pure.shortfall),
        },
        'budget': _budget_json(budget) if budget is not None else None,
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


def _committed_tenant_allocation(cluster_id: str) -> tuple[CapacityVector, int]:
    rows = TenantNamespace.query.filter_by(cluster_id=cluster_id).all()
    cpu_total: Decimal | None = _ZERO
    memory_total: Decimal | None = _ZERO

    for row in rows:
        vector = quota_request_vector(row.allocation_quota_json or {})
        if cpu_total is not None:
            cpu_total = cpu_total + vector.cpu if vector.cpu is not None else None
        if memory_total is not None:
            memory_total = memory_total + vector.memory_bytes if vector.memory_bytes is not None else None

    return CapacityVector(cpu=cpu_total, memory_bytes=memory_total), len(rows)


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


def _blocked_decision(
    *,
    reason: str,
    committed: CapacityVector,
    current: CapacityVector,
    proposed: CapacityVector,
) -> AllocationPreflightDecision:
    projected = _project(committed, current, proposed)
    return AllocationPreflightDecision(
        allowed=False,
        decision='block',
        state='Unknown',
        reason=reason,
        projected_committed=projected,
        projected_headroom=CapacityVector(cpu=None, memory_bytes=None),
        shortfall=CapacityVector(cpu=None, memory_bytes=None),
        positive_change=True,
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
