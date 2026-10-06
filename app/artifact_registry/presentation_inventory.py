from __future__ import annotations

from typing import Any

from sqlalchemy.orm import joinedload

from app.artifact_registry.presentation_common import _fmt_bytes, _overview_kpi_values, _state_view
from app.artifact_registry.presentation_overview import build_overview
from app.common.pagination import paginate_sequence
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
)


def _project_row(item: RegistryProject) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'public': item.public,
        'repository_count': item.repository_count if item.repository_count is not None else len(item.repositories),
        'provider': item.integration_instance_id,
        'provider_id': item.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _repository_row(item: RegistryRepository) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'project': item.project.name,
        'artifact_count': item.artifact_count if item.artifact_count is not None else len(item.artifacts),
        'pull_count': item.pull_count,
        'provider_id': item.project.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _artifact_row(item: RegistryArtifact) -> dict[str, Any]:
    return {
        'id': item.id,
        'digest': item.digest,
        'digest_short': item.digest if len(item.digest) <= 28 else f'{item.digest[:18]}…{item.digest[-8:]}',
        'repository': item.repository.name,
        'project': item.repository.project.name,
        'type': item.artifact_type or item.media_type or 'OCI Artifact',
        'size': _fmt_bytes(item.size_bytes),
        'tags': [tag.name for tag in item.tags],
        'push_time': item.push_time,
        'provider_id': item.repository.project.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _decorate_inventory_provider_provenance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provider_ids = {int(row['provider_id']) for row in rows if row.get('provider_id') is not None}
    providers = (
        IntegrationInstance.query.filter(IntegrationInstance.id.in_(sorted(provider_ids))).all() if provider_ids else []
    )
    provider_lookup = {int(provider.id): provider for provider in providers}
    for row in rows:
        provider_id = int(row['provider_id'])
        provider = provider_lookup.get(provider_id)
        metadata = provider.metadata_json if provider is not None and isinstance(provider.metadata_json, dict) else {}
        provider_key = str(provider.provider_key or 'registry') if provider is not None else 'registry'
        row['provider_name'] = provider.name if provider is not None else f'Registry #{provider_id}'
        row['provider_label'] = str(metadata.get('provider_label') or provider_key.replace('_', ' ').title())
        row['provider_environment'] = (
            str(provider.environment) if provider is not None and provider.environment else 'Not Set'
        )
    return rows


def _inventory_resource_catalog(overview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        'projects': {
            'key': 'projects',
            'title': 'Projects',
            'description': 'Provider-neutral Registry namespaces and visibility from committed snapshots.',
            'icon': 'folder-kanban',
            'count': overview['project_count'],
            'action_label': 'Browse Projects',
            'search_placeholder': 'Search projects or providers',
            'endpoint': 'artifact_registry.inventory_projects',
        },
        'repositories': {
            'key': 'repositories',
            'title': 'Repositories',
            'description': 'Committed repository catalogs linked to their Registry projects.',
            'icon': 'package-open',
            'count': overview['repository_count'],
            'action_label': 'Browse Repositories',
            'search_placeholder': 'Search repositories, projects, or providers',
            'endpoint': 'artifact_registry.inventory_repositories',
        },
        'artifacts': {
            'key': 'artifacts',
            'title': 'Artifacts',
            'description': 'Digest-oriented OCI identities with mutable tags and provider provenance.',
            'icon': 'fingerprint',
            'count': overview['artifact_count'],
            'action_label': 'Browse Artifacts',
            'search_placeholder': 'Search digests, repositories, tags, or providers',
            'endpoint': 'artifact_registry.inventory_artifacts',
        },
    }


def _inventory_snapshot_context(overview: dict[str, Any]) -> dict[str, Any]:
    provider_count = int(overview['provider_count'])
    snapshot_count = int(overview['snapshot_count'])
    stale_count = int(overview['stale_snapshot_count'])
    pending_count = int(overview['pending_snapshot_count'])
    failed_count = int(overview['failed_refresh_count'])
    exception_count = stale_count + pending_count + failed_count

    exception_parts: list[str] = []
    if stale_count:
        exception_parts.append(f'{stale_count} stale')
    if pending_count:
        exception_parts.append(f'{pending_count} pending')
    if failed_count:
        exception_parts.append(f'{failed_count} failed')

    if provider_count and snapshot_count == provider_count and not exception_count:
        coverage_tone = 'normal'
    elif snapshot_count:
        coverage_tone = 'warning'
    else:
        coverage_tone = 'unknown'

    return {
        'source_label': 'Committed Registry State',
        'status': overview['posture']['label'],
        'tone': overview['posture']['tone'],
        'description': ('KAORI reads committed provider-neutral Registry inventory.'),
        'latest_collected_at': overview['latest_committed_at'],
        'scope_label': overview['scope_label'],
        'coverage_label': (f'{snapshot_count} / {provider_count} Providers' if provider_count else 'No Providers'),
        'coverage_tone': coverage_tone,
        'coverage_supporting': 'Providers with committed evidence.',
        'exceptions_label': ' · '.join(exception_parts) if exception_parts else 'No Exceptions',
        'exceptions_tone': 'warning' if exception_count else 'normal',
        'exceptions_supporting': (
            'Stale, pending, or failed committed snapshot conditions.' if exception_count else 'No snapshot issues.'
        ),
        'exception_count': exception_count,
    }


def _inventory_fleet_readings(overview: dict[str, Any]) -> list[dict[str, str]]:
    provider_count = int(overview['provider_count'])
    snapshot_count = int(overview['snapshot_count'])
    exception_count = (
        int(overview['stale_snapshot_count'])
        + int(overview['pending_snapshot_count'])
        + int(overview['failed_refresh_count'])
    )
    project_count = int(overview['project_count'])
    visibility_observed = RegistryProject.query.filter(RegistryProject.public.is_not(None)).count()
    public_projects = RegistryProject.query.filter(RegistryProject.public.is_(True)).count()

    if provider_count == 0:
        coverage_title, coverage_tone = 'No Registry Providers', 'unknown'
        coverage_description = 'Register a Registry provider to establish committed inventory.'
    elif snapshot_count == provider_count:
        coverage_title, coverage_tone = f'{snapshot_count}/{provider_count} Providers Committed', 'normal'
        coverage_description = (
            'Every configured Registry provider has retained a committed inventory snapshot as current KAORI evidence.'
        )
    else:
        coverage_title, coverage_tone = f'{snapshot_count}/{provider_count} Providers Committed', 'warning'
        coverage_description = 'One or more Registry providers still require a committed inventory snapshot.'

    if exception_count:
        exception_title, exception_tone = f'{exception_count} Snapshot Attention', 'warning'
        exception_description = 'Review stale, pending, or failed Registry inventory conditions.'
    else:
        exception_title, exception_tone = 'No Snapshot Attention', 'normal'
        exception_description = 'No stale, pending, or failed committed Registry snapshot condition is active.'

    if project_count == 0:
        visibility_title, visibility_tone = 'No Visibility Evidence', 'unknown'
        visibility_description = 'No committed Registry projects are available for visibility assessment.'
    elif visibility_observed < project_count:
        visibility_title, visibility_tone = f'{visibility_observed}/{project_count} Visibility Observed', 'warning'
        visibility_description = (
            f'{public_projects} public project(s); remaining project visibility still requires provider evidence.'
        )
    else:
        visibility_title, visibility_tone = f'{visibility_observed}/{project_count} Visibility Observed', 'normal'
        visibility_description = (
            f'Project visibility evidence is complete; {public_projects} project(s) are declared public.'
        )

    return [
        {
            'title': coverage_title,
            'description': coverage_description,
            'icon': 'database-backup',
            'tone': coverage_tone,
        },
        {
            'title': exception_title,
            'description': exception_description,
            'icon': 'triangle-alert',
            'tone': exception_tone,
        },
        {
            'title': visibility_title,
            'description': visibility_description,
            'icon': 'globe-2',
            'tone': visibility_tone,
        },
    ]


def _inventory_base_context() -> dict[str, Any]:
    overview = build_overview()
    counts = _overview_kpi_values(None)
    overview = {
        **overview,
        'project_count': counts['projects'],
        'repository_count': counts['repositories'],
        'artifact_count': counts['artifacts'],
    }
    resource_catalog = _inventory_resource_catalog(overview)
    return {
        'setup': overview['setup'],
        'overview': overview,
        'snapshot_context': _inventory_snapshot_context(overview),
        'fleet_readings': _inventory_fleet_readings(overview),
        'asset_catalog': list(resource_catalog.values()),
        'resource_catalog': resource_catalog,
    }


def build_inventory_overview() -> dict[str, Any]:
    return _inventory_base_context()


def _inventory_resource_posture_metrics(
    resource: str,
    rows: list[dict[str, Any]],
) -> list[tuple[str, str, Any, str, str]]:
    provider_count = len({int(row['provider_id']) for row in rows if row.get('provider_id') is not None})

    if resource == 'repositories':
        artifact_count = sum(int(row.get('artifact_count') or 0) for row in rows)
        pull_evidence_count = sum(row.get('pull_count') is not None for row in rows)
        return [
            (
                'package-open',
                'Repositories',
                len(rows),
                'Committed repositories in the current inventory.',
                'brand',
            ),
            (
                'database-backup',
                'Registry Sources',
                provider_count,
                'Registry providers contributing committed repository evidence.',
                'brand',
            ),
            (
                'fingerprint',
                'Artifacts',
                artifact_count,
                'Committed artifact identities referenced by repository inventory.',
                'brand',
            ),
            (
                'activity',
                'Pull Counts Observed',
                pull_evidence_count,
                'Repositories with committed provider pull-count evidence.',
                'info' if pull_evidence_count else 'unknown',
            ),
        ]

    if resource == 'artifacts':
        tagged_artifacts = sum(bool(row.get('tags')) for row in rows)
        untagged_artifacts = max(len(rows) - tagged_artifacts, 0)
        return [
            (
                'fingerprint',
                'Artifacts',
                len(rows),
                'Committed digest-oriented Registry artifact identities.',
                'brand',
            ),
            (
                'database-backup',
                'Registry Sources',
                provider_count,
                'Registry providers contributing committed artifact evidence.',
                'brand',
            ),
            (
                'tags',
                'Tagged Artifacts',
                tagged_artifacts,
                'Artifacts with one or more committed mutable tag references.',
                'info' if tagged_artifacts else 'unknown',
            ),
            (
                'tag',
                'Untagged Artifacts',
                untagged_artifacts,
                'Committed artifacts without a current tag reference.',
                'info' if untagged_artifacts else 'normal',
            ),
        ]

    public_projects = sum(row.get('public') is True for row in rows)
    visibility_missing = sum(row.get('public') is None for row in rows)
    return [
        (
            'folder-kanban',
            'Projects',
            len(rows),
            'Committed Registry project identities.',
            'brand',
        ),
        (
            'database-backup',
            'Registry Sources',
            provider_count,
            'Registry providers contributing committed project evidence.',
            'brand',
        ),
        (
            'globe-2',
            'Public Projects',
            public_projects,
            'Projects marked public by provider evidence.',
            'info' if public_projects else 'normal',
        ),
        (
            'circle-help',
            'Visibility Not Observed',
            visibility_missing,
            'Projects without committed visibility evidence.',
            'warning' if visibility_missing else 'normal',
        ),
    ]


def _inventory_rows(resource: str) -> list[dict[str, Any]]:
    if resource == 'repositories':
        items = RegistryRepository.query.options(
            joinedload(RegistryRepository.project),
            joinedload(RegistryRepository.artifacts),
        ).all()
        rows = [_repository_row(item) for item in items]
    elif resource == 'artifacts':
        items = RegistryArtifact.query.options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            joinedload(RegistryArtifact.tags),
        ).all()
        rows = [_artifact_row(item) for item in items]
    else:
        items = RegistryProject.query.options(joinedload(RegistryProject.repositories)).all()
        rows = [_project_row(item) for item in items]
    return _decorate_inventory_provider_provenance(rows)


