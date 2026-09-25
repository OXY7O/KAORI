from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class TenantLifecycleStatus(StrEnum):
    PENDING = 'pending'
    READY = 'ready'
    DEGRADED = 'degraded'
    DECOMMISSIONING = 'decommissioning'
    DECOMMISSIONED = 'decommissioned'


class TenantOwnershipStatus(StrEnum):
    MANAGED = 'managed'
    DISCOVERED = 'discovered'
    ADOPTED = 'adopted'


class TenantEnvironmentName(StrEnum):
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='RESTRICT'), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantLifecycleStatus.PENDING.value
    )
    ownership_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantOwnershipStatus.MANAGED.value
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_state: Mapped[str] = mapped_column(String(40), nullable=False)
    reconciliation_authority: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    provider_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    environments: Mapped[list[TenantEnvironment]] = relationship(
        'TenantEnvironment', back_populates='tenant', cascade='all, delete-orphan', passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint('cluster_id', 'slug', name='uq_tenants_cluster_slug'),
        UniqueConstraint('correlation_id', name='uq_tenants_correlation_id'),
        CheckConstraint("provider_key IN ('native_kubernetes', 'capsule')", name='ck_tenants_provider_key'),
        CheckConstraint(
            "provider_state IN ('native', 'capsule', 'capsule_degraded', 'native_recovery')",
            name='ck_tenants_provider_state',
        ),
        CheckConstraint("ownership_status IN ('managed', 'discovered', 'adopted')", name='ck_tenants_ownership_status'),
        CheckConstraint(
            "lifecycle_status IN ('pending', 'ready', 'degraded', 'decommissioning', 'decommissioned')",
            name='ck_tenants_lifecycle_status',
        ),
        Index('ix_tenants_cluster_lifecycle', 'cluster_id', 'lifecycle_status'),
        Index('ix_tenants_provider_state', 'provider_key', 'provider_state'),
    )


class TenantEnvironment(db.Model):
    __tablename__ = 'tenant_environments'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    tenant: Mapped[Tenant] = relationship('Tenant', back_populates='environments')
    namespaces: Mapped[list[TenantNamespace]] = relationship(
        'TenantNamespace', back_populates='environment', cascade='all, delete-orphan', passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint('tenant_id', 'environment', name='uq_tenant_environments_tenant_environment'),
        CheckConstraint(
            "environment IN ('development', 'staging', 'production')", name='ck_tenant_environments_environment'
        ),
    )


class TenantNamespace(db.Model):
    __tablename__ = 'tenant_namespaces'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_environment_id: Mapped[int] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='CASCADE'), nullable=False
    )
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='RESTRICT'), nullable=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    ownership_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantOwnershipStatus.MANAGED.value
    )
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    environment: Mapped[TenantEnvironment] = relationship('TenantEnvironment', back_populates='namespaces')

    __table_args__ = (
        UniqueConstraint('cluster_id', 'namespace', name='uq_tenant_namespaces_cluster_namespace'),
        UniqueConstraint('correlation_id', name='uq_tenant_namespaces_correlation_id'),
        CheckConstraint(
            "ownership_status IN ('managed', 'discovered', 'adopted')", name='ck_tenant_namespaces_ownership_status'
        ),
        Index('ix_tenant_namespaces_environment', 'tenant_environment_id', 'namespace'),
    )
