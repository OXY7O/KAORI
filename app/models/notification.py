from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Notification(db.Model):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        db.String(80),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default='info',
        index=True,
    )

    title: Mapped[str] = mapped_column(
        db.String(160),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
    )

    detail: Mapped[str | None] = mapped_column(
        db.Text,
        nullable=True,
    )

    action_url: Mapped[str | None] = mapped_column(
        db.String(500),
        nullable=True,
    )

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        db.JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
