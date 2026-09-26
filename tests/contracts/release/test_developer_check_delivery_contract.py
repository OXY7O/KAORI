from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEVELOPER_WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
DELIVERY = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
TELEGRAM = ROOT / '.github/workflows/telegram-github-actions.yml'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_work_branch_developer_check_is_separate_from_governed_admission() -> None:
    workflow = yaml.safe_load(read(DEVELOPER_WORKFLOW))

    assert workflow['name'] == 'Developer Check'
    assert workflow[True]['pull_request']['branches'] == ['kaori/staging']
    jobs = workflow['jobs']
    assert set(jobs) == {'route', 'toolchain', 'python-check', 'validation-check', 'developer-check', 'full-admission'}
    assert jobs['route']['name'] == 'Route Checks'
    assert jobs['route']['if'] == (
        '${{ github.event.pull_request.head.repo.full_name == github.repository && '
        "startsWith(github.event.pull_request.head.ref, 'kaori/') && "
        "github.event.pull_request.head.ref != 'kaori/staging' }}"
    )
    assert jobs['toolchain']['name'] == 'Prepare Toolchain'
    assert jobs['toolchain']['needs'] == 'route'
    assert jobs['python-check']['name'] == 'Python & Governance'
    assert jobs['validation-check']['name'] == 'Frontend & Focused Validation'
    assert jobs['developer-check']['name'] == 'Developer Check'
    assert jobs['developer-check']['if'].startswith('${{ always()')
    assert set(jobs['python-check']['needs']) == {'route', 'toolchain'}
    assert set(jobs['validation-check']['needs']) == {'route', 'toolchain'}
    assert set(jobs['developer-check']['needs']) == {
        'route',
        'toolchain',
        'python-check',
        'validation-check',
    }
    assert jobs['full-admission']['name'] == 'Full Admission'
    assert jobs['full-admission']['needs'] == 'developer-check'
    assert jobs['full-admission']['uses'] == './.github/workflows/quality.yml'
    assert "needs.developer-check.result == 'success'" in jobs['full-admission']['if']
    assert 'github.event.pull_request.draft == false' in jobs['full-admission']['if']
    source = read(DEVELOPER_WORKFLOW)
    assert 'production-runtime' not in source
    assert 'run-runtime-validation.sh' not in source
    assert 'trivy image' not in source
    assert 'scripts/quality_gate.sh --static' not in source
    assert 'scripts/quality_gate.sh --tests' not in source
    assert 'run-runtime-validation.sh' not in source


def test_developer_check_normalizes_parent_child_test_paths() -> None:
    source = read(DEVELOPER_WORKFLOW)

    assert 'Collapse child selections when their canonical parent is already selected.' in source
    assert '[[ "$selected_path" == tests/contracts/* ]]' in source
    assert 'unset "selected_tests[$selected_path]"' in source
    assert 'mapfile -t sorted_test_paths' in source


def test_developer_check_parallel_lanes_fail_closed_into_one_aggregate() -> None:
    source = read(DEVELOPER_WORKFLOW)

    for token in (
        'toolchain:',
        'python-check:',
        'validation-check:',
        'name: Prepare Toolchain',
        'name: Python & Governance',
        'name: Frontend & Focused Validation',
        'TOOLCHAIN_RESULT: ${{ needs.toolchain.result }}',
        'PYTHON_RESULT: ${{ needs.python-check.result }}',
        'VALIDATION_RESULT: ${{ needs.validation-check.result }}',
        '[[ "$TOOLCHAIN_RESULT" == "success" ]]',
        "assert_lane 'Python & Governance'",
        "assert_lane 'Frontend & Focused Validation'",
    ):
        assert token in source


def test_ready_full_admission_is_strictly_downstream_of_developer_check() -> None:
    workflow = yaml.safe_load(read(DEVELOPER_WORKFLOW))
    jobs = workflow['jobs']
    source = read(DEVELOPER_WORKFLOW)

    assert workflow['permissions']['contents'] == 'read'
    assert workflow['permissions']['actions'] == 'read'
    assert workflow['permissions']['statuses'] == 'write'
    assert jobs['full-admission']['needs'] == 'developer-check'
    assert "needs.developer-check.result == 'success'" in jobs['full-admission']['if']
    assert 'github.event.pull_request.draft == false' in jobs['full-admission']['if']
    assert 'github.event.pull_request.draft == true' not in jobs['route']['if']
    assert 'uses: ./.github/workflows/quality.yml' in source


