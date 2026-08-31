from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEVELOPER_WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
POLICY = ROOT / 'scripts/ci_admission_policy.py'
DELIVERY = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
TELEGRAM = ROOT / '.github/workflows/telegram-github-actions.yml'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_draft_developer_check_is_separate_from_governed_admission() -> None:
    workflow = yaml.safe_load(read(DEVELOPER_WORKFLOW))

    assert workflow['name'] == 'KAORI Developer Check'
    assert workflow[True]['pull_request']['branches'] == ['kaori/staging', 'main']
    jobs = workflow['jobs']
    assert set(jobs) == {'route', 'python', 'templates', 'frontend', 'migrations', 'contracts', 'developer-check'}
    assert jobs['route']['name'] == 'Route Checks'
    assert jobs['route']['if'] == "${{ github.event.pull_request.draft == true && github.event.pull_request.head.repo.full_name == github.repository }}"
    assert jobs['developer-check']['name'] == 'Developer Check'
    assert jobs['developer-check']['if'].startswith('${{ always()')
    source = read(DEVELOPER_WORKFLOW)
    assert 'production-runtime' not in source
    assert 'run-runtime-validation.sh' not in source
    assert 'trivy image' not in source
    assert 'Full Admission' not in source


def test_developer_check_routes_changed_paths_and_fails_safe_for_authority_changes() -> None:
    source = read(POLICY)

    assert 'DeveloperCheckDecision' in source
    assert 'resolve_developer_check' in source
    assert "'validation-authority'" in source
    assert "'.github/'" in source
    assert "'scripts/ci_admission.py'" in source
    assert "'scripts/ci_admission_policy.py'" in source
    assert "'scripts/quality_gate.sh'" in source
    assert "'tests/contracts/release/'" in source
    assert "'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'" in source
    assert 'wide=true' in source or "'wide': 'true'" in source


def test_developer_check_uses_existing_validation_commands() -> None:
    source = read(DEVELOPER_WORKFLOW)

    for command in (
        'python -m ruff check',
        'python -m ruff format --check',
        'python -m djlint',
        'python -m pyright --project pyrightconfig.json',
        'python scripts/verify_migration_graph.py',
        'pytest -q --tb=short',
        'npm run check-format',
    ):
        assert command in source
    assert 'scripts/quality_gate.sh --static' not in source
    assert 'scripts/quality_gate.sh --tests' not in source


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

    assert workflow['name'] == 'KAORI Telegram Notify'
    assert workflow['jobs']['notify']['name'] == 'Notify'
    source = read(TELEGRAM)
    assert 'pull_request:' not in source
    assert 'pull_request_target:' not in source
    assert 'workflow_run:' not in source
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
