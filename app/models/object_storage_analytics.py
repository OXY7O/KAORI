from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class ObjectStorageAnalyticsSnapshot(db.Model):
    """Persistent Object Storage operational analytics produced by the analytics worker."""

    __tablename__ = 'object_storage_analytics_snapshots'
    __table_args__ = (
        UniqueConstraint(
            'object_storage_system_id',
            'time_range',
            name='uq_object_storage_analytics_scope',
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name='ck_object_storage_analytics_status',
        ),
        Index(
            'ix_object_storage_analytics_lookup',
            'object_storage_system_id',
            'time_range',
        ),
        Index('ix_object_storage_analytics_freshness', 'status', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    object_storage_system_id: Mapped[str] = mapped_column(
        ForeignKey('object_storage_systems.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    time_range: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending', index=True)
    generated_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    freshness_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=15)
    stale_grace_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=1440)
    last_attempt_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    last_job_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey('job_executions.id', ondelete='SET NULL'),
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

    object_storage_system = relationship('ObjectStorageSystem')
    last_job_execution = relationship('JobExecution', foreign_keys=[last_job_execution_id])


class ObjectStorageForecastSnapshot(db.Model):
    """Persistent Object Storage forecast produced by the forecasting worker."""

    __tablename__ = 'object_storage_forecast_snapshots'
    __table_args__ = (
        UniqueConstraint(
            'object_storage_system_id',
            'history_window',
            'method',
            name='uq_object_storage_forecast_scope',
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name='ck_object_storage_forecast_status',
        ),
        Index(
            'ix_object_storage_forecast_lookup',
            'object_storage_system_id',
            'history_window',
            'method',
        ),
        Index('ix_object_storage_forecast_freshness', 'status', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    object_storage_system_id: Mapped[str] = mapped_column(
        ForeignKey('object_storage_systems.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    history_window: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False, default='linear-v1')
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending', index=True)
    generated_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    freshness_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=120)
    stale_grace_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=4320)
    last_attempt_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    last_job_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey('job_executions.id', ondelete='SET NULL'),
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

    object_storage_system = relationship('ObjectStorageSystem')
    last_job_execution = relationship('JobExecution', foreign_keys=[last_job_execution_id])
