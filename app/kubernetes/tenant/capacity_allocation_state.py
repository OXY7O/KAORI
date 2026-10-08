from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from sqlalchemy.orm import joinedload

from app.extensions.db import db
from app.kubernetes.tenant.capacity import CapacityVector, quota_request_vector
from app.models.tenant import Tenant, TenantNamespace, TenantNamespaceProvisioningStatus
from app.models.tenant_advanced import (
    TenantAdvancedCapabilityIntent,
    TenantAdvancedCapabilityStatus,
)

_ZERO = Decimal('0')


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
        if any(value is None for value in values[:3]):
            unbounded.append(label)
        for index, value in enumerate(values):
            current = totals[index]
            if current is not None:
                totals[index] = current + value if value is not None else None

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


def _canonical_shared_allocation_quota_by_cluster(
    cluster_ids: list[str],
) -> tuple[dict[str, dict[str, Mapping[str, object]]], dict[str, list[str]]]:
    selected_by_cluster: dict[str, dict[str, Mapping[str, object]]] = {cluster_id: {} for cluster_id in cluster_ids}
    ambiguous_by_cluster: dict[str, set[str]] = {cluster_id: set() for cluster_id in cluster_ids}
    if not cluster_ids:
        return selected_by_cluster, {}

    candidates = (
        db.session.query(TenantAdvancedCapabilityIntent, Tenant.cluster_id)
        .join(Tenant, TenantAdvancedCapabilityIntent.tenant_id == Tenant.id)
        .filter(
            Tenant.cluster_id.in_(cluster_ids),
            TenantAdvancedCapabilityIntent.resource_kind == 'global_resource_quota',
            TenantAdvancedCapabilityIntent.status.in_(
                (
                    TenantAdvancedCapabilityStatus.READY.value,
                    TenantAdvancedCapabilityStatus.DRIFTED.value,
                )
            ),
        )
        .order_by(
            Tenant.cluster_id.asc(),
            TenantAdvancedCapabilityIntent.tenant_id.asc(),
            TenantAdvancedCapabilityIntent.updated_at.desc(),
        )
        .all()
    )
    for intent, cluster_id in candidates:
        normalized_cluster_id = str(cluster_id)
        evidence = intent.reconciliation_evidence_json or {}
        if evidence.get('allocation_governance_scope') != 'tenant_shared':
            continue
        tenant_id = str(intent.tenant_id)
        selected = selected_by_cluster[normalized_cluster_id]
        ambiguous = ambiguous_by_cluster[normalized_cluster_id]
        if tenant_id in selected:
            ambiguous.add(tenant_id)
            continue
        desired = intent.desired_spec_json or {}
        quota = desired.get('quota') if isinstance(desired, Mapping) else None
        hard = quota.get('hard') if isinstance(quota, Mapping) else None
        selected[tenant_id] = dict(hard) if isinstance(hard, Mapping) else {}

    capsule_tenants = Tenant.query.filter(
        Tenant.cluster_id.in_(cluster_ids),
        Tenant.provider_key == 'capsule',
    ).all()
    for tenant in capsule_tenants:
        normalized_cluster_id = str(tenant.cluster_id)
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
        selected = selected_by_cluster[normalized_cluster_id]
        ambiguous = ambiguous_by_cluster[normalized_cluster_id]
        quota = governance.get('desired_quota')
        if tenant_id in selected or not isinstance(quota, Mapping):
            ambiguous.add(tenant_id)
            selected.pop(tenant_id, None)
            continue
        selected[tenant_id] = dict(quota)

    for cluster_id, ambiguous in ambiguous_by_cluster.items():
        selected = selected_by_cluster[cluster_id]
        for tenant_id in ambiguous:
            selected.pop(tenant_id, None)

    return selected_by_cluster, {
        cluster_id: sorted(ambiguous) for cluster_id, ambiguous in ambiguous_by_cluster.items()
    }


def _committed_tenant_allocations(
    cluster_ids: list[str],
) -> dict[str, tuple[CapacityVector, int, list[str]]]:
    rows = (
        TenantNamespace.query.options(joinedload(TenantNamespace.environment))
        .filter(
            TenantNamespace.cluster_id.in_(cluster_ids),
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .order_by(TenantNamespace.cluster_id.asc(), TenantNamespace.namespace.asc())
        .all()
    )
    rows_by_cluster: dict[str, list[TenantNamespace]] = {cluster_id: [] for cluster_id in cluster_ids}
    for row in rows:
        rows_by_cluster.setdefault(str(row.cluster_id), []).append(row)

    shared_by_cluster, ambiguous_by_cluster = _canonical_shared_allocation_quota_by_cluster(cluster_ids)
    result: dict[str, tuple[CapacityVector, int, list[str]]] = {}
    for cluster_id in cluster_ids:
        cluster_rows = rows_by_cluster.get(cluster_id, [])
        committed, unbounded = _aggregate_committed_allocation(
            cluster_rows,
            shared_quota_by_tenant=shared_by_cluster.get(cluster_id, {}),
            ambiguous_shared_tenants=ambiguous_by_cluster.get(cluster_id, []),
        )
        result[cluster_id] = (committed, len(cluster_rows), unbounded)
    return result


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
