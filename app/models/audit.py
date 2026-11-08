from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    target_type: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(db.String(120), nullable=True, index=True)
    action: Mapped[str] = mapped_column(db.String(120), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(db.String(255), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    if TYPE_CHECKING:
        # SQLAlchemy supplies this constructor at runtime. The declaration is
        # for static verification only and must not shadow its runtime mapper.
        def __init__(
            self,
            *,
            target_type: str | None = None,
            action: str | None = None,
            summary: str | None = None,
            actor_user_id: int | None = None,
            target_id: str | None = None,
            metadata_json: dict[str, Any] | None = None,
            ip_address: str | None = None,
            user_agent: str | None = None,
            created_at: datetime | None = None,
            id: int | None = None,
        ) -> None: ...
