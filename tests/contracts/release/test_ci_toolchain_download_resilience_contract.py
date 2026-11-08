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


def test_actionlint_official_rest_fallback_preserves_pinned_binary_and_checksums() -> None:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')

    # Both routes use the same official v1.7.12 release assets, not a mirror.
    assert 'ARG ACTIONLINT_VERSION=1.7.12' in dockerfile
    assert "actionlint_api_asset_id='384924896'" in dockerfile
    assert "actionlint_api_asset_id='384924897'" in dockerfile
    assert 'https://api.github.com/repos/rhysd/actionlint/releases/assets/${actionlint_api_asset_id}' in dockerfile
    assert 'https://api.github.com/repos/rhysd/actionlint/releases/assets/384924918' in dockerfile

    fallback_lines = [
        line.strip()
        for line in dockerfile.splitlines()
        if 'curl ' in line and 'https://api.github.com/repos/rhysd/actionlint/releases/assets/' in line
    ]
    assert len(fallback_lines) == 2
    for line in fallback_lines:
        assert line.startswith('|| curl ')
        assert "-H 'Accept: application/octet-stream'" in line
        for flag in REQUIRED_DOWNLOAD_FLAGS:
            assert flag in line

    # Existing provider checksum list remains mandatory on primary or fallback.
    assert 'grep " actionlint_${ACTIONLINT_VERSION}_linux_${action_asset_arch}.tar.gz$"' in dockerfile
    assert dockerfile.count('sha256sum -c -') == 4
    assert 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]' in dockerfile
