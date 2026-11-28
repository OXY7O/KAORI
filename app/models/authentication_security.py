"""KAORI-owned human MFA factors and security policy; not identity-provider records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db
from app.security.credentials import EncryptedText


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuthenticationSecurityPolicy(db.Model):
    __tablename__ = 'authentication_security_policies'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
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
    enrolled_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f'<AuthenticationMfaFactor user_id={self.user_id} enabled={self.enabled}>'
