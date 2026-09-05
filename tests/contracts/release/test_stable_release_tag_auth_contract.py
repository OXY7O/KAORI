from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = (ROOT / '.github/workflows/release-image.yml').read_text(encoding='utf-8')
RELEASE_LIB = (ROOT / '.github/ci/release-lib.sh').read_text(encoding='utf-8')


def test_stable_tag_publish_uses_explicit_github_token_without_persisted_checkout_credentials() -> None:
    assert 'persist-credentials: false' in WORKFLOW
    assert '- name: Create or Verify Stable Git Tag' in WORKFLOW
    assert 'GITHUB_TOKEN: ${{ github.token }}' in WORKFLOW
    assert ': "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"' in RELEASE_LIB
    assert ': "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"' in RELEASE_LIB
    assert '/git/tags' in RELEASE_LIB
    assert '/git/refs' in RELEASE_LIB
    assert 'git push origin "refs/tags/v$version"' not in RELEASE_LIB
