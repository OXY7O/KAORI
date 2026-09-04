from pathlib import Path


WORKFLOW = Path(".github/workflows/release-image.yml").read_text(encoding="utf-8")


def test_stable_release_promotes_accepted_rc_digest_without_application_rebuild() -> None:
    assert "Resolve Accepted RC Evidence" in WORKFLOW
    assert "Immutable digest:" in WORKFLOW
    assert "Stable promotion requires an accepted RC prerelease" in WORKFLOW
    assert "docker buildx build" not in WORKFLOW
    assert "Resolve or Build Candidate Exactly Once" not in WORKFLOW


def test_stable_release_verifies_rc_source_and_promotes_same_digest() -> None:
    assert 'target_commitish' in WORKFLOW
    assert 'RC_SOURCE_SHA' in WORKFLOW
    assert 'RC_IMAGE_DIGEST' in WORKFLOW
    assert '[[ "$RC_SOURCE_SHA" == "$RELEASE_SHA" ]]' in WORKFLOW
    assert 'source_ref="${DOCKERHUB_IMAGE}@${RC_IMAGE_DIGEST}"' in WORKFLOW
