from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.tenant import Tenant, TenantNamespace


class TenantAdvancedCapabilityStatus(StrEnum):
    PENDING = 'pending'
    READY = 'ready'
    DRIFTED = 'drifted'
    FAILED = 'failed'
    DISABLED = 'disabled'


class TenantAdvancedResourceKind(StrEnum):
    GLOBAL_RESOURCE_QUOTA = 'global_resource_quota'
    RESOURCE_POOL = 'resource_pool'
    RESOURCE_POOL_CLAIM = 'resource_pool_claim'
    TENANT_RESOURCE = 'tenant_resource'
    GLOBAL_TENANT_RESOURCE = 'global_tenant_resource'
    TENANT_CORDON = 'tenant_cordon'
    NAMESPACE_CONTROLS = 'namespace_controls'
    RESOURCE_RULES = 'resource_rules'
    CROSS_NAMESPACE_CREDENTIAL = 'cross_namespace_credential'


class TenantAdvancedCapabilityIntent(db.Model):
    __tablename__ = 'tenant_advanced_capability_intents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    tenant_namespace_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_namespaces.id', ondelete='CASCADE'), nullable=True
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False, default='capsule')
    capability_key: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(253), nullable=False)
    provider_api_version: Mapped[str] = mapped_column(String(40), nullable=False, default='v1beta2')
    desired_spec_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    effective_spec_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TenantAdvancedCapabilityStatus.PENDING.value
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    desired_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reconciliation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconciliation_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    tenant: Mapped[Tenant] = relationship('Tenant')
    namespace: Mapped[TenantNamespace | None] = relationship('TenantNamespace')

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_advanced_capability_intents_public_id'),
        UniqueConstraint('correlation_id', name='uq_tenant_advanced_capability_intents_correlation_id'),
        CheckConstraint("provider_key IN ('capsule')", name='ck_tenant_advanced_capability_intents_provider'),
        CheckConstraint(
            "resource_kind IN ("
            "'global_resource_quota', 'resource_pool', 'resource_pool_claim', 'tenant_resource', "
            "'global_tenant_resource', 'tenant_cordon', 'namespace_controls', 'resource_rules', "
            "'cross_namespace_credential')",
            name='ck_tenant_advanced_capability_intents_kind',
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'drifted', 'failed', 'disabled')",
            name='ck_tenant_advanced_capability_intents_status',
        ),
        CheckConstraint('generation >= 1', name='ck_tenant_advanced_capability_intents_generation'),
        Index('ix_tenant_advanced_capability_intents_tenant_status', 'tenant_id', 'status'),
        Index(
            'ix_tenant_advanced_capability_intents_capability',
            'tenant_id',
            'capability_key',
            'resource_kind',
        ),
    )
