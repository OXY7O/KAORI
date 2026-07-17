from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from app.auth.providers.base import AuthProvider
from app.auth.providers.database import DatabaseAuthProvider

SUPPORTED_ADDITIONAL_PROVIDERS = frozenset({'ldap', 'sso'})


@dataclass(frozen=True)
class ProviderRegistry:
    """Provider availability resolved from application configuration.

    Local database authentication is always registered because it is KAORI's
    recovery and break-glass authentication path. LDAP and SSO remain declared
    capabilities until their adapters and configuration contracts are complete.
    """

    local: AuthProvider
    configured_additional: tuple[str, ...]
    unsupported: tuple[str, ...]


def build_provider_registry() -> ProviderRegistry:
    raw_value = current_app.config.get('AUTH_ADDITIONAL_PROVIDERS', '')
    requested = tuple(
        provider.strip().lower()
        for provider in str(raw_value or '').split(',')
        if provider.strip()
    )

    unsupported = tuple(
        provider for provider in requested if provider not in SUPPORTED_ADDITIONAL_PROVIDERS
    )
    configured = tuple(
        provider for provider in requested if provider in SUPPORTED_ADDITIONAL_PROVIDERS
    )

    return ProviderRegistry(
        local=DatabaseAuthProvider(),
        configured_additional=configured,
        unsupported=unsupported,
    )
