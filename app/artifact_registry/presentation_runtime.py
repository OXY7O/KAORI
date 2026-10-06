from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.artifact_registry.correlation_sync_jobs import correlation_prerequisites
from app.artifact_registry.presentation_common import FRESHNESS_HOURS, _aware_datetime, _providers
from app.artifact_registry.presentation_inventory import _inventory_detail_provider_context
from app.artifact_registry.security.contracts import registry_scan_evidence_ready
from app.common.pagination import paginate_query
from app.models.cluster import Cluster
from app.models.job import JobExecution
from app.models.registry import (
    RegistryArtifact,
    RegistryProject,
    RegistryRepository,
    RegistryWorkloadBinding,
)


def _runtime_match_state(match_type: str, confidence: str) -> dict[str, str]:
    if str(match_type or '').lower() == 'digest':
        return {
            'label': 'Digest Match',
            'tone': 'normal',
            'confidence': 'Strong',
            'description': 'Immutable digest identity match.',
        }
    return {
        'label': 'Tag Match',
        'tone': 'warning',
        'confidence': str(confidence or 'medium').replace('_', ' ').title(),
        'description': 'Mutable reference; lower confidence.',
    }


def _runtime_security_state(
    scan_status: str | None,
    summary: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = summary if isinstance(summary, dict) else {}
    critical = int(normalized.get('critical') or 0)
    high = int(normalized.get('high') or 0)
    if critical:
        label, tone = f'{critical} Critical', 'critical'
    elif high:
        label, tone = f'{high} High', 'warning'
    elif registry_scan_evidence_ready(scan_status):
        label, tone = 'No Critical/High', 'normal'
    else:
        label, tone = 'Not Scanned', 'unknown'
    return {
        'critical': critical,
        'high': high,
        'label': label,
        'tone': tone,
        'exposed': bool(critical or high),
        'scanned': registry_scan_evidence_ready(scan_status),
    }


def _runtime_security_index() -> tuple[dict[int, dict[str, Any]], set[int], set[int], set[int]]:
    security_by_artifact: dict[int, dict[str, Any]] = {}
    critical_ids: set[int] = set()
    high_ids: set[int] = set()
    scanned_ids: set[int] = set()
    rows = RegistryArtifact.query.with_entities(
        RegistryArtifact.id,
        RegistryArtifact.scan_status,
        RegistryArtifact.vulnerability_summary,
    ).all()
    for artifact_id, scan_status, vulnerability_summary in rows:
        state = _runtime_security_state(scan_status, vulnerability_summary)
        normalized_id = int(artifact_id)
        security_by_artifact[normalized_id] = state
        if state['critical']:
            critical_ids.add(normalized_id)
        if state['high']:
            high_ids.add(normalized_id)
        if state['scanned']:
            scanned_ids.add(normalized_id)
    return security_by_artifact, critical_ids, high_ids, scanned_ids


def _runtime_parse_observed_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _runtime_prerequisite_guidance(
    prerequisites: dict[str, int | bool],
    *,
    has_committed_snapshot: bool,
) -> dict[str, Any]:
    eligible = bool(prerequisites.get('eligible'))
    missing_registry = int(prerequisites.get('artifact_count') or 0) == 0
    missing_kubernetes = int(prerequisites.get('pod_count') or 0) == 0
    review_step = 'Review Updated Bindings' if has_committed_snapshot else 'Review Committed Bindings'

    if missing_registry and missing_kubernetes:
        title = 'Committed Inventories Required'
        description = (
            'Runtime correlation requires committed Artifact Registry artifacts and '
            'current Kubernetes Pod inventory before the first materialization.'
        )
        refresh_description = (
            'Runtime Usage remains readable; refresh requires current Registry and Kubernetes inventory.'
        )
        steps = [
            'Sync Artifact Registry Inventory',
            'Sync Kubernetes Inventory',
            'Run Runtime Correlation',
            review_step,
        ]
        action_endpoint = 'artifact_registry.inventory'
        action_label = 'Open Registry Inventory'
        action_icon = 'package-open'
        action_permission = 'artifact_registry.view'
    elif missing_registry:
        title = 'Registry Inventory Required'
        description = (
            'Runtime correlation requires committed Artifact Registry artifacts before the first materialization.'
        )
        refresh_description = 'Runtime Usage remains readable; refresh requires current Registry inventory.'
        steps = [
            'Sync Artifact Registry Inventory',
            'Run Runtime Correlation',
            review_step,
        ]
        action_endpoint = 'artifact_registry.inventory'
        action_label = 'Open Registry Inventory'
        action_icon = 'package-open'
        action_permission = 'artifact_registry.view'
    elif missing_kubernetes:
        title = 'Kubernetes Inventory Required'
        description = (
            'Runtime correlation requires a current committed Kubernetes Pod inventory '
            'generation before the first materialization.'
        )
        refresh_description = 'Runtime Usage remains readable; refresh requires current Kubernetes Pod inventory.'
        steps = [
            'Sync Kubernetes Inventory',
            'Run Runtime Correlation',
            review_step,
        ]
        action_endpoint = 'inventory.overview'
        action_label = 'Open Kubernetes Inventory'
        action_icon = 'boxes'
        action_permission = 'inventory.view'
    else:
        title = 'Correlation Prerequisites Ready'
        description = 'Committed Registry and Kubernetes evidence is ready for correlation.'
        refresh_description = description
        steps = []
        action_endpoint = None
        action_label = None
        action_icon = 'waypoints'
        action_permission = None

    return {
        'is_blocked': bool(not eligible and not has_committed_snapshot),
        'refresh_blocked': bool(not eligible and has_committed_snapshot),
        'missing_registry': missing_registry,
        'missing_kubernetes': missing_kubernetes,
        'title': title,
        'description': description,
        'refresh_description': refresh_description,
        'steps': steps,
        'action_endpoint': action_endpoint,
        'action_label': action_label,
        'action_icon': action_icon,
        'action_permission': action_permission,
    }


@dataclass(frozen=True, slots=True)
class RuntimeUsageRequest:
    search: Any = ''
    source_id: int | None = None
    cluster_id: str = ''
    namespace: str = ''
    match_type: str = ''
    exposure: str = ''
    artifact_id: int | None = None
    page: int = 1
    per_page: int = 5


def _runtime_usage_request(kwargs: dict[str, Any]) -> RuntimeUsageRequest:
    allowed = {
        'search',
        'source_id',
        'cluster_id',
        'namespace',
        'match_type',
        'exposure',
        'artifact_id',
        'page',
        'per_page',
    }
    unknown = sorted(set(kwargs) - allowed)
    if unknown:
        joined = ', '.join(unknown)
        raise TypeError(f'Unexpected runtime usage argument(s): {joined}')
    return RuntimeUsageRequest(
        search=kwargs.get('search', ''),
        source_id=kwargs.get('source_id'),
        cluster_id=kwargs.get('cluster_id', ''),
        namespace=kwargs.get('namespace', ''),
        match_type=kwargs.get('match_type', ''),
        exposure=kwargs.get('exposure', ''),
        artifact_id=kwargs.get('artifact_id'),
        page=kwargs.get('page', 1),
        per_page=kwargs.get('per_page', 5),
    )


def _runtime_filtered_query(
    request: RuntimeUsageRequest,
    *,
    sources: list[Any],
    critical_ids: set[int],
    high_ids: set[int],
    scanned_ids: set[int],
) -> tuple[Any, dict[str, str]]:
    filters = {
        'search': str(request.search or '').strip().lower(),
        'cluster': str(request.cluster_id or '').strip(),
        'namespace': str(request.namespace or '').strip(),
        'match': str(request.match_type or '').strip().lower(),
        'exposure': str(request.exposure or '').strip().lower(),
    }
    query = (
        RegistryWorkloadBinding.query.join(
            RegistryArtifact,
            RegistryWorkloadBinding.artifact_id == RegistryArtifact.id,
        )
        .join(
            RegistryRepository,
            RegistryArtifact.repository_id == RegistryRepository.id,
        )
        .join(
            RegistryProject,
            RegistryRepository.project_id == RegistryProject.id,
        )
        .outerjoin(Cluster, RegistryWorkloadBinding.cluster_id == Cluster.id)
        .options(
            joinedload(RegistryWorkloadBinding.artifact)
            .joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project)
        )
    )
    if request.source_id is not None:
        query = query.filter(RegistryProject.integration_instance_id == int(request.source_id))
    if filters['cluster']:
        query = query.filter(RegistryWorkloadBinding.cluster_id == filters['cluster'])
    if filters['namespace']:
        query = query.filter(RegistryWorkloadBinding.namespace == filters['namespace'])
    if filters['match'] in {'digest', 'tag'}:
        query = query.filter(RegistryWorkloadBinding.match_type == filters['match'])
    if request.artifact_id is not None:
        query = query.filter(RegistryWorkloadBinding.artifact_id == int(request.artifact_id))

    exposed_ids = critical_ids | high_ids
    safe_scanned_ids = scanned_ids - exposed_ids
    exposure_sets = {
        'critical': critical_ids,
        'high': high_ids,
        'no_high_risk': safe_scanned_ids,
    }
    selected_ids = exposure_sets.get(filters['exposure'])
    if selected_ids is not None:
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(selected_ids))
            if selected_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif filters['exposure'] == 'not_scanned' and scanned_ids:
        query = query.filter(~RegistryWorkloadBinding.artifact_id.in_(scanned_ids))

    if filters['search']:
        pattern = f'%{filters["search"]}%'
        matching_source_ids = [
            int(source.id)
            for source in sources
            if filters['search'] in f'{source.name} {source.provider_key} {source.environment or ""}'.lower()
        ]
        search_clauses = [
            func.lower(RegistryArtifact.digest).like(pattern),
            func.lower(RegistryRepository.name).like(pattern),
            func.lower(RegistryProject.name).like(pattern),
            func.lower(RegistryWorkloadBinding.namespace).like(pattern),
            func.lower(func.coalesce(RegistryWorkloadBinding.workload_name, '')).like(pattern),
            func.lower(RegistryWorkloadBinding.pod_name).like(pattern),
            func.lower(func.coalesce(RegistryWorkloadBinding.container_name, '')).like(pattern),
            func.lower(RegistryWorkloadBinding.image_reference).like(pattern),
            func.lower(func.coalesce(Cluster.name, '')).like(pattern),
        ]
        if matching_source_ids:
            search_clauses.append(RegistryProject.integration_instance_id.in_(matching_source_ids))
        query = query.filter(or_(*search_clauses))
    return query, filters


