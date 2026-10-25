"""Database-backed Cloudflare Turnstile instance and server-side admission (#3137)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.access.authentication.bot_protection.registry import bot_provider_definition
from app.access.authentication.bot_protection.turnstile import (
    BotVerificationResult,
    TurnstileVerificationConfig,
    verify_turnstile,
)
from app.models.authentication_security import AuthenticationSecurityPolicy

BOT_DISABLED = 'disabled'
BOT_ALWAYS = 'always'


@dataclass(frozen=True, slots=True)
class BotPublicState:
    mode: str
    provider_key: str
    site_key: str | None
    hostname: str | None
    configured: bool

    @property
    def required(self) -> bool:
        return self.mode == BOT_ALWAYS


def public_bot_state(policy: AuthenticationSecurityPolicy | None) -> BotPublicState:
    """Never serialize provider verification secrets to templates or audit."""
    if policy is None:
        return BotPublicState(BOT_DISABLED, 'cloudflare_turnstile', None, None, False)
    provider_key = policy.bot_provider_key
    if provider_key != 'cloudflare_turnstile':
        # Unknown persisted provider state cannot silently disable protection.
        raise ValueError('Unsupported configured Bot Protection provider.')
    configured = bool(policy.bot_site_key and policy.bot_secret and policy.bot_hostname)
    if policy.bot_mode not in (BOT_DISABLED, BOT_ALWAYS):
        raise ValueError('Unsupported persisted Bot Protection mode.')
    return BotPublicState(
        policy.bot_mode, provider_key, policy.bot_site_key, policy.bot_hostname, configured
    )


def validate_bot_configuration(site_key: str, hostname: str, secret: str) -> None:
    bot_provider_definition('cloudflare_turnstile')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,255}', site_key):
        raise ValueError('A valid Cloudflare Turnstile site key is required.')
    if not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}', hostname):
        raise ValueError('Enter a valid approved hostname without scheme or port.')
    if not isinstance(secret, str) or not 1 <= len(secret) <= 256 or any(char.isspace() for char in secret):
        raise ValueError('A valid protected Turnstile secret key is required.')


def verify_bot_challenge(
    policy: AuthenticationSecurityPolicy | None,
    token: str | None,
) -> BotVerificationResult | None:
    """None means disabled; a required policy rejects all incomplete proofs."""
    state = public_bot_state(policy)
    if not state.required:
        return None
    if policy is None:
        raise ValueError('Bot Protection policy is missing.')
    # The normalized Siteverify result remains provider-authoritative.
    return verify_turnstile(
        token,
        config=TurnstileVerificationConfig(
            secret_key=policy.bot_secret or '',
            expected_hostname=policy.bot_hostname or '',
            expected_action='login',
        ),
    )
