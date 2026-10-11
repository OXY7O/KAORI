from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_depth_one_graph_bounds_namespace_node_orm_rows_before_projection() -> None:
    repository = read('app/kubernetes/inventory/topology/repository.py')
    service = read('app/kubernetes/inventory/topology/service.py')
    assert "shallow_budget = max_nodes if selection.depth == '1' else None" in repository
    assert "totals['namespace'] = query.order_by(None).count()" in repository
    assert "totals['node'] = query.order_by(None).count()" in repository
    assert 'query = query.limit(max_nodes)' in repository
    assert 'max_nodes=_TOPOLOGY_MAX_NODES,' in service
    assert 'source_totals=source_totals' in repository


def test_shallow_truncation_uses_exact_source_counts_without_dropping_relationship_scope() -> None:
    graph = read('app/kubernetes/inventory/topology/graph_builder.py')
    repository = read('app/kubernetes/inventory/topology/repository.py')
    assert 'if self.records.source_totals:' in graph
    assert 'skipped = max(int(total) - displayed[kind], 0)' in graph
    assert 'omitted_nodes = sum(omitted_by_type.values())' in graph
    assert "shallow_budget = max_nodes if selection.depth == '1' else None" in repository
    assert "if not needs_pods:" in repository
    assert '_storage_for_namespace(items, namespace)' in repository


def test_namespace_options_use_distinct_committed_scalar_evidence() -> None:
    repository = read('app/kubernetes/inventory/topology/repository.py')
    assert '.with_entities(NamespaceInventory.cluster_id, NamespaceInventory.namespace)' in repository
    assert '.distinct()' in repository
    assert 'for cluster_id, namespace in rows:' in repository
