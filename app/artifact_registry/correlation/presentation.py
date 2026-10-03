from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload

from app.common.pagination import paginate_sequence
from app.models.cluster import Cluster
from app.models.inventory import PodInventory
from app.models.registry_artifact import RegistryArtifact, RegistryProject, RegistryRepository
from app.models.registry_correlation import RegistryCorrelationState, RegistryWorkloadBinding


def _freshness(value: datetime | None) -> dict[str, str]:
    if value is None:
        return {'label': 'Not Materialized', 'tone': 'unknown'}
    observed = value if value.tzinfo else value.replace(tzinfo=UTC)
    age = max((datetime.now(UTC) - observed.astimezone(UTC)).total_seconds(), 0)
    if age <= 3600:
        return {'label': 'Fresh', 'tone': 'normal'}
    if age <= 86400:
        return {'label': 'Aging', 'tone': 'warning'}
    return {'label': 'Stale', 'tone': 'critical'}


def _match_state(match_type: str, confidence: str) -> dict[str, str]:
    if match_type == 'digest':
        return {'label': 'Digest Match', 'tone': 'normal', 'confidence_label': 'Authoritative'}
    if match_type == 'tag_reference':
        return {'label': 'Tag Match', 'tone': 'warning', 'confidence_label': 'Weaker'}
    if match_type.startswith('ambiguous_'):
        return {'label': 'Ambiguous', 'tone': 'warning', 'confidence_label': 'No Canonical Match'}
    return {'label': 'Unmatched', 'tone': 'unknown', 'confidence_label': 'No Canonical Match'}


@dataclass(frozen=True, slots=True)
class RuntimeUsageFilters:
    query: str = ''
    match_type: str = ''
    cluster_id: str = ''
    artifact_id: int | None = None
    page: int = 1
    per_page: int = 5


def build_runtime_usage(filters: RuntimeUsageFilters) -> dict[str, Any]:
    state = RegistryCorrelationState.query.order_by(RegistryCorrelationState.id.asc()).first()
    query = RegistryWorkloadBinding.query.options(
        joinedload(RegistryWorkloadBinding.cluster),
        joinedload(RegistryWorkloadBinding.artifact)
        .joinedload(RegistryArtifact.repository)
        .joinedload(RegistryRepository.project)
        .joinedload(RegistryProject.integration_instance),
    ).order_by(
        RegistryWorkloadBinding.cluster_id,
        RegistryWorkloadBinding.namespace,
        RegistryWorkloadBinding.pod_name,
        RegistryWorkloadBinding.container_name,
    )
    bindings = query.all()
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        artifact = binding.artifact
        repository = artifact.repository if artifact is not None else None
        project = repository.project if repository is not None else None
        match = _match_state(binding.match_type, binding.confidence)
        rows.append(
            {
                'id': binding.id,
                'artifact_id': artifact.id if artifact is not None else None,
                'digest': artifact.digest if artifact is not None else binding.digest,
                'digest_short': (
                    artifact.digest
                    if artifact is not None and len(artifact.digest) <= 26
                    else (
                        f'{artifact.digest[:18]}…{artifact.digest[-7:]}'
                        if artifact is not None
                        else (binding.digest or 'No Digest')
                    )
                ),
                'repository_name': repository.name if repository is not None else (binding.repository_path or 'Unmatched'),
                'project_name': project.name if project is not None else 'No Canonical Project',
                'registry_source_name': project.integration_instance.name if project is not None else 'No Canonical Source',
                'provider_label': (
                    project.integration_instance.provider_key.replace('_', ' ').title()
                    if project is not None
                    else 'Unmatched'
                ),
                'cluster_id': binding.cluster_id,
                'cluster_name': binding.cluster.name,
                'cluster_environment': binding.cluster.environment,
                'namespace': binding.namespace,
                'pod_name': binding.pod_name,
                'workload_type': binding.workload_type or 'Standalone',
                'workload_name': binding.workload_name or 'Not Reported',
                'container_kind': binding.container_kind,
                'container_name': binding.container_name,
                'image_reference': binding.image_reference,
                'image_id': binding.image_id or 'Not Reported',
                'registry_host': binding.registry_host or 'Not Explicit',
                'tag': binding.tag or 'No Tag',
                'match_type': binding.match_type,
                'match': match,
                'candidate_count': binding.candidate_count,
                'registry_observed_at': binding.registry_observed_at,
                'kubernetes_observed_at': binding.kubernetes_observed_at,
                'correlated_at': binding.correlated_at,
            }
        )

    search = filters.query.strip().lower()
    filtered = [
        row
        for row in rows
        if (
            not search
            or search in ' '.join(
                str(row.get(key) or '')
                for key in (
                    'digest',
                    'repository_name',
                    'project_name',
                    'registry_source_name',
                    'cluster_name',
                    'namespace',
                    'workload_name',
                    'pod_name',
                    'container_name',
                    'image_reference',
                )
            ).lower()
        )
        and (not filters.match_type or row['match_type'] == filters.match_type)
        and (not filters.cluster_id or row['cluster_id'] == filters.cluster_id)
        and (filters.artifact_id is None or row['artifact_id'] == filters.artifact_id)
    ]
    page_rows, pagination = paginate_sequence(filtered, page=filters.page, per_page=filters.per_page)

    matched = [row for row in filtered if row['artifact_id'] is not None]
    artifact_count = RegistryArtifact.query.count()
    pod_inventory_count = PodInventory.query.count()
    return {
        'rows': page_rows,
        'pagination': pagination,
        'artifact_count': artifact_count,
        'pod_inventory_count': pod_inventory_count,
        'is_blocked': not bool(artifact_count and pod_inventory_count),
        'total': len(filtered),
        'state': state,
        'freshness': _freshness(state.observed_at if state is not None else None),
        'runtime_reference_count': state.runtime_reference_count if state is not None else 0,
        'digest_match_count': state.digest_match_count if state is not None else 0,
        'tag_match_count': state.tag_match_count if state is not None else 0,
        'ambiguous_count': state.ambiguous_count if state is not None else 0,
        'unmatched_count': state.unmatched_count if state is not None else 0,
        'cluster_count': len({row['cluster_id'] for row in matched}),
        'namespace_count': len({(row['cluster_id'], row['namespace']) for row in matched}),
        'workload_count': len(
            {
                (row['cluster_id'], row['namespace'], row['workload_type'], row['workload_name'])
                for row in matched
            }
        ),
        'pod_count': len({(row['cluster_id'], row['namespace'], row['pod_name']) for row in matched}),
        'clusters': [
            {'id': cluster.id, 'name': cluster.name}
            for cluster in Cluster.query.order_by(Cluster.name.asc()).all()
        ],
        'match_options': [
            {'value': 'digest', 'label': 'Digest Match'},
            {'value': 'tag_reference', 'label': 'Tag Match'},
            {'value': 'ambiguous_digest', 'label': 'Ambiguous Digest'},
            {'value': 'ambiguous_tag', 'label': 'Ambiguous Tag'},
            {'value': 'unmatched_digest', 'label': 'Unmatched Digest'},
            {'value': 'unmatched_tag', 'label': 'Unmatched Tag'},
            {'value': 'unmatched_reference', 'label': 'Unmatched Reference'},
        ],
        'artifact_filter': filters.artifact_id,
    }
