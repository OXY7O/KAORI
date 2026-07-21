from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.security.credentials import EncryptedText

if TYPE_CHECKING:
    from app.models.integration import IntegrationInstance


class PrometheusInstance(db.Model):
    """Canonical provider record for a Prometheus-compatible runtime."""

    __tablename__ = 'prometheus_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default='none')
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    bearer_token: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version_detection_mode: Mapped[str] = mapped_column(String(20), nullable=False, default='automatic')
    endpoint_product: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_prometheus_major: Mapped[str | None] = mapped_column(String(8), nullable=True)
    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    query_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    query_validation_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    query_validation_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    retention_validation_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    module_readiness: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance')
