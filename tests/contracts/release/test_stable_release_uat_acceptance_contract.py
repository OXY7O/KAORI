from __future__ import annotations

import json
from io import BytesIO
from urllib.error import URLError

import pytest

import scripts.verify_release_governance as governance

VERSION = '0.3.0'
RC = 'v0.3.0-rc.3'
SHA = 'a' * 40
DIGEST = 'sha256:' + 'b' * 64
ISSUE = '5093'
COMMENT = '12345'
URL = f'https://github.com/OXY7O/KAORI/issues/{ISSUE}#issuecomment-{COMMENT}'
MARKER = f'KAORI_APP_UAT_ACCEPTED:{SHA}:{RC}:{DIGEST}'


@pytest.fixture
def evidence(tmp_path, monkeypatch) -> dict[str, object]:
    monkeypatch.setattr(governance, 'ROOT', tmp_path)
    monkeypatch.setenv('GH_TOKEN', 'test-only-token')
    (tmp_path / 'CHANGELOG.md').write_text('## [Unreleased]\n', encoding='utf-8')
    notes = tmp_path / 'docs' / 'releases'
    notes.mkdir(parents=True)
    (notes / 'KAORI_0_3_0.md').write_text(
        f'# KAORI v{VERSION}\n\n'
        f'Accepted RC: {RC}\nHuman UAT evidence: {URL}\n\n'
        '## Highlights\n- Verified product changes.\n\n'
        '## Improvements\n- Improved operator workflows.\n\n'
        '## Fixes\n- Corrected release gates.\n\n'
        '## Known Limitations\n- Hosted UAT is mandatory.\n',
        encoding='utf-8',
    )
    return {
        'html_url': URL,
        'issue_url': f'https://api.github.com/repos/OXY7O/KAORI/issues/{ISSUE}',
        'author_association': 'MEMBER',
        'user': {'login': 'maintainer', 'type': 'User'},
        'body': f'## Human Acceptance — KAORI\n\n{MARKER}\n',
    }


def stub_github(monkeypatch, payload: dict[str, object]) -> None:
    def response(request, timeout):
        assert timeout == 20
        assert request.full_url.endswith('/issues/comments/' + COMMENT)
        assert request.get_header('Authorization') == 'Bearer test-only-token'
        return BytesIO(json.dumps(payload).encode('utf-8'))

    monkeypatch.setattr(governance, 'urlopen', response)


def test_exact_human_uat_comment_is_verified(evidence, monkeypatch) -> None:
    stub_github(monkeypatch, evidence)
    governance.verify_uat_acceptance(VERSION, RC, SHA, DIGEST)


@pytest.mark.parametrize(
    ('field', 'value', 'reason'),
    [
        (
            'html_url',
            'https://github.com/OXY7O/KAORI/issues/5093#issuecomment-99',
            'linked KAORI issue',
        ),
        (
            'issue_url',
            'https://api.github.com/repos/OXY7O/OTHER/issues/5093',
            'linked KAORI issue',
        ),
        ('author_association', 'CONTRIBUTOR', 'repository owner/member'),
        ('user', {'login': 'github-actions[bot]', 'type': 'Bot'}, 'human GitHub user'),
        ('body', '## Human Acceptance\n\nNo exact marker', 'SHA/tag/digest'),
        ('body', f'## Human Acceptance\n\n{MARKER}\n{MARKER}', 'SHA/tag/digest'),
        (
            'body',
            f'## Human Acceptance\n\nKAORI_APP_UAT_ACCEPTED:{"c" * 40}:{RC}:{DIGEST}',
            'SHA/tag/digest',
        ),
        (
            'body',
            f'## Human Acceptance\n\nKAORI_APP_UAT_ACCEPTED:{SHA}:v0.3.0-rc.2:{DIGEST}',
            'SHA/tag/digest',
        ),
        (
            'body',
            f'## Human Acceptance\n\nKAORI_APP_UAT_ACCEPTED:{SHA}:{RC}:sha256:{"d" * 64}',
            'SHA/tag/digest',
        ),
        ('body', f'## Not Accepted\n\n{MARKER}', 'explicit acceptance heading'),
    ],
)
def test_untrusted_or_mismatched_uat_fails_closed(
    evidence, monkeypatch, field: str, value: object, reason: str
) -> None:
    evidence[field] = value
    stub_github(monkeypatch, evidence)
    with pytest.raises(AssertionError, match=reason):
        governance.verify_uat_acceptance(VERSION, RC, SHA, DIGEST)


def test_missing_token_and_unavailable_api_fail_closed(evidence, monkeypatch) -> None:
    stub_github(monkeypatch, evidence)
    monkeypatch.delenv('GH_TOKEN')
    with pytest.raises(AssertionError, match='GitHub authentication'):
        governance.verify_uat_acceptance(VERSION, RC, SHA, DIGEST)
    monkeypatch.setenv('GH_TOKEN', 'test-only-token')

    def offline(_request, timeout):
        raise URLError('unavailable')

    monkeypatch.setattr(governance, 'urlopen', offline)
    with pytest.raises(AssertionError, match='Unable to verify'):
        governance.verify_uat_acceptance(VERSION, RC, SHA, DIGEST)


def test_invalid_release_identity_fails_before_api(evidence, monkeypatch) -> None:
    stub_github(monkeypatch, evidence)
    with pytest.raises(AssertionError, match='source SHA'):
        governance.verify_uat_acceptance(VERSION, RC, 'not-a-sha', DIGEST)
    with pytest.raises(AssertionError, match='digest'):
        governance.verify_uat_acceptance(VERSION, RC, SHA, 'sha256:bad')
