from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_removed_legacy_files_do_not_return() -> None:
    removed = (
        'app/integrations/binding_posture.py',
        'app/analytics/base/prometheus_service.py',
        'app/templates/components/inventory_detail_tip.html',
        'tests/integrations/test_binding_operational_posture.py',
    )
    for relative_path in removed:
        assert not (ROOT / relative_path).exists(), relative_path


def test_integration_routes_use_repository_and_binding_service_boundaries() -> None:
    routes = read('app/integrations/routes.py')
    forbidden = (
        'KubernetesConnection.query',
        'PrometheusInstance.query',
        'AlertmanagerInstance.query',
        'Cluster.query',
    )
    for expression in forbidden:
        assert expression not in routes

    assert 'app.integrations.repository' in routes
    assert 'app.integrations.binding_service' in routes


def test_binding_worker_uses_registry_operation_dispatch() -> None:
    tasks = read('app/integrations/validation/tasks.py')

    assert 'execute_integration_operation' in tasks
    assert "'binding.validate'" in tasks
    assert 'validate_prometheus_binding' not in tasks
    assert 'validate_alertmanager_binding' not in tasks


def test_inventory_uses_explicit_owner_modules_without_forwarding_facades() -> None:
    assert not (ROOT / 'app/inventory/service.py').exists()
    assert not (ROOT / 'app/inventory/collector.py').exists()

    routes = read('app/inventory/routes.py')
    persistence = read('app/inventory/persistence.py')
    adapter = read('app/integrations/kubernetes/adapter.py')

    assert 'from app.inventory.overview import' in routes
    assert 'from app.inventory.resources.nodes import' in routes
    assert 'from app.inventory.collectors.runtime import' in persistence
    assert 'from app.inventory.collectors.configuration import' in persistence
    assert 'from app.inventory.synchronization import sync_inventory' in adapter

    for path in ROOT.joinpath('app').rglob('*.py'):
        source = path.read_text(encoding='utf-8')
        assert 'from app.inventory.service import' not in source
        assert 'import app.inventory.service' not in source
        assert 'from app.inventory.collector import' not in source
        assert 'import app.inventory.collector' not in source


def test_migration_graph_has_one_head_and_no_missing_parent() -> None:
    revisions: dict[str, tuple[Path, str | tuple[str, ...] | None]] = {}

    for path in (ROOT / 'migrations/versions').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        values: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                target = node.targets[0]
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                value = node.value
            else:
                continue

            if isinstance(target, ast.Name) and target.id in {
                'revision',
                'down_revision',
            }:
                values[target.id] = ast.literal_eval(value)

        revision = values.get('revision')
        if isinstance(revision, str):
            down_revision = values.get('down_revision')
            assert down_revision is None or isinstance(
                down_revision,
                (str, tuple),
            )
            revisions[revision] = (path, down_revision)

    referenced_parents: set[str] = set()
    for revision, (path, down_revision) in revisions.items():
        parents = (
            ()
            if down_revision is None
            else down_revision
            if isinstance(down_revision, tuple)
            else (down_revision,)
        )
        for parent in parents:
            assert parent in revisions, (
                f'{path.name} revision {revision} references missing parent '
                f'{parent}'
            )
            referenced_parents.add(parent)

    heads = set(revisions) - referenced_parents
    assert len(heads) == 1, f'Expected one migration head, found: {heads}'
