from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster


class AlertmanagerConfig(db.Model):
    __tablename__ = 'alertmanager_configs'

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
    )

    endpoint: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    auth_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default='none',
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    password: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    bearer_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    timeout: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )

    verify_ssl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


    detected_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    cluster: Mapped[Cluster] = relationship(
        'Cluster',
        back_populates='alertmanager_config',
    )

    __table_args__ = (
        Index(
            'ix_alertmanager_configs_cluster_status',
            'cluster_id',
            'last_status',
        ),
    )

    @property
    def is_configured(self) -> bool:
        return bool(
            self.endpoint,
        )

    @property
    def is_connected(self) -> bool:
        return self.last_status == 'connected'

    @property
    def display_status(self) -> str:
        if not self.endpoint:
            return 'Not Configured'

        if self.last_status == 'connected':
            return 'Connected'

        if self.last_status == 'disconnected':
            return 'Disconnected'

        if self.last_status == 'error':
            return 'Error'

        return 'Configured'
