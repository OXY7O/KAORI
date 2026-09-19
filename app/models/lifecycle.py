from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class DataLifecyclePolicy(db.Model):
    """Persistent retention and archive policy for one KAORI data domain."""

    __tablename__ = 'data_lifecycle_policies'
    __table_args__ = (Index('ix_data_lifecycle_policies_enabled_domain', 'enabled', 'domain'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(db.String(80), nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    hot_retention_days: Mapped[int] = mapped_column(db.Integer, nullable=False, default=90)
    archive_retention_days: Mapped[int] = mapped_column(db.Integer, nullable=False, default=365)
    batch_size: Mapped[int] = mapped_column(db.Integer, nullable=False, default=5000)
    operation_mode: Mapped[str] = mapped_column(db.String(32), nullable=False, default='archive_and_cleanup')
    schedule_enabled: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    schedule_hour: Mapped[int] = mapped_column(db.Integer, nullable=False, default=2)
    schedule_minute: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    protect_unreviewed: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    protected_max_days: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    settings_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
