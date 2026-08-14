from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.security.credentials import EncryptedText

if TYPE_CHECKING:
    from app.models.user import User


class NotificationChannel(db.Model):
    """Provider-neutral outbound notification destination owned by KAORI."""

    __tablename__ = 'notification_channels'
    __table_args__ = (
        CheckConstraint(
            "minimum_severity IN ('critical', 'warning', 'info')",
            name='ck_notification_channels_minimum_severity',
        ),
        CheckConstraint(
            "test_status IN ('not_tested', 'success', 'failed')",
            name='ck_notification_channels_test_status',
        ),
        CheckConstraint(
            "last_delivery_status IN ('never', 'success', 'failed')",
            name='ck_notification_channels_delivery_status',
        ),
        Index('ix_notification_channels_provider_enabled', 'provider_key', 'enabled'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        db.String(64), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(db.String(160), nullable=False)
    provider_key: Mapped[str] = mapped_column(db.String(40), nullable=False, default='telegram')
    enabled: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    credential_payload: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    destination: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    provider_config: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    minimum_severity: Mapped[str] = mapped_column(db.String(20), nullable=False, default='warning')
    domains: Mapped[list[str]] = mapped_column(
        db.JSON, nullable=False, default=lambda: ['kubernetes', 'object_storage']
    )
    event_types: Mapped[list[str]] = mapped_column(
        db.JSON, nullable=False, default=lambda: ['alert_intelligence.active_alert']
    )
    test_status: Mapped[str] = mapped_column(db.String(20), nullable=False, default='not_tested')
    test_message: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_delivery_status: Mapped[str] = mapped_column(db.String(20), nullable=False, default='never')
    last_delivery_message: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    last_delivery_attempt_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
    updated_by: Mapped[User | None] = relationship('User', foreign_keys=[updated_by_user_id])
    deliveries: Mapped[list[NotificationDelivery]] = relationship(
        'NotificationDelivery',
        back_populates='channel',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    @property
    def configured(self) -> bool:
        return bool(self.credential_payload and self.destination)

    @property
    def display_status(self) -> str:
        if not self.enabled:
            return 'Disabled'
        if not self.configured:
            return 'Configuration Required'
        if self.test_status == 'failed':
            return 'Validation Failed'
        if self.test_status != 'success':
            return 'Validation Required'
        if self.last_delivery_status == 'failed':
            return 'Delivery Failed'
        if self.last_delivery_status == 'success':
            return 'Operational'
        return 'Ready'


class NotificationDelivery(db.Model):
    """Delivery and deduplication journal for outbound KAORI notifications."""

    __tablename__ = 'notification_deliveries'
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'sent', 'failed', 'skipped')",
            name='ck_notification_deliveries_status',
        ),
        UniqueConstraint('channel_id', 'event_key', name='uq_notification_delivery_event'),
        Index('ix_notification_deliveries_status_created', 'status', 'created_at'),
        Index('ix_notification_deliveries_domain_asset', 'domain', 'asset_key'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        db.ForeignKey('notification_channels.id', ondelete='CASCADE'), nullable=False, index=True
    )
    event_key: Mapped[str] = mapped_column(db.String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(db.String(120), nullable=False)
    domain: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(db.String(80), nullable=False)
    asset_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(db.String(20), nullable=False)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False, default='queued')
    payload_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(db.String(120), nullable=True)
    attempt_count: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(db.String(1000), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    channel: Mapped[NotificationChannel] = relationship(
        'NotificationChannel', back_populates='deliveries'
    )
