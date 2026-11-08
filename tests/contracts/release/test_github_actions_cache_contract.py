from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / '.github/workflows/quality.yml'
CI_DOCKERFILE = ROOT / '.github/ci/Dockerfile'
PRODUCTION_DOCKERFILE = ROOT / 'Dockerfile'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_ci_toolchain_cache_key_uses_immutable_toolchain_inputs() -> None:
    source = read(QUALITY)

    assert 'Resolve CI Toolchain' in source
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


def test_hosted_profile_keeps_canonical_key_without_cross_runner_image_build() -> None:
    source = read(QUALITY)
    resolver = source.split('- name: Resolve CI Toolchain', 1)[1].split('- name: Resolve Source Identity', 1)[0]
    assert 'kaori-ci-toolchain:$key' in resolver
    assert 'sha256sum | cut -c1-20' in resolver
    assert 'docker image inspect' not in resolver
    assert 'docker build' not in resolver


def test_hosted_toolchain_uses_pinned_branch_scoped_buildkit_cache() -> None:
    developer_source = read(ROOT / '.github/workflows/developer-check.yml')
    quality_source = read(QUALITY)
    expected_setup = 'docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069'
    expected_build = 'docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc'
    for source, expected_jobs in ((developer_source, 2), (quality_source, 2)):
        assert source.count(expected_setup) == expected_jobs
        assert source.count(expected_build) == expected_jobs
        assert source.count('cache-from: type=gha,scope=kaori-ci-toolchain-v1') == expected_jobs
        assert source.count(
            'cache-to: type=gha,scope=kaori-ci-toolchain-v1,mode=max,ignore-error=true,timeout=5m'
        ) == expected_jobs
        assert source.count('file: .github/ci/Dockerfile') >= expected_jobs
        assert source.count('tags: ${{ steps.hosted-toolchain.outputs.image }}') == expected_jobs
        assert source.count('push: false') == expected_jobs
        assert source.count('load: true') == expected_jobs
        assert source.count('docker image inspect "$EXPECTED_IMAGE" >/dev/null') == expected_jobs
        assert source.count('[[ "$image" == "$EXPECTED_IMAGE" ]]') >= expected_jobs
        assert 'cache-mode: write' not in source
        assert 'cache-mode: write-only' not in source


def test_cached_layers_do_not_replace_exact_source_validation() -> None:
    developer = read(ROOT / '.github/workflows/developer-check.yml')
    full = read(QUALITY)
    assert 'Reject untrusted pull request before checkout' in developer
    assert 'ROUTE_RESULT: ${{ needs.route.result }}' in developer
    assert 'Run Python & Governance Checks' in developer
    assert 'Run Frontend & Focused Validation' in developer or 'Frontend & Focused Validation' in developer
    assert 'Run Security Gate' in full
    assert 'Run Functional Tests' in full
    assert 'Scan Production Image' in full
    assert 'Validate Runtime & DAST' in full
    assert 'name: CI Admission' in full
    assert 'statuses: write' in full

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
    assert 'Scan Production Image' in source


def test_cache_optimization_preserves_required_validation_gates() -> None:
    source = read(QUALITY)

    for token in (
        'Run Static & Governance',
        'Run Security Gate',
        'Run Functional Tests',
        'Build & Verify Frontend',
        'Scan Production Image',
        'Validate Runtime & DAST',
        'name: CI Admission',
    ):
        assert token in source
