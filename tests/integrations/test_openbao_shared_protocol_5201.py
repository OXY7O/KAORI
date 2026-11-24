"""Offline shared Vault/OpenBao transport regression; no provider activation."""

import pytest
import requests
from flask import Flask

from app.commands.secret_store import secret_store_status
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPClient, SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import collect_kv2_metadata
from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient, VaultProviderError
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    collect_kv2_metadata as vault_collect_kv2_metadata,
)


class _Response:
    is_redirect = False
    content = b'{}'

    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def json(self):
        return self.body


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', 'openbao')
    monkeypatch.setenv('INTEGRATION_VAULT_ALLOWED_ORIGINS', 'https://vault.example.invalid:8200')
    monkeypatch.setenv('INTEGRATION_OPENBAO_ALLOWED_ORIGINS', 'https://openbao:8200,https://bao.example.invalid:8200')
    monkeypatch.setenv('INTEGRATION_VAULT_CA_BUNDLE', '/trust/vault.pem')
    monkeypatch.setenv('INTEGRATION_OPENBAO_CA_BUNDLE', '/trust/openbao.pem')


def _client(client_type, endpoint):
    return client_type(endpoint=endpoint, role_id='fixture-role', secret_id='fixture-secret', namespace='team')


def test_compatibility_exports_reuse_same_implementation():
    assert VaultProviderError is SecretProviderError
    assert vault_collect_kv2_metadata is collect_kv2_metadata
    assert VaultClient._request is OpenBaoClient._request
    assert VaultClient.login is OpenBaoClient.login
    assert VaultClient.health is OpenBaoClient.health


@pytest.mark.parametrize(
    ('client_type', 'endpoint'),
    [
        (VaultClient, 'https://openbao:8200'),
        (OpenBaoClient, 'https://vault.example.invalid:8200'),
        (OpenBaoClient, 'http://openbao:8200'),
        (OpenBaoClient, 'https://openbao:8200/v1/sys/health'),
        (KV2HTTPClient, 'https://openbao:8200'),
    ],
)
def test_provider_transport_cannot_borrow_other_allowlist(provider_env, client_type, endpoint):
    with pytest.raises(ValueError):
        _client(client_type, endpoint)


@pytest.mark.parametrize(
    ('client_type', 'endpoint', 'ca'),
    [
        (VaultClient, 'https://vault.example.invalid:8200', '/trust/vault.pem'),
        (OpenBaoClient, 'https://openbao:8200', '/trust/openbao.pem'),
        (OpenBaoClient, 'https://bao.example.invalid:8200', '/trust/openbao.pem'),
    ],
)
def test_shared_metadata_protocol_uses_explicit_provider_policy(provider_env, monkeypatch, client_type, endpoint, ca):
    calls = []

    def request(session, method, url, **kwargs):
        calls.append((method, url))
        assert session.trust_env is False
        assert kwargs['verify'] == ca
        assert kwargs['allow_redirects'] is False
        headers = kwargs['headers']
        if url.endswith('/sys/health'):
            assert 'X-Vault-Namespace' not in headers
            return _Response(200, {'initialized': True, 'sealed': False, 'version': '2.4.0'})
        assert headers['X-Vault-Namespace'] == 'team'
        if url.endswith('/auth/approle/login'):
            assert method == 'POST'
            return _Response(200, {'auth': {'client_token': 'transient-fixture-token'}})
        assert headers['X-Vault-Token'] == 'transient-fixture-token'
        if url.endswith('/kv/metadata') and method == 'LIST':
            return _Response(200, {'data': {'keys': ['node']}})
        if url.endswith('/kv/metadata/node') and method == 'GET':
            return _Response(
                200,
                {
                    'data': {
                        'current_version': 1,
                        'oldest_version': 1,
                        'max_versions': 5,
                        'cas_required': True,
                        'versions': {'1': {'created_time': '2026-11-24T00:00:00Z', 'destroyed': False}},
                    }
                },
            )
        pytest.fail('Unexpected provider operation')

    monkeypatch.setattr(requests.Session, 'request', request)
    client = _client(client_type, endpoint)
    assert client.health()['status'] == 'active'
    result = collect_kv2_metadata(client, mount='kv')
    assert result.complete
    assert len(result.records) == 1
    assert result.records[0].current_version == 1
    assert all('/data/' not in url for _, url in calls)


def test_openbao_missing_own_allowlist_fails_closed(provider_env, monkeypatch):
    monkeypatch.delenv('INTEGRATION_OPENBAO_ALLOWED_ORIGINS')
    with pytest.raises(ValueError, match='INTEGRATION_OPENBAO_ALLOWED_ORIGINS'):
        _client(OpenBaoClient, 'https://openbao:8200')


@pytest.mark.parametrize(
    ('code', 'initialized', 'sealed', 'state'),
    [(501, False, True, 'uninitialized'), (503, True, True, 'sealed'), (200, True, False, 'active')],
)
def test_openbao_operator_status_needs_no_approle(provider_env, monkeypatch, code, initialized, sealed, state):
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', 'https://openbao:8200')

    def request(session, method, url, **kwargs):
        assert method == 'GET'
        assert url == 'https://openbao:8200/v1/sys/health'
        assert kwargs['headers'] == {'Accept': 'application/json'}
        assert kwargs['verify'] == '/trust/openbao.pem'
        return _Response(code, {'initialized': initialized, 'sealed': sealed, 'unexpected': 'never-print'})

    monkeypatch.setattr(requests.Session, 'request', request)
    app = Flask(__name__)
    app.cli.add_command(secret_store_status)
    result = app.test_cli_runner().invoke(args=['secret-store-status'])
    assert result.exit_code == 0
    assert f'status={state}' in result.output
    assert 'never-print' not in result.output
    assert 'not admitted' in result.output


def test_secret_store_status_denies_external_vault_endpoint(provider_env, monkeypatch):
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', 'https://vault.example.invalid:8200')

    def no_request(*args, **kwargs):
        pytest.fail('unapproved request')

    monkeypatch.setattr(requests.Session, 'request', no_request)
    app = Flask(__name__)
    app.cli.add_command(secret_store_status)
    result = app.test_cli_runner().invoke(args=['secret-store-status'])
    assert result.exit_code != 0
    assert 'status unavailable' in result.output
    assert 'vault.example.invalid' not in result.output


@pytest.mark.parametrize('provider', ['', 'vault', 'unknown'])
def test_secret_store_status_requires_admitted_provider(provider_env, monkeypatch, provider):
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', provider)
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', 'https://openbao:8200')

    def no_request(*args, **kwargs):
        pytest.fail('unsupported provider must not cause a network request')

    monkeypatch.setattr(requests.Session, 'request', no_request)
    app = Flask(__name__)
    app.cli.add_command(secret_store_status)
    result = app.test_cli_runner().invoke(args=['secret-store-status'])
    assert result.exit_code != 0
    assert 'provider is missing or unsupported' in result.output
