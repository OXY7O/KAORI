from pathlib import Path

DOCKERFILE = Path('.github/ci/Dockerfile')
REQUIRED_DOWNLOAD_FLAGS = (
    '--retry 5',
    '--retry-delay 2',
    '--retry-all-errors',
    '--connect-timeout 15',
    '--max-time 180',
)


def test_ci_tool_downloads_use_bounded_retry_policy() -> None:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')
    download_lines = [
        line.strip() for line in dockerfile.splitlines() if 'curl ' in line and 'https://github.com/' in line
    ]

    assert len(download_lines) == 8
    for line in download_lines:
        for flag in REQUIRED_DOWNLOAD_FLAGS:
            assert flag in line


def test_ci_tool_downloads_keep_checksum_verification() -> None:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')

    assert dockerfile.count('sha256sum -c -') == 4

def test_official_rest_fallback_preserves_all_pinned_ci_tool_checksums() -> None:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')

    # Release asset IDs were verified against the official version-pinned releases.
    for version in (
        'ARG ACTIONLINT_VERSION=1.7.12',
        'ARG GITLEAKS_VERSION=8.30.1',
        'ARG HADOLINT_VERSION=2.15.1',
        'ARG TRIVY_VERSION=0.74.0',
    ):
        assert version in dockerfile

    for asset_id in (
        '384924896',  # actionlint amd64
        '384924897',  # actionlint arm64
        '384924918',  # actionlint provider checksums
        '378332058',  # Gitleaks x64
        '378332057',  # Gitleaks arm64
        '378333193',  # Gitleaks provider checksums
        '496546506',  # Hadolint x86_64
        '496546507',  # Hadolint arm64
        '496546510',  # Hadolint provider checksums
        '514339431',  # Trivy 64bit
        '514339429',  # Trivy ARM64
        '514339622',  # Trivy provider checksums
    ):
        assert asset_id in dockerfile

    fallback_lines = [
        line.strip() for line in dockerfile.splitlines() if 'curl ' in line and 'https://api.github.com/repos/' in line
    ]
    assert len(fallback_lines) == 8
    for line in fallback_lines:
        assert line.startswith('|| curl ')
        assert "-H 'Accept: application/octet-stream'" in line
        for flag in REQUIRED_DOWNLOAD_FLAGS:
            assert flag in line

    # Provider-supplied SHA256 checks are mandatory for every downloaded tool.
    assert 'grep " actionlint_${ACTIONLINT_VERSION}_linux_${action_asset_arch}.tar.gz$"' in dockerfile
    assert 'grep " gitleaks_${GITLEAKS_VERSION}_linux_${gitleaks_arch}.tar.gz$"' in dockerfile
    assert 'hadolint_checksum=' in dockerfile
    assert 'grep " trivy_${TRIVY_VERSION}_Linux-${trivy_arch}.tar.gz$"' in dockerfile
    assert dockerfile.count('sha256sum -c -') == 4
    assert 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]' in dockerfile
