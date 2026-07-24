from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.extensions.db import db
from app.models import (
    Cluster,
    ClusterInventory,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)

INVENTORY_FRESHNESS_HOURS = 24


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_stale_inventory(value: datetime | None) -> bool:
    collected_at = _normalize_datetime(value)
    if collected_at is None:
        return False
    age = datetime.now(UTC) - collected_at
    return age.total_seconds() > INVENTORY_FRESHNESS_HOURS * 3600


def _build_inventory_risk_hints(
    *,
    connected: bool,
    synced_at: datetime | None,
    node_count: int,
    workload_count: int,
    pod_count: int,
    storage_count: int,
) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []

    if not connected:
        hints.append(
            {
                'label': 'Connection risk',
                'tone': 'red',
                'icon': 'unlink',
            }
        )

    if synced_at is None:
        hints.append(
            {
                'label': 'Never synced',
                'tone': 'amber',
                'icon': 'triangle-alert',
            }
        )
    elif _is_stale_inventory(synced_at):
        hints.append(
            {
                'label': 'Stale sync',
                'tone': 'amber',
                'icon': 'clock-alert',
            }
        )
    else:
        hints.append(
            {
                'label': 'Fresh sync',
                'tone': 'green',
                'icon': 'check-circle-2',
            }
        )

    if pod_count >= 100 or workload_count >= 50:
        hints.append(
            {
                'label': 'High density',
                'tone': 'blue',
                'icon': 'activity',
            }
        )

    if node_count > 0 and storage_count == 0:
        hints.append(
            {
                'label': 'No storage data',
                'tone': 'slate',
                'icon': 'hard-drive',
            }
        )

    return hints[:3]


def get_cluster_by_id(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_inventory_clusters() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
    ).all()


def get_inventory_cluster_summary() -> tuple[
    list[Cluster],
    dict[str, dict[str, Any]],
]:
    clusters = get_inventory_clusters()
    cluster_ids = [cluster.id for cluster in clusters]

    inventories: dict[str, ClusterInventory] = {}
    namespace_counts: dict[str, int] = {}

    if cluster_ids:
        inventories = {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(ClusterInventory.cluster_id.in_(cluster_ids)).all()
        }
        namespace_counts = {
            cluster_id: count
            for cluster_id, count in (
                db.session.query(
                    NamespaceInventory.cluster_id,
                    func.count(NamespaceInventory.id),
                )
                .filter(NamespaceInventory.cluster_id.in_(cluster_ids))
                .group_by(NamespaceInventory.cluster_id)
                .all()
            )
        }

    summary: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        inventory = inventories.get(cluster.id)
        summary[cluster.id] = {
            'version': inventory.kubernetes_version if inventory else '-',
            'namespaces': namespace_counts.get(cluster.id, 0),
            'synced_at': inventory.collected_at if inventory else None,
        }

    return clusters, summary


def _cluster_resource_counts(cluster_id: str) -> dict[str, int]:
    return {
        'node_count': NodeInventory.query.filter_by(cluster_id=cluster_id).count(),
        'workload_count': WorkloadInventory.query.filter_by(cluster_id=cluster_id).count(),
        'pod_count': PodInventory.query.filter_by(cluster_id=cluster_id).count(),
        'service_count': ServiceInventory.query.filter_by(cluster_id=cluster_id).count(),
        'ingress_count': IngressInventory.query.filter_by(cluster_id=cluster_id).count(),
        'storage_count': StorageInventory.query.filter_by(cluster_id=cluster_id).count(),
    }


def _sync_status(synced_at: datetime | None) -> tuple[str, str, str]:
    if synced_at is None:
        return 'never_synced', 'Never synced', 'amber'
    if _is_stale_inventory(synced_at):
        return 'stale', 'Stale', 'amber'
    return 'fresh', 'Fresh', 'green'


