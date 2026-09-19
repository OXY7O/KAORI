from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github' / 'workflows' / 'quality.yml'
PUBLISH_WORKFLOW = ROOT / '.github' / 'workflows' / 'publish-staging-image.yml'
DOCKERFILE = ROOT / 'Dockerfile'


def publish_source() -> str:
    assert PUBLISH_WORKFLOW.exists(), 'trusted staging image publish workflow is missing'
    return PUBLISH_WORKFLOW.read_text(encoding='utf-8')


def test_rc_publish_uses_only_deliberate_triggers_and_exact_staging_authority() -> None:
    workflow = publish_source()
    quality = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    trigger_section = workflow.split('on:\n', 1)[1].split('\npermissions:', 1)[0]

    assert 'name: KAORI Release Candidate' in workflow
    assert 'workflow_dispatch:' in trigger_section
    assert 'push:' in trigger_section
    assert '- kaori/rc-request' in trigger_section
    assert '- kaori/staging' not in trigger_section
    assert "github.ref == 'refs/heads/kaori/rc-request'" in workflow
    assert 'refs/heads/kaori/staging' in workflow
    assert '/git/ref/heads/kaori/staging' in workflow
    assert 'ACCEPTED_SHA' in workflow
    assert 'actions: read' in workflow
    assert 'quality.yml' in workflow
    assert 'conclusion' in workflow
    assert 'success' in workflow
    assert 'KAORI_DOCKER_REGISTRY_HOST' in workflow
    assert 'KAORI_DOCKER_REGISTRY_IMAGE' in workflow
    assert 'KAORI_DOCKER_REGISTRY_USERNAME' in workflow
    assert 'KAORI_DOCKER_REGISTRY_PASSWORD' in workflow
    assert 'KAORI_DOCKER_REGISTRY_USERNAME' not in quality
    assert 'KAORI_DOCKER_REGISTRY_PASSWORD' not in quality
    assert 'ghcr.io/oxy7o/kaori' not in workflow.lower()


def test_staging_publish_derives_semver_rc_tag_from_git_history() -> None:
    workflow = publish_source()

    assert "git tag --list 'v[0-9]*.[0-9]*.[0-9]*'" in workflow
    assert "grep -E '^v[0-9]+\\.[0-9]+\\.[0-9]+$'" in workflow
    assert "INITIAL_VERSION='0.1.0'" in workflow
    assert "grep -Eq '^[[:alnum:]_-]+(\\([^)]*\\))?!:'" in workflow
    assert "grep -Eq '^BREAKING CHANGE:'" in workflow
    assert "grep -Eq '^feat(\\([^)]*\\))?:'" in workflow
    assert 'git tag --list "v${NEXT_VERSION}-rc.*"' in workflow
    assert 'CANDIDATE_TAG="v${NEXT_VERSION}-rc.${NEXT_RC}"' in workflow
    assert 'CANDIDATE_TAG="sha-${GITHUB_SHA}"' not in workflow
    assert 'KAORI_RELEASE_VERSION' not in workflow


def test_semver_uses_accepted_staging_checkout_without_persisted_git_credentials() -> None:
    workflow = publish_source()
    checkout_section = workflow.split('      - name: Check Out Exact Accepted Staging SHA\n', 1)[1].split(
        '\n      - name: Resolve Intentional SemVer Candidate', 1
    )[0]
    semver_section = workflow.split('      - name: Resolve Intentional SemVer Candidate\n', 1)[1].split(
        '\n  publish:\n', 1
    )[0]

    assert 'ref: ${{ steps.staging.outputs.accepted_sha }}' in checkout_section
    assert 'fetch-depth: 0' in checkout_section
    assert 'fetch-tags: true' in checkout_section
    assert 'persist-credentials: false' in checkout_section
    assert 'git fetch --force --tags origin' not in semver_section


def test_rc_publish_does_not_consume_another_rc_for_same_source_sha() -> None:
    workflow = publish_source()
    semver_section = workflow.split('      - name: Resolve Intentional SemVer Candidate\n', 1)[1].split(
        '\n  publish:\n', 1
    )[0]

    assert 'git tag --points-at "$ACCEPTED_SHA"' in semver_section
    assert 'existing_rc=' in semver_section
    assert 'should_publish=false' in semver_section
    assert '/releases/tags/${existing_rc}' in semver_section
    assert semver_section.index('existing_rc=') < semver_section.index('NEXT_RC=')
    assert "needs.wait-for-quality.outputs.should_publish == 'true'" in workflow


