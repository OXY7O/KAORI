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
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


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
    assert 'dispatch_integration_runtime_refresh' in _functions('app/integrations/runtime/monitoring.py')


def test_runtime_celery_entrypoint_depends_only_on_monitoring_dispatch() -> None:
    task_imports = _imports('app/integrations/runtime/tasks.py')

    assert 'app.integrations.runtime.monitoring' in task_imports
    assert 'app.integrations.validation.tasks' not in task_imports
