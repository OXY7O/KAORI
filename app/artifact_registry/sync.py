from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.artifact_registry.collectors import InventoryProgressCallback, get_registry_collector
from app.artifact_registry.contracts import ProjectRecord, RegistryInventoryEvidence
from app.artifact_registry.eligibility import registry_inventory_eligibility
from app.extensions.db import db
from app.integrations.kernel.registry import get_integration
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
    RegistryTag,
)

logger = logging.getLogger(__name__)


def _mark_inventory_collection_started(
    state: RegistryCollectionState,
    *,
    started_at: datetime,
) -> None:
    """Keep the last committed snapshot readable while a refresh is in flight."""
    state.status = 'ready' if state.last_committed_at is not None else 'collecting'
    state.last_started_at = started_at


def _mark_inventory_collection_failed(
    state: RegistryCollectionState,
    error: Exception | str,
) -> None:
    """Record refresh failure without invalidating an existing committed snapshot."""
    state.status = 'ready' if state.last_committed_at is not None else 'failed'
    state.last_error = str(error)[:2000]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _lock_collection_state(integration_instance_id: int) -> RegistryCollectionState:
    state = db.session.get(RegistryCollectionState, integration_instance_id)
    if state is None:
        state = RegistryCollectionState()
        state.integration_instance_id = integration_instance_id
        db.session.add(state)
        db.session.flush()
    db.session.execute(
        select(RegistryCollectionState.integration_instance_id)
        .where(RegistryCollectionState.integration_instance_id == integration_instance_id)
        .with_for_update()
    ).scalar_one()
    return state


def _reconcile_tags(
    artifact: RegistryArtifact,
    raw_tags: list[dict[str, Any]],
    *,
    observed_at: datetime,
) -> int:
    existing = {tag.name: tag for tag in artifact.tags}
    count = 0
    for raw_tag in raw_tags:
        tag_name = str(raw_tag.get('name') or '').strip()
        if not tag_name:
            continue
        tag = existing.pop(tag_name, None)
        if tag is None:
            tag = RegistryTag()
            tag.name = tag_name
            artifact.tags.append(tag)
        tag.provider_native_id = str(raw_tag.get('id') or '') or None
        tag.push_time = _parse_datetime(raw_tag.get('push_time'))
        tag.pull_time = _parse_datetime(raw_tag.get('pull_time'))
        tag.provider_metadata = {
            key: raw_tag.get(key) for key in ('immutable', 'signed') if raw_tag.get(key) is not None
        }
        tag.observed_at = observed_at
        count += 1

    for stale in existing.values():
        db.session.delete(stale)
    return count


def _reconcile_artifacts(
    repository: RegistryRepository,
    records: list[Any],
    *,
    observed_at: datetime,
) -> tuple[int, int]:
    existing = {artifact.digest: artifact for artifact in repository.artifacts}
    artifact_count = tag_count = 0
    for record in records:
        artifact = existing.pop(record.digest, None)
        if artifact is None:
            digest_algorithm = record.digest.split(':', 1)[0] if ':' in record.digest else 'unknown'
            artifact = RegistryArtifact()
            artifact.digest = record.digest
            artifact.digest_algorithm = digest_algorithm
            repository.artifacts.append(artifact)
        artifact.provider_native_id = record.provider_native_id
        artifact.digest_algorithm = record.digest.split(':', 1)[0] if ':' in record.digest else 'unknown'
        artifact.artifact_type = record.artifact_type
        artifact.media_type = record.media_type
        artifact.size_bytes = record.size_bytes
        artifact.push_time = record.push_time
        artifact.pull_time = record.pull_time
        artifact.provider_metadata = record.provider_metadata
        artifact.observed_at = observed_at

        # Security posture is owned by the separate security workstream. Inventory
        # reconciliation deliberately preserves scan/signature/SBOM evidence on
        # stable artifact rows and only removes it when the artifact itself is stale.
        tag_count += _reconcile_tags(
            artifact,
            list(record.tags),
            observed_at=observed_at,
        )
        artifact_count += 1

    for stale in existing.values():
        db.session.delete(stale)
    return artifact_count, tag_count


