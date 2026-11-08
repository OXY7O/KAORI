"""Bot Protection persistence policy and server admission contracts (#3137)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.access.authentication.bot_protection import service
from app.access.authentication.bot_protection.service import (
    BotConfigurationError,
    BotPolicyMode,
    BotPolicyState,
    bot_policy_state,
    bot_token_verified,
)
from app.access.authentication.bot_protection.turnstile import TurnstileVerificationConfig
from app.models.authentication_security import AuthenticationSecurityPolicy


class FakeStore:
    def __init__(self, policy: AuthenticationSecurityPolicy | None = None) -> None:
        self.policy = policy

    def get(self, model: object, key: int) -> AuthenticationSecurityPolicy | None:
        assert model is AuthenticationSecurityPolicy
        assert key == 1
        return self.policy


def row(**changes: str) -> AuthenticationSecurityPolicy:
    fields = dict(
        id=1,
        mfa_mode='disabled',
        bot_mode='always',
        bot_provider_key='cloudflare_turnstile',
        bot_site_key='public-test-key',
        bot_secret_key='server-test-secret',
        bot_hostname='kaori.example.com',
    )
    fields.update(changes)
    return AuthenticationSecurityPolicy(**fields)


def test_unconfigured_policy_is_disabled_and_does_not_call_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service.db, 'session', FakeStore())
    state = bot_policy_state()
    assert state.mode == BotPolicyMode.DISABLED and not state.enabled
    assert not state.configured
    assert bot_token_verified(None, state)


def test_committed_turnstile_policy_is_ready_and_strips_secrets_from_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service.db, 'session', FakeStore(row()))
    state = bot_policy_state()
    assert state.enabled and state.configured and state.provider_key == 'cloudflare_turnstile'
    assert state.site_key == 'public-test-key'
    assert state.verification is not None
    assert state.verification.expected_hostname == 'kaori.example.com'
    assert 'server-test-secret' not in repr(state)


@pytest.mark.parametrize(
    'fields',
    [
        {'bot_mode': 'unexpected'},
        {'bot_provider_key': 'unknown'},
        {'bot_secret_key': ''},
        {'bot_site_key': ''},
        {'bot_hostname': ''},
        {'bot_hostname': 'evil.example/path'},
    ],
)
def test_invalid_active_policy_fails_closed(monkeypatch: pytest.MonkeyPatch, fields: dict[str, str]) -> None:
    monkeypatch.setattr(service.db, 'session', FakeStore(row(**fields)))
    with pytest.raises(BotConfigurationError):
        bot_policy_state()


def test_siteverify_outcome_is_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    config = TurnstileVerificationConfig('secret', 'kaori.example.com', 'login')
    state = BotPolicyState(BotPolicyMode.ALWAYS, 'cloudflare_turnstile', 'site', 'kaori.example.com', True, config)
    assert not bot_token_verified(None, state)
    monkeypatch.setattr(service, 'verify_turnstile', lambda token, *, config: SimpleNamespace(passed=token == 'good'))
    assert bot_token_verified('good', state)
    assert not bot_token_verified('bad', state)


def test_active_policy_never_accepts_unconfigured_challenge() -> None:
    state = BotPolicyState(BotPolicyMode.ALWAYS, 'cloudflare_turnstile', None, None, False)
    assert not bot_token_verified('forged', state)


def test_login_and_sso_both_gate_before_admission_source_contract() -> None:
    from pathlib import Path

    source = Path('app/access/authentication/routes.py').read_text()
    assert "bot_token_verified(request.form.get('cf-turnstile-response'), bot_state)" in source
    assert source.index("bot_token_verified(request.form.get('cf-turnstile-response'), bot_state)") < source.index(
        "username = form.username.data or ''"
    )
    assert 'SSO_BOT_GRANT_TTL_SECONDS = 60' in source
    assert 'grant = session.pop(SSO_BOT_GRANT_KEY, None)' in source
    assert 'callback_bot_state.enabled' in source
