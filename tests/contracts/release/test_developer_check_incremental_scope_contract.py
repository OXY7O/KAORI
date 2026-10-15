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


def test_other_owned_workspace_templates_use_domain_regressions() -> None:
    examples = (
        ('access', 'app/templates/access/overview/index.html'),
        ('integrations', 'app/templates/integrations/overview.html'),
        ('intelligence', 'app/templates/intelligence/overview.html'),
        ('platform_operations', 'app/templates/platform_operations/overview/index.html'),
        ('reports', 'app/templates/reports/overview/index.html'),
        ('settings', 'app/templates/settings/general/index.html'),
        ('welcome', 'app/templates/welcome/index.html'),
    )
    for domain, path in examples:
        plan = build_plan([path])
        assert plan.templates and plan.contracts, path
        assert plan.normalized_template_paths() == [path], path
        assert domain in plan.capabilities, path
        assert f'tests/contracts/{domain}' in plan.normalized_test_paths(), path
        assert f'tests/{domain}' in plan.normalized_test_paths(), path
        assert 'tests/contracts/release' not in plan.normalized_test_paths(), path


def test_registry_provider_ui_selects_registry_consumer_contracts() -> None:
    path = 'app/templates/integrations/registry/providers/harbor/index.html'
    plan = build_plan([path])

    assert plan.normalized_template_paths() == [path]
    assert {'integrations', 'artifact_registry'} <= plan.capabilities
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()
    assert 'tests/unit/artifact_registry' in plan.normalized_test_paths()


def test_object_storage_provider_ui_selects_object_storage_consumer_contracts() -> None:
    path = 'app/templates/integrations/storage/object_storage/providers/minio/index.html'
    plan = build_plan([path])

    assert plan.normalized_template_paths() == [path]
    assert {'integrations', 'storage/object_storage'} <= plan.capabilities
    assert 'tests/storage/object_storage' in plan.normalized_test_paths()
    assert 'tests/contracts/storage/object_storage' in plan.normalized_test_paths()


def test_reports_leaf_template_preserves_pdf_governance_lane() -> None:
    plan = build_plan(['app/templates/reports/overview/index.html'])

    assert plan.reports and plan.templates
    assert 'tests/reports' in plan.normalized_test_paths()


def test_shared_workspace_include_components_force_full_template_lint() -> None:
    plan = build_plan(['app/templates/reports/components/_report_header.html'])

    assert plan.templates and plan.broad_templates
    assert plan.normalized_template_paths() == []
    assert 'tests/contracts' in plan.normalized_test_paths()


def test_shared_component_widens_template_lint_and_contracts() -> None:
    plan = build_plan(['app/templates/components/page_hero.html'])

    assert plan.templates and plan.broad_templates
    assert plan.normalized_template_paths() == []
    assert 'tests/contracts' in plan.normalized_test_paths()


def test_shared_domain_partial_never_uses_leaf_scoped_lint() -> None:
    plan = build_plan(['app/templates/storage/object_storage/analytics/partials/_alerts_summary.html'])

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


def test_welcome_copy_change_selects_early_visual_baseline() -> None:
    plan = build_plan(['app/templates/welcome/index.html'])

    assert plan.normalized_template_paths() == ['app/templates/welcome/index.html']
    assert 'ui/welcome-visual' in plan.capabilities
    assert (
        'tests/ui/test_representative_interactions.py::test_welcome_visual_qa_light_and_dark'
        in plan.normalized_test_paths()
    )


def test_shared_shell_and_css_changes_select_visual_contract() -> None:
    for path in (
        'app/templates/components/page_hero.html',
        'app/templates/layouts/base.html',
        'app/static/css/app.css',
        'app/static/js/application_shell.js',
    ):
        plan = build_plan([path])
        assert 'ui/welcome-visual' in plan.capabilities, path
        assert (
            'tests/ui/test_representative_interactions.py::test_welcome_visual_qa_light_and_dark'
            in plan.normalized_test_paths()
        ), path


def test_visual_baseline_authority_change_selects_visual_regression() -> None:
    plan = build_plan(['tests/ui/baselines/authenticated-visual.json'])
    assert 'ui/welcome-visual' in plan.capabilities
    assert (
        'tests/ui/test_representative_interactions.py::test_welcome_visual_qa_light_and_dark'
        in plan.normalized_test_paths()
    )


def test_unrelated_backend_change_does_not_select_browser_visual_check() -> None:
    plan = build_plan(['app/artifact_registry/analytics.py'])
    assert 'ui/welcome-visual' not in plan.capabilities
    assert all('tests/ui/test_representative_interactions.py' not in p for p in plan.normalized_test_paths())


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
