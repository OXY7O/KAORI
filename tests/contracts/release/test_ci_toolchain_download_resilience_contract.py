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
