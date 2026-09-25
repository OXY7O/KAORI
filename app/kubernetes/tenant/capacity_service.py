from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.analytics.materialization.service import read_snapshot
from app.kubernetes.tenant.capacity import (
    CapacityPolicyValues,
    CapacityPreflightResult,
    CapacityVector,
    bytes_to_gib_decimal,
    decimal_text,
    evaluate_preflight,
    parse_cpu_quantity,
    parse_memory_quantity,
    quota_requests,
)
from app.models import (
    Cluster,
    TenantCapacityDecision,
    TenantCapacityPolicy,
    TenantEnvironment,
    TenantNamespace,
    TenantResourceProfile,
)

_GIB = Decimal(1024**3)
_DEFAULT_SAFETY_HEADROOM_PERCENT = 10
_DEFAULT_QUANTITY = '0'


class TenantCapacityDeniedError(ValueError):
    pass


class TenantCapacityPolicyConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CapacitySnapshotEvidence:
    allocatable: CapacityVector
    state: str
    snapshot_id: int | None
    generated_at: Any | None


def _text(source: Mapping[str, Any], key: str) -> str:
    value = source.get(key)
    return str(value).strip() if value is not None else ''


def _normalized_nonnegative_quantity(value: object, *, field: str) -> str:
    rendered = str(value).strip()
    if not rendered:
        return _DEFAULT_QUANTITY
    parsed = parse_cpu_quantity(rendered)
    if parsed is None:
        raise ValueError(f'{field} must be a non-negative Kubernetes resource quantity.')
    return rendered


def _headroom_percent(value: object) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError('Safety headroom must be a whole-number percentage from 0 to 100.') from exc
    if parsed < 0 or parsed > 100:
        raise ValueError('Safety headroom must be a whole-number percentage from 0 to 100.')
    return parsed


def get_capacity_policy(cluster_id: str) -> TenantCapacityPolicy | None:
    return TenantCapacityPolicy.query.filter_by(cluster_id=cluster_id).first()


def capacity_policy_contract(policy: TenantCapacityPolicy | None) -> dict[str, Any]:
    return {
        'system_reserved_cpu': policy.system_reserved_cpu if policy else _DEFAULT_QUANTITY,
        'system_reserved_memory': policy.system_reserved_memory if policy else _DEFAULT_QUANTITY,
        'safety_headroom_percent': (
            int(policy.safety_headroom_percent) if policy else _DEFAULT_SAFETY_HEADROOM_PERCENT
        ),
        'unmanaged_cpu_requests': policy.unmanaged_cpu_requests if policy else _DEFAULT_QUANTITY,
        'unmanaged_memory_requests': policy.unmanaged_memory_requests if policy else _DEFAULT_QUANTITY,
        'version': int(policy.version) if policy else 1,
        'source': 'persisted' if policy else 'default_policy_v1',
    }


def _policy_values(contract: Mapping[str, Any]) -> CapacityPolicyValues:
    try:
        safety = Decimal(str(contract['safety_headroom_percent']))
    except (InvalidOperation, KeyError) as exc:
        raise ValueError('Tenant Capacity Policy has invalid safety-headroom evidence.') from exc

    reserved = CapacityVector(
        parse_cpu_quantity(contract.get('system_reserved_cpu')),
        parse_memory_quantity(contract.get('system_reserved_memory')),
    )
    unmanaged = CapacityVector(
        parse_cpu_quantity(contract.get('unmanaged_cpu_requests')),
        parse_memory_quantity(contract.get('unmanaged_memory_requests')),
    )
    if not reserved.complete or not unmanaged.complete:
        raise ValueError('Tenant Capacity Policy contains an invalid CPU or memory quantity.')
    return CapacityPolicyValues(
        system_reserved=reserved,
        unmanaged_commitment=unmanaged,
        safety_headroom_percent=safety,
    )


