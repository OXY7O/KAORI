from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.kubernetes import KubernetesConnection


class ClusterStatus(StrEnum):
    UNKNOWN = 'unknown'
    CONNECTED = 'connected'
    FAILED = 'failed'


class Cluster(db.Model):
    __tablename__ = 'clusters'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    environment: Mapped[str] = mapped_column(String(20), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)


    secret_reveal_encryption_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    secret_reveal_audit_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )


    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ClusterStatus.UNKNOWN.value)

    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


    kubernetes_connection: Mapped[KubernetesConnection | None] = relationship(
        'KubernetesConnection',
        back_populates='cluster',
        cascade='all, delete-orphan',
        passive_deletes=True,
        uselist=False,
    )


    def __repr__(self) -> str:
        return f'<Cluster {self.name}>'
