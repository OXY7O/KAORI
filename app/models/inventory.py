from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class ClusterInventory(db.Model):
    __tablename__ = 'cluster_inventory'

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    kubernetes_version: Mapped[str | None] = mapped_column(String(50))

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class NodeInventory(db.Model):
    __tablename__ = 'node_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'node_name',
            name='uq_node_inventory_cluster_node',
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

    node_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str | None] = mapped_column(String(50))

    os_image: Mapped[str | None] = mapped_column(String(255))

    kernel_version: Mapped[str | None] = mapped_column(String(255))

    container_runtime: Mapped[str | None] = mapped_column(String(255))

    internal_ip: Mapped[str | None] = mapped_column(String(64))

    external_ip: Mapped[str | None] = mapped_column(String(64))

    hostname_address: Mapped[str | None] = mapped_column(String(255))

    pod_cidrs: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    cpu: Mapped[int | None] = mapped_column(Integer)

    memory: Mapped[str | None] = mapped_column(String(50))

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    status: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    ephemeral_storage: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    ephemeral_storage_allocatable: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )


class NamespaceInventory(db.Model):
    __tablename__ = 'namespace_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            name='uq_namespace_inventory_cluster_namespace',
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

    namespace: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str | None] = mapped_column(String(50))

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class WorkloadInventory(db.Model):
    __tablename__ = 'workload_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            'workload_type',
            name='uq_workload_inventory',
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    workload_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    ready: Mapped[str | None] = mapped_column(
        String(50),
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
    )

    details: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class PodInventory(db.Model):
    __tablename__ = 'pod_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'pod_name',
            name='uq_pod_inventory',
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    pod_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    node_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    phase: Mapped[str | None] = mapped_column(
        String(50),
    )

    pod_ip: Mapped[str | None] = mapped_column(
        String(50),
    )

    ready: Mapped[str | None] = mapped_column(
        String(50),
    )

    restart_count: Mapped[int | None] = mapped_column(
        Integer,
    )

    container_images: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    init_container_images: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    image_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    labels: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    container_names: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    workload_type: Mapped[str | None] = mapped_column(String(50))

    workload_name: Mapped[str | None] = mapped_column(String(255))

    configuration_references: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    persistent_volume_claims: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ServiceInventory(db.Model):
    __tablename__ = 'service_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'service_name',
            name='uq_service_inventory',
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    service_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    service_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    cluster_ip: Mapped[str | None] = mapped_column(
        String(100),
    )

    external_ip: Mapped[str | None] = mapped_column(
        String(255),
    )

    ports: Mapped[str | None] = mapped_column(
        String(255),
    )

    selector: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class IngressInventory(db.Model):
    __tablename__ = 'ingress_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'ingress_name',
            name='uq_ingress_inventory',
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ingress_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ingress_class: Mapped[str | None] = mapped_column(
        String(100),
    )

    host: Mapped[str | None] = mapped_column(
        String(255),
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
    )

    tls_enabled: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    backend_paths: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class StorageInventory(db.Model):
    __tablename__ = 'storage_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            'storage_type',
            name='uq_storage_inventory',
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey(
            'clusters.id',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str | None] = mapped_column(
        String(255),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    storage_class: Mapped[str | None] = mapped_column(
        String(255),
    )

    capacity: Mapped[str | None] = mapped_column(
        String(100),
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
    )

    details: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ConfigurationInventory(db.Model):
    __tablename__ = 'configuration_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            'object_type',
            name='uq_configuration_inventory_object',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    object_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    secret_type: Mapped[str | None] = mapped_column(String(255))

    key_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    key_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    payload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ResourceQuotaInventory(db.Model):
    __tablename__ = 'resource_quota_inventory'

    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            'name',
            name='uq_resource_quota_inventory_object',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    hard: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)

    used: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
