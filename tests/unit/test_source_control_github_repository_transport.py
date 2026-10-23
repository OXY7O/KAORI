"""Installation repository page transport cannot follow arbitrary provider URLs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import transport
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubProviderError,
    InstallationToken,
)


def _token():
    return InstallationToken(
        token='never-persist', expires_at=datetime.now(UTC) + timedelta(minutes=40),
        permissions={'metadata': 'read'}, repository_selection='selected',
    )


@pytest.mark.parametrize('page', [0, -1, True, '2', 10_000])
def test_page_number_validation_blocks_unbounded_requests(page):
    client = transport.GitHubAppClient(app_id=1, private_key_pem='unused')
    with pytest.raises(GitHubProviderError):
        client.repository_page(_token(), page)


def test_repository_page_must_use_approved_endpoint_and_installation_token(monkeypatch):
    client = transport.GitHubAppClient(app_id=1, private_key_pem='unused')
    calls = []
    def fake(method, path, *, bearer, payload=None):
        calls.append((method, path, bearer))
        return 200, {'total_count': 1, 'repositories': [{'id': 7}]}

    monkeypatch.setattr(client, '_request', fake)
    result = client.repository_page(_token(), 2)
    assert result['total_count'] == 1
    assert calls == [('GET', '/installation/repositories?per_page=20&page=2', 'never-persist')]


@pytest.mark.parametrize('path', [
    '/installation/repositories?per_page=100&page=1',
    '/installation/repositories?per_page=20&page=0',
    '/installation/repositories?per_page=20&page=1&other=evil',
    '/installation/repositories?per_page=20&page=0001',
    'https://other.example/installation/repositories?per_page=20&page=1',
])
def test_fixed_api_allowlist_denies_query_injection(path):
    with pytest.raises(GitHubProviderError, match='Unsupported'):
        transport._safe_json_request('GET', path, bearer='token')


def test_expiring_token_blocks_page_before_request(monkeypatch):
    client = transport.GitHubAppClient(app_id=1, private_key_pem='unused')
    expired = InstallationToken(
        token='expired', expires_at=datetime.now(UTC) + timedelta(seconds=10),
        permissions={'metadata': 'read'}, repository_selection='selected',
    )
    def no_network(*args, **kwargs):
        pytest.fail('expired token must not make an HTTP request')

    monkeypatch.setattr(client, '_request', no_network)
    with pytest.raises(GitHubProviderError, match='cannot complete'):
        client.repository_page(expired, 1)
