from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.auth.providers.browser import SsoProviderError, sso_flow_is_valid, state_fingerprint
from app.auth.providers.catalog import browser_sso_provider_types
from app.auth.providers.registry import get_browser_sso_provider, registered_browser_sso_provider_types


def _provider(provider_type: str):
    return SimpleNamespace(
        provider_type=provider_type,
        oidc_client_id='client-id',
        oidc_client_secret_env='CLIENT_SECRET',
        connect_timeout_seconds=5,
    )


def test_browser_provider_registry_is_explicit_and_closed() -> None:
    assert registered_browser_sso_provider_types() == browser_sso_provider_types()
    assert registered_browser_sso_provider_types() == ('google_oidc', 'github_oauth')
    with pytest.raises(SsoProviderError, match='does not support browser SSO'):
        get_browser_sso_provider('unknown')


def test_google_authorization_url_contains_state_nonce_and_oidc_scope() -> None:
    adapter = get_browser_sso_provider('google_oidc')
    url = adapter.build_authorization_url(
        _provider('google_oidc'),
        redirect_uri='https://kaori.example/auth/sso/google/callback',
        state='state-value',
        nonce='nonce-value',
    )
    params = parse_qs(urlparse(url).query)

    assert params['state'] == ['state-value']
    assert params['nonce'] == ['nonce-value']
    assert params['scope'] == ['openid email profile']
    assert adapter.requires_nonce is True


def test_github_authorization_url_disables_signup_and_does_not_require_nonce() -> None:
    adapter = get_browser_sso_provider('github_oauth')
    url = adapter.build_authorization_url(
        _provider('github_oauth'),
        redirect_uri='https://kaori.example/auth/sso/github/callback',
        state='state-value',
        nonce=None,
    )
    params = parse_qs(urlparse(url).query)

    assert params['state'] == ['state-value']
    assert params['allow_signup'] == ['false']
    assert adapter.requires_nonce is False


def test_state_fingerprint_is_deterministic_without_storing_raw_state() -> None:
    assert state_fingerprint('state-value') == state_fingerprint('state-value')
    assert state_fingerprint('state-value') != state_fingerprint('other-state')
    assert state_fingerprint('state-value') != 'state-value'


def test_sso_flow_validation_accepts_only_matching_unexpired_state() -> None:
    flow = {
        'provider_id': 7,
        'state_hash': state_fingerprint('expected-state'),
        'started_at': 1000.0,
    }

    assert sso_flow_is_valid(
        flow,
        provider_id=7,
        supplied_state='expected-state',
        now_timestamp=1050.0,
        ttl_seconds=60,
    )
    assert not sso_flow_is_valid(
        flow,
        provider_id=8,
        supplied_state='expected-state',
        now_timestamp=1050.0,
        ttl_seconds=60,
    )
    assert not sso_flow_is_valid(
        flow,
        provider_id=7,
        supplied_state='wrong-state',
        now_timestamp=1050.0,
        ttl_seconds=60,
    )
    assert not sso_flow_is_valid(
        flow,
        provider_id=7,
        supplied_state='expected-state',
        now_timestamp=1061.0,
        ttl_seconds=60,
    )


def test_sso_flow_validation_fails_closed_for_malformed_session_values() -> None:
    assert not sso_flow_is_valid(
        {'provider_id': 'invalid', 'state_hash': 'hash', 'started_at': 'invalid'},
        provider_id=7,
        supplied_state='state',
        now_timestamp=1050.0,
        ttl_seconds=60,
    )
    assert not sso_flow_is_valid(
        {},
        provider_id=7,
        supplied_state='state',
        now_timestamp=1050.0,
        ttl_seconds=60,
    )
