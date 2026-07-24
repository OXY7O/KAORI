from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class ResolverDeploymentPolicy(db.Model):
    __tablename__ = 'resolver_deployment_policies'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'action_key', name='uq_resolver_policy_cluster_action'),
        CheckConstraint("lifecycle_status IN ('active', 'disabled')", name='ck_resolver_policy_lifecycle'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False, index=True)
    action_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default='disabled', index=True)
    allowed_namespaces_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    required_registry_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class ResolverOperationalControl(db.Model):
    __tablename__ = 'resolver_operational_controls'
    __table_args__ = (
        CheckConstraint('concurrency_limit >= 1', name='ck_resolver_control_concurrency'),
        CheckConstraint('rate_limit_per_minute >= 1', name='ck_resolver_control_rate'),
        CheckConstraint('circuit_failure_threshold >= 1', name='ck_resolver_control_threshold'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=True, index=True)
    global_kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    circuit_failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    circuit_cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


Index(
    'uq_resolver_operational_control_scope',
    func.coalesce(ResolverOperationalControl.cluster_id, '__global__'),
    unique=True,
)


class ResolverProductionReadinessRecord(db.Model):
    __tablename__ = 'resolver_production_readiness'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'action_key', name='uq_resolver_readiness_cluster_action'),
        CheckConstraint(
            "rollout_stage IN ('disabled', 'shadow', 'non_production', 'canary', 'production')",
            name='ck_resolver_readiness_stage',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False, index=True)
    action_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rollout_stage: Mapped[str] = mapped_column(String(32), nullable=False, default='disabled', index=True)
    validation_results_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
