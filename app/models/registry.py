from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class RegistryCollectionState(db.Model):
    """Committed collection boundary for one canonical Registry IntegrationInstance."""

    __tablename__ = 'registry_collection_states'

    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    counts: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    metadata_json: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RegistryProject(db.Model):
    """Provider-neutral committed registry project / namespace."""

    __tablename__ = 'registry_projects'
    __table_args__ = (
        UniqueConstraint('integration_instance_id', 'name', name='uq_registry_project_instance_name'),
        Index('ix_registry_projects_instance_observed', 'integration_instance_id', 'observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    public: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    repository_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    repositories: Mapped[list[RegistryRepository]] = relationship(
        'RegistryRepository',
        back_populates='project',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryRepository.name',
    )


class RegistryRepository(db.Model):
    """Provider-neutral committed repository identity scoped to one Registry Project."""

    __tablename__ = 'registry_repositories'
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_registry_repository_project_name'),
        Index('ix_registry_repositories_project_observed', 'project_id', 'observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('registry_projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pull_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[RegistryProject] = relationship('RegistryProject', back_populates='repositories', lazy='joined')
    artifacts: Mapped[list[RegistryArtifact]] = relationship(
        'RegistryArtifact',
        back_populates='repository',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryArtifact.digest',
    )


class RegistryArtifact(db.Model):
    """Immutable OCI content identity committed by digest when the provider supplies one."""

    __tablename__ = 'registry_artifacts'
    __table_args__ = (
        UniqueConstraint('repository_id', 'digest', name='uq_registry_artifact_repository_digest'),
        Index('ix_registry_artifacts_digest', 'digest'),
        Index('ix_registry_artifacts_repository_observed', 'repository_id', 'observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey('registry_repositories.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    digest: Mapped[str] = mapped_column(String(255), nullable=False)
    digest_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default='unknown')
    artifact_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    push_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pull_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scan_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vulnerability_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    signature_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sbom_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scan_snapshots: Mapped[list[RegistryScanSnapshot]] = relationship(
        'RegistryScanSnapshot',
        back_populates='artifact',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryScanSnapshot.observed_at.desc()',
    )
    repository: Mapped[RegistryRepository] = relationship(
        'RegistryRepository', back_populates='artifacts', lazy='joined'
    )
    tags: Mapped[list[RegistryTag]] = relationship(
        'RegistryTag',
        back_populates='artifact',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryTag.name',
    )


class RegistryTag(db.Model):
    """Mutable registry reference associated with an immutable artifact digest."""

    __tablename__ = 'registry_tags'
    __table_args__ = (
        UniqueConstraint('artifact_id', 'name', name='uq_registry_tag_artifact_name'),
        Index('ix_registry_tags_name', 'name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey('registry_artifacts.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    push_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pull_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    artifact: Mapped[RegistryArtifact] = relationship('RegistryArtifact', back_populates='tags', lazy='joined')


class RegistryScanSnapshot(db.Model):
    """Normalized vulnerability scan evidence for one immutable artifact digest."""

    __tablename__ = 'registry_scan_snapshots'
    __table_args__ = (Index('ix_registry_scan_artifact_observed', 'artifact_id', 'observed_at'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey('registry_artifacts.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    scanner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scanner_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    report_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default='not_scanned')
    severity_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    artifact: Mapped[RegistryArtifact] = relationship(
        'RegistryArtifact', back_populates='scan_snapshots', lazy='joined'
    )
    vulnerabilities: Mapped[list[RegistryVulnerability]] = relationship(
        'RegistryVulnerability',
        back_populates='scan_snapshot',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryVulnerability.severity',
    )


class RegistryVulnerability(db.Model):
    """Normalized vulnerability finding derived from provider scan evidence."""

    __tablename__ = 'registry_vulnerabilities'
    __table_args__ = (
        UniqueConstraint(
            'scan_snapshot_id',
            'vulnerability_id',
            'package',
            'installed_version',
            name='uq_registry_vulnerability_scan_identity',
        ),
        Index('ix_registry_vulnerabilities_severity', 'severity'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey('registry_scan_snapshots.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    vulnerability_id: Mapped[str] = mapped_column(String(255), nullable=False)
    package: Mapped[str] = mapped_column(String(512), nullable=False, default='unknown')
    installed_version: Mapped[str] = mapped_column(String(255), nullable=False, default='unknown')
    fixed_version: Mapped[str | None] = mapped_column(String(512), nullable=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default='unknown')
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)

    scan_snapshot: Mapped[RegistryScanSnapshot] = relationship(
        'RegistryScanSnapshot',
        back_populates='vulnerabilities',
        lazy='joined',
    )


class RegistryWorkloadBinding(db.Model):
    """Derived correlation between committed Registry artifacts and committed Pod inventory."""

    __tablename__ = 'registry_workload_bindings'
    __table_args__ = (
        UniqueConstraint(
            'artifact_id',
            'pod_inventory_id',
            'image_reference',
            name='uq_registry_workload_binding_identity',
        ),
        Index('ix_registry_workload_bindings_cluster_namespace', 'cluster_id', 'namespace'),
        Index('ix_registry_workload_bindings_artifact_observed', 'artifact_id', 'observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey('registry_artifacts.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    pod_inventory_id: Mapped[int] = mapped_column(
        ForeignKey('pod_inventory.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    image_reference: Mapped[str] = mapped_column(String(2048), nullable=False)
    match_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    workload_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workload_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pod_name: Mapped[str] = mapped_column(String(255), nullable=False)
    container_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    artifact: Mapped[RegistryArtifact] = relationship('RegistryArtifact', lazy='joined')


class RegistryGovernanceState(db.Model):
    """Committed provider-neutral Registry governance collection boundary."""

    __tablename__ = 'registry_governance_states'

    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    capability_states: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RegistryProjectGovernance(db.Model):
    """Committed policy posture for one canonical Registry project."""

    __tablename__ = 'registry_project_governance'
    __table_args__ = (
        UniqueConstraint('project_id', name='uq_registry_project_governance_project'),
        Index('ix_registry_project_governance_observed', 'observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('registry_projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    retention_status: Mapped[str] = mapped_column(String(40), nullable=False, default='not_collected')
    retention_policy_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retention_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    immutability_status: Mapped[str] = mapped_column(String(40), nullable=False, default='not_collected')
    immutability_rule_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    immutability_summary: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[RegistryProject] = relationship('RegistryProject', lazy='joined')


class RegistryReplicationPolicy(db.Model):
    """Committed provider-neutral replication policy evidence."""

    __tablename__ = 'registry_replication_policies'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id',
            'provider_native_id',
            name='uq_registry_replication_instance_native',
        ),
        Index('ix_registry_replication_instance_observed', 'integration_instance_id', 'observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider_native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    trigger_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_registry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_registry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_namespace: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filters_json: Mapped[list | None] = mapped_column(db.JSON, nullable=True, default=list)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RegistryWebhookEndpoint(db.Model):
    """KAORI webhook admission posture for one Registry provider instance."""

    __tablename__ = 'registry_webhook_endpoints'

    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RegistryWebhookEvent(db.Model):
    """Idempotent normalized Registry event evidence; raw payloads are not retained."""

    __tablename__ = 'registry_webhook_events'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id',
            'dedup_key',
            name='uq_registry_webhook_event_dedup',
        ),
        Index('ix_registry_webhook_events_instance_received', 'integration_instance_id', 'received_at'),
        Index('ix_registry_webhook_events_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repository_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_digest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artifact_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default='received')
    job_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey('job_executions.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RegistryAnalyticsSnapshot(db.Model):
    """Persistent Artifact Registry analytics materialized from committed evidence."""

    __tablename__ = 'registry_analytics_snapshots'
    __table_args__ = (
        Index('ix_registry_analytics_instance_generated', 'integration_instance_id', 'generated_at'),
        Index('ix_registry_analytics_freshness', 'status', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    time_range: Mapped[str] = mapped_column(String(20), nullable=False, default='current')
    payload_json: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='ready', index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    freshness_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    stale_grace_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    last_job_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey('job_executions.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
