from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.tenant import Tenant, TenantNamespace


class TenantManagedResourceKind(StrEnum):
    TLS = 'tls'
    REGISTRY = 'registry'


class TenantManagedResourceMode(StrEnum):
    PLATFORM_TLS = 'platform_tls'
    NAMESPACE_TLS_COMPAT = 'namespace_tls_compat'
    IMAGE_PULL_SECRET = 'image_pull_secret'
    EXTERNAL_CREDENTIAL_PROVIDER = 'external_credential_provider'


class TenantManagedResourceStatus(StrEnum):
    PENDING = 'pending'
    READY = 'ready'
    DRIFTED = 'drifted'
    FAILED = 'failed'
    DISABLED = 'disabled'


class TenantManagedResourceIntent(db.Model):
    __tablename__ = 'tenant_managed_resource_intents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    tenant_namespace_id: Mapped[int] = mapped_column(
        ForeignKey('tenant_namespaces.id', ondelete='CASCADE'), nullable=False
    )
    resource_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(253), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=TenantManagedResourceStatus.PENDING.value)
    rotation_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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
    namespace: Mapped[TenantNamespace] = relationship('TenantNamespace')

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_managed_resource_intents_public_id'),
        UniqueConstraint('correlation_id', name='uq_tenant_managed_resource_intents_correlation_id'),
        UniqueConstraint(
            'tenant_namespace_id',
            'resource_kind',
            name='uq_tenant_managed_resource_intents_namespace_kind',
        ),
        CheckConstraint(
            "resource_kind IN ('tls', 'registry')",
            name='ck_tenant_managed_resource_intents_kind',
        ),
        CheckConstraint(
            "mode IN ('platform_tls', 'namespace_tls_compat', 'image_pull_secret', 'external_credential_provider')",
            name='ck_tenant_managed_resource_intents_mode',
        ),
        CheckConstraint(
            "((resource_kind = 'tls' AND mode IN ('platform_tls', 'namespace_tls_compat')) "
            "OR (resource_kind = 'registry' AND mode IN ('image_pull_secret', 'external_credential_provider')))",
            name='ck_tenant_managed_resource_intents_kind_mode',
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'drifted', 'failed', 'disabled')",
            name='ck_tenant_managed_resource_intents_status',
        ),
        CheckConstraint('rotation_generation >= 1', name='ck_tenant_managed_resource_intents_generation'),
        Index(
            'ix_tenant_managed_resource_intents_tenant_status',
            'tenant_id',
            'status',
        ),
        Index(
            'ix_tenant_managed_resource_intents_namespace',
            'tenant_namespace_id',
            'resource_kind',
        ),
    )
