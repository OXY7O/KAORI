from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / '.github/workflows/quality.yml'
CI_DOCKERFILE = ROOT / '.github/ci/Dockerfile'
PRODUCTION_DOCKERFILE = ROOT / 'Dockerfile'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_ci_toolchain_cache_key_uses_immutable_toolchain_inputs() -> None:
    source = read(QUALITY)

    assert 'Resolve and Reuse CI Toolchain' in source
    for input_path in (
        '.github/ci/Dockerfile',
        '.github/ci/requirements-security.txt',
        'requirements/base.txt',
        'requirements/dev.txt',
    ):
        assert input_path in source

    assert 'sha256sum | cut -c1-20' in source
    assert 'kaori-ci-toolchain:$key' in source
    assert 'kaori-ci-toolchain:${{ github.sha }}' not in source


def test_existing_local_toolchain_image_is_reused() -> None:
    source = read(QUALITY)

    resolver = source.split('- name: Resolve and Reuse CI Toolchain', 1)[1].split('- name: Resolve Source Identity', 1)[
        0
    ]
    assert 'docker image inspect "$image"' in resolver
    assert '|| docker build' in resolver
    assert '--file .github/ci/Dockerfile' in resolver


def test_buildkit_caches_downloads_without_replacing_install_steps() -> None:
    ci_source = read(CI_DOCKERFILE)
    production_source = read(PRODUCTION_DOCKERFILE)

    assert 'type=cache,target=/root/.cache/pip' in ci_source
    assert 'python -m pip install' in ci_source

    assert 'type=cache,target=/root/.cache/pip' in production_source
    assert 'type=cache,target=/root/.npm' in production_source
    assert 'python -m pip install' in production_source
    assert 'npm ci' in production_source


def test_dockerfiles_pin_bootstrap_pip_without_replacing_requirements() -> None:
    for path in (CI_DOCKERFILE, PRODUCTION_DOCKERFILE):
        source = read(path)
        assert 'ARG PIP_VERSION=26.2.1' in source
        assert 'python -m pip install "pip==${PIP_VERSION}"' in source
        assert 'python -m pip install -r ' in source


def test_ci_checksum_pipeline_uses_pipefail_shell() -> None:
    source = read(CI_DOCKERFILE)

    assert 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]' in source
    assert '| sha256sum -c -' in source


def test_hadolint_exceptions_are_local_to_intentional_os_package_strategy() -> None:
    production_source = read(PRODUCTION_DOCKERFILE)
    ci_source = read(CI_DOCKERFILE)

    assert production_source.count('# hadolint ignore=DL3008') == 2
    assert ci_source.count('# hadolint ignore=DL3008') == 1

    assert production_source.count('# hadolint ignore=DL3066') == 2
    assert 'USER vscode' in production_source
    assert 'USER kaori' in production_source


def test_trivy_database_is_cached_but_each_exact_validation_image_is_scanned() -> None:
    source = read(QUALITY)

    assert 'kaori-trivy-cache' in source
    assert 'trivy image' in source
    assert '--exit-code 1' in source
    assert 'VALIDATION_IMAGE=kaori:ci-${{ needs.validation-profile.outputs.source_sha }}' in source
    assert 'Scan Production Validation Image' in source


def test_cache_optimization_preserves_required_validation_gates() -> None:
    source = read(QUALITY)

    for token in (
        'Run Static Foundation Gate',
        'Run Free-Plan Static Security Gate',
        'Run Functional Test Gate',
        'Build and Verify Frontend',
        'Scan Production Validation Image',
        'Validate Production Runtime',
        'KAORI CI Admission',
    ):
        assert token in source
