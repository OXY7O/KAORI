from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.security.credentials import EncryptedText

if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.integration import IntegrationInstance


class KubernetesConnection(db.Model):
    """Canonical Kubernetes API connection and credential record."""

    __tablename__ = 'kubernetes_connections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    kubeconfig: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_weak_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    server: Mapped[str | None] = mapped_column(String(500), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovery_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance')
    cluster: Mapped[Cluster] = relationship('Cluster', back_populates='kubernetes_connection')
