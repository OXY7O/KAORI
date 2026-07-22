from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_retired_collector_facade_is_absent() -> None:
    assert not (ROOT / 'app/inventory/collector.py').exists()


def test_collector_package_initializer_does_not_reexport_implementations() -> None:
    source = (ROOT / 'app/inventory/collectors/__init__.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    executable = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert executable == []


def test_persistence_imports_concrete_collector_owners() -> None:
    source = (ROOT / 'app/inventory/persistence.py').read_text(encoding='utf-8')

    for module in (
        'configuration',
        'ingresses',
        'pods',
        'runtime',
        'services',
        'storage',
        'workloads',
    ):
        assert f'from app.inventory.collectors.{module} import' in source
    assert 'from app.inventory.collector import' not in source
    assert 'from app.inventory.collectors import' not in source


def test_collector_modules_preserve_resource_ownership() -> None:
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
        source = (ROOT / 'app/inventory/collectors' / module_name).read_text(encoding='utf-8')
        for function_name in function_names:
            assert f'def {function_name}(' in source
