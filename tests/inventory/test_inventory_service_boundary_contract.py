from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_retired_inventory_service_facade_is_absent() -> None:
    assert not (ROOT / 'app/inventory/service.py').exists()


def test_inventory_resource_modules_exist() -> None:
    expected = (
        'common.py', 'nodes.py', 'namespaces.py', 'configuration.py',
        'workloads.py', 'pods.py', 'services.py', 'ingresses.py', 'storage.py',
    )
    for filename in expected:
        assert (ROOT / 'app/inventory/resources' / filename).exists()


def test_inventory_routes_import_resource_owners_explicitly() -> None:
    routes = (ROOT / 'app/inventory/routes.py').read_text(encoding='utf-8')
    for module in (
        'configuration',
        'ingresses',
        'namespaces',
        'nodes',
        'pods',
        'services',
        'storage',
        'workloads',
    ):
        assert f'from app.inventory.resources.{module} import' in routes
    assert 'from app.inventory.overview import' in routes
    assert 'from app.inventory.service import' not in routes
