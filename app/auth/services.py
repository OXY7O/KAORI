from __future__ import annotations

from flask import current_app

from app.auth.providers.database import DatabaseAuthProvider
from app.auth.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthReason,
    AuthResult,
)

SUPPORTED_ADDITIONAL_PROVIDERS = {
    'ldap',
    'sso',
}


def _get_database_provider() -> DatabaseAuthProvider:
    return DatabaseAuthProvider()


def _get_configured_additional_providers() -> list[str]:
    raw_value = current_app.config.get(
        'AUTH_ADDITIONAL_PROVIDERS',
        '',
    )

    provider_names = [provider.strip().lower() for provider in str(raw_value or '').split(',') if provider.strip()]

    unsupported_providers = [provider for provider in provider_names if provider not in SUPPORTED_ADDITIONAL_PROVIDERS]

    if unsupported_providers:
        current_app.logger.warning(
            'Unsupported additional auth providers configured and ignored: %s',
            ', '.join(unsupported_providers),
        )

    return [provider for provider in provider_names if provider in SUPPORTED_ADDITIONAL_PROVIDERS]


# Service function to authenticate a user.
# Database authentication is always available as the local break-glass provider.
# LDAP/SSO are treated as optional additional providers when implemented later.
def authenticate(username: str, password: str) -> AuthResult:
    database_provider = _get_database_provider()
    result = database_provider.authenticate(username=username, password=password)

    if result.success or result.reason == 'database_unavailable':
        return result

    additional_providers = _get_configured_additional_providers()

    if additional_providers:
        current_app.logger.warning(
            'Additional auth providers are configured but not implemented yet: %s',
            ', '.join(additional_providers),
        )

    return result


__all__ = [
    'AuthReason',
    'AuthResult',
    'DATABASE_UNAVAILABLE_MESSAGE',
    'INVALID_LOGIN_MESSAGE',
    'USER_INACTIVE_MESSAGE',
    'authenticate',
]
