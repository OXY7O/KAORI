from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.auth.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthResult,
)
from app.models import User


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
            return AuthResult(
                success=False,
                reason='database_unavailable',
                source=self.source,
                message=DATABASE_UNAVAILABLE_MESSAGE,
            )

        if not user:
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
