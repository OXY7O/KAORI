from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding='utf-8'))


def test_runtime_refresh_command_imports_canonical_monitoring_service() -> None:
    command_tree = _tree('app/commands/integrations.py')
    imports = {
        (node.module, alias.name)
        for node in ast.walk(command_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert (
        'app.integrations.runtime.monitoring',
        'dispatch_integration_runtime_refresh',
    ) in imports

    package_tree = _tree('app/integrations/runtime/__init__.py')
    exported_functions = {
        node.name for node in package_tree.body if isinstance(node, ast.FunctionDef)
    }
    assert 'dispatch_integration_runtime_refresh' not in exported_functions


def test_kubernetes_runtime_sync_initializes_connection_before_use() -> None:
    service_tree = _tree('app/cluster/service.py')
    sync_function = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == '_sync_kubernetes_runtime'
    )
    assignments = [
        node
        for node in sync_function.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'connection' for target in node.targets)
    ]

    assert assignments
    assignment = assignments[0]
    assert isinstance(assignment.value, ast.Attribute)
    assert assignment.value.attr == 'kubernetes_connection'
    assert isinstance(assignment.value.value, ast.Name)
    assert assignment.value.value.id == 'cluster'


def test_storage_export_imports_prometheus_consumer() -> None:
    storage_tree = _tree('app/reports/export/sections/storage.py')
    imports = {
        (node.module, alias.name)
        for node in ast.walk(storage_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert ('app.prometheus.consumer', 'PrometheusConsumer') in imports
