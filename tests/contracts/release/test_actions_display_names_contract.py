from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _workflow(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def test_active_workflow_names_are_concise_and_operator_friendly() -> None:
    expected = {
        '.github/workflows/branch-hygiene.yml': 'name: Branch Hygiene',
        '.github/workflows/deploy-staging-host.yml': 'name: Staging Deploy',
        '.github/workflows/developer-check.yml': 'name: Developer Check',
        '.github/workflows/publish-staging-image.yml': 'name: Release Candidate',
        '.github/workflows/quality.yml': 'name: Full Admission',
        '.github/workflows/reconcile-staging-publication.yml': 'name: Staging Publication',
        '.github/workflows/release-image.yml': 'name: Stable Release',
        '.github/workflows/telegram-github-actions.yml': 'name: Delivery Notifications',
        '.github/workflows/ui-visual-baseline-capture.yml': 'name: Visual Baseline',
    }

    for path, workflow_name in expected.items():
        assert _workflow(path).startswith(workflow_name)


def test_release_action_names_are_short_and_operator_friendly() -> None:
    workflow = _workflow('.github/workflows/release-image.yml')

    assert 'name: Stable Release' in workflow
    assert '    name: Quality Gate' in workflow
    assert '    name: Release Preflight' in workflow
    assert '    name: Publish Stable' in workflow
    assert '- name: Checkout Release SHA' in workflow
    assert '- name: Verify RC Digest' in workflow
    assert '- name: Promote Digest' in workflow
    assert '- name: Publish Stable Release' in workflow
    assert 'Resolve Accepted RC and Release Authority' not in workflow
    assert 'Verify Accepted Digest, Promote, and Publish' not in workflow


def test_rc_action_names_are_short_and_operator_friendly() -> None:
    workflow = _workflow('.github/workflows/publish-staging-image.yml')

    assert 'name: Release Candidate' in workflow
    assert '    name: Staging Gate' in workflow
    assert '    name: Publish RC' in workflow
    assert '- name: Resolve RC Version' in workflow
    assert '- name: Build RC Image' in workflow
    assert '- name: Verify RC Attestations' in workflow
    assert '- name: Publish RC Release' in workflow
    assert 'Resolve Accepted Staging and Quality Evidence' not in workflow
    assert 'Publish Intentional Release Candidate' not in workflow


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
    assert '- name: Deploy to Host' in workflow
    assert 'Resolve Staging Release Evidence' not in workflow
    assert 'Deploy Immutable Candidate to Staging Host' not in workflow


def test_full_admission_telegram_consumer_tracks_display_name_without_changing_check_context() -> None:
    quality = _workflow('.github/workflows/quality.yml')
    telegram = _workflow('.github/workflows/telegram-github-actions.yml')

    assert quality.startswith('name: Full Admission')
    assert 'context":"KAORI CI / Admission"' in quality
    assert '      - Full Admission' in telegram
    assert "github.event.workflow_run.name == 'Full Admission'" in telegram
    assert "github.event.workflow_run.name == 'KAORI CI'" not in telegram
