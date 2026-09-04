from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = (ROOT / '.github/workflows/release-image.yml').read_text(encoding='utf-8')


def test_stable_release_promotes_accepted_rc_digest_without_application_rebuild() -> None:
    assert 'candidate_tag:' in WORKFLOW
    assert 'Resolve Accepted RC Evidence' in WORKFLOW
    assert 'Immutable digest:' in WORKFLOW
    assert 'Stable promotion requires an accepted RC prerelease' in WORKFLOW
    assert 'docker buildx build' not in WORKFLOW
    assert 'Resolve or Build Candidate Exactly Once' not in WORKFLOW
    assert '.github/ci/release-lib.sh preflight' not in WORKFLOW


def test_stable_release_allows_only_reviewed_release_control_drift_after_uat() -> None:
    assert 'RC_SOURCE_SHA' in WORKFLOW
    assert 'ALLOWED_POST_UAT_PATHS' in WORKFLOW
    assert 'git merge-base --is-ancestor "$RC_SOURCE_SHA" "$RELEASE_SHA"' in WORKFLOW
    assert 'git diff --name-only "$RC_SOURCE_SHA" "$RELEASE_SHA"' in WORKFLOW
    assert '.github/workflows/release-image.yml' in WORKFLOW
    assert 'tests/contracts/release/test_stable_release_reuses_accepted_rc_digest_contract.py' in WORKFLOW


def test_stable_release_verifies_registry_rc_and_promotes_same_digest() -> None:
    assert 'target_commitish' in WORKFLOW
    assert 'RC_IMAGE_DIGEST' in WORKFLOW
    assert 'RC_REGISTRY_DIGEST' in WORKFLOW
    assert '[[ "$RC_REGISTRY_DIGEST" == "$RC_IMAGE_DIGEST" ]]' in WORKFLOW
    assert 'source_ref="${REGISTRY_IMAGE}@${RC_IMAGE_DIGEST}"' in WORKFLOW
    assert 'verify-labels "$source_ref" "$CANDIDATE_TAG" "$RC_SOURCE_SHA"' in WORKFLOW


def test_stable_release_builds_release_evidence_from_accepted_rc_not_legacy_docs() -> None:
    assert 'Build Stable Release Notes' in WORKFLOW
    assert 'Generate Stable Release Manifest' in WORKFLOW
    assert '.github/ci/release-lib.sh github-release' not in WORKFLOW