def update_capacity_policy(source: Mapping[str, Any]) -> TenantCapacityPolicy:
    cluster_id = _text(source, 'cluster_id')
    cluster = db.session.get(Cluster, cluster_id)
    if cluster is None:
        raise ValueError('Select an existing Kubernetes cluster.')

    contract = {
        'system_reserved_cpu': _normalized_nonnegative_quantity(
            source.get('system_reserved_cpu', _DEFAULT_QUANTITY),
            field='System reserved CPU',
        ),
        'system_reserved_memory': _normalized_nonnegative_quantity(
            source.get('system_reserved_memory', _DEFAULT_QUANTITY),
            field='System reserved memory',
        ),
        'safety_headroom_percent': _headroom_percent(
            source.get('safety_headroom_percent', _DEFAULT_SAFETY_HEADROOM_PERCENT)
        ),
        'unmanaged_cpu_requests': _normalized_nonnegative_quantity(
            source.get('unmanaged_cpu_requests', _DEFAULT_QUANTITY),
            field='Unmanaged CPU commitment',
        ),
        'unmanaged_memory_requests': _normalized_nonnegative_quantity(
            source.get('unmanaged_memory_requests', _DEFAULT_QUANTITY),
            field='Unmanaged memory commitment',
        ),
    }
    _policy_values(contract)

    policy = get_capacity_policy(cluster_id)
    if policy is None:
        policy = TenantCapacityPolicy()
        policy.cluster_id = cluster_id
        db.session.add(policy)
    else:
        policy.version = int(policy.version) + 1

    policy.system_reserved_cpu = str(contract['system_reserved_cpu'])
    policy.system_reserved_memory = str(contract['system_reserved_memory'])
    policy.safety_headroom_percent = int(contract['safety_headroom_percent'])
    policy.unmanaged_cpu_requests = str(contract['unmanaged_cpu_requests'])
    policy.unmanaged_memory_requests = str(contract['unmanaged_memory_requests'])
    db.session.flush()
    return policy


def update_capacity_policy_committed(source: Mapping[str, Any]) -> TenantCapacityPolicy:
    try:
        policy = update_capacity_policy(source)
        db.session.commit()
        return policy
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantCapacityPolicyConflictError(
            'Tenant Capacity Policy changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _fresh_capacity_snapshot(cluster_id: str) -> CapacitySnapshotEvidence:
    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.capacity',
        parameters={'cluster_id': str(cluster_id), 'time_range': '24h'},
    )
    snapshot = result.snapshot
    if not result.available or result.state != 'fresh':
        return CapacitySnapshotEvidence(
            allocatable=CapacityVector(None, None),
            state=result.state,
            snapshot_id=snapshot.id if snapshot else None,
            generated_at=snapshot.generated_at if snapshot else None,
        )

    context = result.context or {}
    capacity = context.get('capacity_summary')
    if not isinstance(capacity, dict):
        return CapacitySnapshotEvidence(
            allocatable=CapacityVector(None, None),
            state='invalid',
            snapshot_id=snapshot.id if snapshot else None,
            generated_at=snapshot.generated_at if snapshot else None,
        )

    cpu = capacity.get('cpu')
    memory = capacity.get('memory')
    if not isinstance(cpu, dict) or not isinstance(memory, dict):
        return CapacitySnapshotEvidence(
            allocatable=CapacityVector(None, None),
            state='invalid',
            snapshot_id=snapshot.id if snapshot else None,
            generated_at=snapshot.generated_at if snapshot else None,
        )

    cpu_value = (
        Decimal(str(cpu.get('capacity')))
        if cpu.get('capacity_evidence_available') is True and cpu.get('capacity') is not None
        else None
    )
    memory_gib = (
        Decimal(str(memory.get('capacity')))
        if memory.get('capacity_evidence_available') is True and memory.get('capacity') is not None
        else None
    )
    return CapacitySnapshotEvidence(
        allocatable=CapacityVector(cpu_value, memory_gib * _GIB if memory_gib is not None else None),
        state=result.state,
        snapshot_id=snapshot.id if snapshot else None,
        generated_at=snapshot.generated_at if snapshot else None,
    )


def committed_tenant_allocation(cluster_id: str) -> tuple[CapacityVector, list[str]]:
    cpu_total = Decimal(0)
    memory_total = Decimal(0)
    cpu_complete = True
    memory_complete = True
    unbounded: list[str] = []

    namespaces = TenantNamespace.query.filter_by(cluster_id=cluster_id).order_by(TenantNamespace.id.asc()).all()
    for item in namespaces:
        requests = quota_requests(item.allocation_quota_json)
        if requests.cpu_cores is None:
            cpu_complete = False
            unbounded.append(f'{item.namespace}:requests.cpu')
        else:
            cpu_total += requests.cpu_cores
        if requests.memory_bytes is None:
            memory_complete = False
            unbounded.append(f'{item.namespace}:requests.memory')
        else:
            memory_total += requests.memory_bytes

    return CapacityVector(cpu_total if cpu_complete else None, memory_total if memory_complete else None), unbounded


def _vector_payload(vector: CapacityVector) -> dict[str, str | None]:
    memory_gib = bytes_to_gib_decimal(vector.memory_bytes)
    return {
        'cpu_cores': decimal_text(vector.cpu_cores),
        'memory_bytes': decimal_text(vector.memory_bytes),
        'memory_gib': decimal_text(memory_gib),
    }


