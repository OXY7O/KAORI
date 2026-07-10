from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.user import User


class TLSCertificateInventory(db.Model):
    __tablename__ = 'tls_certificate_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'secret_name',
            name='uq_tls_certificate_inventory_secret',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    secret_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    secret_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    common_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)

    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)

    fingerprint_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    dns_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    ingress_hosts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    used_by: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    days_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default='unknown', index=True)

    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default='unknown', index=True)

    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped[Cluster] = relationship('Cluster')


class TLSCertificateUpdateEvent(db.Model):
    __tablename__ = 'tls_certificate_update_events'

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    secret_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    old_fingerprint_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)

    new_fingerprint_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)

    old_not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    new_not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    bulk_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    cluster: Mapped[Cluster] = relationship('Cluster')
    actor: Mapped[User | None] = relationship('User')