def _runtime_usage_counts(
    query: Any,
    *,
    critical_ids: set[int],
    high_ids: set[int],
) -> dict[str, int]:
    exposed_ids = critical_ids | high_ids
    return {
        'binding_total': query.order_by(None).count(),
        'digest_matches': query.filter(RegistryWorkloadBinding.match_type == 'digest').order_by(None).count(),
        'tag_matches': query.filter(RegistryWorkloadBinding.match_type == 'tag').order_by(None).count(),
        'security_exposed': (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(exposed_ids)).order_by(None).count()
            if exposed_ids
            else 0
        ),
        'critical_exposures': (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(critical_ids)).order_by(None).count()
            if critical_ids
            else 0
        ),
        'artifact_count': query.with_entities(RegistryWorkloadBinding.artifact_id).distinct().count(),
    }


def _runtime_usage_rows(
    page_items: list[Any],
    *,
    source_by_id: dict[int, Any],
    cluster_by_id: dict[str, Any],
    security_by_artifact: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for binding in page_items:
        artifact = binding.artifact
        repository = artifact.repository
        project = repository.project
        source = source_by_id.get(int(project.integration_instance_id))
        cluster = cluster_by_id.get(str(binding.cluster_id))
        security = security_by_artifact.get(
            int(artifact.id),
            _runtime_security_state(artifact.scan_status, artifact.vulnerability_summary),
        )
        rows.append(
            {
                'id': int(binding.id),
                'artifact_id': int(artifact.id),
                'project': project.name,
                'repository': repository.name,
                'digest': artifact.digest,
                'digest_short': (
                    artifact.digest if len(artifact.digest) <= 28 else f'{artifact.digest[:18]}…{artifact.digest[-8:]}'
                ),
                'source_id': int(project.integration_instance_id),
                'source_name': source.name if source is not None else 'Unknown Registry Source',
                'provider_label': source.provider_key.replace('_', ' ').title() if source is not None else 'Registry',
                'cluster_id': str(binding.cluster_id),
                'cluster_name': cluster.name if cluster is not None else str(binding.cluster_id),
                'cluster_environment': cluster.environment if cluster is not None else None,
                'namespace': binding.namespace,
                'workload_type': binding.workload_type or 'Workload',
                'workload_name': binding.workload_name or 'Not Resolved',
                'pod_name': binding.pod_name,
                'container_name': binding.container_name or 'Container',
                'image_reference': binding.image_reference,
                'match': _runtime_match_state(binding.match_type, binding.confidence),
                'match_type': binding.match_type,
                'confidence': binding.confidence,
                'security': security,
                'observed_at': binding.observed_at,
            }
        )
    return rows


def _runtime_snapshot_state(prerequisites: dict[str, Any]) -> dict[str, Any]:
    latest_job = (
        JobExecution.query.filter(JobExecution.job_type == 'artifact_registry_runtime_correlation')
        .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
        .first()
    )
    latest_success = (
        JobExecution.query.filter(
            JobExecution.job_type == 'artifact_registry_runtime_correlation',
            JobExecution.status.in_(('succeeded', 'partially_succeeded')),
        )
        .order_by(JobExecution.completed_at.desc(), JobExecution.created_at.desc())
        .first()
    )
    latest_binding_at = RegistryWorkloadBinding.query.with_entities(
        func.max(RegistryWorkloadBinding.observed_at)
    ).scalar()
    latest_correlated_at = (
        latest_success.completed_at
        if latest_success is not None and latest_success.completed_at is not None
        else latest_binding_at
    )
    latest_correlated_at = _aware_datetime(latest_correlated_at)
    setup = _runtime_prerequisite_guidance(
        prerequisites,
        has_committed_snapshot=latest_correlated_at is not None,
    )
    refresh_failed = bool(
        latest_job is not None
        and latest_job.status == 'failed'
        and (latest_success is None or latest_job.created_at > latest_success.created_at)
    )
    refreshing = bool(latest_job is not None and latest_job.is_active)
    stale = bool(
        latest_correlated_at is not None
        and latest_correlated_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
    )
    if refreshing:
        status, tone = 'Refreshing', 'info'
        description = 'Runtime correlation is rebuilding from committed Registry and Kubernetes evidence.'
    elif setup['refresh_blocked']:
        status, tone, description = 'Refresh Unavailable', 'warning', setup['refresh_description']
    elif setup['is_blocked']:
        status, tone, description = 'Prerequisites Required', 'warning', setup['description']
    elif latest_correlated_at is None:
        status, tone = 'Not Materialized', 'unknown'
        description = 'No committed runtime correlation snapshot is available yet.'
    elif refresh_failed:
        status, tone = 'Refresh Failed', 'warning'
        description = 'The latest rebuild failed; the previous committed correlation remains readable.'
    elif stale:
        status, tone = 'Stale', 'warning'
        description = 'Committed runtime correlation is older than the current freshness window.'
    else:
        status, tone = 'Ready', 'normal'
        description = 'Committed cross-domain runtime correlation is available for the active scope.'
    return {
        'setup': setup,
        'latest_correlated_at': latest_correlated_at,
        'status': status,
        'tone': tone,
        'description': description,
    }


def _runtime_scope_projection(
    request: RuntimeUsageRequest,
    *,
    source_by_id: dict[int, Any],
    cluster_by_id: dict[str, Any],
    cluster_value: str,
    namespace_value: str,
) -> dict[str, str]:
    selected_source = source_by_id.get(int(request.source_id)) if request.source_id is not None else None
    source_label = (
        selected_source.name
        if selected_source is not None
        else ('Selected Registry Source' if request.source_id is not None else 'All Registry Sources')
    )
    selected_cluster = cluster_by_id.get(cluster_value) if cluster_value else None
    cluster_label = (
        selected_cluster.name
        if selected_cluster is not None
        else ('Selected Kubernetes Cluster' if cluster_value else 'All Kubernetes Clusters')
    )
    scope_label = f'{source_label} × {cluster_label}'
    if namespace_value:
        scope_label = f'{scope_label} · {namespace_value}'

    artifact_filter_label = ''
    if request.artifact_id is not None:
        artifact_filter = (
            RegistryArtifact.query.options(
                joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project)
            )
            .filter(RegistryArtifact.id == int(request.artifact_id))
            .first()
        )
        if artifact_filter is not None:
            artifact_filter_label = (
                f'{artifact_filter.repository.project.name}/'
                f'{artifact_filter.repository.name} · '
                f'{artifact_filter.digest[:18]}…'
            )
            scope_label = f'{scope_label} · Artifact Scoped'
    return {
        'label': scope_label,
        'source_label': source_label,
        'cluster_label': cluster_label,
        'artifact_filter_label': artifact_filter_label,
    }


