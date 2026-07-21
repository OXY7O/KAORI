from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.security.credentials import EncryptedText


def _alertmanager_identity(name: str) -> IntegrationInstance:
    return IntegrationInstance(
        provider_type='alertmanager',
        name=name,
        enabled=True,
        readiness_status='validation_required',
    )


class AlertmanagerInstance(db.Model):
    """Alertmanager-specific connection record backed by IntegrationInstance identity."""

    __tablename__ = 'alertmanager_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    deployment_type: Mapped[str] = mapped_column(String(40), nullable=False, default='external_managed')
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default='none')
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    bearer_token: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    integration_instance: Mapped[IntegrationInstance] = relationship(
        'IntegrationInstance',
        back_populates='alertmanager_record',
        lazy='joined',
    )

    name: AssociationProxy[str] = association_proxy(
        'integration_instance',
        'name',
        creator=_alertmanager_identity,
    )
    description: AssociationProxy[str | None] = association_proxy(
        'integration_instance',
        'description',
    )
    enabled: AssociationProxy[bool] = association_proxy(
        'integration_instance',
        'enabled',
    )
    readiness_status: AssociationProxy[str | None] = association_proxy(
        'integration_instance',
        'readiness_status',
    )
    last_status: AssociationProxy[str | None] = association_proxy(
        'integration_instance',
        'health_status',
    )
    last_error: AssociationProxy[str | None] = association_proxy(
        'integration_instance',
        'last_error',
    )
    last_checked_at: AssociationProxy[datetime | None] = association_proxy(
        'integration_instance',
        'last_checked_at',
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint)

    @property
    def is_connected(self) -> bool:
        return self.last_status == 'connected'

    @property
    def display_status(self) -> str:
        if not self.enabled:
            return 'Disabled'
        if not self.endpoint:
            return 'Not Configured'
        if self.last_status == 'connected':
            return 'Connected'
        if self.last_status == 'disconnected':
            return 'Disconnected'
        if self.last_status == 'error':
            return 'Error'
        if self.last_status == 'incompatible':
            return 'Incompatible'
        return 'Configured'
