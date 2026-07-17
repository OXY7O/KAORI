from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthResult,
)
from app.extensions import db
from app.models import User

_DUMMY_PASSWORD_HASH = generate_password_hash('kaori-auth-timing-placeholder')


class DatabaseAuthProvider:
    source = 'database'

    def authenticate(self, username: str, password: str) -> AuthResult:
        normalized_username = username.strip()

        try:
            user = User.query.filter(
                User.username == normalized_username,
                User.deleted_at.is_(None),
            ).first()
        except SQLAlchemyError:
            db.session.rollback()
            return AuthResult(
                success=False,
                reason='database_unavailable',
                source=self.source,
                message=DATABASE_UNAVAILABLE_MESSAGE,
            )

        if not user:
            # Perform one password-hash verification for unknown users so the
            # public rejection path is less distinguishable by response timing.
            check_password_hash(_DUMMY_PASSWORD_HASH, password)
            return AuthResult(
                success=False,
                reason='invalid_credentials',
                source=self.source,
                message=INVALID_LOGIN_MESSAGE,
            )

        if user.auth_source != self.source:
            # The username belongs to an external identity. Keep the public
            # response indistinguishable, but allow the provider registry to
            # continue with LDAP or a future password-based external adapter.
            check_password_hash(_DUMMY_PASSWORD_HASH, password)
            return AuthResult(
                success=False,
                reason='invalid_credentials',
                source=self.source,
                message=INVALID_LOGIN_MESSAGE,
            )

        if not user.check_password(password):
            return AuthResult(
                success=False,
                reason='invalid_credentials',
                source=self.source,
                user=user,
                message=INVALID_LOGIN_MESSAGE,
            )

        if not user.is_active:
            return AuthResult(
                success=False,
                reason='user_inactive',
                source=self.source,
                user=user,
                message=USER_INACTIVE_MESSAGE,
            )

        return AuthResult(
            success=True,
            reason='success',
            source=self.source,
            user=user,
        )
