from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import aliased, joinedload

from app.extensions.db import db

from app.common.inventory_generation import filter_current_generation
from app.kubernetes.inventory.topology.contracts import TopologyRecords, TopologySelection
from app.kubernetes.inventory.topology.presentation import iso_datetime, selector_matches
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
    query = Cluster.query.options(joinedload(Cluster.kubernetes_connection)).order_by(
        Cluster.created_at.asc(), Cluster.id.asc()
    )
    return query.filter(Cluster.id == cluster_id).all() if cluster_id else query.all()


def load_namespace_map() -> dict[str, list[str]]:
    rows = (
        filter_current_generation(NamespaceInventory.query, NamespaceInventory)
        .with_entities(NamespaceInventory.cluster_id, NamespaceInventory.namespace)
        .distinct()
        .order_by(NamespaceInventory.cluster_id.asc(), NamespaceInventory.namespace.asc())
        .all()
    )
    namespace_map: dict[str, list[str]] = {}
    for cluster_id, namespace in rows:
        namespace_map.setdefault(cluster_id, []).append(namespace)
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
    max_nodes: int | None = None,
) -> TopologyRecords:
    cluster_ids = [cluster.id for cluster in clusters]
    source_totals: dict[str, int] = {}
    # Parents always take priority in limit_graph. If the committed parent
    # cohort exhausts the graph budget, no resource can be displayed, so
    # count its eligible rows in SQL without materializing any resource ORM.
    shallow_budget = max_nodes if selection.depth == '1' else None
    parent_budget = (
        max(max_nodes - len(clusters), 0)
        if max_nodes is not None and selection.depth != '1'
        else shallow_budget
    )
    namespaces = _load_namespaces(cluster_ids, namespace, max_nodes=parent_budget, totals=source_totals)
    parent_total = source_totals.get('namespace', len(namespaces))
    if selection.depth == '1':
        family_budget = shallow_budget
    elif max_nodes is None:
        family_budget = None
    elif len(clusters) + parent_total >= max_nodes:
        family_budget = 0
    else:
        family_budget = max_nodes

    # Networking Pod relevance is determined by *every* committed Service
    # selector, not merely the 350-or-fewer rendered Service nodes. Stream
    # scalar selectors instead of loading the entire Service ORM family.
    service_selectors = (
        _load_service_selector_index(cluster_ids, namespace)
        if family_budget is not None and selection.scope == 'networking' and selection.include_pods
        else None
    )
    pods = _load_pods(
        cluster_ids,
        namespace,
        selection,
        max_nodes=family_budget,
        totals=source_totals,
        service_selectors=service_selectors,
    )
    return TopologyRecords(
        clusters=clusters,
        cluster_by_id={cluster.id: cluster for cluster in clusters},
        latest_cluster_inventory=latest_inventory,
        namespaces=namespaces,
        nodes=_load_nodes(cluster_ids, namespace, pods, selection, max_nodes=family_budget, totals=source_totals),
        workloads=_load_workloads(cluster_ids, namespace, selection, max_nodes=family_budget, totals=source_totals),
        services=_load_services(
            cluster_ids,
            namespace,
            selection,
            max_nodes=family_budget,
            totals=source_totals,
        ),
        ingresses=_load_ingresses(cluster_ids, namespace, selection, max_nodes=family_budget, totals=source_totals),
        configurations=_load_configurations(
            cluster_ids, namespace, selection, max_nodes=family_budget, totals=source_totals
        ),
        storage_items=_load_storage(
            cluster_ids,
            namespace,
            selection,
            max_nodes=family_budget,
            totals=source_totals,
        ),
        pods=pods,
        source_totals=source_totals,
        service_selectors=service_selectors,
    )


def _current_query(model, cluster_ids: list[str]):
    return filter_current_generation(model.query, model).filter(model.cluster_id.in_(cluster_ids))


def _namespaced_query(model, cluster_ids: list[str], namespace: str):
    query = _current_query(model, cluster_ids)
    return query.filter(model.namespace == namespace) if namespace else query


def _materialize_family(query, *, kind: str, max_nodes: int | None, totals: dict[str, int] | None):
    """Count full committed graph scope before loading a bounded type prefix."""
    if max_nodes is None:
        return query.all()
    if totals is not None:
        totals[kind] = query.order_by(None).count()
    return query.limit(max_nodes).all()


def _visible_namespace_query(query, model, cluster_ids: list[str]):
    """Graph resources require a Namespace parent in the latest generation."""
    visible = _current_query(NamespaceInventory, cluster_ids).filter(
        NamespaceInventory.cluster_id == model.cluster_id,
        NamespaceInventory.namespace == model.namespace,
    )
    return query.filter(visible.exists())


