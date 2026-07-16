from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.alertmanager import AlertmanagerConfig
    from app.models.prometheus import PrometheusConfig


class ClusterStatus(StrEnum):
    UNKNOWN = 'unknown'
    CONNECTED = 'connected'
    FAILED = 'failed'


class Cluster(db.Model):
    __tablename__ = 'clusters'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    environment: Mapped[str] = mapped_column(String(20), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    kubeconfig: Mapped[str] = mapped_column(Text, nullable=False)

    kube_verify_ssl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    kube_allow_weak_tls: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )


    secret_reveal_encryption_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    secret_reveal_audit_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    server: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ClusterStatus.UNKNOWN.value)

    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    kubernetes_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kubernetes_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kubernetes_compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kubernetes_compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kubernetes_lifecycle_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kubernetes_readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kubernetes_validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    kubernetes_last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    prometheus_config: Mapped[PrometheusConfig | None] = relationship(
        back_populates='cluster',
        uselist=False,
        cascade='all, delete-orphan',
    )

    alertmanager_config: Mapped[AlertmanagerConfig | None] = relationship(
        'AlertmanagerConfig',
        back_populates='cluster',
        cascade='all, delete-orphan',
        passive_deletes=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        return f'<Cluster {self.name}>'
