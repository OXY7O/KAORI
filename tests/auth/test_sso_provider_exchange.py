from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.auth.providers import github_oauth, google_oidc
from app.auth.providers.browser import SsoProviderError


class ResponseStub:
    def __init__(self, payload, *, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise github_oauth.requests.HTTPError(f'HTTP {self.status_code}')

    def json(self):
        return self._payload


def _provider(provider_type: str):
    return SimpleNamespace(
        provider_type=provider_type,
        oidc_client_id='client-id',
        oidc_client_secret_env='CLIENT_SECRET',
        connect_timeout_seconds=5,
    )


def test_google_exchange_validates_nonce_and_projects_identity(monkeypatch) -> None:
    monkeypatch.setenv('CLIENT_SECRET', 'secret')
    monkeypatch.setattr(
        google_oidc.requests,
        'post',
        lambda *_args, **_kwargs: ResponseStub({'id_token': 'encoded-token'}),
    )
    monkeypatch.setattr(
        google_oidc.id_token,
        'verify_oauth2_token',
        lambda *_args, **_kwargs: {
            'sub': 'google-subject',
            'email': 'Operator@Example.com',
            'email_verified': True,
            'name': 'KAORI Operator',
            'nonce': 'expected-nonce',
        },
    )

    identity = google_oidc.GoogleOidcProvider().exchange_code(
        _provider('google_oidc'),
        code='authorization-code',
        redirect_uri='https://kaori.example/auth/sso/google/callback',
        expected_nonce='expected-nonce',
    )

    assert identity.subject == 'google-subject'
    assert identity.username == 'operator'
    assert identity.email == 'operator@example.com'
    assert identity.email_verified is True


def test_google_exchange_rejects_nonce_mismatch(monkeypatch) -> None:
    monkeypatch.setenv('CLIENT_SECRET', 'secret')
    monkeypatch.setattr(
        google_oidc.requests,
        'post',
        lambda *_args, **_kwargs: ResponseStub({'id_token': 'encoded-token'}),
    )
    monkeypatch.setattr(
        google_oidc.id_token,
        'verify_oauth2_token',
        lambda *_args, **_kwargs: {'sub': 'subject', 'nonce': 'wrong-nonce'},
    )

    with pytest.raises(SsoProviderError, match='nonce validation failed'):
        google_oidc.GoogleOidcProvider().exchange_code(
            _provider('google_oidc'),
            code='authorization-code',
            redirect_uri='https://kaori.example/auth/sso/google/callback',
            expected_nonce='expected-nonce',
        )


def test_github_exchange_marks_api_verified_email_as_verified(monkeypatch) -> None:
    monkeypatch.setenv('CLIENT_SECRET', 'secret')
    monkeypatch.setattr(
        github_oauth.requests,
        'post',
        lambda *_args, **_kwargs: ResponseStub({'access_token': 'token'}),
    )

    def fake_get(url, **_kwargs):
        if url == github_oauth.GITHUB_USER_URL:
            return ResponseStub({'id': 99, 'login': 'operator', 'name': 'KAORI Operator', 'email': None})
        if url == github_oauth.GITHUB_EMAILS_URL:
            return ResponseStub([{'email': 'operator@example.com', 'primary': True, 'verified': True}])
        raise AssertionError(f'unexpected URL: {url}')

    monkeypatch.setattr(github_oauth.requests, 'get', fake_get)

    identity = github_oauth.GitHubOAuthProvider().exchange_code(
        _provider('github_oauth'),
        code='authorization-code',
        redirect_uri='https://kaori.example/auth/sso/github/callback',
        expected_nonce=None,
    )

    assert identity.subject == '99'
    assert identity.email == 'operator@example.com'
    assert identity.email_verified is True


def test_github_public_profile_email_is_not_claimed_as_verified(monkeypatch) -> None:
    monkeypatch.setenv('CLIENT_SECRET', 'secret')
    monkeypatch.setattr(
        github_oauth.requests,
        'post',
        lambda *_args, **_kwargs: ResponseStub({'access_token': 'token'}),
    )

    def fake_get(url, **_kwargs):
        if url == github_oauth.GITHUB_USER_URL:
            return ResponseStub(
                {
                    'id': 99,
                    'login': 'operator',
                    'name': 'KAORI Operator',
                    'email': 'public@example.com',
                }
            )
        if url == github_oauth.GITHUB_EMAILS_URL:
            return ResponseStub([], status_code=403)
        raise AssertionError(f'unexpected URL: {url}')

    monkeypatch.setattr(github_oauth.requests, 'get', fake_get)

    identity = github_oauth.GitHubOAuthProvider().exchange_code(
        _provider('github_oauth'),
        code='authorization-code',
        redirect_uri='https://kaori.example/auth/sso/github/callback',
        expected_nonce=None,
    )

    assert identity.email == 'public@example.com'
    assert identity.email_verified is False
