from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / ".github/workflows/quality.yml"
CI_DOCKERFILE = ROOT / ".github/ci/Dockerfile"
PRODUCTION_DOCKERFILE = ROOT / "Dockerfile"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ci_toolchain_cache_key_uses_immutable_toolchain_inputs() -> None:
    source = read(QUALITY)

    assert "Resolve CI Toolchain Cache Key" in source
    for input_path in (
        ".github/ci/Dockerfile",
        ".github/ci/requirements-security.txt",
        "requirements/base.txt",
        "requirements/dev.txt",
    ):
        assert input_path in source

    assert "kaori-ci-toolchain:${{ github.sha }}" not in source


def test_existing_local_toolchain_image_is_reused() -> None:
    source = read(QUALITY)

    assert "Build or Reuse CI Toolchain" in source
    assert 'docker image inspect "$CI_TOOLCHAIN_IMAGE"' in source
    assert "Reusing cached CI toolchain" in source


def test_buildkit_caches_downloads_without_replacing_install_steps() -> None:
    ci_source = read(CI_DOCKERFILE)
    production_source = read(PRODUCTION_DOCKERFILE)

    assert "type=cache,target=/root/.cache/pip" in ci_source
    assert "python -m pip install" in ci_source

    assert "type=cache,target=/root/.cache/pip" in production_source
    assert "type=cache,target=/root/.npm" in production_source
    assert "python -m pip install" in production_source
    assert "npm ci" in production_source


def test_trivy_database_is_cached_but_each_validation_image_is_scanned() -> None:
    source = read(QUALITY)

    assert "kaori-trivy-cache" in source
    assert "trivy image" in source
    assert "--exit-code 1" in source
    assert 'VALIDATION_IMAGE=kaori:ci-${GITHUB_SHA}' in source


def test_cache_optimization_preserves_required_validation_gates() -> None:
    source = read(QUALITY)

    for token in (
        "Run Static Foundation Gate",
        "Run Free-Plan Static Security Gate",
        "Run Functional Test Gate",
        "Build and Verify Frontend",
        "Scan Production Validation Image",
        "Validate Production Runtime",
        "KAORI CI Admission",
    ):
        assert token in source
