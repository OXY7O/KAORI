from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_deeper_topology_bounds_only_when_every_parent_fits() -> None:
    repo = source('app/kubernetes/inventory/topology/repository.py')
    assert "len(clusters) + len(namespaces) <= max_nodes" in repo
    assert "source_totals['namespace'] = len(namespaces)" in repo
    assert "family_budget = None" in repo
    assert "max_nodes=family_budget if selection.scope in {'all', 'compute'} else None" in repo


def test_committed_sql_candidate_counts_cover_independent_types() -> None:
    repo = source('app/kubernetes/inventory/topology/repository.py')
    assert "totals[kind] = query.order_by(None).count()" in repo
    assert "query.limit(max_nodes).all()" in repo
    for kind in ("node", "workload", "service", "ingress", "configmap", "secret", "pvc", "pv", "pod"):
        assert f"kind='{kind}'" in repo
    assert "query.filter(visible.exists())" in repo
    assert "NamespaceInventory.namespace == model.namespace" in repo


def test_complex_dependency_scopes_preserve_nonbounded_candidates() -> None:
    repo = source('app/kubernetes/inventory/topology/repository.py')
    assert "max_nodes=family_budget if not namespace else None" in repo
    assert "max_nodes=family_budget if selection.scope in {'all', 'compute'} else None" in repo
    assert "selection.scope == 'networking' and selection.include_pods" in repo
    assert "query.filter(referenced_pod.exists())" in repo
    assert "_storage_for_namespace(items, namespace)" in repo
