from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _imports(relative_path: str) -> set[str]:
    tree = ast.parse((ROOT / relative_path).read_text(encoding='utf-8'))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    return imported


def _functions(relative_path: str) -> set[str]:
    tree = ast.parse((ROOT / relative_path).read_text(encoding='utf-8'))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_runtime_monitoring_and_validation_tasks_are_not_bidirectionally_imported() -> None:
    monitoring_imports = _imports('app/integrations/runtime/monitoring.py')
    task_imports = _imports('app/integrations/validation/tasks.py')

    assert 'app.integrations.validation.tasks' in monitoring_imports
    assert 'app.integrations.runtime.monitoring' not in task_imports
    assert 'app.integrations.runtime.refresh' in task_imports
    assert 'app.integrations.runtime.service' not in task_imports


def test_runtime_refresh_owns_refresh_and_record() -> None:
    assert 'refresh_and_record' in _functions('app/integrations/runtime/refresh.py')
    assert 'refresh_and_record' not in _functions('app/integrations/runtime/monitoring.py')
    assert 'dispatch_integration_runtime_refresh' in _functions(
        'app/integrations/runtime/monitoring.py'
    )


def test_runtime_celery_entrypoint_depends_only_on_monitoring_dispatch() -> None:
    task_imports = _imports('app/integrations/runtime/tasks.py')

    assert 'app.integrations.runtime.monitoring' in task_imports
    assert 'app.integrations.validation.tasks' not in task_imports


def test_validation_tasks_use_runtime_refresh_module_api() -> None:
    tree = ast.parse(
        (ROOT / 'app/integrations/validation/tasks.py').read_text(encoding='utf-8')
    )
    direct_symbol_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == 'app.integrations.runtime.refresh'
        for alias in node.names
    }
    module_aliases = {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == 'app.integrations.runtime.refresh'
    }

    assert 'refresh_and_record' not in direct_symbol_imports
    assert 'runtime_refresh' in module_aliases


def test_runtime_refresh_exports_canonical_public_api() -> None:
    tree = ast.parse(
        (ROOT / 'app/integrations/runtime/refresh.py').read_text(encoding='utf-8')
    )
    exports: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == '__all__'
            for target in node.targets
        ):
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            exports = {
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }

    assert {'refresh_runtime', 'get_runtime_state', 'refresh_and_record'} <= exports

