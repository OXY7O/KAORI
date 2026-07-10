from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster


class Pod(db.Model):
    __tablename__ = 'pods'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            name='uq_pod_cluster_namespace_name',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    cluster: Mapped[Cluster] = relationship(back_populates='pods')

    namespace: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
    )

    status: Mapped[str | None] = mapped_column(db.String(50))

    node_name: Mapped[str | None] = mapped_column(db.String(255))

    pod_ip: Mapped[str | None] = mapped_column(db.String(50))

    restart_count: Mapped[int] = mapped_column(default=0)

    owner_kind: Mapped[str | None] = mapped_column(db.String(50))

    owner_name: Mapped[str | None] = mapped_column(db.String(255))

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f'<Pod {self.namespace}/{self.name}>'
