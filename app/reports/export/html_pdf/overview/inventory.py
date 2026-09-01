from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import integer, mapping, sequence, text, tone


def build_inventory(inventory_snapshot: Mapping[str, Any], selected_cluster_id: Any) -> dict[str, Any]:
    clusters = _cluster_rows(inventory_snapshot, selected_cluster_id)
    totals = _inventory_totals(inventory_snapshot, clusters, selected_cluster_id)
    not_ready = _not_ready_nodes(inventory_snapshot, clusters, totals['nodes'])
    return {
        'metrics': _inventory_metrics(totals),
        'clusters': clusters,
        'totals': totals,
        'total_nodes': totals['nodes'],
        'not_ready_nodes': not_ready,
        'resource_distribution': inventory_distribution(clusters, totals),
        'top_counts': [
            {'label': 'Services', 'value': totals['services']},
            {'label': 'Ingresses', 'value': totals['ingresses']},
            {'label': 'Configuration', 'value': totals['configuration']},
            {'label': 'Storage', 'value': totals['storage']},
        ],
        'health_summary': ' '.join(inventory_health_summary(inventory_snapshot, clusters)),
        'notes': (
            'Inventory values represent the latest committed generation for each asset type.',
            'This overview summarizes long resource identities; complete asset records remain available in Kubernetes Inventory.',
        ),
    }


def _cluster_rows(
    inventory_snapshot: Mapping[str, Any],
    selected_cluster_id: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sequence(inventory_snapshot.get('clusters')):
        if not isinstance(item, Mapping):
            continue
        if selected_cluster_id and str(item.get('id')) != str(selected_cluster_id):
            continue
        rows.append(_cluster_row(item))
    return rows


def _cluster_row(item: Mapping[str, Any]) -> dict[str, Any]:
    counts = mapping(item.get('counts'))
    row_status = text(item.get('sync_status_label') or item.get('status'), 'Unknown')
    return {
        'name': text(item.get('name'), 'Unknown Cluster'),
        'environment': text(item.get('environment'), ''),
        'nodes': integer(counts.get('nodes')),
        'namespaces': integer(counts.get('namespaces')),
        'workloads': integer(counts.get('workloads')),
        'pods': integer(counts.get('pods')),
        'services': integer(counts.get('services')),
        'storage': integer(counts.get('storage')),
        'ready_nodes': integer(counts.get('ready_nodes') or item.get('ready_nodes')),
        'not_ready_nodes': integer(counts.get('not_ready_nodes') or item.get('not_ready_nodes')),
        'status': row_status,
        'tone': tone(item.get('sync_status_tone') or row_status),
        'collected_at': text(item.get('synced_at'), 'Not Available'),
    }


def _inventory_totals(
    inventory_snapshot: Mapping[str, Any],
    clusters: Sequence[Mapping[str, Any]],
    selected_cluster_id: Any,
) -> dict[str, int]:
    scoped = bool(selected_cluster_id)
    return {
        'clusters': len(clusters) if scoped else integer(inventory_snapshot.get('total_clusters')),
        'nodes': _scoped_total(clusters, 'nodes') if scoped else integer(inventory_snapshot.get('total_nodes')),
        'namespaces': (
            _scoped_total(clusters, 'namespaces') if scoped else integer(inventory_snapshot.get('total_namespaces'))
        ),
        'workloads': (
            _scoped_total(clusters, 'workloads') if scoped else integer(inventory_snapshot.get('total_workloads'))
        ),
        'pods': _scoped_total(clusters, 'pods') if scoped else integer(inventory_snapshot.get('total_pods')),
        'services': (
            _scoped_total(clusters, 'services') if scoped else integer(inventory_snapshot.get('total_services'))
        ),
        'ingresses': integer(inventory_snapshot.get('total_ingresses')),
        'storage': (_scoped_total(clusters, 'storage') if scoped else integer(inventory_snapshot.get('total_storage'))),
        'configuration': integer(inventory_snapshot.get('total_configuration')),
    }


def _scoped_total(clusters: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(integer(item.get(key)) for item in clusters)


def _not_ready_nodes(
    inventory_snapshot: Mapping[str, Any],
    clusters: Sequence[Mapping[str, Any]],
    total_nodes: int,
) -> int:
    health = mapping(inventory_snapshot.get('health'))
    explicit_not_ready = _first_count(
        inventory_snapshot.get('not_ready_nodes'),
        inventory_snapshot.get('nodes_not_ready'),
        health.get('not_ready_nodes'),
        health.get('nodes_not_ready'),
    )
    if explicit_not_ready is not None:
        return max(0, min(total_nodes, explicit_not_ready))

    explicit_ready = _first_count(
        inventory_snapshot.get('ready_nodes'),
        inventory_snapshot.get('nodes_ready'),
        health.get('ready_nodes'),
        health.get('nodes_ready'),
    )
    if explicit_ready is not None:
        return max(0, total_nodes - explicit_ready)

    cluster_not_ready = _scoped_total(clusters, 'not_ready_nodes')
    cluster_ready = _scoped_total(clusters, 'ready_nodes')
    if cluster_not_ready > 0:
        return cluster_not_ready
    if cluster_ready > 0:
        return max(0, total_nodes - cluster_ready)
    return 0


def _first_count(*values: Any) -> int | None:
    for value in values:
        if value is None or str(value).strip() == '':
            continue
        return integer(value)
    return None


def _inventory_metrics(totals: Mapping[str, int]) -> list[dict[str, Any]]:
    return [
        {'label': 'Clusters', 'value': str(totals['clusters']), 'tone': 'info'},
        {'label': 'Nodes', 'value': str(totals['nodes']), 'tone': 'info'},
        {'label': 'Namespaces', 'value': str(totals['namespaces']), 'tone': 'normal'},
        {
            'label': 'Workloads',
            'value': str(totals['workloads']),
            'tone': 'warning' if totals['workloads'] else 'neutral',
        },
        {'label': 'Pods', 'value': str(totals['pods']), 'tone': 'info'},
        {'label': 'Storage Volumes', 'value': str(totals['storage']), 'tone': 'neutral'},
    ]


def inventory_distribution(
    clusters: Sequence[Mapping[str, Any]],
    totals: Mapping[str, int],
) -> list[dict[str, Any]]:
    values = (
        [(text(item.get('name')), integer(item.get('pods'))) for item in clusters]
        if clusters
        else [
            ('Workloads', totals.get('workloads', 0)),
            ('Pods', totals.get('pods', 0)),
            ('Services', totals.get('services', 0)),
            ('Storage', totals.get('storage', 0)),
        ]
    )
    total = sum(value for _, value in values) or 1
    return [
        {'marker': str(index), 'name': name, 'value': value, 'percent': (value / total) * 100}
        for index, (name, value) in enumerate(values[:6], start=1)
    ]


def inventory_health_summary(
    inventory_snapshot: Mapping[str, Any],
    clusters: Sequence[Mapping[str, Any]],
) -> list[str]:
    health = mapping(inventory_snapshot.get('health'))
    result: list[str] = []
    if clusters:
        result.append(f'{len(clusters)} cluster inventory snapshot(s) are included in this report.')
    if health:
        result.append(f'Inventory coverage score: {integer(health.get("coverage_score"))}%.')
        result.append(f'Inventory freshness score: {integer(health.get("freshness_score"))}%.')
    if not result:
        result.append('Inventory health evidence is not available for the selected reporting boundary.')
    return result
