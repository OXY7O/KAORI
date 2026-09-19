from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


def utc_now() -> datetime:
    return datetime.now(UTC)


def _policy_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return []


class IdentityProvider(db.Model):
    __tablename__ = 'identity_providers'
    __table_args__ = (
        db.UniqueConstraint('key', name='uq_identity_providers_key'),
        db.CheckConstraint("provider_key <> ''", name='ck_identity_providers_provider_key'),
        db.CheckConstraint("adapter_key <> ''", name='ck_identity_providers_adapter_key'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(db.String(150), nullable=False)
    provider_key: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    adapter_key: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False, index=True)
    jit_enabled: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    default_role_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('roles.id', ondelete='SET NULL'), nullable=True, index=True
    )
    configuration_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict, nullable=False)
    admission_policy_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    identity_links = relationship('ExternalIdentityLink', back_populates='provider', lazy='dynamic')
    default_role = relationship('Role', lazy='joined')

    @property
    def admission_values(self) -> list[str]:
        return _policy_values((self.admission_policy_json or {}).get('values'))


class ExternalIdentityLink(db.Model):
    __tablename__ = 'external_identity_links'
    __table_args__ = (
        db.UniqueConstraint('provider_id', 'subject', name='uq_external_identity_provider_subject'),
        db.UniqueConstraint('user_id', 'provider_id', name='uq_external_identity_user_provider'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
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
