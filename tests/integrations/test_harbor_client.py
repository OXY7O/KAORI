from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.integrations.registry.providers.harbor.client import HarborClient
from app.integrations.registry.providers.harbor.exceptions import HarborAuthError


@dataclass
class _Response:
    status_code: int
    payload: Any

    def json(self) -> Any:
        return self.payload


def test_harbor_client_discovers_identity_and_read_capabilities(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_get(url, *, params=None, auth=None, timeout=None, verify=None, headers=None):
        calls.append((url, params))
        if url.endswith('/api/v2.0/systeminfo'):
            return _Response(
                200,
                {
                    'harbor_version': 'v2.15.2-abc123',
                    'registry_url': 'registry.example.test',
                    'external_url': 'https://harbor.example.test',
                },
            )
        if url.endswith('/api/v2.0/health'):
            return _Response(200, {'status': 'healthy', 'components': []})
        if url.endswith('/api/v2.0/projects'):
            return _Response(200, [])
        if url.endswith('/api/v2.0/repositories'):
            return _Response(200, [])
        raise AssertionError(url)

    monkeypatch.setattr('app.integrations.registry.providers.harbor.client.requests.get', fake_get)

    client = HarborClient(
        endpoint='https://harbor.example.test/',
        username='robot$kaori',
        password='super-secret-value',
        timeout=5,
        verify_ssl=True,
    )

    connection = client.test_connection()
    health = client.get_health()
    projects = client.list_projects()
    repositories = client.list_repositories()

    assert connection['version'] == 'v2.15.2-abc123'
    assert connection['registry_url'] == 'registry.example.test'
    assert health['status'] == 'healthy'
    assert projects == []
    assert repositories == []
    assert {url.rsplit('/', 1)[-1] for url, _ in calls} >= {
        'systeminfo',
        'health',
        'projects',
        'repositories',
    }


def test_harbor_client_rejects_auth_without_leaking_secret(monkeypatch) -> None:
    secret = 'never-retain-this-secret'

    def fake_get(url, **kwargs):
        return _Response(401, {'errors': [{'code': 'UNAUTHORIZED'}]})

    monkeypatch.setattr('app.integrations.registry.providers.harbor.client.requests.get', fake_get)

    client = HarborClient(
        endpoint='https://harbor.example.test',
        username='robot$kaori',
        password=secret,
    )

    with pytest.raises(HarborAuthError) as exc_info:
        client.list_projects()

    assert secret not in str(exc_info.value)
    assert exc_info.value.status == 401


def test_harbor_client_uses_get_only_for_foundation_probes(monkeypatch) -> None:
    methods: list[str] = []

    def fake_get(url, **kwargs):
        methods.append('GET')
        if url.endswith('/systeminfo'):
            return _Response(200, {'harbor_version': 'v2.15.2'})
        return _Response(200, [])

    monkeypatch.setattr('app.integrations.registry.providers.harbor.client.requests.get', fake_get)

    client = HarborClient(endpoint='https://harbor.example.test')
    client.test_connection()
    client.list_projects()
    client.list_repositories()

    assert methods == ['GET', 'GET', 'GET']
