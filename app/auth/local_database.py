from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.auth.results import DATABASE_UNAVAILABLE_MESSAGE, INVALID_LOGIN_MESSAGE, USER_INACTIVE_MESSAGE, AuthResult
from app.extensions.db import db
from app.models import User


class DatabaseAuthProvider:
    source = 'database'

    def authenticate(self, username: str, password: str) -> AuthResult:
        normalized = username.strip()
        if not normalized or not password:
            return AuthResult(False, 'invalid_credentials', source=self.source, message=INVALID_LOGIN_MESSAGE)
        try:
            user = User.query.filter(User.deleted_at.is_(None), User.username == normalized).first()
        except SQLAlchemyError:
            db.session.rollback()
            return AuthResult(False, 'database_unavailable', source=self.source, message=DATABASE_UNAVAILABLE_MESSAGE)
        if user is None:
            return AuthResult(False, 'invalid_credentials', source=self.source, message=INVALID_LOGIN_MESSAGE)
        if user.auth_source != 'database' or not user.password_hash:
            return AuthResult(
                False, 'invalid_credentials', source=self.source, user=user, message=INVALID_LOGIN_MESSAGE
            )
        if not user.check_password(password):
            return AuthResult(
                False, 'invalid_credentials', source=self.source, user=user, message=INVALID_LOGIN_MESSAGE
            )
        if not user.is_active:
            return AuthResult(False, 'user_inactive', source=self.source, user=user, message=USER_INACTIVE_MESSAGE)
        return AuthResult(True, 'success', source=self.source, user=user)
