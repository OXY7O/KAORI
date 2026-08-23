from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class AlertSignalSnapshot(db.Model):
    """Committed fast-path operational signal snapshot for Alert Intelligence.

    This table is intentionally separate from full inventory generations. It stores
    small, alert-oriented evidence collected by background workers at a tighter
    cadence so AlertCase state can recover quickly without accelerating the whole
    inventory synchronization pipeline.
    """

    __tablename__ = 'alert_signal_snapshots'
    __table_args__ = (
        UniqueConstraint('domain', 'asset_key', 'signal_key', name='uq_alert_signal_snapshot_scope'),
        CheckConstraint("status IN ('ready', 'failed')", name='ck_alert_signal_snapshot_status'),
        Index('ix_alert_signal_snapshot_lookup', 'domain', 'asset_key', 'signal_key'),
        Index('ix_alert_signal_snapshot_freshness', 'status', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(db.String(40), nullable=False, index=True)
    asset_key: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    signal_key: Mapped[str] = mapped_column(db.String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False, default='ready', index=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
