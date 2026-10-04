from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.artifact_registry.collectors import InventoryProgressCallback, RegistryInventoryCollector
from app.artifact_registry.contracts import (
    ArtifactRecord,
    ProjectRecord,
    RegistryInventoryEvidence,
    RepositoryRecord,
)
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.models.harbor import HarborInstance


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


def _repository_name(project_name: str, value: Any) -> str:
    name = str(value or '').strip().strip('/')
    prefix = f'{project_name}/'
    return name[len(prefix):] if name.startswith(prefix) else name


def collect_harbor_inventory(
    instance: HarborInstance,
    progress_callback: InventoryProgressCallback | None = None,
) -> RegistryInventoryEvidence:
    """Collect only the canonical inventory facts owned by #895.

    Security detail, governance, and runtime correlation have independent
    workstream authorities and must not extend the inventory critical path.
    """

    client = build_client(instance)
    if progress_callback is not None:
        progress_callback(0, 0, 'Project Discovery')
    raw_projects = client.list_all_projects()
    repository_hint = sum(max(_as_int(project.get('repo_count')) or 0, 0) for project in raw_projects)
    repository_processed = 0
    if progress_callback is not None:
        progress_callback(0, repository_hint, '')

    projects: list[ProjectRecord] = []
    for raw_project in raw_projects:
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
                        tags=[
                            tag
                            for tag in (raw_artifact.get('tags') or [])
                            if isinstance(tag, dict)
                        ],
                        provider_metadata={
                            key: raw_artifact.get(key)
                            for key in ('manifest_media_type', 'project_id', 'repository_id', 'extra_attrs')
                            if raw_artifact.get(key) is not None
                        },
                    )
                )
            project.repositories.append(repository)
            repository_processed += 1
            if progress_callback is not None:
                progress_callback(
                    repository_processed,
                    max(repository_hint, repository_processed),
                    f'{project_name}/{repo_name}',
                )
        projects.append(project)

    if progress_callback is not None:
        progress_callback(repository_processed, repository_processed, '')

    parsed = urlparse(instance.endpoint)
    return RegistryInventoryEvidence(
        projects=projects,
        provider_metadata={
            'provider_key': 'harbor',
            'source': 'harbor_api_v2',
            'provider_record_id': int(instance.id),
            'registry_host': (parsed.hostname or '').lower() or None,
            'registry_scheme': parsed.scheme or None,
        },
    )


collector = RegistryInventoryCollector(
    provider_key='harbor',
    collect=collect_harbor_inventory,
    collect_with_progress=collect_harbor_inventory,
)
