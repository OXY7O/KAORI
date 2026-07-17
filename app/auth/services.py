from __future__ import annotations

from flask import current_app

from app.auth.providers.registry import build_provider_registry
from app.auth.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthReason,
    AuthResult,
)


def authenticate(username: str, password: str) -> AuthResult:
    """Authenticate through the currently active provider chain.

    Local database authentication is authoritative in the current release and
    remains permanently available as the recovery/break-glass provider. LDAP and
    SSO names may be declared in configuration for deployment planning, but are
    never invoked until their adapters are implemented and explicitly activated.
    """

    registry = build_provider_registry()

    if registry.unsupported:
        current_app.logger.warning(
            'Unsupported authentication providers configured and ignored: %s',
            ', '.join(registry.unsupported),
        )

    result = registry.local.authenticate(username=username, password=password)

    if registry.configured_additional:
        current_app.logger.warning(
            'Authentication providers are configured but not active yet: %s',
            ', '.join(registry.configured_additional),
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
