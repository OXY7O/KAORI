from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster


class PrometheusConfig(db.Model):
    __tablename__ = 'prometheus_configs'

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
    )

    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    auth_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='none',
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    bearer_token: Mapped[str | None] = mapped_column(
        String(4096),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    cluster: Mapped[Cluster] = relationship(
        'Cluster',
        back_populates='prometheus_config',
    )

    def __repr__(self) -> str:
        return f'<PrometheusConfig cluster_id={self.cluster_id} endpoint={self.endpoint}>'
