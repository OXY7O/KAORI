from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.inventory import ClusterInventory, NamespaceInventory
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def build_tenant_inventory_snapshot() -> dict[str, Any]:
    """Materialize one Tenant inventory snapshot from committed KAORI evidence.

    Native Kubernetes does not expose a first-class Tenant object. KAORI therefore
    correlates canonical Tenant ownership with the latest committed Kubernetes
    namespace inventory instead of performing live provider reads in the page
    request path.
    """

    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    tenants = Tenant.query.order_by(Tenant.name.asc(), Tenant.id.asc()).all()
    namespaces = (
        TenantNamespace.query.join(
            TenantEnvironment,
            TenantNamespace.tenant_environment_id == TenantEnvironment.id,
        )
        .join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
        .filter(
            Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value,
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .order_by(TenantNamespace.cluster_id.asc(), TenantNamespace.namespace.asc())
        .all()
    )

    observed_namespaces = {
        (str(item.cluster_id), item.namespace): item
        for item in NamespaceInventory.query.all()
    }
    # Cluster inventory can retain more than one generation. Keep the newest
    # committed cutoff for each cluster without querying the provider here.
    normalized_cutoffs: dict[str, datetime] = {}
    for cluster_id, collected_at in (
        ClusterInventory.query.with_entities(
            ClusterInventory.cluster_id,
            ClusterInventory.collected_at,
        )
        .order_by(ClusterInventory.collected_at.desc())
        .all()
    ):
        normalized_cutoffs.setdefault(str(cluster_id), collected_at)
    latest_cluster_inventory = normalized_cutoffs

    tenant_counts: dict[str, int] = {}
    for tenant in tenants:
        tenant_counts[str(tenant.cluster_id)] = tenant_counts.get(str(tenant.cluster_id), 0) + 1

    namespace_counts: dict[str, int] = {}
    covered_counts: dict[str, int] = {}
    exceptions: list[dict[str, str]] = []
    for namespace in namespaces:
        cluster_id = str(namespace.cluster_id)
        namespace_counts[cluster_id] = namespace_counts.get(cluster_id, 0) + 1
        observed = observed_namespaces.get((cluster_id, namespace.namespace))
        if observed is not None:
            covered_counts[cluster_id] = covered_counts.get(cluster_id, 0) + 1
            continue
        exceptions.append(
            {
                'cluster_id': cluster_id,
                'namespace': namespace.namespace,
                'reason': 'Managed Tenant namespace is not present in committed Kubernetes inventory.',
            }
        )

    tenant_cluster_ids = {str(tenant.cluster_id) for tenant in tenants}
    for cluster_id in sorted(tenant_cluster_ids):
        if cluster_id not in latest_cluster_inventory:
            exceptions.append(
                {
                    'cluster_id': cluster_id,
                    'namespace': '',
                    'reason': 'Tenant cluster has no committed Kubernetes inventory snapshot.',
                }
            )

    cluster_rows: list[dict[str, Any]] = []
    cluster_by_id = {str(cluster.id): cluster for cluster in clusters}
    for cluster_id in sorted(set(cluster_by_id) | tenant_cluster_ids):
        cluster = cluster_by_id.get(cluster_id)
        managed_namespaces = namespace_counts.get(cluster_id, 0)
        covered_namespaces = covered_counts.get(cluster_id, 0)
        cluster_rows.append(
            {
                'cluster_id': cluster_id,
                'cluster_name': cluster.name if cluster is not None else 'Unknown cluster',
                'environment': cluster.environment if cluster is not None else 'unknown',
                'tenant_count': tenant_counts.get(cluster_id, 0),
                'namespace_count': managed_namespaces,
                'covered_namespace_count': covered_namespaces,
                'coverage_complete': managed_namespaces == covered_namespaces,
                'source_inventory_cutoff': _iso(latest_cluster_inventory.get(cluster_id)),
            }
        )

    source_cutoffs = [value for value in latest_cluster_inventory.values() if value is not None]
    source_cutoff = max(source_cutoffs) if source_cutoffs else None
    namespace_count = len(namespaces)
    covered_namespace_count = sum(covered_counts.values())

    return {
        'schema_version': 1,
        'authority': 'kubernetes_tenant_inventory',
        'source': 'KAORI Tenant State + committed Kubernetes Inventory',
        'scope_label': 'All Clusters',
        'collected_at': datetime.now(UTC).isoformat(),
        'source_inventory_cutoff': _iso(source_cutoff),
        'registered_cluster_count': len(clusters),
        'tenant_cluster_count': len(tenant_cluster_ids),
        'tenant_count': len(tenants),
        'namespace_count': namespace_count,
        'covered_namespace_count': covered_namespace_count,
        'coverage_complete': namespace_count == covered_namespace_count and not exceptions,
        'exception_count': len(exceptions),
        'exceptions': exceptions[:25],
        'clusters': cluster_rows,
        'secret_material_persisted': False,
    }



def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def apply_missing_namespace_drift_from_inventory() -> list[int]:
    """Commit provider-absence drift only from sufficiently fresh inventory evidence.

    This function is observation-only. It never recreates, patches, or deletes a
    Kubernetes resource. A drifted record stays drifted until an explicit
    provider reconciliation verifies the full effective contract.
    """

    observed = {
        (str(item.cluster_id), item.namespace)
        for item in NamespaceInventory.query.all()
    }
    latest_cutoffs: dict[str, datetime] = {}
    for cluster_id, collected_at in (
        ClusterInventory.query.with_entities(
            ClusterInventory.cluster_id,
            ClusterInventory.collected_at,
        )
        .order_by(ClusterInventory.collected_at.desc())
        .all()
    ):
        latest_cutoffs.setdefault(str(cluster_id), collected_at)

    records = (
        TenantNamespace.query.join(
            TenantEnvironment,
            TenantNamespace.tenant_environment_id == TenantEnvironment.id,
        )
        .join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
        .filter(
            Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value,
            TenantNamespace.provisioning_status == TenantNamespaceProvisioningStatus.READY.value,
        )
        .order_by(TenantNamespace.id.asc())
        .all()
    )

    now = datetime.now(UTC)
    changed: list[int] = []
    for record in records:
        key = (str(record.cluster_id), record.namespace)
        if key in observed:
            continue

        cutoff = _as_utc(latest_cutoffs.get(str(record.cluster_id)))
        anchor_candidates = [
            _as_utc(record.last_reconciled_at),
            _as_utc(record.updated_at),
            _as_utc(record.created_at),
        ]
        anchors = [value for value in anchor_candidates if value is not None]
        anchor = max(anchors) if anchors else None
        if cutoff is None or (anchor is not None and cutoff < anchor):
            # Inventory predates the latest KAORI-side provider evidence and
            # therefore cannot prove that the namespace disappeared.
            continue

        evidence = dict(record.provisioning_evidence_json or {})
        evidence['provider_observation'] = {
            'provider': 'native_kubernetes',
            'namespace': record.namespace,
            'observed_absent': True,
            'source': 'committed_kubernetes_inventory',
            'source_inventory_cutoff': cutoff.isoformat(),
            'observed_at': now.isoformat(),
            'ownership_status': record.ownership_status,
            'secret_material_persisted': False,
        }
        record.provisioning_evidence_json = evidence
        record.provisioning_status = TenantNamespaceProvisioningStatus.DRIFTED.value
        record.provisioning_message = (
            'Committed Kubernetes inventory no longer contains this namespace. '
            'Review provider deletion/loss before explicit reconcile or Tenant decommission.'
        )
        changed.append(record.id)

    if changed:
        db.session.flush()
    return changed
