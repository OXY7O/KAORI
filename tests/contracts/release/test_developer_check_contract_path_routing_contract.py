import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLANNER = ROOT / 'scripts' / 'developer_check_plan.py'
WORKFLOW = ROOT / '.github' / 'workflows' / 'developer-check.yml'


def load_planner():
    spec = importlib.util.spec_from_file_location('developer_check_plan', PLANNER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_developer_check_routes_each_contract_family_to_focused_tests() -> None:
    source = PLANNER.read_text(encoding='utf-8')

    families = (
        'access',
        'analytics',
        'architecture',
        'dashboards',
        'definitions',
        'design',
        'integrations',
        'intelligence',
        'kubernetes',
        'platform_operations',
        'release',
        'reports',
        'settings',
        'storage',
        'welcome',
    )

    for family in families:
        assert f"'{family}'" in source


def test_developer_check_preserves_release_fallback_for_unfocused_contract_changes() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert "paths='tests/contracts/release'" in workflow


def test_kubernetes_tenant_change_uses_capability_aware_tests() -> None:
    planner = load_planner()

    plan = planner.build_plan(['app/kubernetes/tenant/service.py'])
    paths = plan.normalized_test_paths()

    assert 'tests/kubernetes/tenant' in paths
    assert 'tests/kubernetes' not in paths
    assert any(path.startswith('tests/contracts/kubernetes/test_tenant_') for path in paths)
    assert 'kubernetes/tenant' in plan.capabilities


def test_uncertain_kubernetes_change_falls_back_to_domain_suite() -> None:
    planner = load_planner()

    plan = planner.build_plan(['app/kubernetes/__init__.py'])

    assert 'tests/kubernetes' in plan.normalized_test_paths()
    assert 'kubernetes' in plan.capabilities


def test_wide_authority_change_widens_fail_safe() -> None:
    planner = load_planner()

    plan = planner.build_plan(['scripts/developer_check_plan.py'])
    paths = plan.normalized_test_paths()

    assert plan.wide is True
    assert plan.python is True
    assert plan.templates is True
    assert plan.frontend is True
    assert plan.migrations is True
    assert plan.contracts is True
    assert 'tests/contracts' in paths
    assert 'tests/migrations' in paths
