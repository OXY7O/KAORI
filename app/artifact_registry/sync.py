from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.extensions.db import db
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.models.harbor import HarborInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
    RegistryTag,
)

logger = logging.getLogger(__name__)


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


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class ArtifactRecord:
    digest: str
    provider_native_id: str | None
    artifact_type: str | None
    media_type: str | None
    size_bytes: int | None
    push_time: datetime | None
    pull_time: datetime | None
    tags: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RepositoryRecord:
    name: str
    provider_native_id: str | None
    artifact_count: int | None
    pull_count: int | None
    description: str | None
    provider_created_at: datetime | None
    provider_updated_at: datetime | None
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProjectRecord:
    name: str
    provider_native_id: str | None
    public: bool | None
    repository_count: int | None
    repositories: list[RepositoryRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


def _repository_name(project_name: str, value: Any) -> str:
    name = str(value or '').strip().strip('/')
    prefix = f'{project_name}/'
    return name[len(prefix):] if name.startswith(prefix) else name


def collect_harbor_inventory(instance: HarborInstance) -> list[ProjectRecord]:
    client = build_client(instance)
    projects: list[ProjectRecord] = []
    for raw_project in client.list_all_projects():
        project_name = str(raw_project.get('name') or '').strip()
        if not project_name:
            continue
        project = ProjectRecord(
            name=project_name,
            provider_native_id=str(raw_project.get('project_id') or '') or None,
            public=bool(raw_project.get('public')) if raw_project.get('public') is not None else None,
            repository_count=_as_int(raw_project.get('repo_count')),
            provider_metadata={
                key: raw_project.get(key)
                for key in ('creation_time', 'update_time', 'metadata', 'owner_id', 'owner_name')
                if raw_project.get(key) is not None
            },
        )
        for raw_repo in client.list_all_repositories(project_name_or_id=project_name):
            repo_name = _repository_name(project_name, raw_repo.get('name'))
            if not repo_name:
                continue
            repository = RepositoryRecord(
                name=repo_name,
                provider_native_id=str(raw_repo.get('id') or '') or None,
                artifact_count=_as_int(raw_repo.get('artifact_count')),
                pull_count=_as_int(raw_repo.get('pull_count')),
                description=str(raw_repo.get('description') or '').strip() or None,
                provider_created_at=_parse_datetime(raw_repo.get('creation_time')),
                provider_updated_at=_parse_datetime(raw_repo.get('update_time')),
                provider_metadata={
                    key: raw_repo.get(key)
                    for key in ('project_id',)
                    if raw_repo.get(key) is not None
                },
            )
            for raw_artifact in client.list_all_artifacts(
                project_name_or_id=project_name,
                repository_name=repo_name,
                with_scan_overview=False,
                with_sbom_overview=False,
                with_signature=False,
                with_immutable_status=False,
            ):
                digest = str(raw_artifact.get('digest') or '').strip()
                if not digest:
                    continue
                repository.artifacts.append(
                    ArtifactRecord(
                        digest=digest,
                        provider_native_id=str(raw_artifact.get('id') or '') or None,
                        artifact_type=str(raw_artifact.get('type') or '').strip() or None,
                        media_type=str(raw_artifact.get('media_type') or '').strip() or None,
                        size_bytes=_as_int(raw_artifact.get('size')),
                        push_time=_parse_datetime(raw_artifact.get('push_time')),
                        pull_time=_parse_datetime(raw_artifact.get('pull_time')),
                        tags=[tag for tag in (raw_artifact.get('tags') or []) if isinstance(tag, dict)],
                        provider_metadata={
                            key: raw_artifact.get(key)
                            for key in ('manifest_media_type', 'project_id', 'repository_id', 'extra_attrs')
                            if raw_artifact.get(key) is not None
                        },
                    )
                )
            project.repositories.append(repository)
        projects.append(project)
    return projects


def _lock_collection_state(integration_instance_id: int) -> RegistryCollectionState:
    state = db.session.get(RegistryCollectionState, integration_instance_id)
    if state is None:
        state = RegistryCollectionState(integration_instance_id=integration_instance_id)
        db.session.add(state)
        db.session.flush()
    db.session.execute(
        select(RegistryCollectionState.integration_instance_id)
        .where(RegistryCollectionState.integration_instance_id == integration_instance_id)
        .with_for_update()
    ).scalar_one()
    return state


def commit_registry_inventory(
    instance: HarborInstance,
    projects: list[ProjectRecord],
    *,
    observed_at: datetime,
) -> dict[str, int]:
    integration_instance_id = int(instance.integration_instance_id)
    state = _lock_collection_state(integration_instance_id)
    existing_count = RegistryProject.query.filter_by(integration_instance_id=integration_instance_id).count()
    if existing_count and not projects:
        raise RuntimeError(
            'Harbor project discovery returned zero projects while a previous committed Registry snapshot exists. '
            'KAORI preserved the previous snapshot; verify credential scope and provider health before retrying.'
        )

    RegistryProject.query.filter_by(integration_instance_id=integration_instance_id).delete(synchronize_session=False)
    db.session.flush()

    project_count = repository_count = artifact_count = tag_count = 0
    for project_record in projects:
        project = RegistryProject(
            integration_instance_id=integration_instance_id,
            provider_native_id=project_record.provider_native_id,
            name=project_record.name,
            public=project_record.public,
            repository_count=project_record.repository_count,
            provider_metadata=project_record.provider_metadata,
            observed_at=observed_at,
        )
        db.session.add(project)
        db.session.flush()
        project_count += 1
        for repo_record in project_record.repositories:
            repository = RegistryRepository(
                project_id=project.id,
                provider_native_id=repo_record.provider_native_id,
                name=repo_record.name,
                artifact_count=repo_record.artifact_count,
                pull_count=repo_record.pull_count,
                description=repo_record.description,
                provider_created_at=repo_record.provider_created_at,
                provider_updated_at=repo_record.provider_updated_at,
                provider_metadata=repo_record.provider_metadata,
                observed_at=observed_at,
            )
            db.session.add(repository)
            db.session.flush()
            repository_count += 1
            for artifact_record in repo_record.artifacts:
                digest_algorithm = (
                    artifact_record.digest.split(':', 1)[0] if ':' in artifact_record.digest else 'unknown'
                )
                artifact = RegistryArtifact(
                    repository_id=repository.id,
                    provider_native_id=artifact_record.provider_native_id,
                    digest=artifact_record.digest,
                    digest_algorithm=digest_algorithm,
                    artifact_type=artifact_record.artifact_type,
                    media_type=artifact_record.media_type,
                    size_bytes=artifact_record.size_bytes,
                    push_time=artifact_record.push_time,
                    pull_time=artifact_record.pull_time,
                    provider_metadata=artifact_record.provider_metadata,
                    observed_at=observed_at,
                )
                db.session.add(artifact)
                db.session.flush()
                artifact_count += 1
                for raw_tag in artifact_record.tags:
                    tag_name = str(raw_tag.get('name') or '').strip()
                    if not tag_name:
                        continue
                    db.session.add(
                        RegistryTag(
                            artifact_id=artifact.id,
                            name=tag_name,
                            provider_native_id=str(raw_tag.get('id') or '') or None,
                            push_time=_parse_datetime(raw_tag.get('push_time')),
                            pull_time=_parse_datetime(raw_tag.get('pull_time')),
                            provider_metadata={
                                key: raw_tag.get(key)
                                for key in ('immutable', 'signed')
                                if raw_tag.get(key) is not None
                            },
                            observed_at=observed_at,
                        )
                    )
                    tag_count += 1

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
        'provider_key': instance.provider_key,
        'provider_connection_id': instance.id,
        'source': 'harbor_api_v2',
    }
    db.session.flush()
    return dict(state.counts)


def sync_registry_inventory(instance: HarborInstance) -> dict[str, Any]:
    canonical = instance.integration_instance
    if not canonical.enabled or canonical.lifecycle_status != 'active':
        raise RuntimeError('The Harbor Registry integration is not active for inventory synchronization.')
    if instance.readiness_status != 'ready':
        raise RuntimeError('Run Full Validation successfully before Artifact Registry inventory synchronization.')

    observed_at = datetime.now(UTC)
    state = _lock_collection_state(int(instance.integration_instance_id))
    state.status = 'collecting'
    state.last_started_at = observed_at
    state.last_error = None
    db.session.flush()
    try:
        projects = collect_harbor_inventory(instance)
        counts = commit_registry_inventory(instance, projects, observed_at=observed_at)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        state = _lock_collection_state(int(instance.integration_instance_id))
        state.status = 'failed'
        state.last_error = str(exc)[:2000]
        db.session.commit()
        logger.exception('Artifact Registry synchronization failed for Harbor instance %s.', instance.id)
        raise
    return {
        'integration_instance_id': int(instance.integration_instance_id),
        'instance_id': int(instance.id),
        'instance_name': instance.name,
        'observed_at': observed_at.isoformat(),
        **counts,
    }
