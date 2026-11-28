from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from app.access.authentication.lockout_policy import LockoutMode
from app.access.authentication.lockout_state import lock_account_state, stage_password_outcome
from app.access.authentication.login_protection import (
    LoginProtectionUnavailable,
    LoginRequestProtection,
    read_login_policy,
)
from app.access.authentication.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthReason,
    AuthResult,
    LocalCredentialProof,
)
from app.extensions.db import db
from app.models import User

# Valid-format dummy verifier with no real credential. Match the default
# Werkzeug scrypt cost on rejected local paths without sleeping in workers.
_DUMMY_HASH = 'scrypt:32768:8:1$kaoriDummySalt$' + '0' * 128


def _dummy_check(password: str) -> None:
    check_password_hash(_DUMMY_HASH, password)


class DatabaseAuthProvider:
    source = 'database'

    def authenticate(
        self, username: str, password: str, *, protection: LoginRequestProtection | None = None
    ) -> AuthResult:
        if protection is not None and protection.blocked:
            return AuthResult(False, 'rate_limited', source=self.source, message=INVALID_LOGIN_MESSAGE)
        normalized = username.strip()
        if not normalized or not password:
            return AuthResult(False, 'invalid_credentials', source=self.source, message=INVALID_LOGIN_MESSAGE)
        try:
            user = User.query.filter(User.deleted_at.is_(None), User.username == normalized).first()
            if user is None or user.auth_source != 'database':
                _dummy_check(password)
                return AuthResult(
                    False, 'invalid_credentials', source=self.source, user=user, message=INVALID_LOGIN_MESSAGE
                )
            # Refresh the exact local identity under the account lock before
            # checking the password. Do not hold it over a remote provider call.
            user = db.session.execute(
                select(User)
                .where(User.id == user.id, User.username == normalized, User.auth_source == 'database')
                .with_for_update(of=User)
                .execution_options(populate_existing=True)
            ).scalar_one_or_none()
            if user is None:
                db.session.rollback()
                _dummy_check(password)
                return AuthResult(False, 'access_not_permitted', source=self.source, message=INVALID_LOGIN_MESSAGE)
            if not user.is_active or not user.password_hash:
                _dummy_check(password)
                reason: AuthReason = 'user_inactive' if not user.is_active else 'invalid_credentials'
                db.session.rollback()
                return AuthResult(
                    False, reason, source=self.source, user=user, message=USER_INACTIVE_MESSAGE,
                    local_authoritative=True,
                )
            context = lock_account_state(user.id)
            if context is None and not user.is_super_admin:
                raise ValueError('Local lockout account fence changed.')
            if context is None:
                mode, revision = read_login_policy(lock=True)
            else:
                mode, revision = context.decision.mode, context.revision
            if protection is None and mode != LockoutMode.DISABLED:
                raise ValueError('Shared login protection proof is required.')
            if protection is not None and (protection.revision != revision or protection.mode != mode):
                # Do not let an in-flight Disabled request skip the newly
                # activated shared request budget or reuse an obsolete mode.
                raise ValueError('Login protection policy changed.')
            if context is not None and context.decision.blocked:
                _dummy_check(password)
                stage_password_outcome(context, password_valid=None)
                db.session.commit()
                return AuthResult(False, 'account_gate_rejected', source=self.source, user=user,
                                  message=INVALID_LOGIN_MESSAGE)
            verified = user.check_password(password)
            proof = LocalCredentialProof(password_hash=user.password_hash, generation=user.auth_session_version)
            if context is not None:
                stage_password_outcome(context, password_valid=verified)
            # Commit observation/reset before returning a primary result, even
            # when MFA or authorization later rejects session admission.
            db.session.commit()
        except (SQLAlchemyError, ValueError, TypeError, LoginProtectionUnavailable):
            db.session.rollback()
            return AuthResult(False, 'database_unavailable', source=self.source, message=DATABASE_UNAVAILABLE_MESSAGE)
        if not verified:
            return AuthResult(
                False, 'invalid_credentials', source=self.source, user=user, message=INVALID_LOGIN_MESSAGE,
                local_authoritative=True,
            )
        return AuthResult(True, 'success', source=self.source, user=user, local_credential_proof=proof)
