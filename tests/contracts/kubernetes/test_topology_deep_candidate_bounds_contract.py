from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_deeper_topology_bounds_only_when_every_parent_fits() -> None:
    repo = source('app/kubernetes/inventory/topology/repository.py')
    assert 'max(max_nodes - len(clusters), 0)' in repo
    assert "parent_total = source_totals.get('namespace', len(namespaces))" in repo
    assert 'len(clusters) + parent_total >= max_nodes' in repo
    assert 'family_budget = 0' in repo
    assert 'max_nodes=family_budget,' in repo


def test_committed_sql_candidate_counts_cover_independent_types() -> None:
    repo = source('app/kubernetes/inventory/topology/repository.py')
    assert 'totals[kind] = query.order_by(None).count()' in repo
    assert 'query.limit(max_nodes).all()' in repo
    assert "totals['node'] = query.order_by(None).count()" in repo
    for kind in ('workload', 'service', 'ingress', 'configmap', 'secret', 'pvc', 'pv', 'pod'):
        assert f"kind='{kind}'" in repo
    assert 'query.filter(visible.exists())' in repo
    assert 'NamespaceInventory.namespace == model.namespace' in repo


def test_scoped_storage_and_streamed_dependency_candidates_preserve_relation_counts() -> None:
    repo = source('app/kubernetes/inventory/topology/repository.py')
    assert 'max_nodes=family_budget,' in repo
    assert '_load_service_selector_index(cluster_ids, namespace)' in repo
    assert 'yield_per(256)' in repo
    assert 'totals[\'pod\'] = matching_total' in repo
    assert 'func.json_array_length(PodInventory.configuration_references) > 0' in repo
    assert 'func.json_array_length(PodInventory.persistent_volume_claims) > 0' in repo
    assert 'query.filter(referenced_pod.exists())' in repo
    assert 'db.session.query(referenced_claim.id), referenced_claim' in repo
    assert 'referenced_claim.cluster_id == StorageInventory.cluster_id' in repo
    assert "referenced_claim.storage_type == 'PersistentVolumeClaim'" in repo
    assert "func.trim(referenced_claim.details['volume_name'].as_string()) == StorageInventory.name" in repo
    assert 'volumes = volumes.filter(committed_claims.exists())' in repo
    assert '_storage_for_namespace(items, namespace)' in repo
