from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _absolute_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return tuple(targets)


def test_shared_registry_is_owned_by_explicit_integration_kernel_namespace() -> None:
    assert (ROOT / 'app/integrations/kernel/__init__.py').exists()
    assert (ROOT / 'app/integrations/kernel/registry.py').exists()
    assert not (ROOT / 'app/integrations/registry.py').exists()


def test_application_imports_do_not_recreate_retired_registry_kernel_path() -> None:
    forbidden = 'app.integrations.registry'
    for path in (ROOT / 'app').rglob('*.py'):
        for target in _absolute_imports(path):
            assert target != forbidden
            assert not target.startswith(f'{forbidden}.')


def test_registry_capability_namespace_remains_available_for_domain_ownership() -> None:
    kernel = (ROOT / 'app/integrations/kernel/registry.py').read_text(encoding='utf-8')
    assert 'class IntegrationRegistry' in kernel
    assert 'class IntegrationModule' in kernel
    assert 'class IntegrationImplementation' in kernel
    assert 'registry = IntegrationRegistry()' in kernel
