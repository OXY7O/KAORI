from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RegistryCollectionState(db.Model):
    """Committed collection authority for one Registry integration instance."""

    __tablename__ = 'registry_collection_states'
    __table_args__ = (
        UniqueConstraint('integration_instance_id', name='uq_registry_collection_state_integration_instance'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repository_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tag_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', lazy='joined')


class RegistryProject(db.Model):
    """Provider-neutral committed project/namespace identity."""

    __tablename__ = 'registry_projects'
    __table_args__ = (
        UniqueConstraint('integration_instance_id', 'name', name='uq_registry_project_instance_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=False, index=True
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_public: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    repository_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', lazy='joined')
    repositories: Mapped[list['RegistryRepository']] = relationship(
        'RegistryRepository',
        back_populates='project',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryRepository.name',
    )


class RegistryRepository(db.Model):
    """Provider-neutral committed OCI repository identity."""

    __tablename__ = 'registry_repositories'
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_registry_repository_project_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('registry_projects.id', ondelete='CASCADE'), nullable=False, index=True
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pull_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    provider_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[RegistryProject] = relationship('RegistryProject', back_populates='repositories', lazy='joined')
    artifacts: Mapped[list['RegistryArtifact']] = relationship(
        'RegistryArtifact',
        back_populates='repository',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryArtifact.push_time.desc()',
    )


class RegistryArtifact(db.Model):
    """Immutable-by-digest normalized OCI artifact evidence."""

    __tablename__ = 'registry_artifacts'
    __table_args__ = (
        UniqueConstraint('repository_id', 'digest', name='uq_registry_artifact_repository_digest'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey('registry_repositories.id', ondelete='CASCADE'), nullable=False, index=True
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    digest: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manifest_media_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    push_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pull_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    repository: Mapped[RegistryRepository] = relationship(
        'RegistryRepository', back_populates='artifacts', lazy='joined'
    )
    tags: Mapped[list['RegistryTag']] = relationship(
        'RegistryTag',
        back_populates='artifact',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='RegistryTag.name',
    )


class RegistryTag(db.Model):
    """Mutable provider tag observed on one immutable Registry artifact digest."""

    __tablename__ = 'registry_tags'
    __table_args__ = (
        UniqueConstraint('artifact_id', 'name', name='uq_registry_tag_artifact_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey('registry_artifacts.id', ondelete='CASCADE'), nullable=False, index=True
    )
    provider_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    push_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pull_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(db.JSON, nullable=True, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    artifact: Mapped[RegistryArtifact] = relationship('RegistryArtifact', back_populates='tags', lazy='joined')
