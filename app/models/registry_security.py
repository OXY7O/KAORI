from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.registry_artifact import RegistryArtifact


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RegistrySecurityCollectionState(db.Model):
    """Provider-neutral collection state for artifact security and supply-chain evidence."""

    __tablename__ = 'registry_security_collection_states'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id',
            name='uq_registry_security_collection_state_integration_instance',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    vulnerability_capability_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default='not_collected'
    )
    signature_capability_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default='not_collected'
    )
    sbom_capability_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default='not_collected'
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vulnerable_artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signature_observed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sbom_observed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', lazy='joined')


class RegistryArtifactSecuritySnapshot(db.Model):
    """Latest committed security/supply-chain evidence for one immutable artifact digest."""

    __tablename__ = 'registry_artifact_security_snapshots'
    __table_args__ = (
        UniqueConstraint('artifact_id', name='uq_registry_artifact_security_snapshot_artifact'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey('registry_artifacts.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    vulnerability_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    scan_status: Mapped[str] = mapped_column(String(50), nullable=False, default='not_collected')
    scan_severity: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scanner_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    scanner_vendor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    scanner_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scan_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fixable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negligible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signature_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    signature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trust_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_evaluated')
    sbom_state: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    sbom_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    artifact: Mapped[RegistryArtifact] = relationship('RegistryArtifact', lazy='joined')
    findings: Mapped[list['RegistryVulnerabilityFinding']] = relationship(
        'RegistryVulnerabilityFinding',
        back_populates='snapshot',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryVulnerabilityFinding.severity.desc(), RegistryVulnerabilityFinding.vulnerability_id',
    )


class RegistryVulnerabilityFinding(db.Model):
    """Normalized scanner finding attached to one immutable artifact security snapshot."""

    __tablename__ = 'registry_vulnerability_findings'
    __table_args__ = (
        UniqueConstraint('security_snapshot_id', 'finding_key', name='uq_registry_vulnerability_snapshot_key'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    security_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey('registry_artifact_security_snapshots.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    finding_key: Mapped[str] = mapped_column(String(900), nullable=False)
    vulnerability_id: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default='unknown')
    package: Mapped[str | None] = mapped_column(String(500), nullable=True)
    installed_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fixed_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fix_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cvss_score: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    links: Mapped[list[str] | None] = mapped_column(db.JSON, nullable=True, default=list)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    snapshot: Mapped[RegistryArtifactSecuritySnapshot] = relationship(
        'RegistryArtifactSecuritySnapshot', back_populates='findings', lazy='joined'
    )
