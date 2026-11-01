"""Authentication bot-protection providers are not primary Identity Providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.access.authentication.bot_protection.turnstile import (
    BotVerificationResult,
    verify_turnstile,
)


class BotProviderError(ValueError):
    """An unregistered provider must never be accepted by an auth policy."""


@dataclass(frozen=True, slots=True)
class BotProviderDefinition:
    provider_key: str
    label: str
    token_field: str
    verification_url: str


_TURNSTILE = BotProviderDefinition(
    provider_key='cloudflare_turnstile',
    label='Cloudflare Turnstile',
    token_field='cf-turnstile-response',
    verification_url='https://challenges.cloudflare.com/turnstile/v0/siteverify',
)
_PROVIDERS = {_TURNSTILE.provider_key: _TURNSTILE}


def bot_provider_definitions() -> tuple[BotProviderDefinition, ...]:
    return tuple(_PROVIDERS.values())


def bot_provider_definition(provider_key: str) -> BotProviderDefinition:
    normalized = str(provider_key or '').strip().lower()
    try:
        return _PROVIDERS[normalized]
    except KeyError as exc:
        raise BotProviderError('Bot Protection provider is not supported.') from exc


def get_bot_verifier(
    provider_key: str,
) -> Callable[..., BotVerificationResult]:
    """Return a provider adapter; do not treat this registry as live readiness."""
    definition = bot_provider_definition(provider_key)
    if definition.provider_key == 'cloudflare_turnstile':
        return verify_turnstile
    raise BotProviderError('Bot Protection adapter is unavailable.')
