from __future__ import annotations

from app.inventory.topology.service import _limit_graph, _selector_matches


def _node(node_id: str, resource_type: str) -> dict:
    return {'data': {'id': node_id, 'type': resource_type}}


def _edge(source: str, target: str) -> dict:
    return {'data': {'source': source, 'target': target}}


def test_topology_selector_requires_a_non_empty_exact_match() -> None:
    labels = {'app': 'api', 'tier': 'backend'}

    assert _selector_matches({'app': 'api'}, labels) is True
    assert _selector_matches({'app': 'api', 'tier': 'backend'}, labels) is True
    assert _selector_matches({'app': 'web'}, labels) is False
    assert _selector_matches({}, labels) is False


def test_topology_limit_keeps_parent_context_and_valid_edges() -> None:
    nodes = [
        _node('cluster-a', 'cluster'),
        _node('namespace-a', 'namespace'),
        _node('workload-a', 'workload'),
        _node('workload-b', 'workload'),
        _node('pod-a', 'pod'),
        _node('service-a', 'service'),
    ]
    edges = [
        _edge('cluster-a', 'namespace-a'),
        _edge('namespace-a', 'workload-a'),
        _edge('workload-a', 'pod-a'),
        _edge('service-a', 'pod-a'),
    ]

    limited_nodes, limited_edges, omitted = _limit_graph(nodes, edges, max_nodes=4)
    kept_ids = {node['data']['id'] for node in limited_nodes}

    assert {'cluster-a', 'namespace-a'} <= kept_ids
    assert len(limited_nodes) == 4
    assert omitted == 2
    assert all(edge['data']['source'] in kept_ids and edge['data']['target'] in kept_ids for edge in limited_edges)
