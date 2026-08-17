from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.security.credentials import EncryptedText


def _prometheus_identity(name: str) -> IntegrationInstance:
    identity = IntegrationInstance()
    identity.provider_type = 'prometheus'
    identity.name = name
    identity.enabled = True
    identity.readiness_status = 'validation_required'
    return identity


class PrometheusInstance(db.Model):
    """Prometheus-specific connection record backed by IntegrationInstance identity."""

    __tablename__ = 'prometheus_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default='prometheus')
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default='none')
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    bearer_token: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version_detection_mode: Mapped[str] = mapped_column(String(20), nullable=False, default='automatic')
    endpoint_product: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_prometheus_major: Mapped[str | None] = mapped_column(String(8), nullable=True)
    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    query_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    query_validation_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    query_validation_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    retention_validation_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    module_readiness: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    last_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    integration_instance: Mapped[IntegrationInstance] = relationship(
        'IntegrationInstance',
        back_populates='prometheus_record',
        lazy='joined',
    )

    name: AssociationProxy[str] = association_proxy(
        'integration_instance',
        'name',
        creator=_prometheus_identity,
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
