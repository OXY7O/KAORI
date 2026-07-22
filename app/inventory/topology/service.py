from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from flask import url_for
from sqlalchemy import false

from app.cluster.constants import get_environment_label
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

_TOPOLOGY_SCOPES = {
    'all': 'All Resources',
    'compute': 'Compute & Placement',
    'networking': 'Networking',
    'configuration': 'Configuration',
    'storage': 'Storage',
}

_TOPOLOGY_DEPTHS = {
    '1': '1 Level',
    '2': '2 Levels',
    '3': '3 Levels',
    'full': 'Full Relationships',
}

_TOPOLOGY_MAX_NODES = 350

_RESOURCE_GROUP_ORDER = (
    'node',
    'workload',
    'service',
    'ingress',
    'configmap',
    'secret',
    'pvc',
    'pv',
    'pod',
)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_datetime(value: datetime | None) -> str | None:
    normalized = _normalize_datetime(value)
    return normalized.isoformat() if normalized else None


def _display(value: Any, empty: str = 'Not reported') -> str:
    if value is None:
        return empty
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (list, tuple, set)):
        return ', '.join(str(item) for item in value) if value else empty
    normalized = str(value).strip()
    return normalized or empty


def _status_tone(value: str | None, resource_type: str) -> str:
    normalized = (value or '').strip().lower()

    if resource_type == 'cluster':
        if normalized == 'connected':
            return 'healthy'
        if normalized == 'failed':
            return 'critical'
        return 'unknown'

    if resource_type == 'node':
        if normalized == 'ready':
            return 'healthy'
        if normalized in {'notready', 'not ready', 'failed'}:
            return 'critical'
        return 'unknown'

    if resource_type == 'namespace':
        if normalized == 'active':
            return 'healthy'
        if normalized == 'terminating':
            return 'warning'
        return 'unknown'

    if resource_type == 'pod':
        if normalized in {'running', 'succeeded', 'completed'}:
            return 'healthy'
        if normalized in {'pending', 'terminating', 'containercreating'}:
            return 'warning'
        if normalized in {'failed', 'error', 'crashloopbackoff'}:
            return 'critical'
        return 'unknown'

    if resource_type == 'storage':
        if normalized in {'bound', 'available'}:
            return 'healthy'
        if normalized in {'pending', 'released'}:
            return 'warning'
        if normalized in {'failed', 'lost'}:
            return 'critical'
        return 'unknown'

    if resource_type == 'workload':
        if normalized in {'ready', 'running', 'active', 'available', 'complete', 'completed'}:
            return 'healthy'
        if normalized in {'pending', 'progressing', 'partial', 'degraded'}:
            return 'warning'
        if normalized in {'failed', 'unavailable', 'error'}:
            return 'critical'
        return 'info'

    return 'info'


def _field(label: str, value: Any, *, empty: str = 'Not reported') -> dict[str, str]:
    return {
        'label': label,
        'value': _display(value, empty),
    }


def _node_element(
    *,
    element_id: str,
    label: str,
    resource_type: str,
    kind: str,
    status: str,
    status_tone: str,
    cluster_id: str,
    cluster_name: str,
    namespace: str | None,
    parent: str | None,
    fields: list[dict[str, str]],
    collected_at: datetime | None,
    action_url: str | None,
    description: str,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        'id': element_id,
        'label': label,
        'name': label,
        'type': resource_type,
        'kind': kind,
        'status': status,
        'status_tone': status_tone,
        'cluster_id': cluster_id,
        'cluster_name': cluster_name,
        'namespace': namespace,
        'fields': fields,
        'collected_at': _iso_datetime(collected_at),
        'action_url': action_url,
        'description': description,
    }
    if parent:
        data['parent'] = parent
    return {'data': data}


