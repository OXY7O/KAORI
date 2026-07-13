from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


ARCHIVE_STATUS_PENDING = 'pending'
ARCHIVE_STATUS_ARCHIVING = 'archiving'
ARCHIVE_STATUS_VERIFYING = 'verifying'
ARCHIVE_STATUS_CLEANING = 'cleaning'
ARCHIVE_STATUS_READY = 'ready'
ARCHIVE_STATUS_CLEANUP_PARTIAL = 'cleanup_partial'
ARCHIVE_STATUS_FAILED = 'failed'
ARCHIVE_STATUS_EXPIRED = 'expired'

ACTIVE_ARCHIVE_STATUSES = {
    ARCHIVE_STATUS_PENDING,
    ARCHIVE_STATUS_ARCHIVING,
    ARCHIVE_STATUS_VERIFYING,
    ARCHIVE_STATUS_CLEANING,
}


class ArchiveArtifact(db.Model):
    __tablename__ = 'archive_artifacts'
    __table_args__ = (
        Index('ix_archive_artifacts_domain_status_created', 'domain', 'status', 'created_at'),
        Index('ix_archive_artifacts_domain_completed', 'domain', 'completed_at'),
    )

    id: Mapped[str] = mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    domain: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    source_model: Mapped[str] = mapped_column(db.String(120), nullable=False)
    trigger_type: Mapped[str] = mapped_column(db.String(24), nullable=False, index=True)
    operation_mode: Mapped[str] = mapped_column(db.String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        db.String(32),
        nullable=False,
        default=ARCHIVE_STATUS_PENDING,
        index=True,
    )
    schema_version: Mapped[int] = mapped_column(db.Integer, nullable=False, default=1)
    archive_format: Mapped[str] = mapped_column(db.String(24), nullable=False, default='jsonl')
    compression: Mapped[str] = mapped_column(db.String(24), nullable=False, default='gzip')

    cutoff_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    range_start: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    boundary_record_id: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    record_count: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0)
    cleanup_deleted_count: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0)

    storage_backend: Mapped[str | None] = mapped_column(db.String(24), nullable=True, index=True)
    data_object_key: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)
    manifest_object_key: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)
    data_uri: Mapped[str | None] = mapped_column(db.String(1100), nullable=True)
    manifest_uri: Mapped[str | None] = mapped_column(db.String(1100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    manifest_size_bytes: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(db.String(64), nullable=True, index=True)
    manifest_checksum_sha256: Mapped[str | None] = mapped_column(db.String(64), nullable=True)

    triggered_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    celery_task_id: Mapped[str | None] = mapped_column(db.String(64), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    cleanup_completed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    purged_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    @property
    def is_downloadable(self) -> bool:
        return self.status in {ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL} and bool(
            self.data_object_key and self.manifest_object_key
        )

    @property
    def is_verifiable(self) -> bool:
        return self.status in {
            ARCHIVE_STATUS_READY,
            ARCHIVE_STATUS_CLEANUP_PARTIAL,
            ARCHIVE_STATUS_FAILED,
        } and bool(
            self.data_object_key
            and self.manifest_object_key
            and self.checksum_sha256
            and self.manifest_checksum_sha256
        )
