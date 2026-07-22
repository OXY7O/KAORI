from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def utc_now() -> datetime:
    return datetime.now(UTC)


def _split_policy_values(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace('\n', ',')
    return [item.strip().lower() for item in normalized.split(',') if item.strip()]


class IdentityProvider(db.Model):
    __tablename__ = 'identity_providers'
    __table_args__ = (
        db.UniqueConstraint('key', name='uq_identity_providers_key'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(db.String(150), nullable=False)
    provider_type: Mapped[str] = mapped_column(db.String(30), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False, index=True)
    jit_enabled: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)

    server_uri: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    base_dn: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    bind_dn: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    bind_password_env: Mapped[str | None] = mapped_column(db.String(150), nullable=True)
    user_filter: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    group_base_dn: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    group_filter: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    tls_mode: Mapped[str] = mapped_column(db.String(20), default='ldaps', nullable=False)
    connect_timeout_seconds: Mapped[int] = mapped_column(db.Integer, default=5, nullable=False)

    username_attribute: Mapped[str] = mapped_column(db.String(100), default='sAMAccountName', nullable=False)
    email_attribute: Mapped[str] = mapped_column(db.String(100), default='mail', nullable=False)
    display_name_attribute: Mapped[str] = mapped_column(db.String(100), default='displayName', nullable=False)
    stable_id_attribute: Mapped[str] = mapped_column(db.String(100), default='objectGUID', nullable=False)

    oidc_issuer: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    oidc_client_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    oidc_client_secret_env: Mapped[str | None] = mapped_column(db.String(150), nullable=True)
    default_role_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('roles.id', ondelete='SET NULL'), nullable=True, index=True
    )
    allowed_domains: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    allowed_subjects: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    identity_links = relationship('ExternalIdentityLink', back_populates='provider', lazy='dynamic')
    default_role = relationship('Role', lazy='joined')

    @property
    def allowed_domains_list(self) -> list[str]:
        return _split_policy_values(self.allowed_domains)

    @property
    def allowed_subjects_list(self) -> list[str]:
        return _split_policy_values(self.allowed_subjects)


class ExternalIdentityLink(db.Model):
    __tablename__ = 'external_identity_links'
    __table_args__ = (
        db.UniqueConstraint('provider_id', 'subject', name='uq_external_identity_provider_subject'),
        db.UniqueConstraint('user_id', 'provider_id', name='uq_external_identity_user_provider'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        db.ForeignKey('identity_providers.id', ondelete='CASCADE'), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(db.String(500), nullable=False, index=True)
    external_username: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    distinguished_name: Mapped[str | None] = mapped_column(db.String(1000), nullable=True)
    email: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    projection_type: Mapped[str] = mapped_column(db.String(30), default='administrative', nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user = relationship('User', back_populates='external_identities')
    provider = relationship('IdentityProvider', back_populates='identity_links')
