from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from app.integrations.registry.providers.harbor.client import HarborClient
from app.integrations.registry.providers.harbor.exceptions import HarborAuthError, HarborConnectionError


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
            return _Response(200, [{'name': 'library'}])
        if url.endswith('/api/v2.0/projects/library/repositories'):
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
    repositories = client.list_repositories(project_name_or_id='library')

    assert connection['version'] == 'v2.15.2-abc123'
    assert connection['registry_url'] == 'registry.example.test'
    assert health['status'] == 'healthy'
    assert projects == [{'name': 'library'}]
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
    client.list_repositories(project_name_or_id='library')

    assert methods == ['GET', 'GET', 'GET']


def test_harbor_client_normalizes_transport_failure_without_exposing_raw_exception(monkeypatch) -> None:
    secret = 'do-not-reflect-this-secret'

    def fake_get(url, **kwargs):
        raise requests.ConnectionError(f'connection failed while handling {secret}')

    monkeypatch.setattr('app.integrations.registry.providers.harbor.client.requests.get', fake_get)

    client = HarborClient(
        endpoint='https://harbor.example.test',
        username='robot$kaori',
        password=secret,
    )

    with pytest.raises(HarborConnectionError) as exc_info:
        client.test_connection()

    assert str(exc_info.value) == 'Harbor API request failed before a response was received.'
    assert secret not in str(exc_info.value)

def test_harbor_pagination_stops_on_identical_repeated_full_page() -> None:
    page = [{'name': f'project-{index}'} for index in range(100)]

    with pytest.raises(Exception) as exc_info:
        HarborClient._paged(lambda _page, _size: page, page_size=100)

    assert 'repeated an identical full page' in str(exc_info.value)

