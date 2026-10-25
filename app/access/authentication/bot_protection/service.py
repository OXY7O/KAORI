"""KAORI-owned Turnstile instance, policy and fail-closed runtime admission.

Provider Siteverify remains authoritative; KAORI never treats the browser widget
or local form as sufficient proof. No CAPTCHA token/secret is logged or audited.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.access.authentication.bot_protection.registry import bot_provider_definition
from app.access.authentication.bot_protection.turnstile import (
    TurnstileVerificationConfig,
    _configuration_ready,
    verify_turnstile,
)
from app.extensions.db import db
from app.models.authentication_security import AuthenticationSecurityPolicy


class BotPolicyMode(StrEnum):
    DISABLED = 'disabled'
    ALWAYS = 'always'


class BotConfigurationError(RuntimeError):
    """An invalid active policy must not silently fail open."""


@dataclass(frozen=True, slots=True)
class BotPolicyState:
    mode: BotPolicyMode
    provider_key: str
    site_key: str | None
    hostname: str | None
    configured: bool
    verification: TurnstileVerificationConfig | None = None

    @property
    def enabled(self) -> bool:
        return self.mode == BotPolicyMode.ALWAYS


def bot_policy_state() -> BotPolicyState:
    """Read committed policy; never query the external provider on page loads."""
    row = db.session.get(AuthenticationSecurityPolicy, 1)
    if row is None:
        return BotPolicyState(BotPolicyMode.DISABLED, 'cloudflare_turnstile', None, None, False)
    try:
        mode = BotPolicyMode(row.bot_mode)
        definition = bot_provider_definition(row.bot_provider_key)
    except (ValueError, TypeError) as exc:
        raise BotConfigurationError('Authentication bot policy configuration is invalid.') from exc

    secret = row.bot_secret_key
    key = row.bot_site_key
    hostname = row.bot_hostname
    settings = TurnstileVerificationConfig(
        secret_key=secret or '', expected_hostname=hostname or '', expected_action='login'
    )
    configured = bool(
        isinstance(key, str)
        and 1 <= len(key) <= 255
        and key.isascii()
        and not any(char.isspace() for char in key)
        and _configuration_ready(settings)
    )
    if mode == BotPolicyMode.ALWAYS and not configured:
        # A partially configured enabled instance is an availability error,
        # never permission to bypass challenge verification.
        raise BotConfigurationError('The active bot-protection provider is not configured.')
    return BotPolicyState(mode, definition.provider_key, key, hostname, configured, settings if configured else None)


def bot_token_verified(token: str | None, state: BotPolicyState) -> bool:
    """Required verification must be performed on every protected request."""
    if not state.enabled:
        return True
    if not state.configured or state.verification is None:
        return False
    try:
        return bool(verify_turnstile(token, config=state.verification).passed)
    except (OSError, RuntimeError, ValueError):
        return False
