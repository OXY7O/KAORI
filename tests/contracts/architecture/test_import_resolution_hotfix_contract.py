from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding='utf-8'))


def test_analytics_coercion_module_exists_with_canonical_api() -> None:
    module_path = ROOT / 'app' / 'analytics' / 'common' / 'coercion.py'

    assert module_path.is_file()

    module_tree = _tree('app/analytics/common/coercion.py')
    functions = {
        node.name
        for node in module_tree.body
        if isinstance(node, ast.FunctionDef)
    }

    assert {'as_dict', 'as_list', 'safe_float', 'safe_int'} <= functions


def test_runtime_refresh_command_imports_monitoring_module_directly() -> None:
    command_tree = _tree('app/commands/integrations.py')
    imports = {
        alias.name
        for node in ast.walk(command_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert 'app.integrations.runtime.monitoring' in imports

    package_tree = _tree('app/integrations/runtime/__init__.py')
    package_functions = {
        node.name
        for node in package_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert 'dispatch_integration_runtime_refresh' not in package_functions


def test_monitoring_module_defines_runtime_refresh_dispatcher() -> None:
    monitoring_tree = _tree('app/integrations/runtime/monitoring.py')
    functions = {
        node.name
        for node in monitoring_tree.body
        if isinstance(node, ast.FunctionDef)
    }

    assert 'dispatch_integration_runtime_refresh' in functions
