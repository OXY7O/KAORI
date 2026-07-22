from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]


def _import_targets(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
    return targets


def _package_import_targets(relative: str) -> set[str]:
    targets: set[str] = set()
    for path in (ROOT / relative).rglob('*.py'):
        targets.update(_import_targets(path))
    return targets


def test_canonical_provider_packages_do_not_import_web_domains() -> None:
    prometheus_targets = _package_import_targets('app/integrations/prometheus')
    alertmanager_targets = _package_import_targets('app/integrations/alertmanager')

    assert not {
        target
        for target in prometheus_targets
        if target == 'app.prometheus' or target.startswith('app.prometheus.')
    }
    assert not {
        target
        for target in alertmanager_targets
        if target == 'app.alertmanager' or target.startswith('app.alertmanager.')
    }


def test_registry_exposes_canonical_runtime_and_binding_operations() -> None:
    prometheus = (ROOT / 'app/integrations/prometheus/__init__.py').read_text(encoding='utf-8')
    alertmanager = (ROOT / 'app/integrations/alertmanager/__init__.py').read_text(encoding='utf-8')

    for operation in (
        'client.build',
        'runtime.validate',
        'runtime.health',
        'runtime.state',
        'binding.create',
        'binding.selector.update',
        'binding.validate',
    ):
        assert f"'{operation}'" in prometheus
        assert f"'{operation}'" in alertmanager

    assert "'connection.test'" in prometheus
    assert "'query_profile.audit'" in prometheus


def test_provider_adapters_dispatch_without_domain_service_imports() -> None:
    prometheus = (ROOT / 'app/integrations/prometheus/adapter.py').read_text(encoding='utf-8')
    alertmanager = (ROOT / 'app/integrations/alertmanager/adapter.py').read_text(encoding='utf-8')

    assert 'app.prometheus.service' not in prometheus
    assert 'app.alertmanager.service' not in alertmanager
    assert 'validate_binding(' in prometheus
    assert 'validate_binding(' in alertmanager
    assert 'create_binding(' in prometheus
    assert 'create_binding(' in alertmanager
    assert 'update_binding_selector(' in prometheus
    assert 'update_binding_selector(' in alertmanager


def test_domain_facades_delegate_provider_runtime_and_binding_work() -> None:
    prometheus = (ROOT / 'app/prometheus/service.py').read_text(encoding='utf-8')
    alertmanager = (ROOT / 'app/alertmanager/service.py').read_text(encoding='utf-8')

    for operation in (
        'connection.test',
        'runtime.validate',
        'runtime.health',
        'query_profile.audit',
        'binding.create',
        'binding.selector.update',
        'binding.validate',
    ):
        assert f"'{operation}'" in prometheus

    for operation in (
        'runtime.validate',
        'runtime.health',
        'binding.selector.update',
        'binding.validate',
    ):
        assert f"'{operation}'" in alertmanager

    assert 'from app.integrations.alertmanager.validation import' not in alertmanager
    assert 'from app.integrations.alertmanager.status import' not in alertmanager


def test_provider_neutral_binding_orchestration_has_no_web_form_dependency() -> None:
    source = (ROOT / 'app/integrations/binding_service.py').read_text(encoding='utf-8')

    assert 'get_integration(provider)' in source
    assert 'app.prometheus.service' not in source
    assert 'app.alertmanager.service' not in source
    assert 'app.alertmanager.forms' not in source
    assert "'binding.create'" in source


def test_provider_runtime_and_binding_modules_are_present() -> None:
    expected = (
        'app/integrations/prometheus/runtime.py',
        'app/integrations/prometheus/binding_management.py',
        'app/integrations/prometheus/binding_validation.py',
        'app/integrations/prometheus/scope.py',
        'app/integrations/alertmanager/runtime.py',
        'app/integrations/alertmanager/binding_management.py',
        'app/integrations/alertmanager/binding_validation.py',
    )

    assert [path for path in expected if not (ROOT / path).is_file()] == []