def _inventory_filter_options(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    source_lookup: dict[int, dict[str, Any]] = {}
    for row in rows:
        provider_id = int(row['provider_id'])
        source_lookup.setdefault(
            provider_id,
            {
                'id': provider_id,
                'name': row['provider_name'],
                'provider_label': row['provider_label'],
                'environment': row['provider_environment'],
            },
        )
    source_options = sorted(
        source_lookup.values(),
        key=lambda item: (str(item['name']).lower(), int(item['id'])),
    )
    environment_options = sorted(
        {str(row['provider_environment']) for row in rows if str(row.get('provider_environment') or '').strip()},
        key=str.lower,
    )
    return source_options, environment_options


def _inventory_scope_filter(
    rows: list[dict[str, Any]],
    *,
    resource: str,
    source_id: int | None,
    environment: str,
    visibility: str,
) -> list[dict[str, Any]]:
    filtered = rows
    if source_id is not None:
        filtered = [row for row in filtered if int(row['provider_id']) == int(source_id)]
    if environment:
        filtered = [
            row for row in filtered if str(row['provider_environment']).lower() == environment.lower()
        ]
    if resource != 'projects':
        return filtered
    visibility_predicates = {
        'public': lambda row: row['public'] is True,
        'private': lambda row: row['public'] is False,
        'not_observed': lambda row: row['public'] is None,
    }
    predicate = visibility_predicates.get(visibility)
    return [row for row in filtered if predicate(row)] if predicate is not None else filtered


def _inventory_search_text(resource: str, row: dict[str, Any]) -> str:
    if resource == 'repositories':
        return (
            f'{row["name"]} {row["project"]} {row["provider_name"]} '
            f'{row["provider_label"]} {row["provider_environment"]}'
        ).lower()
    if resource == 'artifacts':
        return (
            f'{row["digest"]} {row["repository"]} {row["project"]} '
            f'{" ".join(row["tags"])} {row["provider_name"]} '
            f'{row["provider_label"]} {row["provider_environment"]}'
        ).lower()
    return (
        f'{row["name"]} {row["provider_name"]} {row["provider_label"]} '
        f'{row["provider_environment"]}'
    ).lower()


def _inventory_posture_copy(resource: str) -> dict[str, str]:
    return {
        'projects': {
            'title': 'Project Inventory Posture',
            'intro': 'Review committed project coverage, Registry-source participation, and visibility evidence.',
            'description': 'Committed project catalog posture across the current Artifact Registry inventory.',
        },
        'repositories': {
            'title': 'Repository Inventory Posture',
            'intro': 'Review committed repository coverage, Registry-source participation, and catalog evidence.',
            'description': 'Committed repository catalog posture across the current Artifact Registry inventory.',
        },
        'artifacts': {
            'title': 'Artifact Inventory Posture',
            'intro': 'Review committed artifact coverage, Registry-source participation, and tag evidence.',
            'description': 'Committed artifact catalog posture across the current Artifact Registry inventory.',
        },
    }[resource]


def _inventory_empty_description(
    *,
    has_filters: bool,
    snapshot_count: int,
    resource_title: str,
) -> str:
    if has_filters:
        return f'No committed {resource_title.lower()} match the active filters.'
    if snapshot_count == 0:
        return 'Run Artifact Registry inventory sync after the Registry provider read contract is eligible.'
    return f'The current committed Registry snapshot contains no {resource_title.lower()}.'


def build_inventory(
    *,
    resource: str,
    page: int,
    per_page: int,
    search: str = '',
    source_id: int | None = None,
    environment: str = '',
    visibility: str = '',
) -> dict[str, Any]:
    resource = resource if resource in {'projects', 'repositories', 'artifacts'} else 'projects'
    search_value = search.strip().lower()
    environment_value = environment.strip()
    visibility_value = visibility.strip().lower()
    if visibility_value not in {'public', 'private', 'not_observed'}:
        visibility_value = ''

    rows = _inventory_rows(resource)
    source_options, environment_options = _inventory_filter_options(rows)
    resource_posture_metrics = _inventory_resource_posture_metrics(resource, rows)
    rows = _inventory_scope_filter(
        rows,
        resource=resource,
        source_id=source_id,
        environment=environment_value,
        visibility=visibility_value,
    )
    filtered = [
        row for row in rows if not search_value or search_value in _inventory_search_text(resource, row)
    ]
    paged, pagination = paginate_sequence(filtered, page=page, per_page=per_page)
    context = _inventory_base_context()
    selected_resource = context['resource_catalog'][resource]
    posture_copy = _inventory_posture_copy(resource)
    has_filters = bool(
        search_value or source_id is not None or environment_value or (resource == 'projects' and visibility_value)
    )
    filter_query: dict[str, Any] = {
        'q': search,
        'source_id': source_id,
        'environment': environment_value,
    }
    if resource == 'projects':
        filter_query['visibility'] = visibility_value

    return {
        **context,
        'resource': resource,
        'resource_label': selected_resource['title'],
        'resource_icon': selected_resource['icon'],
        'resource_description': selected_resource['description'],
        'resource_endpoint': selected_resource['endpoint'],
        'search_placeholder': selected_resource['search_placeholder'],
        'rows': paged,
        'pagination': pagination,
        'search': search,
        'total': len(filtered),
        'empty_description': _inventory_empty_description(
            has_filters=has_filters,
            snapshot_count=int(context['overview']['snapshot_count']),
            resource_title=selected_resource['title'],
        ),
        'filters': {
            'source_id': source_id,
            'environment': environment_value,
            'visibility': visibility_value,
        },
        'filter_query': filter_query,
        'has_filters': has_filters,
        'source_options': source_options,
        'environment_options': environment_options,
        'resource_posture_metrics': resource_posture_metrics,
        'resource_posture_title': posture_copy['title'],
        'resource_posture_intro': posture_copy['intro'],
        'resource_posture_description': posture_copy['description'],
        'visibility_options': (
            [
                {'value': 'public', 'label': 'Public'},
                {'value': 'private', 'label': 'Private'},
                {'value': 'not_observed', 'label': 'Not Observed'},
            ]
            if resource == 'projects'
            else []
        ),
    }

def build_inventory_project_detail(project_id: int) -> dict[str, Any] | None:
    project = (
        RegistryProject.query.options(joinedload(RegistryProject.repositories).joinedload(RegistryRepository.artifacts))
        .filter(RegistryProject.id == int(project_id))
        .first()
    )
    if project is None:
        return None

    provider = IntegrationInstance.query.filter(IntegrationInstance.id == int(project.integration_instance_id)).first()
    state = RegistryCollectionState.query.filter(
        RegistryCollectionState.integration_instance_id == int(project.integration_instance_id)
    ).first()
    snapshot = _state_view(state)
    provider_metadata = dict(project.provider_metadata) if isinstance(project.provider_metadata, dict) else {}

    if project.public is True:
        visibility_state = {'label': 'Public', 'tone': 'info', 'icon': 'globe-2'}
    elif project.public is False:
        visibility_state = {'label': 'Private', 'tone': 'normal', 'icon': 'lock-keyhole'}
    else:
        visibility_state = {'label': 'Not Observed', 'tone': 'unknown', 'icon': 'circle-help'}

    repositories = [
        {
            'id': int(repository.id),
            'name': repository.name,
            'artifact_count': (
                int(repository.artifact_count) if repository.artifact_count is not None else len(repository.artifacts)
            ),
            'pull_count': repository.pull_count,
            'observed_at': repository.observed_at,
        }
        for repository in sorted(project.repositories, key=lambda item: item.name.lower())
    ]

    provider_key = str(provider.provider_key or 'registry') if provider is not None else 'registry'
    metadata = provider.metadata_json if provider is not None and isinstance(provider.metadata_json, dict) else {}

    return {
        'id': int(project.id),
        'name': project.name,
        'provider_native_id': project.provider_native_id or 'Not Collected',
        'visibility': visibility_state,
        'repository_count': (
            int(project.repository_count) if project.repository_count is not None else len(project.repositories)
        ),
        'provider_id': int(project.integration_instance_id),
        'provider_name': (provider.name if provider is not None else f'Registry #{project.integration_instance_id}'),
        'provider_label': str(metadata.get('provider_label') or provider_key.replace('_', ' ').title()),
        'provider_environment': (
            str(provider.environment) if provider is not None and provider.environment else 'Not Set'
        ),
        'observed_at': project.observed_at,
        'snapshot': snapshot,
        'repositories': repositories,
        'repository_preview': repositories[:25],
        'repository_truncated': len(repositories) > 25,
        'provider_metadata': provider_metadata,
    }


def _inventory_detail_provider_context(integration_instance_id: int) -> dict[str, Any]:
    provider = IntegrationInstance.query.filter(IntegrationInstance.id == int(integration_instance_id)).first()
    state = RegistryCollectionState.query.filter(
        RegistryCollectionState.integration_instance_id == int(integration_instance_id)
    ).first()
    metadata = provider.metadata_json if provider is not None and isinstance(provider.metadata_json, dict) else {}
    provider_key = str(provider.provider_key or 'registry') if provider is not None else 'registry'
    return {
        'provider_id': int(integration_instance_id),
        'provider_name': (provider.name if provider is not None else f'Registry #{integration_instance_id}'),
        'provider_label': str(metadata.get('provider_label') or provider_key.replace('_', ' ').title()),
        'provider_environment': (
            str(provider.environment) if provider is not None and provider.environment else 'Not Set'
        ),
        'snapshot': _state_view(state),
    }


def build_inventory_repository_detail(repository_id: int) -> dict[str, Any] | None:
    repository = (
        RegistryRepository.query.options(
            joinedload(RegistryRepository.project),
            joinedload(RegistryRepository.artifacts).joinedload(RegistryArtifact.tags),
        )
        .filter(RegistryRepository.id == int(repository_id))
        .first()
    )
    if repository is None:
        return None

    source = _inventory_detail_provider_context(repository.project.integration_instance_id)
    artifacts = [
        {
            'id': int(artifact.id),
            'digest': artifact.digest,
            'digest_short': (
                artifact.digest if len(artifact.digest) <= 32 else f'{artifact.digest[:20]}…{artifact.digest[-10:]}'
            ),
            'type': artifact.artifact_type or artifact.media_type or 'OCI Artifact',
            'size': _fmt_bytes(artifact.size_bytes),
            'tag_count': len(artifact.tags),
            'tags': [tag.name for tag in artifact.tags[:3]],
            'observed_at': artifact.observed_at,
        }
        for artifact in sorted(repository.artifacts, key=lambda item: item.digest)
    ]
    provider_metadata = dict(repository.provider_metadata) if isinstance(repository.provider_metadata, dict) else {}
    return {
        'id': int(repository.id),
        'name': repository.name,
        'provider_native_id': repository.provider_native_id or 'Not Collected',
        'description': repository.description or 'No provider description collected.',
        'project_id': int(repository.project.id),
        'project_name': repository.project.name,
        'artifact_count': (
            int(repository.artifact_count) if repository.artifact_count is not None else len(repository.artifacts)
        ),
        'pull_count': repository.pull_count,
        'provider_created_at': repository.provider_created_at,
        'provider_updated_at': repository.provider_updated_at,
        'observed_at': repository.observed_at,
        'artifacts': artifacts,
        'artifact_preview': artifacts[:25],
        'artifact_truncated': len(artifacts) > 25,
        'provider_metadata': provider_metadata,
        **source,
    }


def build_inventory_artifact_detail(artifact_id: int) -> dict[str, Any] | None:
    artifact = (
        RegistryArtifact.query.options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            joinedload(RegistryArtifact.tags),
        )
        .filter(RegistryArtifact.id == int(artifact_id))
        .first()
    )
    if artifact is None:
        return None

    repository = artifact.repository
    project = repository.project
    source = _inventory_detail_provider_context(project.integration_instance_id)
    tags = [
        {
            'id': int(tag.id),
            'name': tag.name,
            'provider_native_id': tag.provider_native_id or 'Not Collected',
            'push_time': tag.push_time,
            'pull_time': tag.pull_time,
            'observed_at': tag.observed_at,
        }
        for tag in sorted(artifact.tags, key=lambda item: item.name.lower())
    ]
    provider_metadata = dict(artifact.provider_metadata) if isinstance(artifact.provider_metadata, dict) else {}
    return {
        'id': int(artifact.id),
        'digest': artifact.digest,
        'digest_short': (
            artifact.digest if len(artifact.digest) <= 40 else f'{artifact.digest[:24]}…{artifact.digest[-12:]}'
        ),
        'digest_algorithm': artifact.digest_algorithm or 'unknown',
        'provider_native_id': artifact.provider_native_id or 'Not Collected',
        'type': artifact.artifact_type or 'Not Collected',
        'media_type': artifact.media_type or 'Not Collected',
        'size_bytes': artifact.size_bytes,
        'size': _fmt_bytes(artifact.size_bytes),
        'push_time': artifact.push_time,
        'pull_time': artifact.pull_time,
        'observed_at': artifact.observed_at,
        'repository_id': int(repository.id),
        'repository_name': repository.name,
        'project_id': int(project.id),
        'project_name': project.name,
        'tag_count': len(tags),
        'tags': tags,
        'tag_preview': tags[:25],
        'tag_truncated': len(tags) > 25,
        'provider_metadata': provider_metadata,
        **source,
    }
