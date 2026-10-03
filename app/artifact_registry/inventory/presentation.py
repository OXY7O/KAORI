from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload

from app.common.pagination import paginate_sequence
from app.models.integration import IntegrationInstance
from app.models.registry_security import RegistrySecurityCollectionState
from app.models.registry_artifact import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
)


def _age_state(observed_at: datetime | None) -> dict[str, str]:
    if observed_at is None:
        return {'label': 'Not Collected', 'tone': 'unknown'}
    value = observed_at if observed_at.tzinfo is not None else observed_at.replace(tzinfo=UTC)
    age_seconds = max((datetime.now(UTC) - value.astimezone(UTC)).total_seconds(), 0)
    if age_seconds <= 3600:
        return {'label': 'Fresh', 'tone': 'normal'}
    if age_seconds <= 86400:
        return {'label': 'Aging', 'tone': 'warning'}
    return {'label': 'Stale', 'tone': 'critical'}


def _format_bytes(value: int | None) -> str:
    if value is None:
        return 'Not Observed'
    size = float(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if size < 1024 or unit == 'TiB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{int(size)} B'
        size /= 1024
    return f'{int(value)} B'


def _source_instances() -> list[IntegrationInstance]:
    return (
        IntegrationInstance.query.filter(IntegrationInstance.integration_type == 'registry')
        .order_by(IntegrationInstance.name.asc())
        .all()
    )


def _setup_state(instances: list[IntegrationInstance]) -> dict[str, Any]:
    ready = [item for item in instances if item.enabled and item.readiness_status in {'ready', 'degraded'}]
    return {
        'is_blocked': not instances,
        'registered_count': len(instances),
        'ready_count': len(ready),
        'validation_required_count': sum(
            1 for item in instances if item.readiness_status not in {'ready', 'degraded'}
        ),
    }


def _snapshot(instances: list[IntegrationInstance]) -> dict[str, Any]:
    ids = [item.id for item in instances]
    states = (
        RegistryCollectionState.query.filter(RegistryCollectionState.integration_instance_id.in_(ids)).all()
        if ids
        else []
    )
    latest = max((item.observed_at for item in states if item.observed_at), default=None)
    collected = sum(1 for item in states if item.status == 'collected')
    failed = sum(1 for item in states if item.status == 'failed')
    return {
        'source_count': len(instances),
        'collected_source_count': collected,
        'failed_source_count': failed,
        'latest_observed_at': latest,
        'freshness': _age_state(latest),
        'states': states,
    }


def build_overview() -> dict[str, Any]:
    instances = _source_instances()
    projects = RegistryProject.query.count()
    repositories = RegistryRepository.query.count()
    artifacts = RegistryArtifact.query.count()
    tag_count = sum(len(item.tags) for item in RegistryArtifact.query.options(joinedload(RegistryArtifact.tags)).all())
    security_states = RegistrySecurityCollectionState.query.all()
    provider_distribution: dict[str, int] = {}
    for instance in instances:
        provider_distribution[instance.provider_key] = provider_distribution.get(instance.provider_key, 0) + 1
    return {
        'setup': _setup_state(instances),
        'snapshot': _snapshot(instances),
        'provider_count': len(instances),
        'ready_provider_count': sum(
            1 for item in instances if item.enabled and item.readiness_status in {'ready', 'degraded'}
        ),
        'project_count': projects,
        'repository_count': repositories,
        'artifact_count': artifacts,
        'tag_count': tag_count,
        'security': {
            'finding_count': sum(item.finding_count for item in security_states),
            'critical_count': sum(item.critical_count for item in security_states),
            'high_count': sum(item.high_count for item in security_states),
            'scanned_artifact_count': sum(item.scanned_artifact_count for item in security_states),
            'signature_observed_count': sum(item.signature_observed_count for item in security_states),
            'sbom_observed_count': sum(item.sbom_observed_count for item in security_states),
            'latest_observed_at': max(
                (item.observed_at for item in security_states if item.observed_at),
                default=None,
            ),
        },
        'provider_distribution': [
            {'key': key, 'label': key.replace('_', ' ').title(), 'count': count}
            for key, count in sorted(provider_distribution.items())
        ],
    }


@dataclass(frozen=True, slots=True)
class RegistryInventoryFilters:
    query: str = ''
    provider: str = ''
    source_id: int | None = None
    page: int = 1
    per_page: int = 5


def _filter_options(instances: list[IntegrationInstance]) -> dict[str, Any]:
    return {
        'sources': [
            {'id': item.id, 'name': item.name, 'provider_key': item.provider_key}
            for item in instances
        ],
        'providers': [
            {'value': value, 'label': value.replace('_', ' ').title()}
            for value in sorted({item.provider_key for item in instances if item.provider_key})
        ],
    }


def build_projects(filters: RegistryInventoryFilters) -> dict[str, Any]:
    instances = _source_instances()
    rows = []
    for item in RegistryProject.query.options(joinedload(RegistryProject.integration_instance)).all():
        source = item.integration_instance
        row = {
            'id': item.id,
            'name': item.name,
            'source_id': source.id,
            'source_name': source.name,
            'provider_key': source.provider_key,
            'provider_label': source.provider_key.replace('_', ' ').title(),
            'is_public': item.is_public,
            'repository_count': item.repository_count,
            'observed_at': item.observed_at,
            'freshness': _age_state(item.observed_at),
        }
        rows.append(row)
    return _filtered_result(rows, filters, instances, searchable=('name', 'source_name', 'provider_label'))


def build_repositories(filters: RegistryInventoryFilters) -> dict[str, Any]:
    instances = _source_instances()
    rows = []
    query = RegistryRepository.query.options(
        joinedload(RegistryRepository.project).joinedload(RegistryProject.integration_instance)
    )
    for item in query.all():
        project = item.project
        source = project.integration_instance
        rows.append(
            {
                'id': item.id,
                'name': item.name,
                'project_name': project.name,
                'source_id': source.id,
                'source_name': source.name,
                'provider_key': source.provider_key,
                'provider_label': source.provider_key.replace('_', ' ').title(),
                'artifact_count': item.artifact_count,
                'pull_count': item.pull_count,
                'observed_at': item.observed_at,
                'freshness': _age_state(item.observed_at),
            }
        )
    return _filtered_result(
        rows,
        filters,
        instances,
        searchable=('name', 'project_name', 'source_name', 'provider_label'),
    )


def build_artifacts(filters: RegistryInventoryFilters) -> dict[str, Any]:
    instances = _source_instances()
    rows = []
    query = RegistryArtifact.query.options(
        joinedload(RegistryArtifact.tags),
        joinedload(RegistryArtifact.repository)
        .joinedload(RegistryRepository.project)
        .joinedload(RegistryProject.integration_instance),
    )
    for item in query.all():
        repository = item.repository
        project = repository.project
        source = project.integration_instance
        tags = [tag.name for tag in item.tags]
        rows.append(
            {
                'id': item.id,
                'digest': item.digest,
                'digest_short': item.digest if len(item.digest) <= 26 else f'{item.digest[:18]}…{item.digest[-7:]}',
                'repository_name': repository.name,
                'project_name': project.name,
                'source_id': source.id,
                'source_name': source.name,
                'provider_key': source.provider_key,
                'provider_label': source.provider_key.replace('_', ' ').title(),
                'artifact_type': item.artifact_type or 'OCI Artifact',
                'size_bytes': item.size_bytes,
                'size_label': _format_bytes(item.size_bytes),
                'push_time': item.push_time,
                'tags': tags,
                'tag_label': ', '.join(tags[:3]) if tags else 'Untagged',
                'observed_at': item.observed_at,
                'freshness': _age_state(item.observed_at),
            }
        )
    return _filtered_result(
        rows,
        filters,
        instances,
        searchable=('digest', 'repository_name', 'project_name', 'source_name', 'provider_label', 'tag_label'),
    )


def _filtered_result(
    rows: list[dict[str, Any]],
    filters: RegistryInventoryFilters,
    instances: list[IntegrationInstance],
    *,
    searchable: tuple[str, ...],
) -> dict[str, Any]:
    query = filters.query.strip().lower()
    filtered = [
        row
        for row in rows
        if (
            not query
            or query in ' '.join(str(row.get(key) or '') for key in searchable).lower()
        )
        and (not filters.provider or row['provider_key'] == filters.provider)
        and (filters.source_id is None or row['source_id'] == filters.source_id)
    ]
    page_rows, pagination = paginate_sequence(filtered, page=filters.page, per_page=filters.per_page)
    return {
        'rows': page_rows,
        'pagination': pagination,
        'total': len(filtered),
        'setup': _setup_state(instances),
        'snapshot': _snapshot(instances),
        **_filter_options(instances),
    }