def _load_namespaces(
    cluster_ids: list[str],
    namespace: str,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[NamespaceInventory]:
    query = _current_query(NamespaceInventory, cluster_ids)
    if namespace:
        query = query.filter(NamespaceInventory.namespace == namespace)
    query = query.order_by(NamespaceInventory.cluster_id.asc(), NamespaceInventory.namespace.asc())
    if max_nodes is not None:
        if totals is not None:
            totals['namespace'] = query.order_by(None).count()
        query = query.limit(max_nodes)
    return query.all()


def _load_service_selector_index(
    cluster_ids: list[str],
    namespace: str,
) -> dict[tuple[str, str], list[dict[str, str]]]:
    """Stream complete selector *scalars* for networking relevance.

    Only distinct nonempty selectors are held, not Service ORM instances.
    Truncating this source before Pod matching would silently drop relations.
    """
    query = _visible_namespace_query(
        _namespaced_query(ServiceInventory, cluster_ids, namespace),
        ServiceInventory,
        cluster_ids,
    )
    selectors: dict[tuple[str, str], dict[tuple[tuple[str, str], ...], dict[str, str]]] = {}
    for cluster_id, scope, selector in query.with_entities(
        ServiceInventory.cluster_id, ServiceInventory.namespace, ServiceInventory.selector
    ).yield_per(256):
        if selector:
            selectors.setdefault((cluster_id, scope), {})[tuple(sorted(selector.items()))] = selector
    return {key: list(values.values()) for key, values in selectors.items()}


def _load_pods(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
    service_selectors: dict[tuple[str, str], list[dict[str, str]]] | None = None,
) -> list[PodInventory]:
    if not selection.include_pods:
        return []
    query = _namespaced_query(PodInventory, cluster_ids, namespace)
    if max_nodes is not None:
        query = _visible_namespace_query(query, PodInventory, cluster_ids)
    ordering = (
        PodInventory.cluster_id.asc(), PodInventory.namespace.asc(), PodInventory.pod_name.asc()
    )
    query = query.order_by(*ordering)
    if max_nodes is None or selection.scope in {'all', 'compute'}:
        return _materialize_family(query, kind='pod', max_nodes=max_nodes, totals=totals)

    if selection.scope == 'configuration':
        eligible = query.filter(func.json_array_length(PodInventory.configuration_references) > 0)
        return _materialize_family(eligible, kind='pod', max_nodes=max_nodes, totals=totals)
    if selection.scope == 'storage':
        eligible = query.filter(func.json_array_length(PodInventory.persistent_volume_claims) > 0)
        return _materialize_family(eligible, kind='pod', max_nodes=max_nodes, totals=totals)

    if selection.scope == 'networking':
        selectors = service_selectors or {}
        selected_ids: list[int] = []
        matching_total = 0
        # Scan cheap, generation-scoped scalar rows in bounded fetch batches;
        # materialize only the first graph-budget Pod ORM candidates.
        for pod_id, cluster_id, scope, labels in query.with_entities(
            PodInventory.id, PodInventory.cluster_id, PodInventory.namespace, PodInventory.labels
        ).yield_per(256):
            if not any(
                selector_matches(selector, labels or {})
                for selector in selectors.get((cluster_id, scope), ())
            ):
                continue
            matching_total += 1
            if len(selected_ids) < max_nodes:
                selected_ids.append(pod_id)
        if totals is not None:
            totals['pod'] = matching_total
        if not selected_ids:
            return []
        return query.filter(PodInventory.id.in_(selected_ids)).all()

    return _materialize_family(query, kind='pod', max_nodes=max_nodes, totals=totals)


def _load_nodes(
    cluster_ids: list[str],
    namespace: str,
    pods: list[PodInventory],
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[NodeInventory]:
    if not selection.include_level_1 or not selection.show_compute:
        return []
    query = _current_query(NodeInventory, cluster_ids)
    if namespace:
        # The committed correlated EXISTS preserves node placement even if
        # the matching Pod family exceeds the graph budget.
        referenced_pod = _namespaced_query(PodInventory, cluster_ids, namespace).filter(
            PodInventory.cluster_id == NodeInventory.cluster_id,
            PodInventory.node_name == NodeInventory.node_name,
        )
        query = query.filter(referenced_pod.exists())
    query = query.order_by(NodeInventory.cluster_id.asc(), NodeInventory.node_name.asc())
    if max_nodes is not None:
        if totals is not None:
            totals['node'] = query.order_by(None).count()
        query = query.limit(max_nodes)
    return query.all()


def _load_workloads(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[WorkloadInventory]:
    if not selection.include_level_2 or not selection.show_compute:
        return []
    query = _namespaced_query(WorkloadInventory, cluster_ids, namespace)
    if max_nodes is not None:
        query = _visible_namespace_query(query, WorkloadInventory, cluster_ids)
    query = query.order_by(
        WorkloadInventory.cluster_id.asc(),
        WorkloadInventory.namespace.asc(),
        WorkloadInventory.workload_type.asc(),
        WorkloadInventory.name.asc(),
    )
    return _materialize_family(query, kind='workload', max_nodes=max_nodes, totals=totals)


def _load_services(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[ServiceInventory]:
    if not selection.include_level_2 or not selection.show_networking:
        return []
    query = _namespaced_query(ServiceInventory, cluster_ids, namespace)
    if max_nodes is not None:
        query = _visible_namespace_query(query, ServiceInventory, cluster_ids)
    query = query.order_by(
        ServiceInventory.cluster_id.asc(),
        ServiceInventory.namespace.asc(),
        ServiceInventory.service_name.asc(),
    )
    return _materialize_family(query, kind='service', max_nodes=max_nodes, totals=totals)


def _load_ingresses(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[IngressInventory]:
    if not selection.include_level_2 or not selection.show_networking:
        return []
    query = _namespaced_query(IngressInventory, cluster_ids, namespace)
    if max_nodes is not None:
        query = _visible_namespace_query(query, IngressInventory, cluster_ids)
    query = query.order_by(
        IngressInventory.cluster_id.asc(),
        IngressInventory.namespace.asc(),
        IngressInventory.ingress_name.asc(),
    )
    return _materialize_family(query, kind='ingress', max_nodes=max_nodes, totals=totals)


def _load_configurations(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[ConfigurationInventory]:
    if not selection.include_level_2 or not selection.show_configuration:
        return []
    query = _namespaced_query(ConfigurationInventory, cluster_ids, namespace)
    if max_nodes is not None:
        query = _visible_namespace_query(query, ConfigurationInventory, cluster_ids)
    ordering = (
        ConfigurationInventory.cluster_id.asc(),
        ConfigurationInventory.namespace.asc(),
        ConfigurationInventory.object_type.asc(),
        ConfigurationInventory.name.asc(),
    )
    if max_nodes is None:
        return query.order_by(*ordering).all()
    # Different type groups have independent quotas in limit_graph.
    secret = func.lower(ConfigurationInventory.object_type) == 'secret'
    configmaps = query.filter(
        or_(ConfigurationInventory.object_type.is_(None), func.lower(ConfigurationInventory.object_type) != 'secret')
    )
    secrets = query.filter(secret)
    return [
        *_materialize_family(configmaps.order_by(*ordering), kind='configmap', max_nodes=max_nodes, totals=totals),
        *_materialize_family(secrets.order_by(*ordering), kind='secret', max_nodes=max_nodes, totals=totals),
    ]


def _load_storage(
    cluster_ids: list[str],
    namespace: str,
    selection: TopologySelection,
    *,
    max_nodes: int | None = None,
    totals: dict[str, int] | None = None,
) -> list[StorageInventory]:
    if not selection.include_level_2 or not selection.show_storage:
        return []
    query = _current_query(StorageInventory, cluster_ids)
    if namespace:
        query = query.filter(
            (StorageInventory.namespace == namespace)
            | (StorageInventory.namespace.is_(None) & (StorageInventory.storage_type == 'PersistentVolume'))
        )
    ordering = (
        StorageInventory.cluster_id.asc(),
        StorageInventory.storage_type.asc(),
        StorageInventory.namespace.asc(),
        StorageInventory.name.asc(),
    )
    if max_nodes is None:
        items = query.order_by(*ordering).all()
        return _storage_for_namespace(items, namespace) if namespace else items

    # Both kinds have independent graph budgets and exact committed counts.
    # For a selected namespace, only PVs referenced by its PVCs are eligible.
    # Correlate in SQL so a bounded prefix never discards a late valid binding.
    claims = _visible_namespace_query(
        query.filter(StorageInventory.storage_type == 'PersistentVolumeClaim'),
        StorageInventory,
        cluster_ids,
    )
    volumes = query.filter(StorageInventory.storage_type == 'PersistentVolume')
    if namespace:
        referenced_claim = aliased(StorageInventory)
        committed_claims = filter_current_generation(
            db.session.query(referenced_claim.id), referenced_claim
        ).filter(
            referenced_claim.cluster_id == StorageInventory.cluster_id,
            referenced_claim.namespace == namespace,
            referenced_claim.storage_type == 'PersistentVolumeClaim',
            func.trim(referenced_claim.details['volume_name'].as_string()) == StorageInventory.name,
        )
        volumes = volumes.filter(committed_claims.exists())
    return [
        *_materialize_family(claims.order_by(*ordering), kind='pvc', max_nodes=max_nodes, totals=totals),
        *_materialize_family(volumes.order_by(*ordering), kind='pv', max_nodes=max_nodes, totals=totals),
    ]


def _storage_for_namespace(items: list[StorageInventory], namespace: str) -> list[StorageInventory]:
    claims = [item for item in items if item.storage_type == 'PersistentVolumeClaim' and item.namespace == namespace]
    volume_keys = {
        (item.cluster_id, str((item.details or {}).get('volume_name') or '').strip())
        for item in claims
        if str((item.details or {}).get('volume_name') or '').strip()
    }
    return [
        item
        for item in items
        if (item.storage_type == 'PersistentVolumeClaim' and item.namespace == namespace)
        or (item.storage_type == 'PersistentVolume' and (item.cluster_id, item.name) in volume_keys)
    ]
