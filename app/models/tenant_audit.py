from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.tenant import Tenant, TenantAccessGrant, TenantEnvironment, TenantNamespace
    from app.models.user import User


class TenantAuditCorrelationStatus(StrEnum):
    MATCHED = 'matched'
    UNMANAGED = 'unmanaged'
    AMBIGUOUS = 'ambiguous'


class TenantAuditPrincipalKind(StrEnum):
    SERVICE_ACCOUNT = 'service_account'
    USER = 'user'
    UNKNOWN = 'unknown'


class TenantAuditEvidence(db.Model):
    __tablename__ = 'tenant_audit_evidence'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True)
    tenant_environment_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='SET NULL'), nullable=True
    )
    tenant_namespace_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_namespaces.id', ondelete='SET NULL'), nullable=True
    )
    access_grant_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_access_grants.id', ondelete='SET NULL'), nullable=True
    )
    credential_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_credentials.id', ondelete='SET NULL'), nullable=True
    )
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, default='kubernetes_audit')
    source_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    principal_username: Mapped[str] = mapped_column(String(500), nullable=False)
    principal_groups_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    principal_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    identity_class: Mapped[str] = mapped_column(String(30), nullable=False)
    correlation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    credential_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    credential_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    jumpserver_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    resource_group: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subresource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(253), nullable=True)
    kubernetes_namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    verb: Mapped[str] = mapped_column(String(40), nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(80), nullable=False, default='tenant_audit_evidence')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    cluster: Mapped[Cluster] = relationship('Cluster')
    tenant: Mapped[Tenant | None] = relationship('Tenant')
    environment: Mapped[TenantEnvironment | None] = relationship('TenantEnvironment')
    namespace: Mapped[TenantNamespace | None] = relationship('TenantNamespace')
    access_grant: Mapped[TenantAccessGrant | None] = relationship('TenantAccessGrant')
    owner_user: Mapped[User | None] = relationship('User')

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_audit_evidence_public_id'),
        UniqueConstraint('cluster_id', 'idempotency_key', name='uq_tenant_audit_evidence_cluster_idempotency'),
        CheckConstraint(
            "source_kind IN ('kubernetes_audit')",
            name='ck_tenant_audit_evidence_source_kind',
        ),
        CheckConstraint(
            "principal_kind IN ('service_account', 'user', 'unknown')",
            name='ck_tenant_audit_evidence_principal_kind',
        ),
        CheckConstraint(
            "identity_class IN ('human', 'admin', 'cicd', 'group', 'unmanaged', 'ambiguous')",
            name='ck_tenant_audit_evidence_identity_class',
        ),
        CheckConstraint(
            "correlation_status IN ('matched', 'unmanaged', 'ambiguous')",
            name='ck_tenant_audit_evidence_correlation_status',
        ),
        CheckConstraint(
            "outcome IN ('success', 'failure', 'unknown')",
            name='ck_tenant_audit_evidence_outcome',
        ),
        Index('ix_tenant_audit_evidence_tenant_event', 'tenant_id', 'event_at'),
        Index('ix_tenant_audit_evidence_namespace_event', 'tenant_namespace_id', 'event_at'),
        Index('ix_tenant_audit_evidence_credential_event', 'credential_id', 'event_at'),
        Index('ix_tenant_audit_evidence_correlation_event', 'correlation_status', 'event_at'),
    )
