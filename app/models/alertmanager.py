from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster


class AlertmanagerInstance(db.Model):
    """One externally managed Alertmanager deployment known to KAORI."""

    __tablename__ = 'alertmanager_instances'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int | None] = mapped_column(ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default='external_managed',
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default='none')
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    bearer_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    bindings: Mapped[list[AlertmanagerBinding]] = relationship(
        'AlertmanagerBinding',
        back_populates='instance',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='AlertmanagerBinding.priority.asc(), AlertmanagerBinding.id.asc()',
    )

    __table_args__ = (
        Index('ix_alertmanager_instances_readiness', 'readiness_status'),
        Index('ix_alertmanager_instances_status', 'last_status'),
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


class AlertmanagerBinding(db.Model):
    """Associates an Alertmanager instance with an asset or operational scope."""

    __tablename__ = 'alertmanager_bindings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alertmanager_instance_id: Mapped[int] = mapped_column(
        ForeignKey('alertmanager_instances.id', ondelete='CASCADE'),
        nullable=False,
    )
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    binding_role: Mapped[str] = mapped_column(String(30), nullable=False, default='primary')
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    instance: Mapped[AlertmanagerInstance] = relationship(
        'AlertmanagerInstance',
        back_populates='bindings',
    )

    __table_args__ = (
        UniqueConstraint(
            'alertmanager_instance_id',
            'scope_type',
            'scope_key',
            name='uq_alertmanager_binding_instance_scope',
        ),
        Index(
            'ix_alertmanager_bindings_scope',
            'scope_type',
            'scope_key',
            'enabled',
        ),
        Index(
            'ix_alertmanager_bindings_instance_role',
            'alertmanager_instance_id',
            'binding_role',
        ),
    )


class AlertmanagerConfig(db.Model):
    """Legacy cluster-scoped configuration kept during the compatibility window."""

    __tablename__ = 'alertmanager_configs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default='none')
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    bearer_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    cluster: Mapped[Cluster] = relationship('Cluster', back_populates='alertmanager_config')

    __table_args__ = (
        Index('ix_alertmanager_configs_cluster_status', 'cluster_id', 'last_status'),
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint)

    @property
    def is_connected(self) -> bool:
        return self.last_status == 'connected'

    @property
    def display_status(self) -> str:
        if not self.endpoint:
            return 'Not Configured'
        if self.last_status == 'connected':
            return 'Connected'
        if self.last_status == 'disconnected':
            return 'Disconnected'
        if self.last_status == 'error':
            return 'Error'
        return 'Configured'