def _edge_element(
    *,
    edge_id: str,
    source: str,
    target: str,
    relationship: str,
    label: str,
    source_label: str,
    target_label: str,
    description: str,
) -> dict[str, Any]:
    return {
        'data': {
            'id': edge_id,
            'source': source,
            'target': target,
            'relationship': relationship,
            'label': label,
            'source_label': source_label,
            'target_label': target_label,
            'description': description,
        }
    }


def _apply_cluster_filter(query, model, cluster_ids: list[str]):
    return query.filter(model.cluster_id.in_(cluster_ids))


def _apply_namespace_filter(query, model, namespace: str):
    if namespace:
        return query.filter(model.namespace == namespace)
    return query


def _selector_matches(selector: dict[str, str], labels: dict[str, str]) -> bool:
    if not selector:
        return False
    return all(labels.get(key) == value for key, value in selector.items())


def _limit_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    max_nodes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if len(nodes) <= max_nodes:
        return nodes, edges, 0

    parents = [node for node in nodes if node['data']['type'] in {'cluster', 'namespace'}]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_type = node['data']['type']
        if node_type not in {'cluster', 'namespace'}:
            groups[node_type].append(node)

    kept = list(parents[:max_nodes])
    remaining = max(0, max_nodes - len(kept))
    active_types = [resource_type for resource_type in _RESOURCE_GROUP_ORDER if groups.get(resource_type)]

    if remaining and active_types:
        base_share = max(1, remaining // len(active_types))
        offsets: dict[str, int] = {}

        for resource_type in active_types:
            selected = groups[resource_type][:base_share]
            kept.extend(selected)
            offsets[resource_type] = len(selected)

        while len(kept) < max_nodes:
            added = False
            for resource_type in active_types:
                offset = offsets[resource_type]
                group = groups[resource_type]
                if offset >= len(group):
                    continue
                kept.append(group[offset])
                offsets[resource_type] += 1
                added = True
                if len(kept) >= max_nodes:
                    break
            if not added:
                break

    kept_ids = {node['data']['id'] for node in kept}
    limited_edges = [
        edge
        for edge in edges
        if edge['data']['source'] in kept_ids and edge['data']['target'] in kept_ids
    ]
    return kept, limited_edges, len(nodes) - len(kept)


def normalize_topology_filters(
    *,
    cluster_id: str,
    namespace: str,
    scope: str,
    depth: str,
) -> dict[str, str]:
    normalized_cluster_id = cluster_id.strip()
    normalized_namespace = namespace.strip()
    normalized_scope = scope if scope in _TOPOLOGY_SCOPES else 'all'
    normalized_depth = depth if depth in _TOPOLOGY_DEPTHS else '1'

    if normalized_cluster_id:
        cluster_exists = Cluster.query.filter(Cluster.id == normalized_cluster_id).first() is not None
        if not cluster_exists:
            normalized_cluster_id = ''
            normalized_namespace = ''

    if normalized_namespace and normalized_cluster_id:
        namespace_exists = (
            NamespaceInventory.query.filter(
                NamespaceInventory.cluster_id == normalized_cluster_id,
                NamespaceInventory.namespace == normalized_namespace,
            ).first()
            is not None
        )
        if not namespace_exists:
            normalized_namespace = ''
    elif normalized_namespace:
        normalized_namespace = ''

    return {
        'cluster_id': normalized_cluster_id,
        'namespace': normalized_namespace,
        'scope': normalized_scope,
        'depth': normalized_depth,
    }


def build_topology_page_context(
    *,
    cluster_id: str,
    namespace: str,
    scope: str,
    depth: str,
) -> dict[str, Any]:
    filters = normalize_topology_filters(
        cluster_id=cluster_id,
        namespace=namespace,
        scope=scope,
        depth=depth,
    )

    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    namespace_rows = NamespaceInventory.query.order_by(
        NamespaceInventory.cluster_id.asc(),
        NamespaceInventory.namespace.asc(),
    ).all()

    namespace_map: dict[str, list[str]] = defaultdict(list)
    for row in namespace_rows:
        namespace_map[row.cluster_id].append(row.namespace)

    graph = build_topology_graph(**filters)

    return {
        'clusters': clusters,
        'namespace_map': dict(namespace_map),
        'scope_options': _TOPOLOGY_SCOPES,
        'depth_options': _TOPOLOGY_DEPTHS,
        'filters': filters,
        'graph': graph,
    }


def build_topology_graph(
    *,
    cluster_id: str,
    namespace: str,
    scope: str,
    depth: str,
) -> dict[str, Any]:
    filters = normalize_topology_filters(
        cluster_id=cluster_id,
        namespace=namespace,
        scope=scope,
        depth=depth,
    )
    cluster_id = filters['cluster_id']
    namespace = filters['namespace']
    scope = filters['scope']
    depth = filters['depth']

    cluster_query = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc())
    if cluster_id:
        cluster_query = cluster_query.filter(Cluster.id == cluster_id)
    clusters = cluster_query.all()
    cluster_ids = [cluster.id for cluster in clusters]

    if not cluster_ids:
        return {
            'nodes': [],
            'edges': [],
            'summary': {
                'clusters': 0,
                'namespaces': 0,
                'resources': 0,
                'relationships': 0,
                'last_collected_at': None,
                'scope_label': _TOPOLOGY_SCOPES[scope],
                'depth_label': _TOPOLOGY_DEPTHS[depth],
                'truncated': False,
                'omitted_nodes': 0,
            },
            'type_counts': {},
            'filters': filters,
        }

    cluster_by_id = {cluster.id: cluster for cluster in clusters}

    namespace_query = _apply_cluster_filter(
        NamespaceInventory.query,
        NamespaceInventory,
        cluster_ids,
    )
    if namespace:
        namespace_query = namespace_query.filter(NamespaceInventory.namespace == namespace)
    namespaces = namespace_query.order_by(
        NamespaceInventory.cluster_id.asc(),
        NamespaceInventory.namespace.asc(),
    ).all()


    def namespaced_query(model):
        query = _apply_cluster_filter(model.query, model, cluster_ids)
        return _apply_namespace_filter(query, model, namespace)

    pods = namespaced_query(PodInventory).order_by(
        PodInventory.cluster_id.asc(),
        PodInventory.namespace.asc(),
        PodInventory.pod_name.asc(),
    ).all()

    node_query = _apply_cluster_filter(NodeInventory.query, NodeInventory, cluster_ids)
    if namespace:
        referenced_nodes = sorted({pod.node_name for pod in pods if pod.node_name})
        if referenced_nodes:
            node_query = node_query.filter(NodeInventory.node_name.in_(referenced_nodes))
        else:
            node_query = node_query.filter(false())
    nodes_inventory = node_query.order_by(
        NodeInventory.cluster_id.asc(),
        NodeInventory.node_name.asc(),
    ).all()

    workloads = namespaced_query(WorkloadInventory).order_by(
        WorkloadInventory.cluster_id.asc(),
        WorkloadInventory.namespace.asc(),
        WorkloadInventory.workload_type.asc(),
        WorkloadInventory.name.asc(),
    ).all()
    services = namespaced_query(ServiceInventory).order_by(
        ServiceInventory.cluster_id.asc(),
        ServiceInventory.namespace.asc(),
        ServiceInventory.service_name.asc(),
    ).all()
    ingresses = namespaced_query(IngressInventory).order_by(
        IngressInventory.cluster_id.asc(),
        IngressInventory.namespace.asc(),
        IngressInventory.ingress_name.asc(),
    ).all()
    configurations = namespaced_query(ConfigurationInventory).order_by(
        ConfigurationInventory.cluster_id.asc(),
        ConfigurationInventory.namespace.asc(),
        ConfigurationInventory.object_type.asc(),
        ConfigurationInventory.name.asc(),
    ).all()

    storage_query = _apply_cluster_filter(StorageInventory.query, StorageInventory, cluster_ids)
    if namespace:
        storage_query = storage_query.filter(
            (StorageInventory.namespace == namespace)
            | (
                StorageInventory.namespace.is_(None)
                & (StorageInventory.storage_type == 'PersistentVolume')
            )
        )
    storage_items = storage_query.order_by(
        StorageInventory.cluster_id.asc(),
        StorageInventory.storage_type.asc(),
        StorageInventory.namespace.asc(),
        StorageInventory.name.asc(),
    ).all()

    if namespace:
        selected_claims = [
            item
            for item in storage_items
            if item.storage_type == 'PersistentVolumeClaim'
            and item.namespace == namespace
        ]
        selected_volume_names = {
            str((item.details or {}).get('volume_name') or '').strip()
            for item in selected_claims
            if str((item.details or {}).get('volume_name') or '').strip()
        }
        storage_items = [
            item
            for item in storage_items
            if (
                item.storage_type == 'PersistentVolumeClaim'
                and item.namespace == namespace
            )
            or (
                item.storage_type == 'PersistentVolume'
                and item.name in selected_volume_names
            )
        ]

    cluster_inventory_rows = (
        ClusterInventory.query.filter(ClusterInventory.cluster_id.in_(cluster_ids))
        .order_by(ClusterInventory.collected_at.desc())
        .all()
    )
    latest_cluster_inventory: dict[str, ClusterInventory] = {}
    for row in cluster_inventory_rows:
        latest_cluster_inventory.setdefault(row.cluster_id, row)

    include_level_1 = True
    include_level_2 = depth in {'2', '3', 'full'}
    include_pods = depth in {'3', 'full'}
    include_all_relationships = depth == 'full'

    show_compute = scope in {'all', 'compute'}
    show_networking = scope in {'all', 'networking'}
    show_configuration = scope in {'all', 'configuration'}
    show_storage = scope in {'all', 'storage'}

    graph_nodes: list[dict[str, Any]] = []
    graph_edges: list[dict[str, Any]] = []
    collected_values: list[datetime] = []

    cluster_node_ids: dict[str, str] = {}
    namespace_node_ids: dict[tuple[str, str], str] = {}
    node_node_ids: dict[tuple[str, str], str] = {}
    workload_node_ids: dict[tuple[str, str, str, str], str] = {}
    service_node_ids: dict[tuple[str, str, str], str] = {}
    config_node_ids: dict[tuple[str, str, str, str], str] = {}
    pvc_node_ids: dict[tuple[str, str, str], str] = {}
    pv_node_ids: dict[tuple[str, str], str] = {}
    pod_node_ids: dict[tuple[str, str, str], str] = {}

    for cluster in clusters:
        element_id = f'cluster:{cluster.id}'
        cluster_node_ids[cluster.id] = element_id
        inventory_row = latest_cluster_inventory.get(cluster.id)
        if inventory_row:
            collected_values.append(inventory_row.collected_at)
        graph_nodes.append(
            _node_element(
                element_id=element_id,
                label=cluster.name,
                resource_type='cluster',
                kind='Cluster',
                status=cluster.status or 'Unknown',
                status_tone=_status_tone(cluster.status, 'cluster'),
                cluster_id=cluster.id,
                cluster_name=cluster.name,
                namespace=None,
                parent=None,
                fields=[
                    _field('Environment', get_environment_label(cluster.environment)),
                    _field('Status', cluster.status),
                    _field('API server', cluster.kubernetes_connection.server),
                    _field('Kubernetes version', inventory_row.kubernetes_version if inventory_row else None),
                    _field('Nodes', cluster.node_count),
                ],
                collected_at=inventory_row.collected_at if inventory_row else cluster.updated_at,
                action_url=url_for('integrations.kubernetes'),
                description='Registered Kubernetes cluster and inventory snapshot boundary.',
            )
        )

    for item in namespaces:
        cluster = cluster_by_id[item.cluster_id]
        element_id = f'namespace:{item.id}'
        namespace_node_ids[(item.cluster_id, item.namespace)] = element_id
        collected_values.append(item.collected_at)
        graph_nodes.append(
            _node_element(
                element_id=element_id,
                label=item.namespace,
                resource_type='namespace',
                kind='Namespace',
                status=item.status or 'Unknown',
                status_tone=_status_tone(item.status, 'namespace'),
                cluster_id=item.cluster_id,
                cluster_name=cluster.name,
                namespace=item.namespace,
                parent=cluster_node_ids[item.cluster_id],
                fields=[
                    _field('Status', item.status),
                    _field('Kubernetes UID', item.uid),
                    _field('LimitRanges', item.limit_range_count, empty='0'),
                    _field('NetworkPolicies', item.network_policy_count, empty='0'),
                    _field('ServiceAccounts', item.service_account_count, empty='0'),
                ],
                collected_at=item.collected_at,
                action_url=url_for(
                    'inventory.namespaces',
                    cluster_id=item.cluster_id,
                    search=item.namespace,
                ),
                description='Namespace boundary containing namespaced Kubernetes resources.',
            )
        )

    if include_level_1 and show_compute:
        for item in nodes_inventory:
            cluster = cluster_by_id[item.cluster_id]
            element_id = f'node:{item.id}'
            node_node_ids[(item.cluster_id, item.node_name)] = element_id
            collected_values.append(item.collected_at)
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.node_name,
                    resource_type='node',
                    kind='Node',
                    status=item.status or 'Unknown',
                    status_tone=_status_tone(item.status, 'node'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=None,
                    parent=cluster_node_ids[item.cluster_id],
                    fields=[
                        _field('Role', item.role),
                        _field('Status', item.status),
                        _field('Internal IP', item.internal_ip),
                        _field('Operating system', item.os_image),
                        _field('Kubelet version', item.kubelet_version),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.nodes',
                        cluster_id=item.cluster_id,
                        search=item.node_name,
                    ),
                    description='Kubernetes node used for workload placement and scheduling.',
                )
            )

    if include_level_2 and show_compute:
        for item in workloads:
            parent = namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = cluster_by_id[item.cluster_id]
            element_id = f'workload:{item.id}'
            workload_node_ids[(item.cluster_id, item.namespace, item.workload_type, item.name)] = element_id
            collected_values.append(item.collected_at)
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.name,
                    resource_type='workload',
                    kind=item.workload_type,
                    status=item.status or item.ready or 'Unknown',
                    status_tone=_status_tone(item.status or item.ready, 'workload'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        _field('Type', item.workload_type),
                        _field('Status', item.status),
                        _field('Ready', item.ready),
                        _field('Namespace', item.namespace),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.workloads',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.name,
                    ),
                    description='Workload controller recorded in the latest inventory snapshot.',
                )
            )

    if include_level_2 and show_networking:
        for item in services:
            parent = namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = cluster_by_id[item.cluster_id]
            element_id = f'service:{item.id}'
            service_node_ids[(item.cluster_id, item.namespace, item.service_name)] = element_id
            collected_values.append(item.collected_at)
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.service_name,
                    resource_type='service',
                    kind='Service',
                    status='Configured',
                    status_tone='info',
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        _field('Type', item.service_type),
                        _field('Cluster IP', item.cluster_ip),
                        _field('External IP', item.external_ip),
                        _field('Ports', item.ports),
                        _field('Selector labels', len(item.selector or {}), empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.services',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.service_name,
                    ),
                    description='Service exposing pods selected by Kubernetes labels.',
                )
            )

        for item in ingresses:
            parent = namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = cluster_by_id[item.cluster_id]
            element_id = f'ingress:{item.id}'
            collected_values.append(item.collected_at)
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.ingress_name,
                    resource_type='ingress',
                    kind='Ingress',
                    status='Configured' if item.backend_paths else 'No backends',
                    status_tone='info' if item.backend_paths else 'warning',
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        _field('Host', item.host),
                        _field('Ingress class', item.ingress_class),
                        _field('Address', item.address),
                        _field('TLS enabled', item.tls_enabled),
                        _field('Backend paths', len(item.backend_paths or []), empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.ingresses',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.ingress_name,
                    ),
                    description='Ingress routing external hosts and paths to Kubernetes Services.',
                )
            )

    if include_level_2 and show_configuration:
        for item in configurations:
            parent = namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = cluster_by_id[item.cluster_id]
            object_type = item.object_type or 'Configuration'
            resource_type = 'secret' if object_type.lower() == 'secret' else 'configmap'
            element_id = f'configuration:{item.id}'
            config_node_ids[(item.cluster_id, item.namespace, object_type, item.name)] = element_id
            collected_values.append(item.collected_at)
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.name,
                    resource_type=resource_type,
                    kind=object_type,
                    status='Immutable' if item.immutable else 'Mutable',
                    status_tone='info',
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        _field('Object type', object_type),
                        _field('Secret type', item.secret_type),
                        _field('Keys', item.key_count, empty='0'),
                        _field('Immutable', item.immutable),
                        _field('Payload bytes', item.payload_size_bytes, empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.configuration',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        type=object_type,
                        search=item.name,
                    ),
                    description='Configuration object referenced by pods through volumes or environment sources.',
                )
            )

    if include_level_2 and show_storage:
        for item in storage_items:
            cluster = cluster_by_id[item.cluster_id]
            if item.storage_type == 'PersistentVolumeClaim':
                if not item.namespace:
                    continue
                parent = namespace_node_ids.get((item.cluster_id, item.namespace))
                if not parent:
                    continue
                resource_type = 'pvc'
                kind = 'PersistentVolumeClaim'
                element_id = f'pvc:{item.id}'
                pvc_node_ids[(item.cluster_id, item.namespace, item.name)] = element_id
                action_url = url_for(
                    'inventory.storage',
                    cluster_id=item.cluster_id,
                    namespace=item.namespace,
                    type=item.storage_type,
                    search=item.name,
                )
            elif item.storage_type == 'PersistentVolume':
                parent = cluster_node_ids[item.cluster_id]
                resource_type = 'pv'
                kind = 'PersistentVolume'
                element_id = f'pv:{item.id}'
                pv_node_ids[(item.cluster_id, item.name)] = element_id
                action_url = url_for(
                    'inventory.storage',
                    cluster_id=item.cluster_id,
                    type=item.storage_type,
                    search=item.name,
                )
            else:
                continue

            collected_values.append(item.collected_at)
            details = item.details or {}
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.name,
                    resource_type=resource_type,
                    kind=kind,
                    status=item.status or 'Unknown',
                    status_tone=_status_tone(item.status, 'storage'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        _field('Status', item.status),
                        _field('Storage class', item.storage_class),
                        _field('Capacity', item.capacity),
                        _field('Bound volume', details.get('volume_name')),
                        _field('Claim', details.get('claim_name')),
                    ],
                    collected_at=item.collected_at,
                    action_url=action_url,
                    description='Persistent storage object and its current binding state.',
                )
            )

    if include_pods:
        for item in pods:
            parent = namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue

            relevant = scope == 'all'
            if scope == 'compute':
                relevant = True
            elif scope == 'networking':
                relevant = any(_selector_matches(service.selector or {}, item.labels or {}) for service in services)
            elif scope == 'configuration':
                relevant = bool(item.configuration_references)
            elif scope == 'storage':
                relevant = bool(item.persistent_volume_claims)

            if not relevant:
                continue

            cluster = cluster_by_id[item.cluster_id]
            element_id = f'pod:{item.id}'
            pod_node_ids[(item.cluster_id, item.namespace, item.pod_name)] = element_id
            collected_values.append(item.collected_at)
            owner = (
                f'{item.workload_type}/{item.workload_name}'
                if item.workload_type and item.workload_name
                else 'Standalone Pod'
            )
            graph_nodes.append(
                _node_element(
                    element_id=element_id,
                    label=item.pod_name,
                    resource_type='pod',
                    kind='Pod',
                    status=item.phase or 'Unknown',
                    status_tone=_status_tone(item.phase, 'pod'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        _field('Phase', item.phase),
                        _field('Ready', item.ready),
                        _field('Owner', owner),
                        _field('Node', item.node_name),
                        _field('Pod IP', item.pod_ip),
                        _field('Restarts', item.restart_count, empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.pods',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.pod_name,
                    ),
                    description='Pod instance with workload ownership, placement, and dependency references.',
                )
            )

    # Workload ownership and node placement.
    if include_pods and show_compute:
        for pod in pods:
            pod_id = pod_node_ids.get((pod.cluster_id, pod.namespace, pod.pod_name))
            if not pod_id:
                continue

            workload_id = None
            if pod.workload_type and pod.workload_name:
                workload_id = workload_node_ids.get(
                    (pod.cluster_id, pod.namespace, pod.workload_type, pod.workload_name)
                )
            if workload_id:
                graph_edges.append(
                    _edge_element(
                        edge_id=f'owns:{workload_id}:{pod_id}',
                        source=workload_id,
                        target=pod_id,
                        relationship='owns',
                        label='owns',
                        source_label=pod.workload_name or 'Workload',
                        target_label=pod.pod_name,
                        description='The workload controller owns this pod instance.',
                    )
                )

            node_id = node_node_ids.get((pod.cluster_id, pod.node_name or ''))
            if node_id:
                graph_edges.append(
                    _edge_element(
                        edge_id=f'scheduled:{pod_id}:{node_id}',
                        source=pod_id,
                        target=node_id,
                        relationship='scheduled_on',
                        label='scheduled on',
                        source_label=pod.pod_name,
                        target_label=pod.node_name or 'Node',
                        description='The Kubernetes scheduler placed this pod on the selected node.',
                    )
                )

    # Service selectors and ingress routes.
    if show_networking and include_level_2:
        for ingress in ingresses:
            ingress_id = f'ingress:{ingress.id}'
            for index, backend in enumerate(ingress.backend_paths or []):
                service_name = str(backend.get('service_name') or '').strip()
                service_id = service_node_ids.get((ingress.cluster_id, ingress.namespace, service_name))
                if not service_id:
                    continue
                graph_edges.append(
                    _edge_element(
                        edge_id=f'routes:{ingress_id}:{service_id}:{index}',
                        source=ingress_id,
                        target=service_id,
                        relationship='routes_to',
                        label='routes to',
                        source_label=ingress.ingress_name,
                        target_label=service_name,
                        description=(
                            f"Ingress path {backend.get('path') or '/'} routes to Service "
                            f"{service_name}:{backend.get('service_port') or '-'}"
                        ),
                    )
                )

        if include_pods:
            for service in services:
                service_id = service_node_ids.get((service.cluster_id, service.namespace, service.service_name))
                if not service_id or not service.selector:
                    continue
                for pod in pods:
                    if pod.cluster_id != service.cluster_id or pod.namespace != service.namespace:
                        continue
                    pod_id = pod_node_ids.get((pod.cluster_id, pod.namespace, pod.pod_name))
                    if not pod_id or not _selector_matches(service.selector or {}, pod.labels or {}):
                        continue
                    graph_edges.append(
                        _edge_element(
                            edge_id=f'selects:{service_id}:{pod_id}',
                            source=service_id,
                            target=pod_id,
                            relationship='selects',
                            label='selects',
                            source_label=service.service_name,
                            target_label=pod.pod_name,
                            description='The Service selector matches the labels recorded on this pod.',
                        )
                    )

    # Pod configuration references.
    if show_configuration and include_pods:
        for pod in pods:
            pod_id = pod_node_ids.get((pod.cluster_id, pod.namespace, pod.pod_name))
            if not pod_id:
                continue
            for index, reference in enumerate(pod.configuration_references or []):
                object_type = str(reference.get('type') or '').strip()
                object_name = str(reference.get('name') or '').strip()
                config_id = config_node_ids.get((pod.cluster_id, pod.namespace, object_type, object_name))
                if not config_id:
                    continue
                graph_edges.append(
                    _edge_element(
                        edge_id=f'uses:{pod_id}:{config_id}:{index}',
                        source=pod_id,
                        target=config_id,
                        relationship='uses',
                        label='uses',
                        source_label=pod.pod_name,
                        target_label=object_name,
                        description=f'The pod references this {object_type} through its configuration.',
                    )
                )

    # Pod mounts and PVC to PV bindings.
    if show_storage and include_level_2:
        for pvc in storage_items:
            if pvc.storage_type != 'PersistentVolumeClaim' or not pvc.namespace:
                continue
            pvc_id = pvc_node_ids.get((pvc.cluster_id, pvc.namespace, pvc.name))
            if not pvc_id:
                continue
            volume_name = str((pvc.details or {}).get('volume_name') or '').strip()
            pv_id = pv_node_ids.get((pvc.cluster_id, volume_name))
            if pv_id:
                graph_edges.append(
                    _edge_element(
                        edge_id=f'binds:{pvc_id}:{pv_id}',
                        source=pvc_id,
                        target=pv_id,
                        relationship='binds',
                        label='binds',
                        source_label=pvc.name,
                        target_label=volume_name,
                        description='The PersistentVolumeClaim is bound to this PersistentVolume.',
                    )
                )

        if include_pods:
            for pod in pods:
                pod_id = pod_node_ids.get((pod.cluster_id, pod.namespace, pod.pod_name))
                if not pod_id:
                    continue
                for index, claim_name in enumerate(pod.persistent_volume_claims or []):
                    pvc_id = pvc_node_ids.get((pod.cluster_id, pod.namespace, claim_name))
                    if not pvc_id:
                        continue
                    graph_edges.append(
                        _edge_element(
                            edge_id=f'mounts:{pod_id}:{pvc_id}:{index}',
                            source=pod_id,
                            target=pvc_id,
                            relationship='mounts',
                            label='mounts',
                            source_label=pod.pod_name,
                            target_label=claim_name,
                            description='The pod mounts storage provided by this PersistentVolumeClaim.',
                        )
                    )

    # Full mode keeps every supported edge. Three-level mode intentionally hides
    # indirect configuration and storage edges when the matching scope is not selected.
    if not include_all_relationships and scope == 'all' and depth == '3':
        allowed_relationships = {'owns', 'scheduled_on', 'selects', 'routes_to'}
        graph_edges = [
            edge for edge in graph_edges if edge['data']['relationship'] in allowed_relationships
        ]

    graph_nodes, graph_edges, omitted_nodes = _limit_graph(
        graph_nodes,
        graph_edges,
        _TOPOLOGY_MAX_NODES,
    )

    type_counts: dict[str, int] = defaultdict(int)
    for node in graph_nodes:
        type_counts[node['data']['type']] += 1

    normalized_collected_values = [
        normalized
        for value in collected_values
        if (normalized := _normalize_datetime(value)) is not None
    ]
    latest_collected = max(normalized_collected_values, default=None)

    cluster_count = type_counts.get('cluster', 0)
    namespace_count = type_counts.get('namespace', 0)
    resource_count = max(len(graph_nodes) - cluster_count - namespace_count, 0)

    return {
        'nodes': graph_nodes,
        'edges': graph_edges,
        'summary': {
            'clusters': cluster_count,
            'namespaces': namespace_count,
            'resources': resource_count,
            'relationships': len(graph_edges),
            'last_collected_at': _iso_datetime(latest_collected),
            'scope_label': _TOPOLOGY_SCOPES[scope],
            'depth_label': _TOPOLOGY_DEPTHS[depth],
            'truncated': omitted_nodes > 0,
            'omitted_nodes': omitted_nodes,
        },
        'type_counts': dict(type_counts),
        'filters': filters,
    }
