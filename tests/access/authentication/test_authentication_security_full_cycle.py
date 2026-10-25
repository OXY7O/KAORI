"""UAT-grade contract tests for session-bound MFA and Turnstile security (#3134/#3137)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor.totp import TOTP

from app.access.authentication.bot_protection.service import (
    BOT_ALWAYS,
    BOT_DISABLED,
    public_bot_state,
    validate_bot_configuration,
)
from app.access.authentication.mfa.service import _accepted_step
from app.models.authentication_security import AuthenticationSecurityPolicy


def test_totp_accepts_only_fresh_step_using_vetted_crypto_primitive() -> None:
    secret = base64.b32encode(b'kaori-unit-test-secret').decode('ascii')
    now = datetime(2026, 10, 25, 8, 0, 15, tzinfo=UTC)
    step = int(now.timestamp()) // 30
    otp = TOTP(base64.b32decode(secret), 6, hashes.SHA1(), 30).generate(step * 30).decode('ascii')
    assert _accepted_step(secret, otp, last_accepted_step=None, now=now) == step
    assert _accepted_step(secret, otp, last_accepted_step=step, now=now) is None
    assert _accepted_step(secret, '0000000', last_accepted_step=None, now=now) is None
    assert _accepted_step(secret, 'abcdef', last_accepted_step=None, now=now) is None


def test_previous_and_future_totp_windows_are_bounded() -> None:
    secret = base64.b32encode(b'kaori-test-secret-bytes').decode('ascii')
    now = datetime(2026, 10, 25, 8, 0, 15, tzinfo=UTC)
    otp = TOTP(base64.b32decode(secret), 6, hashes.SHA1(), 30)
    previous_step = int((now - timedelta(seconds=30)).timestamp()) // 30
    recent = otp.generate(previous_step * 30).decode('ascii')
    assert _accepted_step(secret, recent, last_accepted_step=None, now=now) == previous_step
    too_old = otp.generate((previous_step - 2) * 30).decode('ascii')
    assert _accepted_step(secret, too_old, last_accepted_step=None, now=now) is None


def test_bot_provider_configuration_is_validated_before_activation() -> None:
    validate_bot_configuration('0x4AAAA-example', 'localhost', '0x4AAAA-verified-secret')
    for site_key, hostname, secret in (
        ('', 'localhost', 'secret'),
        ('test', 'https://evil.test/', 'secret'),
        ('test', 'valid.example', ''),
        ('test', 'valid.example', 'bad\nsecret'),
    ):
        with pytest.raises(ValueError):
            validate_bot_configuration(site_key, hostname, secret)


def test_bot_policy_projection_never_returns_verification_secret() -> None:
    policy = AuthenticationSecurityPolicy(
        id=1,
        mfa_mode='disabled',
        bot_mode=BOT_ALWAYS,
        bot_provider_key='cloudflare_turnstile',
        bot_site_key='public-key',
        bot_secret='super-secret-not-for-browser',
        bot_hostname='localhost',
    )
    public = public_bot_state(policy)
    assert public.required and public.configured
    assert public.site_key == 'public-key'
    assert public.hostname == 'localhost'
    assert 'super-secret-not-for-browser' not in repr(public)
    policy.bot_mode = BOT_DISABLED
    assert not public_bot_state(policy).required
    policy.bot_provider_key = 'unexpected_provider'
    with pytest.raises(ValueError):
        public_bot_state(policy)


def test_csp_turnstile_exception_is_fixed_and_scoped() -> None:
    from app.bootstrap.security import _content_security_policy

    default = _content_security_policy('test-nonce')
    challenged = _content_security_policy('test-nonce', allow_turnstile=True)
    assert 'challenges.cloudflare.com' not in default
    assert 'script-src ' in challenged
    assert 'frame-src https://challenges.cloudflare.com' in challenged
    assert 'connect-src ' in challenged
    assert "'nonce-test-nonce'" in default and "'nonce-test-nonce'" in challenged
    assert "frame-ancestors 'none'" in default and "frame-ancestors 'none'" in challenged
