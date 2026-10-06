from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.tenant import Tenant, TenantEnvironment, TenantNamespace


class TenantDomainMatchMode(StrEnum):
    EXACT = 'exact'
    WILDCARD = 'wildcard'
    REGEX = 'regex'


class TenantDomainReservationStatus(StrEnum):
    ACTIVE = 'active'
    REVOKED = 'revoked'


class TenantExposurePolicyStatus(StrEnum):
    ACTIVE = 'active'
    DISABLED = 'disabled'


class TenantDomainReservation(db.Model):
    __tablename__ = 'tenant_domain_reservations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    tenant_environment_id: Mapped[int] = mapped_column(
        ForeignKey('tenant_environments.id', ondelete='CASCADE'), nullable=False
    )
    hostname_pattern: Mapped[str] = mapped_column(String(253), nullable=False)
    match_mode: Mapped[str] = mapped_column(String(20), nullable=False, default=TenantDomainMatchMode.EXACT.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TenantDomainReservationStatus.ACTIVE.value)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    tenant: Mapped[Tenant] = relationship('Tenant')
    environment: Mapped[TenantEnvironment] = relationship('TenantEnvironment')

    __table_args__ = (
        UniqueConstraint('public_id', name='uq_tenant_domain_reservations_public_id'),
        UniqueConstraint('correlation_id', name='uq_tenant_domain_reservations_correlation_id'),
        UniqueConstraint(
            'tenant_environment_id',
            'hostname_pattern',
            'match_mode',
            name='uq_tenant_domain_reservations_environment_pattern',
        ),
        CheckConstraint(
            "match_mode IN ('exact', 'wildcard', 'regex')",
            name='ck_tenant_domain_reservations_match_mode',
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name='ck_tenant_domain_reservations_status',
        ),
        Index('ix_tenant_domain_reservations_tenant_status', 'tenant_id', 'status'),
        Index('ix_tenant_domain_reservations_environment', 'tenant_environment_id', 'status'),
    )


class TenantExposurePolicy(db.Model):
    __tablename__ = 'tenant_exposure_policies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    tenant_namespace_id: Mapped[int] = mapped_column(
        ForeignKey('tenant_namespaces.id', ondelete='CASCADE'), nullable=False
    )
    profile_key: Mapped[str] = mapped_column(String(40), nullable=False, default='ingress_only')
    allow_cluster_ip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_ingress: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_node_port: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_load_balancer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_external_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TenantExposurePolicyStatus.ACTIVE.value)
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
        UniqueConstraint('public_id', name='uq_tenant_exposure_policies_public_id'),
        UniqueConstraint('correlation_id', name='uq_tenant_exposure_policies_correlation_id'),
        UniqueConstraint('tenant_namespace_id', name='uq_tenant_exposure_policies_namespace'),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name='ck_tenant_exposure_policies_status',
        ),
        Index('ix_tenant_exposure_policies_tenant_status', 'tenant_id', 'status'),
    )
