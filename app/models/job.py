from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class JobExecution(db.Model):
    """Canonical lifecycle record for every asynchronous KAORI operation."""

    __tablename__ = 'job_executions'
    __table_args__ = (
        Index('ix_job_executions_status_queue', 'status', 'queue_name'),
        Index('ix_job_executions_type_created', 'job_type', 'created_at'),
        Index('ix_job_executions_resource_status', 'resource_group', 'status'),
        Index('ix_job_executions_requester_status', 'requested_by_user_id', 'status'),
        Index('ix_job_executions_deduplication', 'deduplication_key'),
        Index('ix_job_executions_retention_boundary', 'status', 'workload_class', 'completed_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        db.String(36), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    job_type: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    workload_class: Mapped[str] = mapped_column(db.String(40), nullable=False, default='standard', index=True)
    queue_name: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(db.Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(db.String(30), nullable=False, default='queued', index=True)

    requested_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    provider_type: Mapped[str | None] = mapped_column(db.String(80), nullable=True, index=True)
    provider_instance_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True, index=True)
    scope_type: Mapped[str | None] = mapped_column(db.String(80), nullable=True, index=True)
    scope_key: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    resource_group: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)

    deduplication_key: Mapped[str] = mapped_column(db.String(255), nullable=False)
    # PostgreSQL permits multiple NULL values in a unique column. Active jobs keep
    # this value populated; terminal jobs clear it, which gives us a database-level
    # multi-process deduplication guard without blocking historical rows.
    active_deduplication_key: Mapped[str | None] = mapped_column(
        db.String(255), nullable=True, unique=True
    )
    parameter_fingerprint: Mapped[str] = mapped_column(db.String(64), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)

    celery_task_id: Mapped[str | None] = mapped_column(db.String(64), nullable=True, unique=True, index=True)
    parent_job_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('job_executions.id', ondelete='SET NULL'), nullable=True, index=True
    )

    progress_current: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(db.String(255), nullable=True)

    attempt_count: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(db.Integer, nullable=False, default=3)
    error_code: Mapped[str | None] = mapped_column(db.String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    result_type: Mapped[str | None] = mapped_column(db.String(80), nullable=True)
    result_reference: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)

    queued_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    requested_by: Mapped[User | None] = relationship('User', foreign_keys=[requested_by_user_id])
    parent: Mapped[JobExecution | None] = relationship(
        'JobExecution', remote_side='JobExecution.id', back_populates='children'
    )
    children: Mapped[list[JobExecution]] = relationship('JobExecution', back_populates='parent')
    subscribers: Mapped[list[JobExecutionSubscriber]] = relationship(
        'JobExecutionSubscriber', back_populates='job', cascade='all, delete-orphan',
        passive_deletes=True
    )

    @property
    def is_active(self) -> bool:
        return self.status in {'queued', 'running', 'retrying', 'cancel_requested'}

    @property
    def is_terminal(self) -> bool:
        return self.status in {'succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired'}


class JobExecutionSubscriber(db.Model):
    """Users observing one shared job execution."""

    __tablename__ = 'job_execution_subscribers'
    __table_args__ = (
        UniqueConstraint('job_execution_id', 'user_id', name='uq_job_execution_subscriber'),
        Index('ix_job_execution_subscribers_user', 'user_id', 'subscribed_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_execution_id: Mapped[int] = mapped_column(
        db.ForeignKey('job_executions.id', ondelete='CASCADE'), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True
    )
    notify_on_completion: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    subscribed_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    job: Mapped[JobExecution] = relationship('JobExecution', back_populates='subscribers')
    user: Mapped[User] = relationship('User')