def _reconcile_repositories(
    project: RegistryProject,
    records: list[Any],
    *,
    observed_at: datetime,
) -> tuple[int, int, int]:
    existing = {repository.name: repository for repository in project.repositories}
    repository_count = artifact_count = tag_count = 0
    for record in records:
        repository = existing.pop(record.name, None)
        if repository is None:
            repository = RegistryRepository()
            repository.name = record.name
            project.repositories.append(repository)
        repository.provider_native_id = record.provider_native_id
        repository.artifact_count = record.artifact_count
        repository.pull_count = record.pull_count
        repository.description = record.description
        repository.provider_created_at = record.provider_created_at
        repository.provider_updated_at = record.provider_updated_at
        repository.provider_metadata = record.provider_metadata
        repository.observed_at = observed_at

        child_artifacts, child_tags = _reconcile_artifacts(
            repository,
            list(record.artifacts),
            observed_at=observed_at,
        )
        repository_count += 1
        artifact_count += child_artifacts
        tag_count += child_tags

    for stale in existing.values():
        db.session.delete(stale)
    return repository_count, artifact_count, tag_count


def commit_registry_inventory(
    identity: IntegrationInstance,
    evidence: RegistryInventoryEvidence,
    *,
    observed_at: datetime,
) -> dict[str, int]:
    integration_instance_id = int(identity.id)
    projects: list[ProjectRecord] = evidence.projects
    state = _lock_collection_state(integration_instance_id)
    existing_projects = {
        project.name: project
        for project in RegistryProject.query.options(
            selectinload(RegistryProject.repositories)
            .selectinload(RegistryRepository.artifacts)
            .selectinload(RegistryArtifact.tags)
        )
        .filter_by(integration_instance_id=integration_instance_id)
        .all()
    }
    if existing_projects and not projects:
        raise RuntimeError(
            'Registry project discovery returned zero projects while a previous committed snapshot exists. '
            'KAORI preserved the previous snapshot; verify provider scope and health before retrying.'
        )

    project_count = repository_count = artifact_count = tag_count = 0
    for record in projects:
        project = existing_projects.pop(record.name, None)
        if project is None:
            project = RegistryProject()
            project.integration_instance_id = integration_instance_id
            project.name = record.name
            db.session.add(project)
        project.provider_native_id = record.provider_native_id
        project.public = record.public
        project.repository_count = record.repository_count
        project.provider_metadata = record.provider_metadata
        project.observed_at = observed_at

        child_repositories, child_artifacts, child_tags = _reconcile_repositories(
            project,
            list(record.repositories),
            observed_at=observed_at,
        )
        project_count += 1
        repository_count += child_repositories
        artifact_count += child_artifacts
        tag_count += child_tags

    for stale in existing_projects.values():
        db.session.delete(stale)

    state.status = 'ready'
    state.last_observed_at = observed_at
    state.last_committed_at = datetime.now(UTC)
    state.last_error = None
    state.counts = {
        'projects': project_count,
        'repositories': repository_count,
        'artifacts': artifact_count,
        'tags': tag_count,
    }
    state.metadata_json = {
        **(evidence.provider_metadata or {}),
        'provider_key': identity.provider_key,
        'integration_instance_id': integration_instance_id,
    }
    db.session.flush()
    return dict(state.counts)


def sync_registry_inventory(
    identity: IntegrationInstance,
    *,
    progress_callback: InventoryProgressCallback | None = None,
) -> dict[str, Any]:
    if identity.integration_type != 'registry':
        raise RuntimeError('Artifact Registry inventory requires a canonical Registry integration identity.')

    provider_module = get_integration('registry')
    provider_record = provider_module.require_record_for_canonical(int(identity.id))
    eligibility = registry_inventory_eligibility(identity, provider_record=provider_record)
    if not eligibility.eligible:
        raise RuntimeError(eligibility.reason)

    collector = get_registry_collector(identity.provider_key)
    observed_at = datetime.now(UTC)
    state = _lock_collection_state(int(identity.id))
    _mark_inventory_collection_started(state, started_at=observed_at)
    db.session.flush()
    try:
        evidence = (
            collector.collect_with_progress(provider_record, progress_callback)
            if collector.collect_with_progress is not None
            else collector.collect(provider_record)
        )
        counts = commit_registry_inventory(identity, evidence, observed_at=observed_at)
        db.session.commit()
    except (LookupError, RuntimeError, ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        state = _lock_collection_state(int(identity.id))
        _mark_inventory_collection_failed(state, exc)
        db.session.commit()
        logger.exception(
            'Artifact Registry synchronization failed for Registry instance %s (%s).',
            identity.id,
            identity.provider_key,
        )
        raise
    return {
        'integration_instance_id': int(identity.id),
        'instance_name': identity.name,
        'provider_key': identity.provider_key,
        'observed_at': observed_at.isoformat(),
        **counts,
    }
