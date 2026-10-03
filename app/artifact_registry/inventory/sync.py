from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.artifact_registry.inventory.contracts import RegistryInventoryEvidence
from app.artifact_registry.inventory.providers import collect_registry_inventory
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.registry_artifact import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
    RegistryTag,
)

logger = logging.getLogger(__name__)


def _collection_state(instance_id: int) -> RegistryCollectionState:
    state = RegistryCollectionState.query.filter_by(integration_instance_id=instance_id).first()
    if state is None:
        state = RegistryCollectionState(integration_instance_id=instance_id)
        db.session.add(state)
        db.session.flush()
    return state


def _record_failure(instance_id: int, exc: Exception) -> None:
    try:
        state = _collection_state(instance_id)
        state.status = 'failed'
        state.last_attempt_at = datetime.now(UTC)
        state.last_error = str(exc)[:4000]
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Could not persist Registry inventory failure evidence for instance %s.', instance_id)


def _commit_tags(artifact: RegistryArtifact, evidence, observed_at: datetime) -> None:
    existing = {tag.name: tag for tag in artifact.tags}
    for item in evidence.tags:
        tag = existing.pop(item.name, None)
        if tag is None:
            tag = RegistryTag(artifact_id=artifact.id, name=item.name)
            db.session.add(tag)
        tag.provider_native_id = item.provider_native_id
        tag.push_time = item.push_time
        tag.pull_time = item.pull_time
        tag.provider_metadata = dict(item.metadata or {})
        tag.observed_at = observed_at
    for stale in existing.values():
        db.session.delete(stale)


def _commit_artifacts(repository: RegistryRepository, evidence, observed_at: datetime) -> None:
    existing = {artifact.digest: artifact for artifact in repository.artifacts}
    for item in evidence.artifacts:
        artifact = existing.pop(item.digest, None)
        if artifact is None:
            artifact = RegistryArtifact(repository_id=repository.id, digest=item.digest)
            db.session.add(artifact)
            db.session.flush()
        artifact.provider_native_id = item.provider_native_id
        artifact.artifact_type = item.artifact_type
        artifact.media_type = item.media_type
        artifact.manifest_media_type = item.manifest_media_type
        artifact.size_bytes = item.size_bytes
        artifact.push_time = item.push_time
        artifact.pull_time = item.pull_time
        artifact.provider_metadata = dict(item.metadata or {})
        artifact.observed_at = observed_at
        _commit_tags(artifact, item, observed_at)
    for stale in existing.values():
        db.session.delete(stale)


def _commit_repositories(project: RegistryProject, evidence, observed_at: datetime) -> None:
    existing = {repository.name: repository for repository in project.repositories}
    for item in evidence.repositories:
        repository = existing.pop(item.name, None)
        if repository is None:
            repository = RegistryRepository(project_id=project.id, name=item.name)
            db.session.add(repository)
            db.session.flush()
        repository.provider_native_id = item.provider_native_id
        repository.description = item.description
        repository.artifact_count = item.artifact_count
        repository.pull_count = item.pull_count
        repository.provider_created_at = item.provider_created_at
        repository.provider_updated_at = item.provider_updated_at
        repository.provider_metadata = dict(item.metadata or {})
        repository.observed_at = observed_at
        _commit_artifacts(repository, item, observed_at)
    for stale in existing.values():
        db.session.delete(stale)


def commit_registry_inventory(
    instance: IntegrationInstance,
    evidence: RegistryInventoryEvidence,
) -> dict[str, int]:
    """Atomically reconcile one provider inventory snapshot while preserving stable row identity."""

    db.session.execute(
        select(IntegrationInstance.id).where(IntegrationInstance.id == instance.id).with_for_update()
    ).scalar_one()
    existing_projects = {
        project.name: project
        for project in RegistryProject.query.filter_by(integration_instance_id=instance.id).all()
    }
    if existing_projects and not evidence.projects:
        raise RuntimeError(
            'Registry provider discovery returned zero projects while committed inventory already exists. '
            'KAORI preserved the previous snapshot; verify provider scope before retrying.'
        )

    for item in evidence.projects:
        project = existing_projects.pop(item.name, None)
        if project is None:
            project = RegistryProject(integration_instance_id=instance.id, name=item.name)
            db.session.add(project)
            db.session.flush()
        project.provider_native_id = item.provider_native_id
        project.is_public = item.is_public
        project.repository_count = item.repository_count
        project.provider_created_at = item.provider_created_at
        project.provider_updated_at = item.provider_updated_at
        project.provider_metadata = dict(item.metadata or {})
        project.observed_at = evidence.observed_at
        _commit_repositories(project, item, evidence.observed_at)

    for stale in existing_projects.values():
        db.session.delete(stale)

    state = _collection_state(instance.id)
    state.status = 'collected'
    state.last_attempt_at = evidence.observed_at
    state.last_success_at = evidence.observed_at
    state.observed_at = evidence.observed_at
    state.last_error = None
    state.project_count = len(evidence.projects)
    state.repository_count = evidence.repository_count
    state.artifact_count = evidence.artifact_count
    state.tag_count = evidence.tag_count
    db.session.flush()
    return {
        'projects': state.project_count,
        'repositories': state.repository_count,
        'artifacts': state.artifact_count,
        'tags': state.tag_count,
    }


def sync_registry_instance(instance: IntegrationInstance) -> dict[str, object]:
    if not instance.enabled or instance.lifecycle_status != 'active':
        raise RuntimeError('Registry integration is not active for inventory synchronization.')
    if instance.readiness_status not in {'ready', 'degraded'}:
        raise RuntimeError('Run Full Validation before Artifact Registry inventory synchronization.')

    try:
        evidence = collect_registry_inventory(instance)
        counts = commit_registry_inventory(instance, evidence)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        _record_failure(instance.id, exc)
        raise

    return {
        'integration_instance_id': instance.id,
        'provider_key': instance.provider_key,
        'instance_name': instance.name,
        'observed_at': evidence.observed_at.isoformat(),
        **counts,
    }
