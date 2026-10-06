from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class AnalyticsSnapshot(db.Model):
    """Persistent, shareable analytics result produced by background workers."""

    __tablename__ = 'analytics_snapshots'
    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'dataset_key',
            'parameter_fingerprint',
            name='uq_analytics_snapshot_scope',
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name='ck_analytics_snapshot_status',
        ),
        Index('ix_analytics_snapshots_lookup', 'cluster_id', 'dataset_key', 'parameter_fingerprint'),
        Index('ix_analytics_snapshots_freshness', 'status', 'expires_at'),
        Index('ix_analytics_snapshots_dataset_generated', 'dataset_key', 'generated_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[str] = mapped_column(
        db.String(36),
        db.ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    dataset_key: Mapped[str] = mapped_column(db.String(120), nullable=False)
    parameter_fingerprint: Mapped[str] = mapped_column(db.String(64), nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False, default='pending', index=True)
    generated_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    freshness_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=20)
    stale_grace_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=1440)
    last_attempt_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    last_job_execution_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('job_executions.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    cluster = relationship('Cluster')
    last_job_execution = relationship('JobExecution', foreign_keys=[last_job_execution_id])
