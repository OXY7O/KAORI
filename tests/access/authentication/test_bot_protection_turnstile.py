"""Cloudflare Siteverify kernel: fail closed without exposing raw secrets (#3136)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import requests

from app.access.authentication.bot_protection.registry import (
    BotProviderError,
    bot_provider_definition,
    bot_provider_definitions,
    get_bot_verifier,
)
from app.access.authentication.bot_protection.turnstile import (
    SITEVERIFY_URL,
    BotVerificationReason,
    TurnstileVerificationConfig,
    verify_turnstile,
)

CURRENT = datetime(2026, 10, 25, 6, 0, tzinfo=UTC)
CONFIG = TurnstileVerificationConfig(
    secret_key='server-test-secret',
    expected_hostname='kaori.example.com',
    expected_action='login',
)


class FakeResponse:
    def __init__(self, payload: object, *, status: int = 200, extra_bytes: int = 0) -> None:
        self.status_code = status
        self.raw = json.dumps(payload).encode('utf-8') + b'x' * extra_bytes
        self.closed = False

    def iter_content(self, *, chunk_size: int):
        yield from (self.raw[i : i + chunk_size] for i in range(0, len(self.raw), chunk_size))

    def close(self) -> None:
        self.closed = True


def trusted_response(**changes: Any) -> dict[str, object]:
    payload: dict[str, object] = {
        'success': True,
        'hostname': 'kaori.example.com',
        'action': 'login',
        'challenge_ts': '2026-10-25T05:59:50Z',
    }
    payload.update(changes)
    return payload


def test_provider_registry_is_distinct_from_identity_provider_catalog() -> None:
    definition = bot_provider_definition('cloudflare_turnstile')
    assert len(bot_provider_definitions()) == 1
    assert definition.token_field == 'cf-turnstile-response'
    assert get_bot_verifier(definition.provider_key) is verify_turnstile
    with pytest.raises(BotProviderError):
        get_bot_verifier('hcaptcha')  # Not admitted as an adapter yet.


def test_verified_token_uses_fixed_https_endpoint_and_bounded_request() -> None:
    calls: list[dict[str, object]] = []
    response = FakeResponse(trusted_response())

    def post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append({'url': url, **kwargs})
        return response

    result = verify_turnstile('issued-one-time-token', config=CONFIG, transport=post, now=CURRENT)
    assert result.passed and result.reason == BotVerificationReason.VERIFIED
    assert calls[0]['url'] == SITEVERIFY_URL
    assert calls[0]['data'] == {'secret': 'server-test-secret', 'response': 'issued-one-time-token'}
    assert calls[0]['timeout'] == (2, 4)
    assert calls[0]['allow_redirects'] is False
    assert calls[0]['stream'] is True
    assert 'remoteip' not in calls[0]['data']
    assert response.closed


@pytest.mark.parametrize('token', [None, '', ' ', 'a' * 2049, '\\nnewline', 'non-ascii-☃'])
def test_missing_or_malformed_token_rejected_without_network(token: str | None) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> FakeResponse:
        raise AssertionError('must not call provider')

    result = verify_turnstile(token, config=CONFIG, transport=forbidden, now=CURRENT)
    assert not result.passed
    assert result.reason == BotVerificationReason.MISSING_TOKEN


@pytest.mark.parametrize(
    'configuration',
    [
        TurnstileVerificationConfig('', 'kaori.example.com', 'login'),
        TurnstileVerificationConfig('secret', 'https://evil.example', 'login'),
        TurnstileVerificationConfig('secret', 'kaori.example.com', ''),
        TurnstileVerificationConfig('secret', 'kaori.example.com', 'a' * 33),
    ],
)
def test_invalid_configuration_fails_before_transport(configuration: TurnstileVerificationConfig) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> FakeResponse:
        raise AssertionError('must not call provider')

    result = verify_turnstile('token', config=configuration, transport=forbidden, now=CURRENT)
    assert not result.passed
    assert result.reason == BotVerificationReason.INVALID_CONFIGURATION


@pytest.mark.parametrize(
    ('payload', 'reason'),
    [
        (trusted_response(success=False), BotVerificationReason.PROVIDER_REJECTED),
        (trusted_response(hostname='other.example.com'), BotVerificationReason.HOSTNAME_MISMATCH),
        (trusted_response(action='register'), BotVerificationReason.ACTION_MISMATCH),
        (trusted_response(challenge_ts='2026-10-25T05:50:00Z'), BotVerificationReason.EXPIRED),
        (trusted_response(challenge_ts='2026-10-25T06:01:00Z'), BotVerificationReason.EXPIRED),
        (trusted_response(challenge_ts='invalid'), BotVerificationReason.EXPIRED),
        ({'success': 'true'}, BotVerificationReason.INVALID_RESPONSE),
        ([{'success': True}], BotVerificationReason.INVALID_RESPONSE),
    ],
)
def test_invalid_siteverify_payloads_fail_closed(payload: object, reason: BotVerificationReason) -> None:
    response = FakeResponse(payload)
    result = verify_turnstile('token', config=CONFIG, transport=lambda *a, **k: response, now=CURRENT)
    assert not result.passed and result.reason == reason


def test_network_and_redirect_fail_closed_without_secret_in_result() -> None:
    def down(*args: Any, **kwargs: Any) -> FakeResponse:
        raise requests.Timeout('sensitive provider transport detail')

    result = verify_turnstile('token', config=CONFIG, transport=down, now=CURRENT)
    assert not result.passed and result.reason == BotVerificationReason.PROVIDER_UNAVAILABLE
    assert 'sensitive' not in repr(result)
    redirect = FakeResponse(trusted_response(), status=302)
    result = verify_turnstile('token', config=CONFIG, transport=lambda *a, **k: redirect, now=CURRENT)
    assert result.reason == BotVerificationReason.PROVIDER_UNAVAILABLE


def test_oversize_response_is_rejected_and_closed() -> None:
    response = FakeResponse(trusted_response(), extra_bytes=9000)
    result = verify_turnstile('token', config=CONFIG, transport=lambda *a, **k: response, now=CURRENT)
    assert result.reason == BotVerificationReason.INVALID_RESPONSE
    assert response.closed


def test_configuration_repr_hides_secret() -> None:
    assert 'server-test-secret' not in repr(CONFIG)
