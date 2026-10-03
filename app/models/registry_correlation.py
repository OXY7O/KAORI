from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.inventory import PodInventory
from app.models.registry_artifact import RegistryArtifact


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RegistryCorrelationState(db.Model):
    """Committed cross-domain materialization state for Registry ↔ Kubernetes runtime usage."""

    __tablename__ = 'registry_correlation_states'
    __table_args__ = (CheckConstraint('id = 1', name='ck_registry_correlation_state_singleton'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_materialized')
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_reference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    digest_match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tag_match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ambiguous_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class RegistryWorkloadBinding(db.Model):
    """Materialized correlation between committed Registry artifacts and Kubernetes runtime image usage."""

    __tablename__ = 'registry_workload_bindings'
    __table_args__ = (
        UniqueConstraint(
            'pod_inventory_id',
            'container_kind',
            'container_name',
            'image_reference',
            'image_id',
            name='uq_registry_workload_binding_runtime_image',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registry_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey('registry_artifacts.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    pod_inventory_id: Mapped[int] = mapped_column(
        ForeignKey('pod_inventory.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    cluster_id: Mapped[str] = mapped_column(
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    namespace: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pod_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workload_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workload_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    container_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    container_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    image_id: Mapped[str] = mapped_column(String(1000), nullable=False, default='')
    registry_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repository_path: Mapped[str | None] = mapped_column(String(700), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    digest: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    match_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registry_source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    registry_provider_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registry_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kubernetes_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    evidence: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)

    artifact: Mapped[RegistryArtifact | None] = relationship('RegistryArtifact', lazy='joined')
    pod: Mapped[PodInventory] = relationship('PodInventory', lazy='joined')
    cluster: Mapped[Cluster] = relationship('Cluster', lazy='joined')
