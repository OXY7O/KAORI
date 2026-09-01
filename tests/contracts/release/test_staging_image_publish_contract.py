from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "quality.yml"
DOCKERFILE = ROOT / "Dockerfile"


def test_staging_publish_runs_only_after_trusted_staging_admission() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "publish-staging-image:" in workflow
    assert "name: Publish Accepted Staging Image" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "github.ref == 'refs/heads/kaori/staging'" in workflow
    assert "needs.ci-admission.result == 'success'" in workflow
    assert "KAORI_DOCKER_REGISTRY_HOST" in workflow
    assert "KAORI_DOCKER_REGISTRY_IMAGE" in workflow
    assert "KAORI_DOCKER_REGISTRY_USERNAME" in workflow
    assert "KAORI_DOCKER_REGISTRY_PASSWORD" in workflow
    assert "ghcr.io/oxy7o/kaori" not in workflow.lower()


def test_staging_publish_validates_exact_image_before_registry_push() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'CANDIDATE_TAG="sha-${GITHUB_SHA}"' in workflow
    assert 'CANDIDATE_IMAGE="$REGISTRY_IMAGE:$CANDIDATE_TAG"' in workflow
    assert "--build-arg OCI_SOURCE=" in workflow
    assert "--build-arg OCI_REVISION=" in workflow
    assert 'trivy image' in workflow
    assert '"$CANDIDATE_IMAGE"' in workflow
    assert 'run-runtime-validation.sh "$CANDIDATE_IMAGE"' in workflow
    assert 'docker login "$REGISTRY_HOST"' in workflow
    assert "--password-stdin" in workflow
    assert 'docker push "$CANDIDATE_IMAGE"' in workflow
    assert "RepoDigests" in workflow
    assert "latest" not in workflow.lower().split("publish accepted staging image", 1)[-1]


def test_staging_publish_records_immutable_digest_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for token in (
        "KAORI_IMAGE_NAME=",
        "KAORI_SOURCE_SHA=",
        "KAORI_CANDIDATE_TAG=",
        "KAORI_IMAGE_DIGEST=",
        "KAORI_IMAGE_REF=",
        "staging-image.env",
    ):
        assert token in workflow
    assert "Upload Staging Image Evidence" in workflow


def test_production_image_carries_oci_source_and_revision_labels() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "ARG OCI_SOURCE" in dockerfile
    assert "ARG OCI_REVISION" in dockerfile
    assert "org.opencontainers.image.source" in dockerfile
    assert "org.opencontainers.image.revision" in dockerfile
