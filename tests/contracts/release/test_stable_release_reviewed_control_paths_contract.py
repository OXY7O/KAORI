from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[3] / '.github/workflows/release-image.yml').read_text(encoding='utf-8')


def test_stable_release_allows_only_reviewed_post_acceptance_control_paths() -> None:
    required_paths = {
        '.github/workflows/release-image.yml',
        '.github/workflows/deploy-uat-vps.yml',
        'tests/contracts/release/test_stable_release_reuses_accepted_rc_digest_contract.py',
        'tests/contracts/release/test_ci_output_readability_contract.py',
        'tests/contracts/release/test_stable_release_cosign_auth_permissions_contract.py',
    }

    for path in required_paths:
        assert f"'{path}'" in WORKFLOW
    assert 'ALLOWED_POST_UAT_PATHS=(\n            \"*\"' not in WORKFLOW
