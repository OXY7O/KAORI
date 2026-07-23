from pathlib import Path

RESOURCE_MODELS = {
    'nodes.py': 'NodeInventory',
    'namespaces.py': 'NamespaceInventory',
    'workloads.py': 'WorkloadInventory',
    'pods.py': 'PodInventory',
    'services.py': 'ServiceInventory',
    'ingresses.py': 'IngressInventory',
    'storage.py': 'StorageInventory',
    'configuration.py': 'ConfigurationInventory',
}


def test_inventory_views_filter_to_committed_generation() -> None:
    for filename, model in RESOURCE_MODELS.items():
        source = Path('app/inventory/resources', filename).read_text()
        assert 'filter_current_generation' in source
        assert f'filter_current_generation(query, {model})' in source


def test_generation_filter_uses_cluster_inventory_marker() -> None:
    source = Path('app/inventory/resources/common.py').read_text()
    assert 'select(ClusterInventory.collected_at)' in source
    assert 'ClusterInventory.cluster_id == model.cluster_id' in source
    assert 'model.collected_at == generation' in source
