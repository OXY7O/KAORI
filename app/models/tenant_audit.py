from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class TenantKubernetesAuditObservation(db.Model):
    __tablename__ = 'tenant_kubernetes_audit_observations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    username: Mapped[str] = mapped_column(String(253), nullable=False)
    principal_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    service_account_namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    service_account_name: Mapped[str | None] = mapped_column(String(253), nullable=True)

    verb: Mapped[str] = mapped_column(String(64), nullable=False)
    api_group: Mapped[str | None] = mapped_column(String(253), nullable=True)
    api_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource: Mapped[str | None] = mapped_column(String(253), nullable=True)
    subresource: Mapped[str | None] = mapped_column(String(253), nullable=True)
    namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(253), nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)

    correlation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True)
    tenant_environment_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='SET NULL'), nullable=True
    )
    tenant_namespace_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_namespaces.id', ondelete='SET NULL'), nullable=True
    )
    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_memberships.id', ondelete='SET NULL'), nullable=True
    )
    access_grant_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_access_grants.id', ondelete='SET NULL'), nullable=True
    )
    credential_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenant_credentials.id', ondelete='SET NULL'), nullable=True
    )
    correlation_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint('event_uid', name='uq_tenant_kubernetes_audit_observations_event_uid'),
        CheckConstraint(
            "principal_kind IN ('service_account', 'user', 'group', 'unknown')",
            name='ck_tenant_kubernetes_audit_observations_principal_kind',
        ),
        CheckConstraint(
            "outcome IN ('success', 'failed', 'unknown')",
            name='ck_tenant_kubernetes_audit_observations_outcome',
        ),
        CheckConstraint(
            "correlation_status IN ('managed', 'managed_revoked', 'unmanaged', 'ambiguous')",
            name='ck_tenant_kubernetes_audit_observations_correlation_status',
        ),
        Index(
            'ix_tenant_kubernetes_audit_observations_scope_time',
            'cluster_id',
            'namespace',
            'occurred_at',
        ),
        Index(
            'ix_tenant_kubernetes_audit_observations_correlation',
            'correlation_status',
            'occurred_at',
        ),
        Index(
            'ix_tenant_kubernetes_audit_observations_retention',
            'expires_at',
        ),
    )
