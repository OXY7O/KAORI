from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.security.credentials import EncryptedText

if TYPE_CHECKING:
    from app.models.object_storage import ObjectStorageSystem


def _minio_identity(name: str) -> IntegrationInstance:
    identity = IntegrationInstance()
    identity.integration_type = 'object_storage'
    identity.provider_key = 'minio'
    identity.adapter_key = 's3'
    identity.name = name
    identity.enabled = True
    identity.readiness_status = 'validation_required'
    return identity


class MinioInstance(db.Model):
    """MinIO S3 API connection backed by canonical IntegrationInstance identity."""

    __tablename__ = 'minio_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    object_storage_system_id: Mapped[str] = mapped_column(
        ForeignKey('object_storage_systems.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    access_key: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_key: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    region: Mapped[str] = mapped_column(String(80), nullable=False, default='us-east-1')
    addressing_style: Mapped[str] = mapped_column(String(20), nullable=False, default='path')
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    declared_release: Mapped[str] = mapped_column(String(96), nullable=False)
    detected_product: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observed_server_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deployment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    validation_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', lazy='joined')
    object_storage_system: Mapped[ObjectStorageSystem] = relationship('ObjectStorageSystem', lazy='joined')

    name: AssociationProxy[str] = association_proxy(
        'integration_instance',
        'name',
        creator=_minio_identity,
    )
    provider_key: AssociationProxy[str] = association_proxy('integration_instance', 'provider_key')
    adapter_key: AssociationProxy[str] = association_proxy('integration_instance', 'adapter_key')
    description: AssociationProxy[str | None] = association_proxy('integration_instance', 'description')
    environment: AssociationProxy[str | None] = association_proxy('integration_instance', 'environment')
    enabled: AssociationProxy[bool] = association_proxy('integration_instance', 'enabled')
    readiness_status: AssociationProxy[str | None] = association_proxy('integration_instance', 'readiness_status')
    last_status: AssociationProxy[str | None] = association_proxy('integration_instance', 'health_status')
    last_error: AssociationProxy[str | None] = association_proxy('integration_instance', 'last_error')
    last_checked_at: AssociationProxy[datetime | None] = association_proxy(
        'integration_instance',
        'last_checked_at',
    )
