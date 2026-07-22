from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_service_is_a_thin_public_facade():
    source = (ROOT / 'app/inventory/service.py').read_text(encoding='utf-8')

    assert len(source.splitlines()) < 180
    assert 'def get_inventory_overview(' not in source
    assert 'def get_inventory_health(' not in source
    assert 'def get_recent_inventory_activity(' not in source
    assert 'from app.inventory.overview import (' in source


def test_overview_module_owns_operational_summary():
    source = (ROOT / 'app/inventory/overview.py').read_text(encoding='utf-8')

    for function_name in (
        'get_cluster_by_id',
        'get_inventory_clusters',
        'get_inventory_cluster_summary',
        'get_inventory_overview',
        'get_inventory_health',
        'get_recent_inventory_activity',
    ):
        assert f'def {function_name}(' in source

    assert 'INVENTORY_FRESHNESS_HOURS = 24' in source


def test_resource_descriptions_are_not_owned_by_service_facade():
    service = (ROOT / 'app/inventory/service.py').read_text(encoding='utf-8')
    descriptions = (
        ROOT / 'app/inventory/resources/descriptions.py'
    ).read_text(encoding='utf-8')

    for constant_name in (
        'NODE_ROLE_DESCRIPTIONS',
        'WORKLOAD_TYPE_DESCRIPTIONS',
        'SERVICE_TYPE_DESCRIPTIONS',
        'STORAGE_TYPE_DESCRIPTIONS',
    ):
        assert constant_name not in service
        assert constant_name in descriptions


def test_resource_modules_import_their_description_authority():
    expected = {
        'nodes.py': 'NODE_ROLE_DESCRIPTIONS',
        'workloads.py': 'WORKLOAD_TYPE_DESCRIPTIONS',
        'services.py': 'SERVICE_TYPE_DESCRIPTIONS',
        'storage.py': 'STORAGE_TYPE_DESCRIPTIONS',
    }

    for filename, constant_name in expected.items():
        source = (
            ROOT / 'app/inventory/resources' / filename
        ).read_text(encoding='utf-8')
        assert 'from app.inventory.resources.descriptions import' in source
        assert constant_name in source
