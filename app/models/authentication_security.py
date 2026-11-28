"""KAORI-owned human MFA factors and security policy; not identity-provider records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db
from app.security.credentials import EncryptedText


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuthenticationSecurityPolicy(db.Model):
    __tablename__ = 'authentication_security_policies'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    __table_args__ = (
        db.CheckConstraint(
            "lockout_mode IN ('disabled', 'monitor_only', 'enforced')",
            name='ck_auth_security_lockout_mode',
        ),
        db.CheckConstraint('lockout_revision >= 1', name='ck_auth_security_lockout_revision'),
    )

    lockout_mode: Mapped[str] = mapped_column(
        db.String(24), nullable=False, default='disabled', server_default='disabled'
    )
    lockout_revision: Mapped[int] = mapped_column(
        db.BigInteger, nullable=False, default=1, server_default=db.text('1')
    )
    mfa_mode: Mapped[str] = mapped_column(db.String(32), nullable=False, default='disabled')
    bot_mode: Mapped[str] = mapped_column(db.String(24), nullable=False, default='disabled')
    bot_provider_key: Mapped[str] = mapped_column(db.String(60), nullable=False, default='cloudflare_turnstile')
    bot_site_key: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    bot_secret_key: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    bot_hostname: Mapped[str | None] = mapped_column(db.String(253), nullable=True)
    bot_tested_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    session_privileged_idle_minutes: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=15, server_default=db.text('15')
    )
    session_privileged_absolute_hours: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=4, server_default=db.text('4')
    )
    session_regular_idle_minutes: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=30, server_default=db.text('30')
    )
    session_regular_absolute_hours: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=8, server_default=db.text('8')
    )
    session_warning_minutes: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=2, server_default=db.text('2')
    )
    session_regular_remember: Mapped[bool] = mapped_column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class AuthenticationMfaFactor(db.Model):
    __tablename__ = 'authentication_mfa_factors'
    __table_args__ = (db.UniqueConstraint('user_id', name='uq_auth_mfa_user'),)

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    totp_secret: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    enabled: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    recovery_hashes: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    last_accepted_step: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    enrollment_expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True))
    enrollment_generation: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    enrollment_authenticated: Mapped[bool | None] = mapped_column(db.Boolean, nullable=True)
    replacement_totp_secret: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    replacement_generation: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    replacement_expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    replacement_provider_proof: Mapped[dict[str, Any] | None] = mapped_column(db.JSON(none_as_null=True), nullable=True)
    enrolled_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f'<AuthenticationMfaFactor user_id={self.user_id} enabled={self.enabled}>'


class AuthenticationAccountLockout(db.Model):
    """Bounded local-password observation; independent of account lifecycle."""

    __tablename__ = 'authentication_account_lockouts'
    __table_args__ = (
        db.CheckConstraint('policy_revision >= 1', name='ck_auth_lockout_policy_revision'),
        db.CheckConstraint('json_array_length(failure_times) <= 10', name='ck_auth_lockout_failure_bound'),
        db.CheckConstraint(
            'cooldown_until IS NULL OR locked_until IS NULL', name='ck_auth_lockout_exclusive_deadline'
        ),
    )

    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    policy_revision: Mapped[int] = mapped_column(db.BigInteger, nullable=False)
    failure_times: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    cooldown_until: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
