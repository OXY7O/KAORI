from __future__ import annotations

import ast
from pathlib import Path

RESOURCE_READ_CONTRACTS = {
    'nodes.py': {
        'get_node_filter_roles': {'NodeInventory'},
        'get_node_filter_statuses': {'NodeInventory'},
        'get_node_inventory': {'NodeInventory'},
        'get_node_detail': {'NodeInventory', 'PodInventory'},
    },
    'namespaces.py': {
        'get_namespace_filter_statuses': {'NamespaceInventory'},
        'get_namespace_inventory': {'NamespaceInventory'},
        'get_namespace_detail': {'NamespaceInventory', 'WorkloadInventory'},
    },
    'workloads.py': {
        'get_workload_detail': {'WorkloadInventory', 'PodInventory'},
        'get_workload_filter_namespaces': {'WorkloadInventory'},
        'get_workload_filter_types': {'WorkloadInventory'},
        'get_workload_filter_statuses': {'WorkloadInventory'},
        'get_workload_inventory': {'WorkloadInventory', 'PodInventory'},
    },
    'pods.py': {
        'get_pod_filter_namespaces': {'PodInventory'},
        'get_pod_filter_statuses': {'PodInventory'},
        'get_pod_filter_owner_types': {'PodInventory'},
        'get_pod_filter_nodes': {'PodInventory'},
        'get_pod_inventory': {'PodInventory'},
        'get_pod_detail': {'PodInventory'},
    },
    'services.py': {
        'get_service_filter_namespaces': {'ServiceInventory'},
        'get_service_filter_types': {'ServiceInventory'},
        'get_service_inventory': {'ServiceInventory'},
        'get_service_detail': {'ServiceInventory', 'PodInventory'},
    },
    'ingresses.py': {
        'get_ingress_filter_namespaces': {'IngressInventory'},
        'get_ingress_filter_classes': {'IngressInventory'},
        'get_ingress_inventory': {'IngressInventory'},
        'get_ingress_detail': {'IngressInventory'},
    },
    'storage.py': {
        '_storage_bound_pods': {'StorageInventory', 'PodInventory'},
        'get_storage_detail': {'StorageInventory'},
        'get_storage_filter_namespaces': {'StorageInventory'},
        'get_storage_filter_types': {'StorageInventory'},
        'get_storage_filter_statuses': {'StorageInventory'},
        'get_storage_inventory_view': {'StorageInventory'},
    },
    'configuration.py': {
        'get_configuration_filter_namespaces': {'ConfigurationInventory'},
        'get_configuration_inventory_view': {'ConfigurationInventory'},
        'get_configuration_detail': {'ConfigurationInventory', 'PodInventory'},
    },
}


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text()
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    )
    segment = ast.get_source_segment(source, function)
    assert segment is not None
    return segment


def test_every_inventory_read_path_uses_the_committed_generation() -> None:
    for filename, functions in RESOURCE_READ_CONTRACTS.items():
        path = Path('app/inventory/resources', filename)
        for function_name, models in functions.items():
            source = _function_source(path, function_name)
            assert 'filter_current_generation' in source, f'{filename}:{function_name}'
            for model in models:
                assert model in source, f'{filename}:{function_name} does not guard {model}'


def test_namespace_related_counts_use_one_generation_guard() -> None:
    source = _function_source(Path('app/inventory/resources/namespaces.py'), 'get_namespace_detail')

    assert 'def _current_namespace_count' in source
    assert 'filter_current_generation(model.query, model)' in source
    for model in ('PodInventory', 'ServiceInventory', 'IngressInventory', 'StorageInventory'):
        inline_call = f'_current_namespace_count({model},'
        multiline_call = f'_current_namespace_count(\n            {model},'
        assert inline_call in source or multiline_call in source


def test_overview_and_topology_use_committed_inventory_rows() -> None:
    overview = Path('app/inventory/overview.py').read_text()
    topology = Path('app/inventory/topology/service.py').read_text()

    assert 'filter_current_generation(namespace_count_query, NamespaceInventory)' in overview
    assert 'filter_current_generation(model.query, model)' in overview
    assert 'filter_current_generation(query, model)' in overview

    assert 'filter_current_generation(NamespaceInventory.query, NamespaceInventory)' in topology
    assert 'return filter_current_generation(query, model).filter(' in topology
    assert '_apply_cluster_filter(NodeInventory.query, NodeInventory, cluster_ids)' in topology
    assert '_apply_cluster_filter(StorageInventory.query, StorageInventory, cluster_ids)' in topology


def test_generation_filter_uses_cluster_inventory_marker() -> None:
    source = Path('app/common/inventory_generation.py').read_text()
    assert 'select(ClusterInventory.collected_at)' in source
    assert 'ClusterInventory.cluster_id == model.cluster_id' in source
    assert 'model.collected_at == generation' in source
