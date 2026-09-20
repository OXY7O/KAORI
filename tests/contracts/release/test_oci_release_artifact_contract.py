from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_production_image_emits_complete_oci_identity_annotations() -> None:
    dockerfile = read('Dockerfile')

    for argument in (
        'ARG OCI_CREATED=""',
        'ARG OCI_TITLE=""',
        'ARG OCI_DESCRIPTION=""',
        'ARG OCI_DOCUMENTATION=""',
        'ARG OCI_LICENSES=""',
    ):
        assert argument in dockerfile

    for annotation in (
        'org.opencontainers.image.created',
        'org.opencontainers.image.title',
        'org.opencontainers.image.description',
        'org.opencontainers.image.documentation',
        'org.opencontainers.image.licenses',
    ):
        assert annotation in dockerfile


def test_rc_publication_attaches_real_sbom_and_provenance_to_immutable_digest() -> None:
    workflow = read('.github/workflows/publish-staging-image.yml')

    assert 'id-token: write' in workflow
    assert 'OCI_CREATED=' in workflow
    assert '--build-arg OCI_CREATED="$OCI_CREATED"' in workflow
    assert '--build-arg OCI_TITLE="KAORI"' in workflow
    assert '--build-arg OCI_LICENSES="LicenseRef-KAORI-Internal-Use"' in workflow

    assert 'trivy image' in workflow
    assert '--format spdx-json' in workflow
    assert 'kaori-sbom.spdx.json' in workflow
    assert 'https://slsa.dev/provenance/v1' in workflow
    assert 'kaori-provenance.json' in workflow

    assert 'COSIGN_IMAGE: ghcr.io/sigstore/cosign/cosign:v3.1.3' in workflow
    assert workflow.count('attest --yes') >= 2
    assert '--type spdxjson' in workflow
    assert '--type slsaprovenance1' in workflow
    assert workflow.count('verify-attestation') >= 2
    assert 'KAORI_IMAGE_REF' in workflow


def test_release_verification_checks_full_oci_metadata_and_attestations() -> None:
    release_lib = read('.github/ci/release-lib.sh')
    stable = read('.github/workflows/release-image.yml')

    for annotation in (
        'org.opencontainers.image.source',
        'org.opencontainers.image.revision',
        'org.opencontainers.image.version',
        'org.opencontainers.image.created',
        'org.opencontainers.image.title',
        'org.opencontainers.image.description',
        'org.opencontainers.image.documentation',
        'org.opencontainers.image.licenses',
    ):
        assert annotation in release_lib

    assert 'LicenseRef-KAORI-Internal-Use' in release_lib
    assert 'sbom: true' not in release_lib
    assert 'provenance: true' not in release_lib
    assert 'verification_sha256' in release_lib
    assert 'Verify Accepted RC Attestations' in stable
    assert stable.count('verify-attestation') >= 2
    assert '--type spdxjson' in stable
    assert '--type slsaprovenance1' in stable


def test_stable_promotion_remains_digest_preserving() -> None:
    stable = read('.github/workflows/release-image.yml')

    assert 'docker buildx build' not in stable
    assert 'source_ref="${REGISTRY_IMAGE}@${RC_IMAGE_DIGEST}"' in stable
    assert 'Promote Same Immutable Digest' in stable
    assert 'docker buildx imagetools create' in stable
