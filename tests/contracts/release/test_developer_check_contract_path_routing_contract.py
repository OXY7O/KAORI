from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLANNER = ROOT / 'scripts' / 'resolve_developer_check_plan.py'


def load_planner():
    spec = importlib.util.spec_from_file_location('kaori_developer_validation_plan', PLANNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_developer_check_routes_nested_source_capabilities_to_existing_test_boundaries() -> None:
    planner = load_planner()

    cases = {
        'app/kubernetes/tenant/routes.py': 'tests/kubernetes/tenant',
        'app/kubernetes/inventory/routes.py': 'tests/kubernetes/inventory',
        'app/kubernetes/operations/routes.py': 'tests/kubernetes/operations',
        'app/integrations/runtime/service.py': 'tests/integrations/runtime',
        'app/storage/object_storage/service.py': 'tests/storage/object_storage',
        'app/access/authentication/service.py': 'tests/access/authentication',
    }

    for changed_path, expected_test_path in cases.items():
        plan = planner.resolve_plan((changed_path,), root=ROOT)
        assert expected_test_path in plan.test_paths, changed_path


def test_developer_check_falls_back_to_parent_domain_when_nested_test_boundary_is_absent() -> None:
    planner = load_planner()

    plan = planner.resolve_plan(('app/kubernetes/cluster/service.py',), root=ROOT)

    assert plan.test_paths == ('tests/kubernetes',)
    assert 'kubernetes' in plan.capabilities


def test_developer_check_preserves_contract_family_routing() -> None:
    planner = load_planner()

    plan = planner.resolve_plan(
        ('tests/contracts/kubernetes/test_tenant_domain_foundation_contract.py',),
        root=ROOT,
    )

    assert plan.contracts is True
    assert plan.test_paths == ('tests/contracts/kubernetes',)


def test_validation_authority_changes_use_release_contract_and_migration_fallback_not_all_contracts() -> None:
    planner = load_planner()

    plan = planner.resolve_plan(('.github/workflows/developer-check.yml',), root=ROOT)

    assert plan.wide is True
    assert plan.python is True
    assert plan.templates is True
    assert plan.frontend is True
    assert plan.migrations is True
    assert plan.contracts is True
    assert plan.test_paths == ('tests/contracts/release', 'tests/migrations')
    assert 'tests/contracts' not in plan.test_paths


def test_shared_application_change_fails_safe_to_release_contracts() -> None:
    planner = load_planner()

    plan = planner.resolve_plan(('app/common/navigation.py',), root=ROOT)

    assert plan.contracts is True
    assert plan.test_paths == ('tests/contracts/release',)


def test_parent_child_test_paths_are_normalized() -> None:
    planner = load_planner()

    normalized = planner._normalize_test_paths(
        ('tests/contracts', 'tests/contracts/release', 'tests/kubernetes/tenant')
    )

    assert normalized == ('tests/contracts', 'tests/kubernetes/tenant')
