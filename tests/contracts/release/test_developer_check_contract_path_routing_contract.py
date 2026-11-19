import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_kubernetes_focused_contracts_prepare_generated_css_before_pytest() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')
    assert '" $TEST_PATHS " == *" tests/contracts/kubernetes "*' in workflow
    assert workflow.index("run_toolchain 'Frontend Test Assets'") < workflow.index(
        'docker compose --file .github/ci/compose.yml run'
    )
    assert 'if [[ "$CHECK_FRONTEND" == "true" ]]; then' in workflow

@pytest.mark.parametrize(
    ('frontend', 'test_paths', 'should_build'),
    [
        ('false', 'tests/contracts/kubernetes', True),
        (
            'false',
            'tests/kubernetes/tenant tests/contracts/kubernetes/test_tenant_access_governance_contract.py',
            True,
        ),
        ('false', 'tests/contracts/kubernetes/test_inventory_pod_styling_guide_contract.py', True),
        ('false', 'tests/contracts/kubernetes-similar', False),
        ('false', 'tests/contracts/release', False),
        ('true', 'tests/contracts/release', True),
    ],
)
def test_kubernetes_asset_preparation_condition_matches_trusted_test_selectors(
    frontend: str, test_paths: str, should_build: bool
) -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')
    condition = next(
        line.strip().removeprefix('if ').removesuffix('; then')
        for line in workflow.splitlines()
        if line.strip().startswith('if [[ "$CHECK_FRONTEND" == "true" || ')
    )
    check = subprocess.run(
        ['bash', '-c', condition],
        env={**os.environ, 'CHECK_FRONTEND': frontend, 'TEST_PATHS': test_paths},
        check=False,
        capture_output=True,
    )
    assert (check.returncode == 0) is should_build


def test_kubernetes_tenant_planner_file_selectors_prepare_generated_css() -> None:
    planner = load_planner()
    plan = planner.build_plan(['app/kubernetes/tenant/service.py'])
    test_paths = ' '.join(plan.normalized_test_paths())
    assert 'tests/contracts/kubernetes/test_tenant_' in test_paths

    workflow = WORKFLOW.read_text(encoding='utf-8')
    condition = next(
        line.strip().removeprefix('if ').removesuffix('; then')
        for line in workflow.splitlines()
        if line.strip().startswith('if [[ "$CHECK_FRONTEND" == "true" || ')
    )
    result = subprocess.run(
        ['bash', '-c', condition],
        env={**os.environ, 'CHECK_FRONTEND': 'false', 'TEST_PATHS': test_paths},
        check=False,
        capture_output=True,
    )
    assert result.returncode == 0
