from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github' / 'workflows' / 'quality.yml'
PUBLISH_WORKFLOW = ROOT / '.github' / 'workflows' / 'publish-staging-image.yml'
DOCKERFILE = ROOT / 'Dockerfile'


def publish_source() -> str:
    assert PUBLISH_WORKFLOW.exists(), 'trusted staging image publish workflow is missing'
    return PUBLISH_WORKFLOW.read_text(encoding='utf-8')


def test_staging_publish_is_trusted_push_only_and_waits_for_exact_ci() -> None:
    workflow = publish_source()
    quality = QUALITY_WORKFLOW.read_text(encoding='utf-8')

    assert 'name: KAORI Staging Image Publish' in workflow
    assert 'push:' in workflow
    assert '- kaori/staging' in workflow
    assert "github.event_name == 'push'" in workflow
    assert "github.ref == 'refs/heads/kaori/staging'" in workflow
    assert 'actions: read' in workflow
    assert 'quality.yml' in workflow
    assert 'GITHUB_SHA' in workflow
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


def test_staging_publish_validates_exact_image_before_registry_push() -> None:
    workflow = publish_source()

    assert 'CANDIDATE_IMAGE="$REGISTRY_IMAGE:$CANDIDATE_TAG"' in workflow
    assert '--build-arg OCI_SOURCE=' in workflow
    assert '--build-arg OCI_REVISION=' in workflow
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


def test_staging_publish_records_immutable_digest_evidence_before_tagging_rc() -> None:
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
    assert 'Create Published RC Git Tag' in workflow
    assert 'refs/tags/${CANDIDATE_TAG}' in workflow
    assert workflow.index('Record Immutable Digest Evidence') < workflow.index('Create Published RC Git Tag')


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

    assert 'runs-on: ubuntu-latest' in wait_section
    assert 'runs-on: [self-hosted, linux, x64, kaori-ci]' not in wait_section
    assert 'runs-on: [self-hosted, linux, x64, kaori-ci]' in publish_section
    assert 'contents: write' in publish_section
