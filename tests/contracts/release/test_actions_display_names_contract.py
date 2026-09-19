from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _workflow(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def test_release_action_names_are_short_and_operator_friendly() -> None:
    workflow = _workflow('.github/workflows/release-image.yml')

    assert 'name: Release KAORI' in workflow
    assert '    name: Quality Gate' in workflow
    assert '    name: Release Preflight' in workflow
    assert '    name: Publish Stable' in workflow
    assert 'Resolve Accepted RC and Release Authority' not in workflow
    assert 'Verify Accepted Digest, Promote, and Publish' not in workflow


def test_rc_action_names_are_short_and_operator_friendly() -> None:
    workflow = _workflow('.github/workflows/publish-staging-image.yml')

    assert 'name: KAORI Release Candidate' in workflow
    assert '    name: Staging Gate' in workflow
    assert '    name: Publish RC' in workflow
    assert 'Resolve Accepted Staging and Quality Evidence' not in workflow
    assert 'Publish Intentional Release Candidate' not in workflow


def test_staging_deploy_names_and_code_path_are_host_neutral() -> None:
    workflow_path = REPO_ROOT / '.github/workflows/deploy-staging-host.yml'
    legacy_path = REPO_ROOT / '.github/workflows/deploy-uat-vps.yml'

    assert workflow_path.is_file()
    assert not legacy_path.exists()
    workflow = workflow_path.read_text(encoding='utf-8')
    assert 'name: KAORI Staging Deployment' in workflow
    assert '    name: Release Evidence' in workflow
    assert '    name: Deploy Staging' in workflow
    assert 'Resolve Staging Release Evidence' not in workflow
    assert 'Deploy Immutable Candidate to Staging Host' not in workflow
