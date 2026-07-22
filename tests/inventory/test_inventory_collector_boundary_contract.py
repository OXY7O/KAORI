from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_collector_facade_is_thin_and_preserves_public_api():
    source = (ROOT / 'app/inventory/collector.py').read_text(encoding='utf-8')

    assert len(source.splitlines()) < 60
    assert 'from app.inventory.collectors import (' in source
    for public_name in (
        'get_cluster_version',
        'get_configuration_inventory',
        'get_ingresses',
        'get_nodes',
        'get_pods',
        'get_resource_quotas',
        'get_services',
        'get_storage_inventory',
        'get_workloads',
    ):
        assert public_name in source


def test_resource_collectors_do_not_import_facade():
    collectors = ROOT / 'app/inventory/collectors'
    expected_modules = {
        '__init__.py',
        'common.py',
        'runtime.py',
        'workloads.py',
        'pods.py',
        'services.py',
        'ingresses.py',
        'configuration.py',
        'storage.py',
    }
    assert expected_modules <= {path.name for path in collectors.glob('*.py')}

    for path in collectors.glob('*.py'):
        source = path.read_text(encoding='utf-8')
        assert 'from app.inventory.collector import' not in source
        assert 'import app.inventory.collector' not in source


def test_persistence_still_uses_stable_collector_facade():
    source = (ROOT / 'app/inventory/persistence.py').read_text(encoding='utf-8')

    assert 'from app.inventory.collector import (' in source
    assert 'from app.inventory.collectors' not in source


def test_collector_modules_preserve_resource_ownership():
    ownership = {
        'runtime.py': ('get_cluster_version', 'get_nodes'),
        'workloads.py': ('get_workloads',),
        'pods.py': ('get_pods',),
        'services.py': ('get_services',),
        'ingresses.py': ('get_ingresses',),
        'configuration.py': (
            'get_configuration_inventory',
            'get_resource_quotas',
        ),
        'storage.py': ('get_storage_inventory',),
    }

    for module_name, function_names in ownership.items():
        source = (
            ROOT / 'app/inventory/collectors' / module_name
        ).read_text(encoding='utf-8')
        for function_name in function_names:
            assert f'def {function_name}(' in source
