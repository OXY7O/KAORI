from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from typing import Any

from app.common.inventory_generation import filter_current_generation
from app.inventory.kubernetes.topology.contracts import TopologySelection
from app.inventory.kubernetes.topology.graph_builder import TopologyGraphBuilder
from app.inventory.kubernetes.topology.repository import (
    latest_cluster_inventory,
    load_clusters,
    load_namespace_map,
    load_topology_records,
    topology_generation_signature,
)
from app.models import Cluster, NamespaceInventory

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
_TOPOLOGY_CACHE_MAX_ENTRIES = 24
_TOPOLOGY_CACHE: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
_TOPOLOGY_CACHE_LOCK = RLock()


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

    if normalized_cluster_id and not _cluster_exists(normalized_cluster_id):
        normalized_cluster_id = ''
        normalized_namespace = ''
    if normalized_namespace and not _namespace_exists(normalized_cluster_id, normalized_namespace):
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
    return {
        'clusters': load_clusters(''),
        'namespace_map': load_namespace_map(),
        'scope_options': _TOPOLOGY_SCOPES,
        'depth_options': _TOPOLOGY_DEPTHS,
        'filters': filters,
        'graph': build_topology_graph(**filters),
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
    clusters = load_clusters(filters['cluster_id'])
    if not clusters:
        return _empty_graph(filters)

    latest_inventory = latest_cluster_inventory([cluster.id for cluster in clusters])
    generation_signature = topology_generation_signature(clusters, latest_inventory)
    cache_key = _cache_key(generation_signature, filters)
    cached_payload = _topology_cache_get(cache_key)
    if cached_payload is not None:
        return cached_payload

    selection = TopologySelection.from_filters(scope=filters['scope'], depth=filters['depth'])
    records = load_topology_records(
        clusters=clusters,
        latest_inventory=latest_inventory,
        namespace=filters['namespace'],
        selection=selection,
    )
    payload = TopologyGraphBuilder(records, selection, max_nodes=_TOPOLOGY_MAX_NODES).build(
        filters=filters,
        scope_label=_TOPOLOGY_SCOPES[filters['scope']],
        depth_label=_TOPOLOGY_DEPTHS[filters['depth']],
    )
    _topology_cache_put(cache_key, payload)
    return payload


def _cluster_exists(cluster_id: str) -> bool:
    return Cluster.query.filter(Cluster.id == cluster_id).first() is not None


def _namespace_exists(cluster_id: str, namespace: str) -> bool:
    if not cluster_id:
        return False
    return (
        filter_current_generation(NamespaceInventory.query, NamespaceInventory)
        .filter(
            NamespaceInventory.cluster_id == cluster_id,
            NamespaceInventory.namespace == namespace,
        )
        .first()
        is not None
    )


def _empty_graph(filters: dict[str, str]) -> dict[str, Any]:
    return {
        'nodes': [],
        'edges': [],
        'summary': {
            'clusters': 0,
            'namespaces': 0,
            'resources': 0,
            'relationships': 0,
            'last_collected_at': None,
            'scope_label': _TOPOLOGY_SCOPES[filters['scope']],
            'depth_label': _TOPOLOGY_DEPTHS[filters['depth']],
            'truncated': False,
            'omitted_nodes': 0,
            'omitted_by_type': {},
        },
        'type_counts': {},
        'filters': filters,
    }


def _cache_key(
    generation_signature: tuple[tuple[str, str | None, str | None], ...],
    filters: dict[str, str],
) -> tuple[Any, ...]:
    return (
        generation_signature,
        filters['cluster_id'],
        filters['namespace'],
        filters['scope'],
        filters['depth'],
    )


def _topology_cache_get(key: tuple[Any, ...]) -> dict[str, Any] | None:
    with _TOPOLOGY_CACHE_LOCK:
        cached = _TOPOLOGY_CACHE.get(key)
        if cached is None:
            return None
        _TOPOLOGY_CACHE.move_to_end(key)
        return deepcopy(cached)


def _topology_cache_put(key: tuple[Any, ...], payload: dict[str, Any]) -> None:
    with _TOPOLOGY_CACHE_LOCK:
        _TOPOLOGY_CACHE[key] = deepcopy(payload)
        _TOPOLOGY_CACHE.move_to_end(key)
        while len(_TOPOLOGY_CACHE) > _TOPOLOGY_CACHE_MAX_ENTRIES:
            _TOPOLOGY_CACHE.popitem(last=False)
