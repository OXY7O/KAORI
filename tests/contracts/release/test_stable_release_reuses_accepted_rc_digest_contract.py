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


def test_stable_release_proves_main_tree_matches_accepted_rc_source() -> None:
    assert 'RC_SOURCE_SHA' in WORKFLOW
    assert 'RC_SOURCE_TREE' in WORKFLOW
    assert 'RELEASE_TREE' in WORKFLOW
    assert 'git merge-base --is-ancestor "$RC_SOURCE_SHA" "$RELEASE_SHA"' in WORKFLOW
    assert '[[ "$RC_SOURCE_TREE" == "$RELEASE_TREE" ]]' in WORKFLOW


def test_stable_release_verifies_registry_rc_and_promotes_same_digest() -> None:
    assert 'target_commitish' in WORKFLOW
    assert 'RC_IMAGE_DIGEST' in WORKFLOW
    assert 'RC_REGISTRY_DIGEST' in WORKFLOW
    assert '[[ "$RC_REGISTRY_DIGEST" == "$RC_IMAGE_DIGEST" ]]' in WORKFLOW
    assert 'source_ref="${REGISTRY_IMAGE}@${RC_IMAGE_DIGEST}"' in WORKFLOW
