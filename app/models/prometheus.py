from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster


class PrometheusConfig(db.Model):
    __tablename__ = 'prometheus_configs'

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
    )

    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    auth_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='none',
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    bearer_token: Mapped[str | None] = mapped_column(
        String(4096),
        nullable=True,
    )

    timeout: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )

    verify_ssl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


    version_detection_mode: Mapped[str] = mapped_column(String(20), nullable=False, default='automatic')
    endpoint_product: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_prometheus_major: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Endpoint identity. In automatic mode this is Prometheus; in manual mode
    # it is the intermediary runtime (currently Thanos Query).
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    cluster: Mapped[Cluster] = relationship(
        'Cluster',
        back_populates='prometheus_config',
    )

    def __repr__(self) -> str:
        return f'<PrometheusConfig cluster_id={self.cluster_id} endpoint={self.endpoint}>'

class PrometheusInstance(db.Model):
    """Standalone Prometheus-compatible runtime managed independently from assets."""

    __tablename__ = 'prometheus_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int | None] = mapped_column(ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default='none')
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    bearer_token: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    bindings: Mapped[list[PrometheusBinding]] = relationship(
        'PrometheusBinding', back_populates='instance', cascade='all, delete-orphan', passive_deletes=True,
        order_by='PrometheusBinding.priority.asc(), PrometheusBinding.id.asc()'
    )


class PrometheusBinding(db.Model):
    """Maps a standalone Prometheus runtime to an asset or operational scope."""

    __tablename__ = 'prometheus_bindings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prometheus_instance_id: Mapped[int] = mapped_column(ForeignKey('prometheus_instances.id', ondelete='CASCADE'), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    binding_role: Mapped[str] = mapped_column(String(30), nullable=False, default='primary')
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    instance: Mapped[PrometheusInstance] = relationship('PrometheusInstance', back_populates='bindings')

    __table_args__ = (
        db.UniqueConstraint('prometheus_instance_id', 'scope_type', 'scope_key', name='uq_prometheus_binding_instance_scope'),
        db.Index('ix_prometheus_bindings_scope', 'scope_type', 'scope_key', 'enabled'),
    )
