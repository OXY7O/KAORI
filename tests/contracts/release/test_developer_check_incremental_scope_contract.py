"""Developer Check change-impact routing; full admission remains separately authoritative."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from developer_check_plan import build_plan, write_github_output  # noqa: E402


def test_registry_leaf_template_limits_djlint_and_selects_own_contracts() -> None:
    changed = 'app/templates/artifact_registry/inventory.html'
    plan = build_plan([changed])

    assert plan.templates and plan.contracts
    assert not plan.python and not plan.wide
    assert plan.normalized_template_paths() == [changed]
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()
    assert 'tests/contracts/release' not in plan.normalized_test_paths()


def test_storage_leaf_template_avoids_unrelated_storage_behavior_suite() -> None:
    changed = 'app/templates/storage/object_storage/analytics/index.html'
    plan = build_plan([changed])

    assert plan.normalized_template_paths() == [changed]
    assert 'tests/storage/object_storage' in plan.normalized_test_paths()
    assert 'tests/storage' not in plan.normalized_test_paths()
    assert 'tests/contracts/storage/object_storage' in plan.normalized_test_paths()


def test_tenant_leaf_template_selects_tenant_tests() -> None:
    changed = 'app/templates/kubernetes/tenant/overview.html'
    plan = build_plan([changed])

    assert plan.normalized_template_paths() == [changed]
    assert 'kubernetes/tenant' in plan.capabilities
    assert 'tests/kubernetes/tenant' in plan.normalized_test_paths()


def test_shared_component_widens_template_lint_and_contracts() -> None:
    plan = build_plan(['app/templates/components/page_hero.html'])

    assert plan.templates and plan.broad_templates
    assert plan.normalized_template_paths() == []
    assert 'tests/contracts' in plan.normalized_test_paths()


def test_missing_template_fails_safe_to_full_template_lint() -> None:
    plan = build_plan(['app/templates/artifact_registry/removed_nonexistent.html'])

    assert plan.templates and plan.broad_templates
    assert plan.normalized_template_paths() == []
    assert 'tests/contracts' in plan.normalized_test_paths()


def test_mixed_leaf_and_shared_change_widens_instead_of_silently_narrowing() -> None:
    plan = build_plan(
        [
            'app/templates/artifact_registry/inventory.html',
            'app/templates/components/page_hero.html',
        ]
    )

    assert plan.normalized_template_paths() == []
    assert 'tests/contracts' in plan.normalized_test_paths()


def test_unknown_template_ownership_widens_even_when_only_one_file_changed() -> None:
    plan = build_plan(['app/templates/unknown_domain/unknown.html'])

    assert plan.templates and plan.broad_templates
    assert 'tests/contracts' in plan.normalized_test_paths()


def test_non_authority_document_change_requires_no_heavy_toolchain() -> None:
    plan = build_plan(['README.md'])

    assert not any(
        (
            plan.python,
            plan.templates,
            plan.frontend,
            plan.migrations,
            plan.contracts,
            plan.reports,
            plan.wide,
        )
    )
    assert plan.normalized_test_paths() == []
    assert plan.normalized_template_paths() == []
    assert 'template_scope=none' in plan.summary()


def test_release_or_validation_authority_expands_full_developer_check() -> None:
    for path in (
        '.github/workflows/developer-check.yml',
        'scripts/verify_release_surface_coverage.py',
        'docs/setup/GITHUB_ACTIONS_CI_CD.md',
        'docs/deployment/RELEASE_GOVERNANCE.md',
    ):
        plan = build_plan([path])
        assert plan.wide, path
        assert plan.normalized_template_paths() == [], path
        assert 'tests/contracts' in plan.normalized_test_paths(), path


def test_python_only_change_does_not_trigger_djlint() -> None:
    plan = build_plan(['app/artifact_registry/analytics.py'])

    assert plan.python and not plan.templates
    assert plan.normalized_template_paths() == []
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()


def test_github_output_includes_safe_template_paths(tmp_path: Path) -> None:
    plan = build_plan(['app/templates/artifact_registry/inventory.html'])
    output = tmp_path / 'github-output'
    write_github_output(output, plan)

    contents = output.read_text(encoding='utf-8')
    assert 'template_paths=app/templates/artifact_registry/inventory.html\n' in contents
    assert 'test_paths=' in contents
    assert 'template_scope=changed' in contents


def test_workflow_preserves_full_lint_fallback_and_aggregate_contract() -> None:
    workflow = (ROOT / '.github/workflows/developer-check.yml').read_text(encoding='utf-8')

    assert 'needs.route.outputs.template_paths' in workflow
    assert 'python -m djlint "${changed_templates[@]}" --check' in workflow
    assert "python -m djlint app/templates --check" in workflow
    assert "assert_lane 'Prepare Toolchain' \"$toolchain_required\" \"$TOOLCHAIN_RESULT\"" in workflow
    assert 'uses: ./.github/workflows/quality.yml' in workflow
