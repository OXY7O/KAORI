from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.inventory.topology.contracts import TopologyEdgeSpec, TopologyNodeSpec

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


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_datetime(value: datetime | None) -> str | None:
    normalized = normalize_datetime(value)
    return normalized.isoformat() if normalized else None


def display(value: Any, empty: str = 'Not Reported') -> str:
    if value is None:
        return empty
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (list, tuple, set)):
        return ', '.join(str(item) for item in value) if value else empty
    normalized = str(value).strip()
    return normalized or empty


def status_tone(value: str | None, resource_type: str) -> str:
    normalized = (value or '').strip().lower()
    handlers = {
        'cluster': _cluster_tone,
        'node': _node_tone,
        'namespace': _namespace_tone,
        'pod': _pod_tone,
        'storage': _storage_tone,
        'workload': _workload_tone,
    }
    handler = handlers.get(resource_type)
    return handler(normalized) if handler else 'info'


def _cluster_tone(value: str) -> str:
    if value == 'connected':
        return 'healthy'
    if value == 'failed':
        return 'critical'
    return 'unknown'


def _node_tone(value: str) -> str:
    if value == 'ready':
        return 'healthy'
    if value in {'notready', 'not ready', 'failed'}:
        return 'critical'
    return 'unknown'


def _namespace_tone(value: str) -> str:
    if value == 'active':
        return 'healthy'
    if value == 'terminating':
        return 'warning'
    return 'unknown'


def _pod_tone(value: str) -> str:
    if value in {'running', 'succeeded', 'completed'}:
        return 'healthy'
    if value in {'pending', 'terminating', 'containercreating'}:
        return 'warning'
    if value in {'failed', 'error', 'crashloopbackoff'}:
        return 'critical'
    return 'unknown'


def _storage_tone(value: str) -> str:
    if value in {'bound', 'available'}:
        return 'healthy'
    if value in {'pending', 'released'}:
        return 'warning'
    if value in {'failed', 'lost'}:
        return 'critical'
    return 'unknown'


def _workload_tone(value: str) -> str:
    if value in {'stable', 'ready', 'active', 'available', 'complete', 'completed'}:
        return 'healthy'
    if value in {'pending', 'progressing', 'partial', 'degraded', 'suspended'}:
        return 'warning'
    if value in {'failed', 'unavailable', 'error'}:
        return 'critical'
    if value in {'unknown', 'not reported'}:
        return 'unknown'
    return 'info'


def field(label: str, value: Any, *, empty: str = 'Not Reported') -> dict[str, str]:
    return {'label': label, 'value': display(value, empty)}


def node_element(spec: TopologyNodeSpec) -> dict[str, Any]:
    data: dict[str, Any] = {
        'id': spec.element_id,
        'label': spec.label,
        'name': spec.label,
        'type': spec.resource_type,
        'kind': spec.kind,
        'status': spec.status,
        'status_tone': spec.status_tone,
        'cluster_id': spec.cluster_id,
        'cluster_name': spec.cluster_name,
        'namespace': spec.namespace,
        'fields': spec.fields,
        'collected_at': iso_datetime(spec.collected_at),
        'action_url': spec.action_url,
        'description': spec.description,
    }
    if spec.parent:
        data['parent'] = spec.parent
    return {'data': data}


def edge_element(spec: TopologyEdgeSpec) -> dict[str, Any]:
    return {
        'data': {
            'id': spec.edge_id,
            'source': spec.source,
            'target': spec.target,
            'relationship': spec.relationship,
            'label': spec.label,
            'source_label': spec.source_label,
            'target_label': spec.target_label,
            'description': spec.description,
        }
    }


def selector_matches(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return bool(selector) and all(labels.get(key) == value for key, value in selector.items())


def limit_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    max_nodes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, dict[str, int]]:
    if len(nodes) <= max_nodes:
        return nodes, edges, 0, {}

    parents = [node for node in nodes if node['data']['type'] in {'cluster', 'namespace'}]
    groups = _group_resource_nodes(nodes)
    kept = list(parents[:max_nodes])
    _fill_resource_budget(kept, groups, max_nodes)

    kept_ids = {node['data']['id'] for node in kept}
    limited_edges = [
        edge for edge in edges if edge['data']['source'] in kept_ids and edge['data']['target'] in kept_ids
    ]
    omitted_by_type: dict[str, int] = defaultdict(int)
    for node in nodes:
        if node['data']['id'] not in kept_ids:
            omitted_by_type[node['data']['type']] += 1
    return kept, limited_edges, len(nodes) - len(kept), dict(omitted_by_type)


def _group_resource_nodes(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_type = node['data']['type']
        if node_type not in {'cluster', 'namespace'}:
            groups[node_type].append(node)
    return groups


def _fill_resource_budget(
    kept: list[dict[str, Any]],
    groups: dict[str, list[dict[str, Any]]],
    max_nodes: int,
) -> None:
    remaining = max(0, max_nodes - len(kept))
    active_types = [resource_type for resource_type in _RESOURCE_GROUP_ORDER if groups.get(resource_type)]
    if not remaining or not active_types:
        return

    base_share = max(1, remaining // len(active_types))
    offsets: dict[str, int] = {}
    for resource_type in active_types:
        available_slots = max_nodes - len(kept)
        if available_slots <= 0:
            offsets[resource_type] = 0
            continue
        selected = groups[resource_type][: min(base_share, available_slots)]
        kept.extend(selected)
        offsets[resource_type] = len(selected)

    while len(kept) < max_nodes:
        if not _append_next_group_items(kept, groups, active_types, offsets, max_nodes):
            break


def _append_next_group_items(
    kept: list[dict[str, Any]],
    groups: dict[str, list[dict[str, Any]]],
    active_types: list[str],
    offsets: dict[str, int],
    max_nodes: int,
) -> bool:
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
    return added
