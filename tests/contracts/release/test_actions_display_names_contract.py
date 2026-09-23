from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _workflow(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def test_active_workflow_names_use_concise_delivery_vocabulary() -> None:
    expected = {
        '.github/workflows/branch-hygiene.yml': 'Branch Hygiene',
        '.github/workflows/deploy-staging-host.yml': 'Staging Deploy',
        '.github/workflows/developer-check.yml': 'Developer Check',
        '.github/workflows/publish-staging-image.yml': 'Release Candidate',
        '.github/workflows/quality.yml': 'Full Admission',
        '.github/workflows/reconcile-staging-publication.yml': 'Staging Publication',
        '.github/workflows/release-image.yml': 'Stable Release',
        '.github/workflows/telegram-github-actions.yml': 'Delivery Notifications',
        '.github/workflows/ui-visual-baseline-capture.yml': 'Visual Baseline',
    }

    for path, name in expected.items():
        workflow = _workflow(path)
        assert workflow.startswith(f'name: {name}\n')


def test_release_action_names_are_short_and_operator_friendly() -> None:
    workflow = _workflow('.github/workflows/release-image.yml')

    assert 'name: Stable Release' in workflow
    assert '    name: Quality Gate' in workflow
    assert '    name: Release Preflight' in workflow
    assert '    name: Publish Stable' in workflow
    for concise in (
        'Checkout Release SHA',
        'Resolve RC Evidence',
        'Run Final Release Gate',
        'Verify RC Digest',
        'Scan RC Digest',
        'Promote Digest',
        'Verify Stable Digest',
        'Publish Stable Release',
    ):
        assert f'- name: {concise}' in workflow


def test_rc_action_names_are_short_and_operator_friendly() -> None:
    workflow = _workflow('.github/workflows/publish-staging-image.yml')

    assert 'name: Release Candidate' in workflow
    assert '    name: Staging Gate' in workflow
    assert '    name: Publish RC' in workflow
    for concise in (
        'Resolve Staging SHA',
        'Require Full Admission',
        'Resolve RC Version',
        'Build RC Image',
        'Scan RC Image',
        'Generate RC Evidence',
        'Publish RC Release',
    ):
        assert f'- name: {concise}' in workflow


def test_staging_deploy_names_and_code_path_are_host_neutral() -> None:
    workflow_path = REPO_ROOT / '.github/workflows/deploy-staging-host.yml'
    legacy_path = REPO_ROOT / '.github/workflows/deploy-uat-vps.yml'

    assert workflow_path.is_file()
    assert not legacy_path.exists()
    workflow = workflow_path.read_text(encoding='utf-8')
    assert 'name: Staging Deploy' in workflow
    assert '    name: Release Evidence' in workflow
    assert '    name: Deploy Staging' in workflow
    assert '- name: Checkout Staging SHA' in workflow
    assert '- name: Validate Inputs' in workflow


def test_full_admission_rename_preserves_notification_and_required_status_compatibility() -> None:
    quality = _workflow('.github/workflows/quality.yml')
    telegram = _workflow('.github/workflows/telegram-github-actions.yml')

    assert quality.startswith('name: Full Admission\n')
    assert 'context":"KAORI CI / Admission"' in quality
    assert 'workflows:\n      - Full Admission' in telegram
    assert "github.event.workflow_run.name == 'Full Admission'" in telegram
    assert "github.event.workflow_run.path == '.github/workflows/quality.yml'" in telegram
