from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_service_is_a_facade_for_resource_queries():
    service = (ROOT / 'app/inventory/service.py').read_text(encoding='utf-8')
    assert 'from app.inventory.resources.nodes import' in service
    assert 'from app.inventory.resources.pods import' in service
    assert 'from app.inventory.resources.workloads import' in service
    assert 'def get_node_inventory(' not in service
    assert 'def get_pod_inventory(' not in service
    assert 'def get_workload_inventory(' not in service


def test_inventory_resource_modules_exist():
    expected = (
        'common.py', 'nodes.py', 'namespaces.py', 'configuration.py',
        'workloads.py', 'pods.py', 'services.py', 'ingresses.py', 'storage.py',
    )
    for filename in expected:
        assert (ROOT / 'app/inventory/resources' / filename).exists()


def test_inventory_routes_keep_stable_service_import_boundary():
    routes = (ROOT / 'app/inventory/routes.py').read_text(encoding='utf-8')
    assert 'app.inventory.resources' not in routes
