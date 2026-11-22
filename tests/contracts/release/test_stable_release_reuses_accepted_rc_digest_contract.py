from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = (ROOT / '.github/workflows/release-image.yml').read_text(encoding='utf-8')


def test_stable_release_promotes_accepted_rc_digest_without_application_rebuild() -> None:
    assert 'candidate_tag:' in WORKFLOW
    assert 'Resolve RC Evidence' in WORKFLOW
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


def test_stable_release_grants_reusable_quality_workflow_required_permissions() -> None:
    permissions_block = WORKFLOW.split('permissions:', maxsplit=1)[1].split('concurrency:', maxsplit=1)[0]
    assert 'contents: read' in permissions_block
    assert 'actions: read' in permissions_block


def test_stable_release_verifies_registry_rc_and_promotes_same_digest() -> None:
    assert 'target_commitish' in WORKFLOW
    assert 'RC_IMAGE_DIGEST' in WORKFLOW
    assert 'RC_REGISTRY_DIGEST' in WORKFLOW
    assert '[[ "$RC_REGISTRY_DIGEST" == "$RC_IMAGE_DIGEST" ]]' in WORKFLOW
    assert 'source_ref="${REGISTRY_IMAGE}@${RC_IMAGE_DIGEST}"' in WORKFLOW
    assert 'verify-labels "$source_ref" "$CANDIDATE_TAG" "$RC_SOURCE_SHA"' in WORKFLOW


def test_stable_release_passes_registry_auth_to_cosign_container() -> None:
    assert '--env DOCKER_CONFIG=/root/.docker' in WORKFLOW
    assert '--volume "$HOME/.docker:/root/.docker:ro"' in WORKFLOW


def test_stable_release_builds_release_evidence_from_accepted_rc_not_legacy_docs() -> None:
    assert 'Build Stable Release Notes' in WORKFLOW
    assert 'Generate Release Manifest' in WORKFLOW
    assert '.github/ci/release-lib.sh github-release' not in WORKFLOW


def test_stable_release_is_explicit_and_checks_notes_before_privileged_publication() -> None:
    events = WORKFLOW.split('on:', 1)[1].split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in events
    assert 'push:' not in events
    assert '      - name: Require Reviewed Stable Change Notes' in WORKFLOW
    assert '      - name: Recheck Reviewed Stable Notes Before Publication' in WORKFLOW
    assert WORKFLOW.index('Require Reviewed Stable Change Notes') < WORKFLOW.index('Resolve RC Evidence')
    assert WORKFLOW.index('Recheck Reviewed Stable Notes Before Publication') < WORKFLOW.index(
        'Log In to Docker Registry'
    )
    assert 'docs/releases/KAORI_${RELEASE_VERSION//./_}.md' in WORKFLOW
    assert 'CHANGELOG.md' in WORKFLOW
    assert WORKFLOW.index('## Technical Evidence') < WORKFLOW.index('      - name: Publish Stable Release')


def test_reviewed_notes_are_required_and_bound_to_the_exact_rc(tmp_path, monkeypatch) -> None:
    import pytest

    import scripts.verify_release_governance as governance

    monkeypatch.setattr(governance, 'ROOT', tmp_path)
    notes_dir = tmp_path / 'docs' / 'releases'
    notes_dir.mkdir(parents=True)
    (tmp_path / 'CHANGELOG.md').write_text('## [Unreleased]\n- Added release improvements.\n', encoding='utf-8')
    notes_path = notes_dir / 'KAORI_0_3_0.md'
    with pytest.raises(AssertionError, match='Missing release-governance file'):
        governance.verify_stable_notes('0.3.0', 'v0.3.0-rc.2')

    valid = (
        '# KAORI v0.3.0\n\n'
        'Accepted RC: v0.3.0-rc.2\n'
        'Human UAT evidence: https://github.com/OXY7O/KAORI/issues/5093#issuecomment-12345\n\n'
        '## Highlights\n- Cross-domain context is visible.\n\n'
        '## Improvements\n- Runtime targets are discoverable.\n\n'
        '## Fixes\n- Release validation is guarded.\n\n'
        '## Known Limitations\n- Operational UAT is separately governed.\n'
    )
    notes_path.write_text(''.join(valid), encoding='utf-8')
    governance.verify_stable_notes('0.3.0', 'v0.3.0-rc.2')
    with pytest.raises(AssertionError, match='matching accepted RC'):
        governance.verify_stable_notes('0.3.0', 'v0.2.0-rc.2')
    with pytest.raises(AssertionError, match='accepted RC'):
        governance.verify_stable_notes('0.3.0', 'v0.3.0-rc.3')
    notes_path.write_text(''.join(valid).replace('#issuecomment-12345', '#issuecomment-TODO'), encoding='utf-8')
    with pytest.raises(AssertionError, match='Human UAT evidence'):
        governance.verify_stable_notes('0.3.0', 'v0.3.0-rc.2')
    notes_path.write_text(''.join(valid).replace('Runtime targets are discoverable.', 'TODO'), encoding='utf-8')
    with pytest.raises(AssertionError, match='Missing reviewed content'):
        governance.verify_stable_notes('0.3.0', 'v0.3.0-rc.2')
