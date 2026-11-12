from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class InternalPKIEvidenceBatch(db.Model):
    """Operator-attested, metadata-only PKI source evidence, not renewal proof."""

    __tablename__ = 'internal_pki_evidence_batches'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), index=True)
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    source_version: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    coverage_state: Mapped[str] = mapped_column(String(20), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index('ix_internal_pki_batch_scope', 'cluster_id', 'node_name', 'source_kind', 'collected_at'),
    )


class InternalPKICertificateInventory(db.Model):
    """Normalized certificate expiry metadata; never PEM, private keys or kubeconfig."""

    __tablename__ = 'internal_pki_certificate_inventory'

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    component: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    externally_managed: Mapped[bool | None] = mapped_column(db.Boolean(), nullable=True)
    evidence_batch_id: Mapped[str] = mapped_column(
        ForeignKey('internal_pki_evidence_batches.id', ondelete='RESTRICT'), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint('cluster_id', 'node_name', 'source_kind', 'component', name='uq_internal_pki_source_cert'),
        Index('ix_internal_pki_certificate_scope', 'cluster_id', 'node_name', 'source_kind'),
    )
