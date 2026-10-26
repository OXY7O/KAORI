from __future__ import annotations

from dataclasses import replace

import pytest
import requests
from flask import Flask

from app.integrations.secrets_management.secrets_pki.providers.vault.application.forms import VaultConnectionInput
from app.integrations.secrets_management.secrets_pki.providers.vault.application.registration import (
    issue_proof,
    verified_secret,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient, VaultProviderError
from app.integrations.secrets_management.secrets_pki.providers.vault.transport import (
    validate_auth_mount,
    validate_vault_endpoint,
)


class FakeResponse:
    def __init__(self, status: int, data: dict):
        self.status_code = status
        self.data = data
        self.content = b'{}'
        self.is_redirect = False

    def json(self) -> dict:
        return self.data


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setenv('INTEGRATION_VAULT_ALLOWED_ORIGINS', 'https://vault.example.internal:8200')


def test_endpoint_fails_closed_when_allowlist_missing(monkeypatch):
    monkeypatch.delenv('INTEGRATION_VAULT_ALLOWED_ORIGINS', raising=False)
    with pytest.raises(ValueError, match='approved'):
        validate_vault_endpoint('https://vault.example.internal:8200')


@pytest.mark.parametrize('url', [
    'http://vault.example.internal:8200', 'https://alice:secret@vault.example.internal:8200',
    'https://vault.example.internal:8200/v1/sys/health',
    'https://vault.example.internal:8200?token=anything',
])
def test_endpoint_rejects_insecure_or_malformed(url, approved):
    with pytest.raises(ValueError):
        validate_vault_endpoint(url)


def test_mount_cannot_be_arbitrary_path():
    for value in ('', 'approle/another', '../approle', 'approle?x=1'):
        with pytest.raises(ValueError):
            validate_auth_mount(value)


@pytest.mark.parametrize('status,expected', [(200, 'active'), (429, 'standby'), (473, 'performance_standby'),
                                              (472, 'dr_secondary'), (503, 'sealed'), (501, 'uninitialized')])
def test_vault_health_preserves_status(monkeypatch, approved, status, expected):
    monkeypatch.setattr(
        requests.Session, 'request',
        lambda self, method, url, **kwargs: FakeResponse(status, {
            'initialized': status != 501, 'sealed': status == 503,
            'standby': status == 429, 'version': '2.2.0',
        }),
    )
    client = VaultClient(endpoint='https://vault.example.internal:8200', role_id='reader', secret_id='sensitive')
    assert client.health()['status'] == expected


def test_approle_token_remains_transient(monkeypatch, approved):
    calls: list[tuple[str, dict]] = []

    def request(self, method: str, url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith('/sys/health'):
            return FakeResponse(200, {'version': '2.2.0', 'initialized': True, 'sealed': False})
        if url.endswith('/auth/approle/login'):
            return FakeResponse(200, {'auth': {'client_token': 'never-persist-me'}})
        if url.endswith('/auth/token/lookup-self'):
            return FakeResponse(200, {'data': {'policies': ['kaori-read']}})
        if url.endswith('/sys/mounts'):
            return FakeResponse(403, {'errors': ['permission denied']})
        raise AssertionError(url)

    monkeypatch.setattr(requests.Session, 'request', request)
    client = VaultClient(endpoint='https://vault.example.internal:8200', role_id='reader', secret_id='sensitive')
    result = client.validate_capabilities()
    assert result['mount_metadata'] == 'permission_unavailable'
    assert result['health']['status'] == 'active'
    assert 'never-persist-me' not in repr(result)
    assert 'sensitive' not in repr(result)
    assert len([url for url, _ in calls if url.endswith('/auth/approle/login')]) == 1
    assert all(call['allow_redirects'] is False and call['timeout'] == 5 for _, call in calls)
    assert all('never-persist-me' not in repr(call.get('json')) for _, call in calls)


def test_vault_failure_never_returns_provider_error_body(monkeypatch, approved):
    monkeypatch.setattr(requests.Session, 'request', lambda self, method, url, **kwargs:
                        FakeResponse(403, {'errors': ['secret/path/hidden']}))
    client = VaultClient(endpoint='https://vault.example.internal:8200', role_id='reader', secret_id='sensitive')
    with pytest.raises(VaultProviderError) as exc:
        client.test_connection()
    assert 'secret/path/hidden' not in str(exc.value)


def test_registration_proof_bound_to_exact_secret_and_user():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'testing-only'
    app.config['INTEGRATION_CREDENTIAL_KEY'] = 'credential-test-only'
    values = VaultConnectionInput(
        'Vault Prod', 'production', None, 'https://vault.example.internal:8200', None,
        'approle', 'reader', 'never-store-in-proof', 5, True,
    )
    with app.app_context():
        proof = issue_proof(values, 42)
        assert 'never-store-in-proof' not in proof
        assert verified_secret(proof, replace(values, secret_id=''), 42) == 'never-store-in-proof'
        assert verified_secret(proof, values, 42) == 'never-store-in-proof'
        assert verified_secret(proof, values, 43) is None
        assert verified_secret(proof, replace(values, secret_id='rotated'), 42) is None
        assert verified_secret(proof, replace(values, endpoint='https://elsewhere'), 42) is None