def get_inventory_overview() -> dict[str, Any]:
    clusters, inventory_summary = get_inventory_cluster_summary()
    cluster_rows: list[dict[str, Any]] = []

    for cluster in clusters:
        summary = inventory_summary.get(cluster.id, {})
        synced_at = summary.get('synced_at')
        counts = _cluster_resource_counts(cluster.id)
        sync_status, sync_label, sync_tone = _sync_status(synced_at)
        connection = cluster.kubernetes_connection
        server = connection.server if connection is not None else None
        verify_ssl = connection.verify_ssl if connection is not None else True
        allow_weak_tls = connection.allow_weak_tls if connection is not None else False

        cluster_rows.append(
            {
                'id': cluster.id,
                'name': cluster.name,
                'environment': cluster.environment,
                'server': server,
                'status': cluster.status,
                'node_count': counts['node_count'],
                'last_check': cluster.last_check,
                'created_at': cluster.created_at,
                'updated_at': cluster.updated_at,
                'kube_verify_ssl': verify_ssl,
                'kube_allow_weak_tls': allow_weak_tls,
                'workload_count': counts['workload_count'],
                'pod_count': counts['pod_count'],
                'service_count': counts['service_count'],
                'ingress_count': counts['ingress_count'],
                'storage_count': counts['storage_count'],
                'sync_status': sync_status,
                'sync_status_label': sync_label,
                'sync_status_tone': sync_tone,
                'risk_hints': _build_inventory_risk_hints(
                    connected=cluster.status == 'connected',
                    synced_at=synced_at,
                    node_count=counts['node_count'],
                    workload_count=counts['workload_count'],
                    pod_count=counts['pod_count'],
                    storage_count=counts['storage_count'],
                ),
            }
        )

    return {
        'total_clusters': _count_rows(Cluster),
        'total_nodes': _count_rows(NodeInventory),
        'total_namespaces': _count_rows(NamespaceInventory),
        'total_workloads': _count_rows(WorkloadInventory),
        'total_pods': _count_rows(PodInventory),
        'total_services': _count_rows(ServiceInventory),
        'total_ingresses': _count_rows(IngressInventory),
        'total_storage': _count_rows(StorageInventory),
        'clusters': cluster_rows,
        'inventory_summary': inventory_summary,
        'health': get_inventory_health(),
        'activities': get_recent_inventory_activity(),
    }


def _count_rows(model: type) -> int:
    return db.session.query(func.count(model.id)).scalar() or 0


def get_inventory_health() -> dict[str, Any]:
    clusters = Cluster.query.all()
    total_clusters = len(clusters)
    healthy_clusters = 0
    never_synced = 0
    stale_synced = 0
    fresh_synced = 0
    last_sync = None
    connected_clusters = 0

    inventory_by_cluster = (
        {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(
                ClusterInventory.cluster_id.in_([cluster.id for cluster in clusters])
            ).all()
        }
        if clusters
        else {}
    )

    for cluster in clusters:
        if cluster.status == 'connected':
            connected_clusters += 1

        inventory = inventory_by_cluster.get(cluster.id)
        if inventory is None:
            never_synced += 1
            continue

        if cluster.status == 'connected':
            healthy_clusters += 1

        collected_at = _normalize_datetime(inventory.collected_at)
        if _is_stale_inventory(collected_at):
            stale_synced += 1
        else:
            fresh_synced += 1

        if collected_at and (last_sync is None or collected_at > last_sync):
            last_sync = collected_at

    synced_clusters = total_clusters - never_synced
    disconnected_clusters = total_clusters - connected_clusters

    def percentage(value: int) -> int:
        return round((value / total_clusters) * 100) if total_clusters else 0

    return {
        'connected_clusters': connected_clusters,
        'healthy_clusters': healthy_clusters,
        'never_synced': never_synced,
        'stale_synced': stale_synced,
        'fresh_synced': fresh_synced,
        'synced_clusters': synced_clusters,
        'disconnected_clusters': disconnected_clusters,
        'coverage_score': percentage(synced_clusters),
        'connection_score': percentage(connected_clusters),
        'freshness_score': percentage(fresh_synced),
        'freshness_window_hours': INVENTORY_FRESHNESS_HOURS,
        'last_sync': last_sync,
    }


def get_recent_inventory_activity() -> list[dict[str, Any]]:
    inventories = ClusterInventory.query.order_by(ClusterInventory.collected_at.desc()).limit(5).all()
    if not inventories:
        return []

    cluster_ids = {inventory.cluster_id for inventory in inventories}
    clusters = {cluster.id: cluster for cluster in Cluster.query.filter(Cluster.id.in_(cluster_ids)).all()}

    return [
        {
            'cluster': (clusters[inventory.cluster_id].name if inventory.cluster_id in clusters else 'Unknown'),
            'collected_at': inventory.collected_at,
        }
        for inventory in inventories
    ]
