"""Only validated GitHub repository ownership can produce a full branch SHA."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.source_control.source_control.providers.github import transport
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubAppClient, GitHubProviderError, InstallationToken,
)


def _token():
    return InstallationToken(
        'memory-only', datetime.now(UTC) + timedelta(minutes=30),
        {'metadata': 'read', 'contents': 'read'}, 'selected',
    )


def test_native_repository_identity_proved_before_and_after_branch(monkeypatch):
    client = GitHubAppClient(app_id=4, private_key_pem='unused')
    calls = []
    def request(method, path, *, bearer, payload=None):
        calls.append((path, bearer))
        if path.endswith('/branches/feature%2Fdemo'):
            return 200, {'name': 'feature/demo', 'commit': {'sha': 'A' * 40}}
        return 200, {'id': 991, 'owner': {'login': 'org'}, 'name': 'repo',
                     'default_branch': 'feature/demo'}
    monkeypatch.setattr(client, '_request', request)
    assert client.default_branch_tip(_token(), 'org', 'repo', 'feature/demo', '991') == 'a' * 40
    assert [path for path, _ in calls] == [
        '/repos/org/repo', '/repos/org/repo/branches/feature%2Fdemo', '/repos/org/repo',
    ]
    assert all(bearer == 'memory-only' for _, bearer in calls)


def test_repo_name_reassignment_cannot_prove_original_native_id(monkeypatch):
    client = GitHubAppClient(app_id=4, private_key_pem='unused')
    monkeypatch.setattr(client, '_request', lambda *_args, **_kwargs: (
        200, {'id': 222, 'owner': {'login': 'org'}, 'name': 'repo', 'default_branch': 'main'},
    ))
    with pytest.raises(GitHubProviderError, match='native repository'):
        client.default_branch_tip(_token(), 'org', 'repo', 'main', '991')


def test_unqualified_sha_is_rejected(monkeypatch):
    client = GitHubAppClient(app_id=4, private_key_pem='unused')
    records = iter([
        {'id': 991, 'owner': {'login': 'org'}, 'name': 'repo', 'default_branch': 'main'},
        {'name': 'main', 'commit': {'sha': 'abcdef'}},
    ])
    monkeypatch.setattr(client, '_request', lambda *_a, **_k: (200, next(records)))
    with pytest.raises(GitHubProviderError, match='exact branch revision'):
        client.default_branch_tip(_token(), 'org', 'repo', 'main', '991')


@pytest.mark.parametrize('ref', ['/main', 'main/', '..', 'main..old', 'foo//bar',
                                  'feature@{1}', 'main?x=1'])
def test_unsafe_ref_rejected_before_provider_request(ref):
    client = GitHubAppClient(app_id=4, private_key_pem='unused')
    with pytest.raises(GitHubProviderError):
        client.default_branch_tip(_token(), 'org', 'repo', ref, '991')


@pytest.mark.parametrize('path', [
    'https://outside.example/repos/org/repo',
    '/repos/org/repo/branches/main?token=sensitive',
    '/repos/org/repo/branches/branch%0Aname',
    '/repos/org/repo/branches/branch%252Fname',
    '/repos/org/repo/contents/file',
])
def test_transport_denies_nonallowlisted_branch_paths(path):
    with pytest.raises(GitHubProviderError, match='Unsupported'):
        transport._safe_json_request('GET', path, bearer='token')
