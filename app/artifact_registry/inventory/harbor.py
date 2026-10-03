from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.artifact_registry.inventory.contracts import (
    RegistryArtifactEvidence,
    RegistryInventoryEvidence,
    RegistryProjectEvidence,
    RegistryRepositoryEvidence,
    RegistryTagEvidence,
)
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.models.harbor import HarborInstance

_PAGE_SIZE = 100


def _datetime(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _integer(value: Any) -> int | None:
    if value in {None, ''}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _identifier(value: Any) -> str | None:
    text = str(value or '').strip()
    return text or None


def _all_pages(fetch_page) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = fetch_page(page, _PAGE_SIZE)
        rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return rows
        page += 1


def _repository_scope(project_name: str, provider_name: str) -> str:
    prefix = f'{project_name}/'
    return provider_name[len(prefix) :] if provider_name.startswith(prefix) else provider_name


def collect_harbor_inventory(source: HarborInstance) -> RegistryInventoryEvidence:
    """Collect read-only Harbor inventory and normalize it before persistence."""

    client = build_client(source)
    observed_at = datetime.now(UTC)
    system_info = client.get_system_info()
    registry_hosts: list[str] = []
    for candidate in (system_info.get('registry_url'), system_info.get('external_url'), source.endpoint):
        text = str(candidate or '').strip()
        if not text:
            continue
        parsed = urlparse(text if '://' in text else f'//{text}')
        host = (parsed.netloc or parsed.path.split('/', 1)[0]).strip().lower()
        if host and host not in registry_hosts:
            registry_hosts.append(host)
    project_rows = _all_pages(
        lambda page, page_size: client.list_projects(page=page, page_size=page_size)
    )
    projects: list[RegistryProjectEvidence] = []

    for project_row in project_rows:
        project_name = str(project_row.get('name') or '').strip()
        if not project_name:
            continue
        repository_rows = _all_pages(
            lambda page, page_size, project_name=project_name: client.list_repositories(
                project_name_or_id=project_name,
                page=page,
                page_size=page_size,
            )
        )
        repositories: list[RegistryRepositoryEvidence] = []
        for repository_row in repository_rows:
            provider_repository_name = str(repository_row.get('name') or '').strip()
            if not provider_repository_name:
                continue
            repository_name = _repository_scope(project_name, provider_repository_name)
            artifact_rows = _all_pages(
                lambda page, page_size, project_name=project_name, repository_name=repository_name: client.list_artifacts(
                    project_name_or_id=project_name,
                    repository_name=repository_name,
                    page=page,
                    page_size=page_size,
                )
            )
            artifacts: list[RegistryArtifactEvidence] = []
            for artifact_row in artifact_rows:
                digest = str(artifact_row.get('digest') or '').strip()
                if not digest:
                    continue
                tags: list[RegistryTagEvidence] = []
                for tag_row in artifact_row.get('tags') or ():
                    if not isinstance(tag_row, dict):
                        continue
                    tag_name = str(tag_row.get('name') or '').strip()
                    if not tag_name:
                        continue
                    tags.append(
                        RegistryTagEvidence(
                            name=tag_name,
                            provider_native_id=_identifier(tag_row.get('id')),
                            push_time=_datetime(tag_row.get('push_time')),
                            pull_time=_datetime(tag_row.get('pull_time')),
                            metadata={
                                'immutable': tag_row.get('immutable'),
                                'signed': tag_row.get('signed'),
                            },
                        )
                    )
                artifacts.append(
                    RegistryArtifactEvidence(
                        digest=digest,
                        provider_native_id=_identifier(artifact_row.get('id')),
                        artifact_type=_identifier(artifact_row.get('type')),
                        media_type=_identifier(artifact_row.get('media_type')),
                        manifest_media_type=_identifier(artifact_row.get('manifest_media_type')),
                        size_bytes=_integer(artifact_row.get('size')),
                        push_time=_datetime(artifact_row.get('push_time')),
                        pull_time=_datetime(artifact_row.get('pull_time')),
                        tags=tuple(tags),
                        metadata={
                            'icon': artifact_row.get('icon'),
                            'annotations': artifact_row.get('annotations') or {},
                            'reference_count': len(artifact_row.get('references') or ()),
                            'accessory_count': len(artifact_row.get('accessories') or ()),
                        },
                    )
                )
            repositories.append(
                RegistryRepositoryEvidence(
                    name=repository_name,
                    provider_native_id=_identifier(repository_row.get('id')),
                    description=_identifier(repository_row.get('description')),
                    artifact_count=_integer(repository_row.get('artifact_count')),
                    pull_count=_integer(repository_row.get('pull_count')),
                    provider_created_at=_datetime(repository_row.get('creation_time')),
                    provider_updated_at=_datetime(repository_row.get('update_time')),
                    artifacts=tuple(artifacts),
                    metadata={'provider_name': provider_repository_name},
                )
            )
        metadata = project_row.get('metadata') if isinstance(project_row.get('metadata'), dict) else {}
        public_value = metadata.get('public')
        is_public = None if public_value is None else str(public_value).strip().lower() in {'true', '1', 'yes'}
        projects.append(
            RegistryProjectEvidence(
                name=project_name,
                provider_native_id=_identifier(project_row.get('project_id')),
                is_public=is_public,
                repository_count=_integer(project_row.get('repo_count')),
                provider_created_at=_datetime(project_row.get('creation_time')),
                provider_updated_at=_datetime(project_row.get('update_time')),
                repositories=tuple(repositories),
                metadata={
                    'owner_id': project_row.get('owner_id'),
                    'current_user_role_id': project_row.get('current_user_role_id'),
                    'registry_hosts': registry_hosts,
                },
            )
        )

    return RegistryInventoryEvidence(
        provider_key='harbor',
        integration_instance_id=source.integration_instance_id,
        observed_at=observed_at,
        projects=tuple(projects),
    )