def test_rc_publish_reserves_tag_and_refuses_registry_tag_reuse() -> None:
    workflow = publish_source()
    semver_section = workflow.split('      - name: Resolve Intentional SemVer Candidate\n', 1)[1].split(
        '\n  publish:\n', 1
    )[0]
    publish_section = workflow.split('\n  publish:\n', 1)[1]

    assert 'Reserved RC tag has no GitHub prerelease; its number remains consumed.' in semver_section
    assert 'Reserve RC Git Tag' in publish_section
    assert 'refs/tags/${CANDIDATE_TAG}' in publish_section
    assert '"sha": "${ACCEPTED_SHA}"' in publish_section
    assert 'Refuse Existing Registry Tag' in publish_section
    assert 'docker manifest inspect "$CANDIDATE_IMAGE"' in publish_section
    assert publish_section.index('Reserve RC Git Tag') < publish_section.index('Refuse Existing Registry Tag')
    assert publish_section.index('Refuse Existing Registry Tag') < publish_section.index('Push Exact Candidate')


def test_staging_publish_validates_exact_image_before_registry_push() -> None:
    workflow = publish_source()

    assert 'CANDIDATE_IMAGE="$REGISTRY_IMAGE:$CANDIDATE_TAG"' in workflow
    assert '--build-arg OCI_SOURCE=' in workflow
    assert '--build-arg OCI_REVISION="$ACCEPTED_SHA"' in workflow
    assert '--build-arg OCI_VERSION=' in workflow
    assert 'trivy image' in workflow
    assert '"$CANDIDATE_IMAGE"' in workflow
    assert 'run-runtime-validation.sh "$CANDIDATE_IMAGE"' in workflow
    assert 'docker login "$REGISTRY_HOST"' in workflow
    assert '--password-stdin' in workflow
    assert 'docker push "$CANDIDATE_IMAGE"' in workflow
    assert 'docker pull "$CANDIDATE_IMAGE"' in workflow
    assert 'RepoDigests' in workflow
    assert ':latest' not in workflow.lower()


def test_rc_publish_records_digest_and_human_friendly_github_prerelease() -> None:
    workflow = publish_source()

    for token in (
        'KAORI_IMAGE_NAME=',
        'KAORI_SOURCE_SHA=',
        'KAORI_CANDIDATE_TAG=',
        'KAORI_IMAGE_DIGEST=',
        'KAORI_IMAGE_REF=',
        'staging-image.env',
    ):
        assert token in workflow

    assert 'Upload Staging Image Evidence' in workflow
    assert 'Build Human-Friendly RC Release Notes' in workflow
    assert 'Create Human-Friendly GitHub Prerelease' in workflow
    assert '"/releases"' in workflow
    assert 'prerelease: true' in workflow
    assert 'make_latest: "false"' in workflow
    for heading in (
        '## Overview',
        '## Highlights',
        '## Operational Impact',
        '## Validation Evidence',
        '### Immutable Evidence',
        '## Known Limitations',
        '## Promotion Status',
    ):
        assert heading in workflow
    assert '## What Changed' not in workflow
    assert workflow.index('Record Immutable Digest Evidence') < workflow.index(
        'Create Human-Friendly GitHub Prerelease'
    )


def test_production_image_carries_oci_source_and_revision_labels() -> None:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')

    assert 'ARG OCI_SOURCE' in dockerfile
    assert 'ARG OCI_REVISION' in dockerfile
    assert 'org.opencontainers.image.source' in dockerfile
    assert 'org.opencontainers.image.revision' in dockerfile


def test_staging_publish_wait_does_not_occupy_kaori_ci_runner() -> None:
    workflow = publish_source()
    wait_section = workflow.split('  wait-for-quality:\n', 1)[1].split('\n  publish:\n', 1)[0]
    publish_section = workflow.split('\n  publish:\n', 1)[1]

    assert 'runs-on: [self-hosted, linux, x64, platform-ci]' in wait_section
    assert 'runs-on: [self-hosted, linux, x64, kaori-ci]' not in wait_section
    assert 'runs-on: [self-hosted, linux, x64, kaori-ci]' in publish_section
    assert 'contents: write' in publish_section