def test_developer_check_routes_changed_paths_and_fails_safe_for_authority_changes() -> None:
    source = read(DEVELOPER_WORKFLOW)

    for token in (
        '.github/*',
        'requirements/*',
        'scripts/ci_admission.py',
        'scripts/ci_admission_policy.py',
        'scripts/quality_gate.sh',
        'scripts/verify_analytics_pdf_publication.py',
        'scripts/verify_pre_release_type_safety.py',
        'scripts/verify_code_health.py',
        'scripts/verify_code_health_baseline_integrity.py',
        'docs/architecture/code-health-debt-baseline.json',
        'tests/contracts/release/*',
        'docs/engineering/KAORI_DELIVERY_WORKFLOW.md',
        'wide=true',
        'reports=true',
        'selected_tests',
        'selected_tests[tests/contracts]=1',
        'selected_tests[tests/migrations]=1',
        'tests/reports',
        'tests/contracts/reports',
        'tests/contracts/analytics',
        'tests/contracts/platform_operations',
        'tests/kubernetes',
        'tests/storage',
        'tests/access',
    ):
        assert token in source

    for redundant_pattern in (
        '.github/*|.github/ci/*',
        'app/templates/*|app/*/templates/*|app/*/templates/**/*',
        'app/static/*|app/static/**/*',
        'frontend/*|frontend/**/*',
        'migrations/*|migrations/**/*',
    ):
        assert redundant_pattern not in source


def test_developer_check_uses_existing_validation_commands() -> None:
    source = read(DEVELOPER_WORKFLOW)

    for command in (
        'actionlint .github/workflows/*.yml',
        'python -m ruff check',
        'python -m ruff format --check',
        'python -m djlint',
        'python -m pyright --project pyrightconfig.json',
        'python scripts/verify_pre_release_type_safety.py',
        'python scripts/verify_code_health.py',
        'python scripts/verify_code_health_baseline_integrity.py',
        'python scripts/verify_migration_graph.py',
        'python scripts/verify_analytics_pdf_publication.py',
        'pytest -q --tb=short',
        'npm run check-format',
    ):
        assert command in source
    assert 'scripts/quality_gate.sh --static' not in source
    assert 'scripts/quality_gate.sh --tests' not in source


def test_developer_check_output_is_progress_visible_and_actionable() -> None:
    source = read(DEVELOPER_WORKFLOW)

    for token in ('⏳', '✅', '📦', '⏱', '➡️'):
        assert token in source
    assert 'Developer Check PASS' in source
    assert 'Draft validation is complete' in source
    assert 'Ready exact-head Developer Check PASS; starting governed Full Admission.' in source


def test_governed_ci_graph_uses_concise_job_names() -> None:
    source = read(QUALITY_WORKFLOW)

    for expected in (
        'name: Resolve Profile',
        'name: Static & Governance',
        'name: Security',
        'name: Functional Tests',
        'name: Frontend',
        'name: Runtime & DAST',
        'name: Fast Smoke',
        'name: CI Admission',
    ):
        assert expected in source
    for verbose in (
        'Resolve KAORI Validation Profile',
        'Static, Architecture, and Governance',
        'Secrets, SAST, Dependencies, and Workflow Security',
        'Functional and Integration Tests',
        'Frontend Reproducibility',
        'Production Image, Container Security, Runtime, and DAST',
        'KAORI Fast Integration Smoke',
        'KAORI CI Admission',
    ):
        assert f'name: {verbose}' not in source


def test_telegram_workflow_name_is_concise_without_changing_trust_boundary() -> None:
    workflow = yaml.safe_load(read(TELEGRAM))

    assert workflow['name'] == 'Delivery Notifications'
    assert workflow['jobs']['notify']['name'] == 'Notify'
    source = read(TELEGRAM)
    assert 'pull_request:' not in source
    assert 'pull_request_target:' not in source
    assert 'workflow_run:' in source
    assert '- Full Admission' in source
    assert '- completed' in source
    assert "github.event.workflow_run.event == 'push'" in source
    assert "github.event.workflow_run.head_repository.full_name == 'OXY7O/KAORI'" in source
    assert 'workflow_call:' not in source
    assert 'workflow_dispatch:' not in source


def test_delivery_standard_codifies_pre_ready_and_batch_repair() -> None:
    source = read(DELIVERY)

    for token in (
        'Developer Check',
        'Pre-Ready',
        'path-aware',
        'batch repair',
        'frozen final candidate',
        'one fresh Full Admission',
        'Vault Management',
        'small issue',
    ):
        assert token in source
