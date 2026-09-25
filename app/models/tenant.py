from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from app.models.user import User


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


class TenantMembershipPrincipalType(StrEnum):
    USER = 'user'
    GROUP = 'group'


class TenantMembershipStatus(StrEnum):
    ACTIVE = 'active'
    REVOKED = 'revoked'


class TenantAccessProfileKey(StrEnum):
    VIEWER = 'viewer'
    OPERATOR = 'operator'
    TENANT_ADMIN = 'tenant_admin'
    DEPLOYER = 'deployer'


class TenantAccessScope(StrEnum):
    TENANT = 'tenant'
    ENVIRONMENT = 'environment'
    NAMESPACE = 'namespace'


class TenantAccessGrantStatus(StrEnum):
    ACTIVE = 'active'
    REVOKED = 'revoked'


class TenantAccessReconciliationStatus(StrEnum):
    PENDING = 'pending'
    READY = 'ready'
    DRIFTED = 'drifted'
    FAILED = 'failed'
    REVOKED = 'revoked'


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
    groups: Mapped[list[TenantGroup]] = relationship(
        'TenantGroup', back_populates='tenant', cascade='all, delete-orphan', passive_deletes=True
    )
    memberships: Mapped[list[TenantMembership]] = relationship(
        'TenantMembership', back_populates='tenant', cascade='all, delete-orphan', passive_deletes=True
    )
    access_grants: Mapped[list[TenantAccessGrant]] = relationship(
        'TenantAccessGrant', back_populates='tenant', cascade='all, delete-orphan', passive_deletes=True
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
    access_grants: Mapped[list[TenantAccessGrant]] = relationship(
        'TenantAccessGrant', back_populates='environment', passive_deletes=True
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
    access_grants: Mapped[list[TenantAccessGrant]] = relationship(
        'TenantAccessGrant', back_populates='namespace', passive_deletes=True
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



class TenantGroup(db.Model):
    __tablename__ = 'tenant_groups'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(253), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    tenant: Mapped[Tenant] = relationship('Tenant', back_populates='groups')
    memberships: Mapped[list[TenantMembership]] = relationship(
        'TenantMembership', back_populates='group', passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_groups_public_id'),
        UniqueConstraint('correlation_id', name='uq_tenant_groups_correlation_id'),
        UniqueConstraint('tenant_id', 'slug', name='uq_tenant_groups_tenant_slug'),
        Index('ix_tenant_groups_tenant_enabled', 'tenant_id', 'enabled'),
    )


class TenantMembership(db.Model):
    __tablename__ = 'tenant_memberships'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('tenant_groups.id', ondelete='RESTRICT'), nullable=True)
    subject_name: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TenantMembershipStatus.ACTIVE.value)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    tenant: Mapped[Tenant] = relationship('Tenant', back_populates='memberships')
    user: Mapped[User | None] = relationship('User')
    group: Mapped[TenantGroup | None] = relationship('TenantGroup', back_populates='memberships')
    access_grants: Mapped[list[TenantAccessGrant]] = relationship(
        'TenantAccessGrant', back_populates='membership', cascade='all, delete-orphan', passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint('correlation_id', name='uq_tenant_memberships_correlation_id'),
        UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_memberships_tenant_user'),
        UniqueConstraint('tenant_id', 'group_id', name='uq_tenant_memberships_tenant_group'),
        CheckConstraint(
            "principal_type IN ('user', 'group')",
            name='ck_tenant_memberships_principal_type',
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name='ck_tenant_memberships_status',
        ),
        CheckConstraint(
            "((principal_type = 'user' AND user_id IS NOT NULL AND group_id IS NULL) "
            "OR (principal_type = 'group' AND group_id IS NOT NULL AND user_id IS NULL))",
            name='ck_tenant_memberships_principal_reference',
        ),
        Index('ix_tenant_memberships_tenant_status', 'tenant_id', 'status'),
    )


class TenantAccessGrant(db.Model):
    __tablename__ = 'tenant_access_grants'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    membership_id: Mapped[int] = mapped_column(ForeignKey('tenant_memberships.id', ondelete='CASCADE'), nullable=False)
    tenant_environment_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='CASCADE'), nullable=True
    )
    tenant_namespace_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_namespaces.id', ondelete='CASCADE'), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    access_profile: Mapped[str] = mapped_column(String(30), nullable=False)
    access_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TenantAccessGrantStatus.ACTIVE.value)
    reconciliation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantAccessReconciliationStatus.PENDING.value
    )
    reconciliation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reconciliation_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    tenant: Mapped[Tenant] = relationship('Tenant', back_populates='access_grants')
    membership: Mapped[TenantMembership] = relationship('TenantMembership', back_populates='access_grants')
    environment: Mapped[TenantEnvironment | None] = relationship(
        'TenantEnvironment', back_populates='access_grants'
    )
    namespace: Mapped[TenantNamespace | None] = relationship('TenantNamespace', back_populates='access_grants')

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_access_grants_public_id'),
        UniqueConstraint('correlation_id', name='uq_tenant_access_grants_correlation_id'),
        CheckConstraint(
            "scope_type IN ('tenant', 'environment', 'namespace')",
            name='ck_tenant_access_grants_scope_type',
        ),
        CheckConstraint(
            "access_profile IN ('viewer', 'operator', 'tenant_admin', 'deployer')",
            name='ck_tenant_access_grants_profile',
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name='ck_tenant_access_grants_status',
        ),
        CheckConstraint(
            "reconciliation_status IN ('pending', 'ready', 'drifted', 'failed', 'revoked')",
            name='ck_tenant_access_grants_reconciliation_status',
        ),
        CheckConstraint(
            "((scope_type = 'tenant' AND tenant_environment_id IS NULL AND tenant_namespace_id IS NULL) "
            "OR (scope_type = 'environment' AND tenant_environment_id IS NOT NULL AND tenant_namespace_id IS NULL) "
            "OR (scope_type = 'namespace' AND tenant_environment_id IS NULL AND tenant_namespace_id IS NOT NULL))",
            name='ck_tenant_access_grants_scope_reference',
        ),
        Index('ix_tenant_access_grants_tenant_status', 'tenant_id', 'status'),
        Index('ix_tenant_access_grants_membership', 'membership_id', 'scope_type'),
        Index('ix_tenant_access_grants_reconciliation', 'tenant_id', 'reconciliation_status'),
    )
