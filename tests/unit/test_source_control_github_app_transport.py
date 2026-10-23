"""GitHub.com App JWT, permission and network-boundary tests (#2741)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.integrations.source_control.source_control.providers.github.auth import (
    GitHubAppAuthError,
    build_app_jwt,
)
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubAppClient,
    GitHubProviderError,
    _safe_json_request,
)


@pytest.fixture
def private_key_pem():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')
    return private_key, pem


def _decode(data: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)))


def test_app_jwt_is_valid_rs256_with_clock_skew(private_key_pem):
    private_key, pem = private_key_pem
    now = datetime(2026, 10, 23, tzinfo=UTC)
    token = build_app_jwt(123, pem, now=now)
    head, claims, signature = token.split('.')
    assert _decode(head) == {'alg': 'RS256', 'typ': 'JWT'}
    body = _decode(claims)
    assert body['iss'] == '123'
    assert body['iat'] == int(now.timestamp()) - 60
    assert body['exp'] == int(now.timestamp()) + 480
    private_key.public_key().verify(
        base64.urlsafe_b64decode(signature + '=' * (-len(signature) % 4)),
        f'{head}.{claims}'.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


@pytest.mark.parametrize('identity', ['x', 0, -2, True, '0'])
def test_app_id_must_be_positive(identity, private_key_pem):
    with pytest.raises(GitHubAppAuthError):
        build_app_jwt(identity, private_key_pem[1])


def test_private_key_not_exposed_on_signing_error():
    with pytest.raises(GitHubAppAuthError, match='invalid') as caught:
        build_app_jwt(12, '-----BEGIN PRIVATE KEY----- secret-value')
    assert 'secret-value' not in str(caught.value)


class FakeResponse:
    def __init__(self, status: int, value: dict | None = None, *, raw: bytes | None = None):
        self.status_code = status
        self.body = raw if raw is not None else json.dumps(value or {}).encode()
        self.closed = False

    def iter_content(self, *, chunk_size: int):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, results):
        self.results = results
        self.trust_env = True
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.results.pop(0)

    def close(self):
        self.closed = True


def test_fixed_https_origin_no_proxy_no_redirect_and_bounded_response():
    response = FakeResponse(200, {'id': 123})
    session = FakeSession([response])
    status, data = _safe_json_request(
        'GET', '/app/installations/123', bearer='transient', session_factory=lambda: session
    )
    assert (status, data) == (200, {'id': 123})
    assert session.trust_env is False
    assert session.closed and response.closed
    method, url, args = session.calls[0]
    assert (method, url) == ('GET', 'https://api.github.com/app/installations/123')
    assert args['verify'] is True
    assert args['allow_redirects'] is False
    assert args['stream'] is True
    assert args['headers']['X-GitHub-Api-Version']


@pytest.mark.parametrize('path', ['https://evil.example', '//evil.example', '/a//b', '/a?evil=1', '/a#x'])
def test_arbitrary_endpoint_or_query_not_accepted(path):
    with pytest.raises(GitHubProviderError):
        _safe_json_request('GET', path, bearer='token')


def test_redirects_and_large_json_are_fail_closed():
    for response in [FakeResponse(302), FakeResponse(200, raw=b'x' * 262_145)]:
        session = FakeSession([response])
        with pytest.raises(GitHubProviderError):
            _safe_json_request('GET', '/app/installations/1', bearer='token',
                               session_factory=lambda session=session: session)
        assert response.closed and session.closed


def test_permission_escalation_rejected_before_network(private_key_pem):
    _, pem = private_key_pem
    client = GitHubAppClient(app_id=3, private_key_pem=pem)
    with pytest.raises(GitHubProviderError):
        client.mint_installation_token(3, permissions={'contents': 'write'})


def test_account_mismatch_and_revocation_block_installation_probe(private_key_pem):
    _, pem = private_key_pem
    sample = {
        'id': 5, 'app_id': 3, 'repository_selection': 'selected',
        'account': {'id': 99, 'type': 'Organization'}, 'permissions': {'metadata': 'read'},
    }
    for sample_delta in [{'account': {'id': 98}}, {'suspended_at': '2026-01-01T00:00:00Z'}]:
        session = FakeSession([FakeResponse(200, {**sample, **sample_delta})])
        client = GitHubAppClient(app_id=3, private_key_pem=pem, session_factory=lambda: session)
        with pytest.raises(GitHubProviderError):
            client.installation_detail(5, 99)
        assert session.closed


def test_valid_selected_installation_metadata_probe_has_no_inventory_side_effect(private_key_pem):
    _, pem = private_key_pem
    expiry = (datetime.now(UTC) + timedelta(minutes=50)).isoformat()
    session = FakeSession([
        FakeResponse(200, {
            'id': 5, 'app_id': 3, 'account': {'id': 99, 'type': 'Organization'},
            'suspended_at': None, 'repository_selection': 'selected',
            'permissions': {'metadata': 'read', 'contents': 'read'},
        }),
        FakeResponse(201, {
            'token': 'ghs-test', 'expires_at': expiry,
            'permissions': {'metadata': 'read'}, 'repository_selection': 'selected',
        }),
        FakeResponse(200, {'total_count': 7, 'repositories': [{'id': 4}]}),
    ])
    # Each new Session comes from the same stub; its stream queue advances.
    client = GitHubAppClient(app_id=3, private_key_pem=pem, session_factory=lambda: session)
    result = client.validate_installation(5, 99)
    assert result.account_id == 99
    assert result.granted_repository_count == 7
    assert result.repository_selection == 'selected'
    assert result.permission_names == ('contents', 'metadata')
    assert len(session.calls) == 3
    assert session.calls[1][2]['json'] == {'permissions': {'metadata': 'read'}}
    assert session.calls[2][1].endswith('/installation/repositories?per_page=1')


def test_token_repr_never_displays_token():
    from app.integrations.source_control.source_control.providers.github.transport import InstallationToken
    token = InstallationToken('ghs-sensitive', datetime.now(UTC), {'metadata': 'read'}, 'selected')
    assert 'ghs-sensitive' not in repr(token)
