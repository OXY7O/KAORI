from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.minio import MinioInstance


class ObjectStorageSystem(db.Model):
    """Provider-neutral managed asset for one object-storage runtime boundary."""

    __tablename__ = 'object_storage_systems'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='unknown')
    last_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inventory_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    minio_connection: Mapped[MinioInstance | None] = relationship(
        'MinioInstance',
        back_populates='object_storage_system',
        cascade='all, delete-orphan',
        passive_deletes=True,
        uselist=False,
    )
    buckets: Mapped[list[ObjectStorageBucket]] = relationship(
        'ObjectStorageBucket',
        back_populates='object_storage_system',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='ObjectStorageBucket.name',
    )


class ObjectStorageBucket(db.Model):
    """Committed bucket/container namespace snapshot for one object-storage system.

    The historical class/table name stays stable for migration compatibility; native_type
    carries the provider-specific namespace concept (for example bucket or container).
    """

    __tablename__ = 'object_storage_buckets'
    __table_args__ = (
        UniqueConstraint('object_storage_system_id', 'name', name='uq_object_storage_bucket_system_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_storage_system_id: Mapped[str] = mapped_column(
        ForeignKey('object_storage_systems.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    native_type: Mapped[str] = mapped_column(String(32), nullable=False, default='bucket')
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    versioning_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    immutability_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    encryption_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    replication_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    access_policy_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    exposure_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    provider_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    object_storage_system: Mapped[ObjectStorageSystem] = relationship(
        'ObjectStorageSystem',
        back_populates='buckets',
        lazy='joined',
    )
