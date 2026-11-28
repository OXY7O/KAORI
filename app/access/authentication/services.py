from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.admission import enforce_login_admission
from app.access.authentication.identity_provider.registry import build_credential_provider_registry
from app.access.authentication.identity_provider.proof import lock_external_credential_proof
from app.access.authentication.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthReason,
    AuthResult,
    ExternalCredentialProof,
    LocalCredentialProof,
)
from app.access.authentication.session import AuthSessionError
from app.extensions.db import db
from app.models import Role, User


def _finalize_result(result: AuthResult) -> AuthResult:
    return enforce_login_admission(result) if result.success else result


def authenticate(username: str, password: str) -> AuthResult:
    registry = build_credential_provider_registry()
    local_result = registry.local.authenticate(username=username, password=password)
    # A provisioned directory user has a KAORI User row but no local password.
    # The Local Database probe must not claim that external identity; only
    # Local Database identities retain authority over a failed local login.
    local_user = local_result.user
    if (
        local_result.success
        or local_result.reason in {'user_inactive', 'database_unavailable'}
        or (local_user is not None and local_user.auth_source == 'database')
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


def stage_successful_authentication(
    user: User,
    *,
    source: str,
    client_ip: str | None,
    local_credential_proof: LocalCredentialProof | None = None,
    pending_generation: int | None = None,
    external_credential_proof: ExternalCredentialProof | None = None,
) -> int:
    """Stage the one current login generation; the caller owns commit/rollback.

    PostgreSQL serializes concurrent UPDATEs on the same user row. RETURNING
    captures *this login's* generation; re-reading the ORM object after commit
    could instead capture a newer concurrent login and admit both browsers.
    """
    normalized_source = source.strip().lower()
    if normalized_source != 'database':
        lock_external_credential_proof(user.id, normalized_source, external_credential_proof)
    if pending_generation is None and normalized_source == 'database':
        if local_credential_proof is None or not local_credential_proof.password_hash:
            raise AuthSessionError('Verified local credential proof is missing.')
        # Compare under the user-row lock. The password hash never appears
        # in SQL bind parameters, a pending cookie or audit metadata.
        current_hash = db.session.execute(
            select(User.password_hash).where(User.id == user.id).with_for_update()
        ).scalar_one_or_none()
        if current_hash != local_credential_proof.password_hash:
            raise AuthSessionError('Verified local credential proof is stale.')

    conditions = [
        User.id == user.id,
        User.account_is_active.is_(True),
        User.deleted_at.is_(None),
        func.lower(User.auth_source) == normalized_source,
        or_(
            User.is_super_admin.is_(True) & (User.auth_source == 'database'),
            User.role_record.has(Role.is_active.is_(True)),
        ),
    ]
    if pending_generation is not None:
        if type(pending_generation) is not int or pending_generation < 1:
            raise AuthSessionError('Pending authentication generation is invalid.')
        conditions.append(User.auth_session_version == pending_generation)
    issued_at = datetime.now(UTC)
    issued_version = db.session.execute(
        update(User)
        .where(*conditions)
        .values(
            auth_session_version=func.coalesce(User.auth_session_version, 1) + 1,
            auth_session_issued_at=issued_at,
            auth_session_activity_at=issued_at,
            last_login_at=issued_at,
            last_login_ip=client_ip,
            last_auth_source=source,
        )
        .returning(User.auth_session_version)
    ).scalar_one_or_none()
    if issued_version is None:
        # The account can have changed since primary authentication.
        raise AuthSessionError('KAORI session admission was revoked before issuance.')
    return int(issued_version)


def record_successful_authentication(
    user: User,
    *,
    source: str,
    client_ip: str | None,
    local_credential_proof: LocalCredentialProof | None = None,
    external_credential_proof: ExternalCredentialProof | None = None,
) -> int:
    """Commit a primary-only admitted login; pending MFA has its own transaction owner."""
    try:
        issued_version = stage_successful_authentication(
            user,
            source=source,
            client_ip=client_ip,
            local_credential_proof=local_credential_proof,
            external_credential_proof=external_credential_proof,
        )
        db.session.commit()
    except (SQLAlchemyError, AuthSessionError):
        db.session.rollback()
        raise
    return issued_version


def load_pending_mfa_user(user_id: int) -> User | None:
    """Load an MFA challenge principal without admitting a browser session.

    The route independently verifies identity source and authentication
    generation before any second-factor operation can complete.
    """
    return User.query.filter_by(id=user_id).first()


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
    'load_pending_mfa_user',
    'record_successful_authentication',
]
