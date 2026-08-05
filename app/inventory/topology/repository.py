from __future__ import annotations

from sqlalchemy import false

from app.common.inventory_generation import filter_current_generation
from app.inventory.topology.contracts import TopologyRecords, TopologySelection
from app.inventory.topology.presentation import iso_datetime
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


def load_clusters(cluster_id: str) -> list[Cluster]:
    query = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc())
    return query.filter(Cluster.id == cluster_id).all() if cluster_id else query.all()


def load_namespace_map() -> dict[str, list[str]]:
    rows = (
        filter_current_generation(NamespaceInventory.query, NamespaceInventory)
        .order_by(NamespaceInventory.cluster_id.asc(), NamespaceInventory.namespace.asc())
        .all()
    )
    namespace_map: dict[str, list[str]] = {}
    for row in rows:
        namespace_map.setdefault(row.cluster_id, []).append(row.namespace)
    return namespace_map


def latest_cluster_inventory(cluster_ids: list[str]) -> dict[str, ClusterInventory]:
    rows = (
        ClusterInventory.query.filter(ClusterInventory.cluster_id.in_(cluster_ids))
        .order_by(ClusterInventory.collected_at.desc())
        .all()
    )
    latest: dict[str, ClusterInventory] = {}
    for row in rows:
        latest.setdefault(row.cluster_id, row)
    return latest


def topology_generation_signature(
    clusters: list[Cluster],
    latest_inventory: dict[str, ClusterInventory],
) -> tuple[tuple[str, str | None, str | None], ...]:
    return tuple(
        (
            cluster.id,
            iso_datetime(cluster.updated_at),
            iso_datetime(latest_inventory[cluster.id].collected_at) if cluster.id in latest_inventory else None,
        )
        for cluster in clusters
    )


def load_topology_records(
    *,
    clusters: list[Cluster],
    latest_inventory: dict[str, ClusterInventory],
    namespace: str,
    selection: TopologySelection,
) -> TopologyRecords:
    cluster_ids = [cluster.id for cluster in clusters]
    pods = _load_pods(cluster_ids, namespace, selection)
    return TopologyRecords(
        clusters=clusters,
        cluster_by_id={cluster.id: cluster for cluster in clusters},
        latest_cluster_inventory=latest_inventory,
        namespaces=_load_namespaces(cluster_ids, namespace),
        nodes=_load_nodes(cluster_ids, namespace, pods, selection),
        workloads=_load_workloads(cluster_ids, namespace, selection),
        services=_load_services(cluster_ids, namespace, selection),
        ingresses=_load_ingresses(cluster_ids, namespace, selection),
        configurations=_load_configurations(cluster_ids, namespace, selection),
        storage_items=_load_storage(cluster_ids, namespace, selection),
        pods=pods,
    )


def _current_query(model, cluster_ids: list[str]):
    return filter_current_generation(model.query, model).filter(model.cluster_id.in_(cluster_ids))


def _namespaced_query(model, cluster_ids: list[str], namespace: str):
    query = _current_query(model, cluster_ids)
    return query.filter(model.namespace == namespace) if namespace else query


def _load_namespaces(cluster_ids: list[str], namespace: str) -> list[NamespaceInventory]:
    query = _current_query(NamespaceInventory, cluster_ids)
    if namespace:
        query = query.filter(NamespaceInventory.namespace == namespace)
    return query.order_by(NamespaceInventory.cluster_id.asc(), NamespaceInventory.namespace.asc()).all()


def _load_pods(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
) -> list[PodInventory]:
    needs_pods = selection.include_pods or (bool(namespace) and selection.show_compute)
    if not needs_pods:
        return []
    return (
        _namespaced_query(PodInventory, cluster_ids, namespace)
        .order_by(PodInventory.cluster_id.asc(), PodInventory.namespace.asc(), PodInventory.pod_name.asc())
        .all()
    )


def _load_nodes(
    cluster_ids: list[str],
    namespace: str,
    pods: list[PodInventory],
    selection: TopologySelection,
) -> list[NodeInventory]:
    if not selection.include_level_1 or not selection.show_compute:
        return []
    query = _current_query(NodeInventory, cluster_ids)
    if namespace:
        referenced_nodes = sorted({pod.node_name for pod in pods if pod.node_name})
        query = (
            query.filter(NodeInventory.node_name.in_(referenced_nodes))
            if referenced_nodes
            else query.filter(false())
        )
    return query.order_by(NodeInventory.cluster_id.asc(), NodeInventory.node_name.asc()).all()


def _load_workloads(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
) -> list[WorkloadInventory]:
    if not selection.include_level_2 or not selection.show_compute:
        return []
    return (
        _namespaced_query(WorkloadInventory, cluster_ids, namespace)
        .order_by(
            WorkloadInventory.cluster_id.asc(),
            WorkloadInventory.namespace.asc(),
            WorkloadInventory.workload_type.asc(),
            WorkloadInventory.name.asc(),
        )
        .all()
    )


def _load_services(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
) -> list[ServiceInventory]:
    if not selection.include_level_2 or not selection.show_networking:
        return []
    return (
        _namespaced_query(ServiceInventory, cluster_ids, namespace)
        .order_by(
            ServiceInventory.cluster_id.asc(),
            ServiceInventory.namespace.asc(),
            ServiceInventory.service_name.asc(),
        )
        .all()
    )


def _load_ingresses(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
) -> list[IngressInventory]:
    if not selection.include_level_2 or not selection.show_networking:
        return []
    return (
        _namespaced_query(IngressInventory, cluster_ids, namespace)
        .order_by(
            IngressInventory.cluster_id.asc(),
            IngressInventory.namespace.asc(),
            IngressInventory.ingress_name.asc(),
        )
        .all()
    )


def _load_configurations(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
) -> list[ConfigurationInventory]:
    if not selection.include_level_2 or not selection.show_configuration:
        return []
    return (
        _namespaced_query(ConfigurationInventory, cluster_ids, namespace)
        .order_by(
            ConfigurationInventory.cluster_id.asc(),
            ConfigurationInventory.namespace.asc(),
            ConfigurationInventory.object_type.asc(),
            ConfigurationInventory.name.asc(),
        )
        .all()
    )


def _load_storage(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
) -> list[StorageInventory]:
    if not selection.include_level_2 or not selection.show_storage:
        return []
    query = _current_query(StorageInventory, cluster_ids)
    if namespace:
        query = query.filter(
            (StorageInventory.namespace == namespace)
            | (StorageInventory.namespace.is_(None) & (StorageInventory.storage_type == 'PersistentVolume'))
        )
    items = query.order_by(
        StorageInventory.cluster_id.asc(),
        StorageInventory.storage_type.asc(),
        StorageInventory.namespace.asc(),
        StorageInventory.name.asc(),
    ).all()
    return _storage_for_namespace(items, namespace) if namespace else items


def _storage_for_namespace(items: list[StorageInventory], namespace: str) -> list[StorageInventory]:
    claims = [
        item for item in items if item.storage_type == 'PersistentVolumeClaim' and item.namespace == namespace
    ]
    volume_names = {
        str((item.details or {}).get('volume_name') or '').strip()
        for item in claims
        if str((item.details or {}).get('volume_name') or '').strip()
    }
    return [
        item
        for item in items
        if (item.storage_type == 'PersistentVolumeClaim' and item.namespace == namespace)
        or (item.storage_type == 'PersistentVolume' and item.name in volume_names)
    ]
