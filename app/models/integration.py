from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.alertmanager import AlertmanagerInstance
    from app.models.minio import MinioInstance
    from app.models.prometheus import PrometheusInstance


class IntegrationInstance(db.Model):
    """Canonical identity and lifecycle record for every external runtime."""

    __tablename__ = 'integration_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, default='active')
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    health_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    bindings: Mapped[list[IntegrationBinding]] = relationship(
        'IntegrationBinding',
        back_populates='instance',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='IntegrationBinding.priority.asc(), IntegrationBinding.id.asc()',
    )

    prometheus_record: Mapped[PrometheusInstance | None] = relationship(
        'PrometheusInstance',
        back_populates='integration_instance',
        uselist=False,
        passive_deletes=True,
    )
    alertmanager_record: Mapped[AlertmanagerInstance | None] = relationship(
        'AlertmanagerInstance',
        back_populates='integration_instance',
        uselist=False,
        passive_deletes=True,
    )
    minio_record: Mapped[MinioInstance | None] = relationship(
        'MinioInstance',
        back_populates='integration_instance',
        uselist=False,
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint('provider_type', 'name', name='uq_integration_instance_provider_name'),
        Index('ix_integration_instances_provider_enabled', 'provider_type', 'enabled'),
        Index('ix_integration_instances_readiness', 'provider_type', 'readiness_status'),
    )


class IntegrationBinding(db.Model):
    """Provider-neutral mapping between an integration runtime and an asset."""

    __tablename__ = 'integration_bindings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=False
    )
    asset_type: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_key: Mapped[str] = mapped_column(String(255), nullable=False)
    binding_role: Mapped[str] = mapped_column(String(30), nullable=False, default='primary')
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    capability_scope: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    selector_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    routing_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    validation_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', back_populates='bindings')

    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id',
            'asset_type',
            'asset_key',
            'binding_role',
            name='uq_integration_binding_instance_asset_role',
        ),
        Index('ix_integration_bindings_asset', 'asset_type', 'asset_key', 'enabled'),
        Index('ix_integration_bindings_provider_role', 'integration_instance_id', 'binding_role'),
        Index('ix_integration_bindings_validation', 'asset_type', 'validation_status'),
    )