def _runtime_posture(counts: dict[str, int]) -> dict[str, str]:
    if counts['critical_exposures']:
        return {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    if counts['security_exposed']:
        return {'label': 'High-Risk Runtime Exposure', 'tone': 'warning'}
    if counts['binding_total'] and counts['tag_matches']:
        return {'label': 'Tag-Matched Runtime Evidence', 'tone': 'info'}
    if counts['binding_total']:
        return {'label': 'Digest-Correlated', 'tone': 'normal'}
    return {'label': 'No Runtime Correlation', 'tone': 'unknown'}


def _runtime_exceptions(counts: dict[str, int]) -> dict[str, str]:
    if counts['tag_matches']:
        return {
            'label': (
                f'{counts["tag_matches"]} Tag Match'
                if counts['tag_matches'] == 1
                else f'{counts["tag_matches"]} Tag Matches'
            ),
            'supporting': 'Mutable references; lower confidence.',
            'tone': 'warning',
        }
    if counts['binding_total']:
        return {
            'label': 'Digest-only',
            'supporting': 'No tag-only correlation in this scope.',
            'tone': 'normal',
        }
    return {
        'label': 'No Correlation',
        'supporting': 'No committed runtime binding in this scope.',
        'tone': 'unknown',
    }


def _runtime_empty_state(
    *,
    artifact_id: int | None,
    binding_total: int,
    has_filters: bool,
    latest_correlated_at: Any,
) -> tuple[str, str]:
    if artifact_id is not None and not binding_total:
        return (
            'Artifact Not Observed at Runtime',
            'No committed Kubernetes workload binding currently resolves to this artifact.',
        )
    if has_filters and not binding_total:
        return 'No Runtime Bindings Match', 'No committed runtime correlation matches the active filters.'
    if latest_correlated_at is None:
        return (
            'Runtime Correlation Not Materialized',
            'Run the canonical Runtime Correlation job after Registry and Kubernetes inventory are committed.',
        )
    return (
        'No Runtime Usage Observed',
        'The latest committed correlation contains no Registry-to-Kubernetes bindings.',
    )


def _runtime_namespace_options() -> list[str]:
    return [
        value
        for (value,) in (
            RegistryWorkloadBinding.query.with_entities(RegistryWorkloadBinding.namespace)
            .distinct()
            .order_by(RegistryWorkloadBinding.namespace.asc())
            .all()
        )
        if value
    ]


def _build_runtime_usage(request: RuntimeUsageRequest) -> dict[str, Any]:
    sources = _providers()
    source_by_id = {int(item.id): item for item in sources}
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    cluster_by_id = {str(item.id): item for item in clusters}
    prerequisites = correlation_prerequisites()
    security_by_artifact, critical_ids, high_ids, scanned_ids = _runtime_security_index()
    query, filters = _runtime_filtered_query(
        request,
        sources=sources,
        critical_ids=critical_ids,
        high_ids=high_ids,
        scanned_ids=scanned_ids,
    )
    counts = _runtime_usage_counts(query, critical_ids=critical_ids, high_ids=high_ids)
    page_items, pagination = paginate_query(
        query.order_by(
            RegistryWorkloadBinding.namespace.asc(),
            RegistryWorkloadBinding.workload_name.asc(),
            RegistryWorkloadBinding.pod_name.asc(),
            RegistryWorkloadBinding.id.asc(),
        ),
        page=request.page,
        per_page=request.per_page,
    )
    rows = _runtime_usage_rows(
        page_items,
        source_by_id=source_by_id,
        cluster_by_id=cluster_by_id,
        security_by_artifact=security_by_artifact,
    )
    snapshot = _runtime_snapshot_state(prerequisites)
    scope = _runtime_scope_projection(
        request,
        source_by_id=source_by_id,
        cluster_by_id=cluster_by_id,
        cluster_value=filters['cluster'],
        namespace_value=filters['namespace'],
    )
    has_filters = bool(
        filters['search']
        or request.source_id is not None
        or filters['cluster']
        or filters['namespace']
        or filters['match']
        or filters['exposure']
        or request.artifact_id is not None
    )
    empty_title, empty_description = _runtime_empty_state(
        artifact_id=request.artifact_id,
        binding_total=counts['binding_total'],
        has_filters=has_filters,
        latest_correlated_at=snapshot['latest_correlated_at'],
    )
    exceptions = _runtime_exceptions(counts)
    return {
        'setup': {**snapshot['setup'], 'provider_count': len(sources)},
        'prerequisites': prerequisites,
        'total': counts['binding_total'],
        'digest_matches': counts['digest_matches'],
        'tag_matches': counts['tag_matches'],
        'security_exposed': counts['security_exposed'],
        'critical_exposures': counts['critical_exposures'],
        'artifact_count': counts['artifact_count'],
        'posture': _runtime_posture(counts),
        'rows': rows,
        'pagination': pagination,
        'has_filters': has_filters,
        'filters': {
            'search': request.search,
            'source_id': request.source_id,
            'cluster_id': filters['cluster'],
            'namespace': filters['namespace'],
            'match_type': filters['match'],
            'exposure': filters['exposure'],
            'artifact_id': request.artifact_id,
        },
        'source_options': sources,
        'cluster_options': clusters,
        'namespace_options': _runtime_namespace_options(),
        'match_options': [
            {'value': 'digest', 'label': 'Digest Match'},
            {'value': 'tag', 'label': 'Tag Match'},
        ],
        'exposure_options': [
            {'value': 'critical', 'label': 'Critical'},
            {'value': 'high', 'label': 'High'},
            {'value': 'no_high_risk', 'label': 'No Critical/High'},
            {'value': 'not_scanned', 'label': 'Not Scanned'},
        ],
        'scope': {
            'label': scope['label'],
            'source_label': scope['source_label'],
            'cluster_label': scope['cluster_label'],
        },
        'artifact_filter_label': scope['artifact_filter_label'],
        'snapshot': {
            'source_label': 'Committed Artifact Registry × Kubernetes',
            'status': snapshot['status'],
            'tone': snapshot['tone'],
            'description': snapshot['description'],
            'latest_collected_at': snapshot['latest_correlated_at'],
            'scope_label': scope['label'],
            'coverage_label': f'{counts["artifact_count"]} artifacts · {counts["binding_total"]} bindings',
            'coverage_supporting': 'Runtime usage in scope.',
            'coverage_tone': 'normal' if counts['binding_total'] else 'warning',
            'exceptions_label': exceptions['label'],
            'exceptions_supporting': exceptions['supporting'],
            'exceptions_tone': exceptions['tone'],
        },
        'empty_title': empty_title,
        'empty_description': empty_description,
    }


def build_runtime_usage(**kwargs: Any) -> dict[str, Any]:
    return _build_runtime_usage(_runtime_usage_request(kwargs))

def build_runtime_binding_detail(binding_id: int) -> dict[str, Any] | None:
    binding = (
        RegistryWorkloadBinding.query.options(
            joinedload(RegistryWorkloadBinding.artifact)
            .joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project),
            joinedload(RegistryWorkloadBinding.artifact).joinedload(RegistryArtifact.tags),
        )
        .filter(RegistryWorkloadBinding.id == int(binding_id))
        .first()
    )
    if binding is None:
        return None

    artifact = binding.artifact
    repository = artifact.repository
    project = repository.project
    source = _inventory_detail_provider_context(project.integration_instance_id)
    cluster = Cluster.query.filter(Cluster.id == str(binding.cluster_id)).first()
    match = _runtime_match_state(binding.match_type, binding.confidence)
    security = _runtime_security_state(artifact.scan_status, artifact.vulnerability_summary)
    details = dict(binding.details) if isinstance(binding.details, dict) else {}

    return {
        'id': int(binding.id),
        'artifact_id': int(artifact.id),
        'project': project.name,
        'repository': repository.name,
        'digest': artifact.digest,
        'digest_short': (
            artifact.digest if len(artifact.digest) <= 40 else f'{artifact.digest[:24]}…{artifact.digest[-12:]}'
        ),
        'tags': [tag.name for tag in sorted(artifact.tags, key=lambda item: item.name.lower())],
        'image_reference': binding.image_reference,
        'match': match,
        'match_type': binding.match_type,
        'confidence': binding.confidence,
        'cluster_id': str(binding.cluster_id),
        'cluster_name': cluster.name if cluster is not None else str(binding.cluster_id),
        'cluster_environment': cluster.environment if cluster is not None else 'Not Set',
        'namespace': binding.namespace,
        'workload_type': binding.workload_type or 'Workload',
        'workload_name': binding.workload_name or 'Not Resolved',
        'pod_name': binding.pod_name,
        'container_name': binding.container_name or 'Container',
        'source_kind': str(details.get('source_kind') or 'container').replace('_', ' ').title(),
        'registry_host': details.get('registry_host') or 'Not Collected',
        'registry_observed_at': _runtime_parse_observed_at(details.get('registry_observed_at')) or artifact.observed_at,
        'kubernetes_observed_at': _runtime_parse_observed_at(details.get('pod_collected_at')),
        'correlated_at': binding.observed_at,
        'security': security,
        'scan_status': (str(artifact.scan_status).replace('_', ' ').title() if artifact.scan_status else 'Not Scanned'),
        **source,
    }
