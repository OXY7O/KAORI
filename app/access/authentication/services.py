from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.admission import enforce_login_admission
from app.access.authentication.identity_provider.registry import build_credential_provider_registry
from app.access.authentication.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthReason,
    AuthResult,
)
from app.extensions.db import db
from app.models import User


def _finalize_result(result: AuthResult) -> AuthResult:
    return enforce_login_admission(result) if result.success else result


def authenticate(username: str, password: str) -> AuthResult:
    registry = build_credential_provider_registry()
    local_result = registry.local.authenticate(username=username, password=password)
    if (
        local_result.success
        or local_result.user is not None
        or local_result.reason in {'user_inactive', 'database_unavailable'}
    ):
        return _finalize_result(local_result)

    unavailable_result: AuthResult | None = None
    for provider in registry.external:
        result = provider.authenticate(username=username, password=password)
        if result.success or result.user is not None or result.reason == 'user_inactive':
            return _finalize_result(result)
        if result.reason == 'provider_unavailable':
            unavailable_result = result

    return unavailable_result or local_result


def record_successful_authentication(
    user: User,
    *,
    source: str,
    client_ip: str | None,
) -> None:
    """Persist login evidence before the authenticated session is established."""

    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = client_ip
    user.last_auth_source = source
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def credential_failure_message(result: AuthResult) -> str:
    """Return the public message for username/password authentication failures.

    Account state, provider ownership, role state, and LDAP reachability remain
    audit-only details so the login surface does not become a username or account
    state enumeration oracle.
    """

    if result.reason == 'database_unavailable':
        return result.message or DATABASE_UNAVAILABLE_MESSAGE
    return INVALID_LOGIN_MESSAGE


__all__ = [
    'AuthReason',
    'AuthResult',
    'DATABASE_UNAVAILABLE_MESSAGE',
    'INVALID_LOGIN_MESSAGE',
    'PROVIDER_UNAVAILABLE_MESSAGE',
    'USER_INACTIVE_MESSAGE',
    'authenticate',
    'credential_failure_message',
    'record_successful_authentication',
]
