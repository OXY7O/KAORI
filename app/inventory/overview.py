from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
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


def _build_inventory_signals(
    *,
    connected: bool,
    synced_at: datetime | None,
    node_count: int,
    workload_count: int,
    pod_count: int,
    storage_count: int,
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []

    if not connected:
        signals.append({'label': 'Connection Risk', 'tone': 'critical'})

    if synced_at is None:
        signals.append({'label': 'Never Collected', 'tone': 'warning'})
    elif _is_stale_inventory(synced_at):
        signals.append({'label': 'Stale Snapshot', 'tone': 'warning'})

    if pod_count >= 100 or workload_count >= 50:
        signals.append({'label': 'High Density', 'tone': 'info'})

    if node_count > 0 and storage_count == 0:
        signals.append({'label': 'No Storage Data', 'tone': 'unknown'})

    return signals[:3]


def get_cluster_by_id(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_inventory_clusters() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
    ).all()


def _grouped_current_counts(model: Any, cluster_ids: list[Any]) -> dict[Any, int]:
    if not cluster_ids:
        return {}

    query = db.session.query(model.cluster_id, func.count(model.id))
    query = filter_current_generation(query, model)
    return {
        cluster_id: int(count or 0)
        for cluster_id, count in (
            query.filter(model.cluster_id.in_(cluster_ids))
            .group_by(model.cluster_id)
            .all()
        )
    }


def get_inventory_cluster_summary() -> tuple[
    list[Cluster],
    dict[str, dict[str, Any]],
]:
    clusters = get_inventory_clusters()
    cluster_ids = [cluster.id for cluster in clusters]

    inventories: dict[str, ClusterInventory] = {}
    namespace_counts = _grouped_current_counts(NamespaceInventory, cluster_ids)

    if cluster_ids:
        inventories = {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(
                ClusterInventory.cluster_id.in_(cluster_ids)
            ).all()
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


def _sync_status(synced_at: datetime | None) -> tuple[str, str]:
    if synced_at is None:
        return 'Never Collected', 'warning'
    if _is_stale_inventory(synced_at):
        return 'Stale', 'warning'
    return 'Current', 'normal'


def get_inventory_freshness_context(cluster_id: str = '') -> dict[str, Any]:
    """Describe when the committed inventory snapshot for the current scope was collected."""
    clusters, summary = get_inventory_cluster_summary()
    selected = [cluster for cluster in clusters if not cluster_id or str(cluster.id) == str(cluster_id)]
    snapshots = [
        _normalize_datetime(summary.get(cluster.id, {}).get('synced_at'))
        for cluster in selected
    ]
    committed = [value for value in snapshots if value is not None]
    latest = max(committed) if committed else None
    oldest = min(committed) if committed else None
    missing_count = max(len(selected) - len(committed), 0)
    stale_count = sum(1 for value in committed if _is_stale_inventory(value))

    if not selected:
        status = 'No Scope'
        tone = 'unknown'
        description = 'No registered Kubernetes cluster matches the selected inventory scope.'
    elif not committed:
        status = 'Not Collected'
        tone = 'warning'
        description = 'Run Inventory Sync before relying on this inventory view.'
    elif stale_count or missing_count:
        status = 'Review Freshness'
        tone = 'warning'
        description = (
            f'{len(committed)} of {len(selected)} cluster snapshots are committed; '
            f'{stale_count} are older than the {INVENTORY_FRESHNESS_HOURS}-hour freshness window.'
        )
    else:
        status = 'Current'
        tone = 'normal'
        description = (
            f'All {len(selected)} cluster snapshots are within the '
            f'{INVENTORY_FRESHNESS_HOURS}-hour freshness window.'
        )

    return {
        'latest_collected_at': latest,
        'oldest_collected_at': oldest,
        'cluster_count': len(selected),
        'committed_count': len(committed),
        'missing_count': missing_count,
        'stale_count': stale_count,
        'freshness_window_hours': INVENTORY_FRESHNESS_HOURS,
        'scope_label': selected[0].name if len(selected) == 1 else f'{len(selected)} Clusters',
        'status': status,
        'tone': tone,
        'description': description,
        'source_label': 'Committed Database Snapshot',
    }


def _asset_catalog(totals: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            'key': 'nodes',
            'title': 'Nodes',
            'count': totals['nodes'],
            'icon': 'cpu',
            'description': 'Worker and control-plane capacity.',
            'endpoint': 'inventory.nodes',
        },
        {
            'key': 'namespaces',
            'title': 'Namespaces',
            'count': totals['namespaces'],
            'icon': 'folder-tree',
            'description': 'Tenant and application scopes.',
            'endpoint': 'inventory.namespaces',
        },
        {
            'key': 'workloads',
            'title': 'Workloads',
            'count': totals['workloads'],
            'icon': 'boxes',
            'description': 'Deployments and workload controllers.',
            'endpoint': 'inventory.workloads',
        },
        {
            'key': 'pods',
            'title': 'Pods',
            'count': totals['pods'],
            'icon': 'container',
            'description': 'Current runtime workload instances.',
            'endpoint': 'inventory.pods',
        },
        {
            'key': 'services',
            'title': 'Services',
            'count': totals['services'],
            'icon': 'network',
            'description': 'Cluster networking endpoints.',
            'endpoint': 'inventory.services',
        },
        {
            'key': 'ingresses',
            'title': 'Ingresses',
            'count': totals['ingresses'],
            'icon': 'route',
            'description': 'Published application entry points.',
            'endpoint': 'inventory.ingresses',
        },
        {
            'key': 'storage',
            'title': 'Storage',
            'count': totals['storage'],
            'icon': 'hard-drive',
            'description': 'Storage classes, volumes, and claims.',
            'endpoint': 'inventory.storage',
        },
        {
            'key': 'configuration',
            'title': 'Configuration',
            'count': totals['configuration'],
            'icon': 'file-cog',
            'description': 'ConfigMaps and Secret metadata.',
            'endpoint': 'inventory.configuration',
        },
    ]


def get_inventory_overview() -> dict[str, Any]:
    clusters, inventory_summary = get_inventory_cluster_summary()
    cluster_ids = [cluster.id for cluster in clusters]

    count_maps = {
        'nodes': _grouped_current_counts(NodeInventory, cluster_ids),
        'namespaces': _grouped_current_counts(NamespaceInventory, cluster_ids),
        'workloads': _grouped_current_counts(WorkloadInventory, cluster_ids),
        'pods': _grouped_current_counts(PodInventory, cluster_ids),
        'services': _grouped_current_counts(ServiceInventory, cluster_ids),
        'ingresses': _grouped_current_counts(IngressInventory, cluster_ids),
        'storage': _grouped_current_counts(StorageInventory, cluster_ids),
        'configuration': _grouped_current_counts(ConfigurationInventory, cluster_ids),
    }

    cluster_rows: list[dict[str, Any]] = []
    for cluster in clusters:
        summary = inventory_summary.get(cluster.id, {})
        synced_at = summary.get('synced_at')
        counts = {key: values.get(cluster.id, 0) for key, values in count_maps.items()}
        total_objects = sum(counts.values())
        sync_label, sync_tone = _sync_status(synced_at)
        signals = _build_inventory_signals(
            connected=cluster.status == 'connected',
            synced_at=synced_at,
            node_count=counts['nodes'],
            workload_count=counts['workloads'],
            pod_count=counts['pods'],
            storage_count=counts['storage'],
        )

        cluster_rows.append(
            {
                'id': cluster.id,
                'name': cluster.name,
                'environment': cluster.environment,
                'status': cluster.status,
                'kubernetes_version': summary.get('version') or '-',
                'synced_at': synced_at,
                'sync_status_label': sync_label,
                'sync_status_tone': sync_tone,
                'counts': counts,
                'total_objects': total_objects,
                'signals': signals,
            }
        )

    totals = {
        'clusters': _count_rows(Cluster),
        'nodes': _count_rows(NodeInventory),
        'namespaces': _count_rows(NamespaceInventory),
        'workloads': _count_rows(WorkloadInventory),
        'pods': _count_rows(PodInventory),
        'services': _count_rows(ServiceInventory),
        'ingresses': _count_rows(IngressInventory),
        'storage': _count_rows(StorageInventory),
        'configuration': _count_rows(ConfigurationInventory),
    }
    inventory_total = sum(value for key, value in totals.items() if key != 'clusters')
    health = get_inventory_health()
    total_clusters = totals['clusters']
    posture_status = (
        'Unknown'
        if total_clusters == 0
        else 'Healthy'
        if health['healthy_clusters'] == total_clusters
        else 'Attention'
    )
    posture_tone = 'unknown' if posture_status == 'Unknown' else 'normal' if posture_status == 'Healthy' else 'warning'

    return {
        'total_clusters': totals['clusters'],
        'total_nodes': totals['nodes'],
        'total_namespaces': totals['namespaces'],
        'total_workloads': totals['workloads'],
        'total_pods': totals['pods'],
        'total_services': totals['services'],
        'total_ingresses': totals['ingresses'],
        'total_storage': totals['storage'],
        'total_configuration': totals['configuration'],
        'inventory_total': inventory_total,
        'asset_catalog': _asset_catalog(totals),
        'clusters': cluster_rows,
        'inventory_summary': inventory_summary,
        'health': health,
        'posture': {
            'status': posture_status,
            'tone': posture_tone,
        },
    }


def _count_rows(model: Any) -> int:
    query = db.session.query(func.count(model.id))
    if model is not Cluster:
        query = filter_current_generation(query, model)
    return query.scalar() or 0


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
        connected = cluster.status == 'connected'
        if connected:
            connected_clusters += 1

        inventory = inventory_by_cluster.get(cluster.id)
        if inventory is None:
            never_synced += 1
            continue

        collected_at = _normalize_datetime(inventory.collected_at)
        if _is_stale_inventory(collected_at):
            stale_synced += 1
        else:
            fresh_synced += 1
            if connected:
                healthy_clusters += 1

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
