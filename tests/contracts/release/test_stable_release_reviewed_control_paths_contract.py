from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[3] / '.github/workflows/release-image.yml').read_text(encoding='utf-8')


def test_stable_release_allows_only_reviewed_post_acceptance_control_paths() -> None:
    required_paths = {
        '.github/workflows/release-image.yml',
        '.github/workflows/deploy-staging-host.yml',
        'tests/contracts/release/test_stable_release_reuses_accepted_rc_digest_contract.py',
        'tests/contracts/release/test_ci_output_readability_contract.py',
        'tests/contracts/release/test_stable_release_cosign_auth_permissions_contract.py',
        'tests/contracts/release/test_stable_release_reviewed_control_paths_contract.py',
    }

    for path in required_paths:
        assert f"'{path}'" in WORKFLOW
    assert 'ALLOWED_POST_UAT_PATHS=(\n            "*"' not in WORKFLOW


def test_stable_release_grants_reusable_ci_status_permission() -> None:
    caller_header = WORKFLOW.split('\njobs:', 1)[0]

    assert 'permissions:' in caller_header
    assert '  contents: read' in caller_header
    assert '  actions: read' in caller_header
    assert '  statuses: write' in caller_header

