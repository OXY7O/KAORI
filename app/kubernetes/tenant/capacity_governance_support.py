from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from kubernetes.utils.quantity import parse_quantity

from app.kubernetes.analytics.materialization.service import SnapshotResult
from app.kubernetes.tenant.capacity import (
    AllocationPreflightDecision,
    CapacityVector,
    TenantAllocationBudget,
    build_tenant_allocation_budget,
)
from app.models.tenant import TenantCapacityPolicy

_GIB = Decimal(1024**3)
_ZERO = Decimal('0')


def _budget(policy: TenantCapacityPolicy, capacity: CapacityVector) -> TenantAllocationBudget:
    storage_budget = _quantity(policy.tenant_storage_budget) if policy.tenant_storage_budget not in (None, '') else None
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


def _optional_positive_gib_quantity(value: object | None, *, label: str) -> str | None:
    rendered = str(value or '').strip()
    if not rendered:
        return None
    try:
        parsed = Decimal(rendered)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be a positive numeric GiB value.') from exc
    if parsed <= _ZERO:
        raise ValueError(f'{label} must be greater than zero when configured.')
    return f'{format(parsed.normalize(), "f")}Gi'


def _quantity_gib_text(value: object | None) -> str | None:
    if value in (None, ''):
        return None
    gib = _quantity(value) / _GIB
    return format(gib.normalize(), 'f')


def _logical_storage_budget_vector(policy: TenantCapacityPolicy) -> CapacityVector:
    storage_budget = _quantity(policy.tenant_storage_budget) if policy.tenant_storage_budget not in (None, '') else None
    return CapacityVector(
        cpu=None,
        memory_bytes=None,
        pods=None,
        storage_bytes=storage_budget,
    )


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
        'tenant_storage_budget_gib': _quantity_gib_text(policy.tenant_storage_budget),
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
