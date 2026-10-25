"""Bounded Cloudflare Turnstile Siteverify adapter (#3136).

Standalone server-side verification only. No login enforcement, provider
registration, secrets persistence, or policy activation exists in BP-01.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Callable

import requests

SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
MAX_TOKEN_LENGTH = 2048
MAX_RESPONSE_BYTES = 8192
TOKEN_MAX_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30


class BotVerificationReason(StrEnum):
    VERIFIED = 'verified'
    MISSING_TOKEN = 'missing_token'
    INVALID_CONFIGURATION = 'invalid_configuration'
    PROVIDER_REJECTED = 'provider_rejected'
    PROVIDER_UNAVAILABLE = 'provider_unavailable'
    INVALID_RESPONSE = 'invalid_response'
    HOSTNAME_MISMATCH = 'hostname_mismatch'
    ACTION_MISMATCH = 'action_mismatch'
    EXPIRED = 'expired'


@dataclass(frozen=True, slots=True)
class TurnstileVerificationConfig:
    secret_key: str = field(repr=False)
    expected_hostname: str
    expected_action: str


@dataclass(frozen=True, slots=True)
class BotVerificationResult:
    passed: bool
    reason: BotVerificationReason
    provider_key: str = 'cloudflare_turnstile'


def _result(reason: BotVerificationReason) -> BotVerificationResult:
    return BotVerificationResult(passed=reason == BotVerificationReason.VERIFIED, reason=reason)


def _configuration_ready(config: TurnstileVerificationConfig) -> bool:
    secret = config.secret_key
    hostname = config.expected_hostname
    action = config.expected_action
    return (
        isinstance(secret, str)
        and 1 <= len(secret) <= 256
        and not any(char.isspace() for char in secret)
        and isinstance(hostname, str)
        and 1 <= len(hostname) <= 253
        and not any(char in hostname for char in '/: \\t\\r\\n')
        and isinstance(action, str)
        and re.fullmatch(r'[a-zA-Z0-9_-]{1,32}', action) is not None
    )


def _validated_challenge_time(raw: object, *, now: datetime) -> bool:
    if not isinstance(raw, str) or len(raw) > 60:
        return False
    try:
        issued = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return False
    if issued.tzinfo is None or now.tzinfo is None:
        return False
    age = (now - issued).total_seconds()
    return -MAX_FUTURE_SKEW_SECONDS <= age <= TOKEN_MAX_AGE_SECONDS


def verify_turnstile(
    token: str | None,
    *,
    config: TurnstileVerificationConfig,
    transport: Callable[..., requests.Response] | None = None,
    now: datetime | None = None,
) -> BotVerificationResult:
    """Verify a one-time token without exposing credentials or accepting URLs.

    The server must call this only after it has resolved an admitted provider
    instance and bound hostname/action. A widget alone NEVER grants access.
    Remote-IP submission is intentionally omitted until privacy policy review.
    """
    if not _configuration_ready(config):
        return _result(BotVerificationReason.INVALID_CONFIGURATION)
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH:
        return _result(BotVerificationReason.MISSING_TOKEN)
    if token != token.strip() or any(ord(char) < 33 or ord(char) > 126 for char in token):
        return _result(BotVerificationReason.MISSING_TOKEN)

    post = transport or requests.post
    response: requests.Response | None = None
    try:
        response = post(
            SITEVERIFY_URL,
            data={'secret': config.secret_key, 'response': token},
            timeout=(2, 4),
            stream=True,
            allow_redirects=False,
        )
        if response.status_code != 200:
            return _result(BotVerificationReason.PROVIDER_UNAVAILABLE)

        chunks: list[bytes] = []
        consumed = 0
        for chunk in response.iter_content(chunk_size=2048):
            consumed += len(chunk)
            if consumed > MAX_RESPONSE_BYTES:
                return _result(BotVerificationReason.INVALID_RESPONSE)
            chunks.append(chunk)
        payload = json.loads(b''.join(chunks))
    except (requests.RequestException, ValueError, TypeError, UnicodeError, OSError):
        return _result(BotVerificationReason.PROVIDER_UNAVAILABLE)
    finally:
        if response is not None:
            response.close()

    if not isinstance(payload, dict) or type(payload.get('success')) is not bool:
        return _result(BotVerificationReason.INVALID_RESPONSE)
    if not payload['success']:
        # The provider's raw error values are never echoed into KAORI activity.
        return _result(BotVerificationReason.PROVIDER_REJECTED)
    hostname = payload.get('hostname')
    if not isinstance(hostname, str) or hostname.lower() != config.expected_hostname.lower():
        return _result(BotVerificationReason.HOSTNAME_MISMATCH)
    if payload.get('action') != config.expected_action:
        return _result(BotVerificationReason.ACTION_MISMATCH)
    verified_at = now or datetime.now(UTC)
    if not _validated_challenge_time(payload.get('challenge_ts'), now=verified_at):
        return _result(BotVerificationReason.EXPIRED)
    return _result(BotVerificationReason.VERIFIED)
