from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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


class TenantResourceProfileClass(StrEnum):
    SMALL = 'small'
    STANDARD = 'standard'
    LARGE = 'large'
    CUSTOM = 'custom'


class TenantNamespaceProvisioningStatus(StrEnum):
    PENDING = 'pending'
    READY = 'ready'
    DRIFTED = 'drifted'
    FAILED = 'failed'


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


class TenantResourceProfile(db.Model):
    __tablename__ = 'tenant_resource_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_class: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_preset_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    base_preset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quota_hard_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    limit_defaults_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    namespaces: Mapped[list[TenantNamespace]] = relationship('TenantNamespace', back_populates='resource_profile')

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_resource_profiles_public_id'),
        UniqueConstraint('name', name='uq_tenant_resource_profiles_name'),
        CheckConstraint(
            "profile_class IN ('small', 'standard', 'large', 'custom')",
            name='ck_tenant_resource_profiles_class',
        ),
        Index('ix_tenant_resource_profiles_class_enabled', 'profile_class', 'enabled'),
    )


class TenantCapacityPolicy(db.Model):
    __tablename__ = 'tenant_capacity_policies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    platform_reserve_cpu: Mapped[str] = mapped_column(String(50), nullable=False, default='0')
    platform_reserve_memory: Mapped[str] = mapped_column(String(50), nullable=False, default='0')
    safety_headroom_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmanaged_commitment_cpu: Mapped[str] = mapped_column(String(50), nullable=False, default='0')
    unmanaged_commitment_memory: Mapped[str] = mapped_column(String(50), nullable=False, default='0')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint('cluster_id', name='uq_tenant_capacity_policies_cluster'),
        CheckConstraint(
            'safety_headroom_percent >= 0 AND safety_headroom_percent < 100',
            name='ck_tenant_capacity_policies_headroom_percent',
        ),
        Index('ix_tenant_capacity_policies_cluster', 'cluster_id'),
    )


class TenantCapacityDecision(db.Model):
    __tablename__ = 'tenant_capacity_decisions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='RESTRICT'), nullable=False)
    tenant_environment_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='SET NULL'), nullable=True
    )
    resource_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_resource_profiles.id', ondelete='SET NULL'), nullable=True
    )
    resource_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity_state: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    data_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint('correlation_id', name='uq_tenant_capacity_decisions_correlation_id'),
        CheckConstraint(
            "operation IN ('create', 'increase', 'decrease', 'no_change')",
            name='ck_tenant_capacity_decisions_operation',
        ),
        CheckConstraint(
            "decision IN ('allow', 'block')",
            name='ck_tenant_capacity_decisions_decision',
        ),
        CheckConstraint(
            "capacity_state IN ('Healthy', 'Near Capacity', 'Critical', 'Exhausted', 'Overcommitted', 'Unknown')",
            name='ck_tenant_capacity_decisions_state',
        ),
        Index('ix_tenant_capacity_decisions_cluster_created', 'cluster_id', 'created_at'),
        Index('ix_tenant_capacity_decisions_result', 'decision', 'capacity_state'),
    )


class TenantNamespace(db.Model):
    __tablename__ = 'tenant_namespaces'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_environment_id: Mapped[int] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='CASCADE'), nullable=False
    )
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='RESTRICT'), nullable=False)
    resource_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_resource_profiles.id', ondelete='RESTRICT'), nullable=True
    )
    resource_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity_decision_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_capacity_decisions.id', ondelete='SET NULL'), nullable=True
    )
    allocation_quota_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    allocation_limit_defaults_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    allocation_customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    ownership_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantOwnershipStatus.MANAGED.value
    )
    provisioning_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantNamespaceProvisioningStatus.PENDING.value
    )
    provisioning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provisioning_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    environment: Mapped[TenantEnvironment] = relationship('TenantEnvironment', back_populates='namespaces')
    resource_profile: Mapped[TenantResourceProfile | None] = relationship(
        'TenantResourceProfile', back_populates='namespaces'
    )

    __table_args__ = (
        UniqueConstraint('cluster_id', 'namespace', name='uq_tenant_namespaces_cluster_namespace'),
        UniqueConstraint('correlation_id', name='uq_tenant_namespaces_correlation_id'),
        CheckConstraint(
            "ownership_status IN ('managed', 'discovered', 'adopted')", name='ck_tenant_namespaces_ownership_status'
        ),
        CheckConstraint(
            "provisioning_status IN ('pending', 'ready', 'drifted', 'failed')",
            name='ck_tenant_namespaces_provisioning_status',
        ),
        Index('ix_tenant_namespaces_environment', 'tenant_environment_id', 'namespace'),
        Index('ix_tenant_namespaces_capacity_decision', 'capacity_decision_id'),
        Index('ix_tenant_namespaces_provisioning', 'cluster_id', 'provisioning_status'),
    )