def _decision_evidence(
    *,
    snapshot: CapacitySnapshotEvidence,
    policy_contract: Mapping[str, Any],
    result: CapacityPreflightResult,
    unbounded_existing: list[str],
) -> dict[str, Any]:
    return {
        'capacity_source': {
            'dataset_key': 'analytics.capacity',
            'time_range': '24h',
            'snapshot_id': snapshot.snapshot_id,
            'state': snapshot.state,
            'generated_at': snapshot.generated_at.isoformat() if snapshot.generated_at else None,
        },
        'policy': dict(policy_contract),
        'allocatable': _vector_payload(snapshot.allocatable),
        'budget': _vector_payload(result.budget),
        'committed': _vector_payload(result.committed),
        'current': _vector_payload(result.current),
        'proposed': _vector_payload(result.proposed),
        'projected': _vector_payload(result.projected),
        'remaining': _vector_payload(result.remaining),
        'shortfall': _vector_payload(result.shortfall),
        'unbounded_existing_dimensions': unbounded_existing[:50],
        'reason': result.reason,
        'resource_quota_is_physical_reservation': False,
    }


def _decision_message(result: CapacityPreflightResult) -> str:
    if result.allowed:
        return result.reason
    if result.state == 'unknown':
        return (
            'Tenant allocation preflight is blocked because fresh committed CPU/memory capacity evidence '
            'or bounded request allocation evidence is unavailable.'
        )
    short_cpu = decimal_text(result.shortfall.cpu_cores) or '0'
    short_memory = decimal_text(bytes_to_gib_decimal(result.shortfall.memory_bytes)) or '0'
    return (
        'Tenant allocation preflight denied: projected commitment exceeds the governed allocation budget '
        f'(CPU shortfall {short_cpu} cores, memory shortfall {short_memory} GiB).'
    )


def preflight_namespace_allocation(
    *,
    environment: TenantEnvironment,
    profile: TenantResourceProfile,
    namespace: str,
    proposed_quota: dict[str, Any],
    operation: str = 'create',
    current_quota: dict[str, Any] | None = None,
) -> TenantCapacityDecision:
    cluster_id = environment.tenant.cluster_id
    snapshot = _fresh_capacity_snapshot(cluster_id)
    policy_contract = capacity_policy_contract(get_capacity_policy(cluster_id))
    policy = _policy_values(policy_contract)
    committed, unbounded_existing = committed_tenant_allocation(cluster_id)
    proposed = quota_requests(proposed_quota)
    current = quota_requests(current_quota) if current_quota is not None else CapacityVector(Decimal(0), Decimal(0))

    result = evaluate_preflight(
        allocatable=snapshot.allocatable,
        policy=policy,
        committed=committed,
        proposed=proposed,
        current=current,
    )
    decision = TenantCapacityDecision()
    decision.cluster_id = cluster_id
    decision.tenant_environment_id = environment.id
    decision.resource_profile_id = profile.id
    decision.namespace = namespace
    decision.operation = operation
    decision.decision = 'allow' if result.allowed else 'block'
    decision.capacity_state = result.state
    decision.proposal_quota_json = dict(proposed_quota)
    decision.evidence_json = _decision_evidence(
        snapshot=snapshot,
        policy_contract=policy_contract,
        result=result,
        unbounded_existing=unbounded_existing,
    )
    decision.data_cutoff = snapshot.generated_at
    db.session.add(decision)
    db.session.flush()

    if not result.allowed:
        raise TenantCapacityDeniedError(_decision_message(result))
    return decision


def capacity_governance_rows(clusters: list[Cluster]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        snapshot = _fresh_capacity_snapshot(cluster.id)
        policy_contract = capacity_policy_contract(get_capacity_policy(cluster.id))
        policy = _policy_values(policy_contract)
        committed, unbounded = committed_tenant_allocation(cluster.id)
        result = evaluate_preflight(
            allocatable=snapshot.allocatable,
            policy=policy,
            committed=committed,
            proposed=CapacityVector(Decimal(0), Decimal(0)),
        )
        rows.append(
            {
                'cluster': cluster,
                'state': result.state,
                'policy': policy_contract,
                'budget': _vector_payload(result.budget),
                'committed': _vector_payload(committed),
                'remaining': _vector_payload(result.remaining),
                'evidence_state': snapshot.state,
                'data_cutoff': snapshot.generated_at,
                'unbounded_dimensions': len(unbounded),
            }
        )
    return rows
