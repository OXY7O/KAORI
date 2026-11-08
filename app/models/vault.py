from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.security.credentials import EncryptedText


def _vault_identity(name: str) -> IntegrationInstance:
    identity = IntegrationInstance()
    identity.integration_type = 'secrets_pki'
    identity.provider_key = 'vault'
    identity.adapter_key = 'vault_http_v1'
    identity.name = name
    identity.enabled = True
    identity.readiness_status = 'validation_required'
    return identity


class VaultInstance(db.Model):
    """Vault provider connection. Only the AppRole SecretID is persisted encrypted."""

    __tablename__ = 'vault_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_mount: Mapped[str] = mapped_column(String(160), nullable=False, default='approle')
    role_id: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_id: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    kv2_mounts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    pki_mounts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    pki_stored_certs_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', lazy='joined')
    name: AssociationProxy[str] = association_proxy('integration_instance', 'name', creator=_vault_identity)
    provider_key: AssociationProxy[str] = association_proxy('integration_instance', 'provider_key')
    adapter_key: AssociationProxy[str] = association_proxy('integration_instance', 'adapter_key')
    environment: AssociationProxy[str | None] = association_proxy('integration_instance', 'environment')
    description: AssociationProxy[str | None] = association_proxy('integration_instance', 'description')
    enabled: AssociationProxy[bool] = association_proxy('integration_instance', 'enabled')
    readiness_status: AssociationProxy[str | None] = association_proxy('integration_instance', 'readiness_status')
    last_status: AssociationProxy[str | None] = association_proxy('integration_instance', 'health_status')
    last_error: AssociationProxy[str | None] = association_proxy('integration_instance', 'last_error')
    last_checked_at: AssociationProxy[datetime | None] = association_proxy('integration_instance', 'last_checked_at')
