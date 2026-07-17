from __future__ import annotations

from app.auth.providers.registry import build_provider_registry
from app.auth.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthReason,
    AuthResult,
)


def authenticate(username: str, password: str) -> AuthResult:
    registry = build_provider_registry()
    local_result = registry.local.authenticate(username=username, password=password)
    if local_result.success or local_result.reason in {'user_inactive', 'database_unavailable'}:
        return local_result

    unavailable_result: AuthResult | None = None
    for provider in registry.external:
        result = provider.authenticate(username=username, password=password)
        if result.success or result.reason == 'user_inactive':
            return result
        if result.reason == 'provider_unavailable':
            unavailable_result = result

    return unavailable_result or local_result


__all__ = [
    'AuthReason', 'AuthResult', 'DATABASE_UNAVAILABLE_MESSAGE', 'INVALID_LOGIN_MESSAGE',
    'PROVIDER_UNAVAILABLE_MESSAGE', 'USER_INACTIVE_MESSAGE', 'authenticate',
]
