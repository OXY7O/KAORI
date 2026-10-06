from __future__ import annotations

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


def build_runtime_usage(
    *,
    search: str = '',
    source_id: int | None = None,
    cluster_id: str = '',
    namespace: str = '',
    match_type: str = '',
    exposure: str = '',
    artifact_id: int | None = None,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    sources = _providers()
    source_by_id = {int(item.id): item for item in sources}
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    cluster_by_id = {str(item.id): item for item in clusters}
    prerequisites = correlation_prerequisites()

    search_value = str(search or '').strip().lower()
    cluster_value = str(cluster_id or '').strip()
    namespace_value = str(namespace or '').strip()
    match_value = str(match_type or '').strip().lower()
    exposure_value = str(exposure or '').strip().lower()

    security_by_artifact, critical_ids, high_ids, scanned_ids = _runtime_security_index()
    exposed_ids = critical_ids | high_ids
    safe_scanned_ids = scanned_ids - exposed_ids

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

    if source_id is not None:
        query = query.filter(RegistryProject.integration_instance_id == int(source_id))
    if cluster_value:
        query = query.filter(RegistryWorkloadBinding.cluster_id == cluster_value)
    if namespace_value:
        query = query.filter(RegistryWorkloadBinding.namespace == namespace_value)
    if match_value in {'digest', 'tag'}:
        query = query.filter(RegistryWorkloadBinding.match_type == match_value)
    if artifact_id is not None:
        query = query.filter(RegistryWorkloadBinding.artifact_id == int(artifact_id))

    if exposure_value == 'critical':
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(critical_ids))
            if critical_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif exposure_value == 'high':
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(high_ids))
            if high_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif exposure_value == 'no_high_risk':
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(safe_scanned_ids))
            if safe_scanned_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif exposure_value == 'not_scanned' and scanned_ids:
        query = query.filter(~RegistryWorkloadBinding.artifact_id.in_(scanned_ids))

    if search_value:
        pattern = f'%{search_value}%'
        matching_source_ids = [
            int(source.id)
            for source in sources
            if search_value in f'{source.name} {source.provider_key} {source.environment or ""}'.lower()
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

    binding_total = query.order_by(None).count()
    digest_matches = query.filter(RegistryWorkloadBinding.match_type == 'digest').order_by(None).count()
    tag_matches = query.filter(RegistryWorkloadBinding.match_type == 'tag').order_by(None).count()
    security_exposed = (
        query.filter(RegistryWorkloadBinding.artifact_id.in_(exposed_ids)).order_by(None).count() if exposed_ids else 0
    )
    critical_exposures = (
        query.filter(RegistryWorkloadBinding.artifact_id.in_(critical_ids)).order_by(None).count()
        if critical_ids
        else 0
    )
    artifact_count = query.with_entities(RegistryWorkloadBinding.artifact_id).distinct().count()

    page_items, pagination = paginate_query(
        query.order_by(
            RegistryWorkloadBinding.namespace.asc(),
            RegistryWorkloadBinding.workload_name.asc(),
            RegistryWorkloadBinding.pod_name.asc(),
            RegistryWorkloadBinding.id.asc(),
        ),
        page=page,
        per_page=per_page,
    )

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
        match = _runtime_match_state(binding.match_type, binding.confidence)
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
                'provider_label': (source.provider_key.replace('_', ' ').title() if source is not None else 'Registry'),
                'cluster_id': str(binding.cluster_id),
                'cluster_name': cluster.name if cluster is not None else str(binding.cluster_id),
                'cluster_environment': cluster.environment if cluster is not None else None,
                'namespace': binding.namespace,
                'workload_type': binding.workload_type or 'Workload',
                'workload_name': binding.workload_name or 'Not Resolved',
                'pod_name': binding.pod_name,
                'container_name': binding.container_name or 'Container',
                'image_reference': binding.image_reference,
                'match': match,
                'match_type': binding.match_type,
                'confidence': binding.confidence,
                'security': security,
                'observed_at': binding.observed_at,
            }
        )

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
        latest_correlated_at is not None and latest_correlated_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
    )

    if refreshing:
        snapshot_status, snapshot_tone = 'Refreshing', 'info'
        snapshot_description = 'Runtime correlation is rebuilding from committed Registry and Kubernetes evidence.'
    elif setup['refresh_blocked']:
        snapshot_status, snapshot_tone = 'Refresh Unavailable', 'warning'
        snapshot_description = setup['refresh_description']
    elif setup['is_blocked']:
        snapshot_status, snapshot_tone = 'Prerequisites Required', 'warning'
        snapshot_description = setup['description']
    elif latest_correlated_at is None:
        snapshot_status, snapshot_tone = 'Not Materialized', 'unknown'
        snapshot_description = 'No committed runtime correlation snapshot is available yet.'
    elif refresh_failed:
        snapshot_status, snapshot_tone = 'Refresh Failed', 'warning'
        snapshot_description = 'The latest rebuild failed; the previous committed correlation remains readable.'
    elif stale:
        snapshot_status, snapshot_tone = 'Stale', 'warning'
        snapshot_description = 'Committed runtime correlation is older than the current freshness window.'
    else:
        snapshot_status, snapshot_tone = 'Ready', 'normal'
        snapshot_description = 'Committed cross-domain runtime correlation is available for the active scope.'

    selected_source = source_by_id.get(int(source_id)) if source_id is not None else None
    source_scope_label = (
        selected_source.name
        if selected_source is not None
        else ('Selected Registry Source' if source_id is not None else 'All Registry Sources')
    )
    selected_cluster = cluster_by_id.get(cluster_value) if cluster_value else None
    cluster_scope_label = (
        selected_cluster.name
        if selected_cluster is not None
        else ('Selected Kubernetes Cluster' if cluster_value else 'All Kubernetes Clusters')
    )
    scope_label = f'{source_scope_label} × {cluster_scope_label}'
    if namespace_value:
        scope_label = f'{scope_label} · {namespace_value}'

    artifact_filter_label = ''
    if artifact_id is not None:
        artifact_filter = (
            RegistryArtifact.query.options(
                joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project)
            )
            .filter(RegistryArtifact.id == int(artifact_id))
            .first()
        )
        if artifact_filter is not None:
            artifact_filter_label = (
                f'{artifact_filter.repository.project.name}/'
                f'{artifact_filter.repository.name} · '
                f'{artifact_filter.digest[:18]}…'
            )
            scope_label = f'{scope_label} · Artifact Scoped'

    if critical_exposures:
        posture = {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    elif security_exposed:
        posture = {'label': 'High-Risk Runtime Exposure', 'tone': 'warning'}
    elif binding_total and tag_matches:
        posture = {'label': 'Tag-Matched Runtime Evidence', 'tone': 'info'}
    elif binding_total:
        posture = {'label': 'Digest-Correlated', 'tone': 'normal'}
    else:
        posture = {'label': 'No Runtime Correlation', 'tone': 'unknown'}

    if tag_matches:
        exceptions_label = f'{tag_matches} Tag Match' if tag_matches == 1 else f'{tag_matches} Tag Matches'
        exceptions_supporting = 'Mutable references; lower confidence.'
        exceptions_tone = 'warning'
    elif binding_total:
        exceptions_label = 'Digest-only'
        exceptions_supporting = 'No tag-only correlation in this scope.'
        exceptions_tone = 'normal'
    else:
        exceptions_label = 'No Correlation'
        exceptions_supporting = 'No committed runtime binding in this scope.'
        exceptions_tone = 'unknown'

    has_filters = bool(
        search_value
        or source_id is not None
        or cluster_value
        or namespace_value
        or match_value
        or exposure_value
        or artifact_id is not None
    )
    if artifact_id is not None and not binding_total:
        empty_title = 'Artifact Not Observed at Runtime'
        empty_description = 'No committed Kubernetes workload binding currently resolves to this artifact.'
    elif has_filters and not binding_total:
        empty_title = 'No Runtime Bindings Match'
        empty_description = 'No committed runtime correlation matches the active filters.'
    elif latest_correlated_at is None:
        empty_title = 'Runtime Correlation Not Materialized'
        empty_description = (
            'Run the canonical Runtime Correlation job after Registry and Kubernetes inventory are committed.'
        )
    else:
        empty_title = 'No Runtime Usage Observed'
        empty_description = 'The latest committed correlation contains no Registry-to-Kubernetes bindings.'

    namespace_options = [
        value
        for (value,) in (
            RegistryWorkloadBinding.query.with_entities(RegistryWorkloadBinding.namespace)
            .distinct()
            .order_by(RegistryWorkloadBinding.namespace.asc())
            .all()
        )
        if value
    ]

    return {
        'setup': {
            **setup,
            'provider_count': len(sources),
        },
        'prerequisites': prerequisites,
        'total': binding_total,
        'digest_matches': digest_matches,
        'tag_matches': tag_matches,
        'security_exposed': security_exposed,
        'critical_exposures': critical_exposures,
        'artifact_count': artifact_count,
        'posture': posture,
        'rows': rows,
        'pagination': pagination,
        'has_filters': has_filters,
        'filters': {
            'search': search,
            'source_id': source_id,
            'cluster_id': cluster_value,
            'namespace': namespace_value,
            'match_type': match_value,
            'exposure': exposure_value,
            'artifact_id': artifact_id,
        },
        'source_options': sources,
        'cluster_options': clusters,
        'namespace_options': namespace_options,
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
            'label': scope_label,
            'source_label': source_scope_label,
            'cluster_label': cluster_scope_label,
        },
        'artifact_filter_label': artifact_filter_label,
        'snapshot': {
            'source_label': 'Committed Artifact Registry × Kubernetes',
            'status': snapshot_status,
            'tone': snapshot_tone,
            'description': snapshot_description,
            'latest_collected_at': latest_correlated_at,
            'scope_label': scope_label,
            'coverage_label': f'{artifact_count} artifacts · {binding_total} bindings',
            'coverage_supporting': 'Runtime usage in scope.',
            'coverage_tone': 'normal' if binding_total else 'warning',
            'exceptions_label': exceptions_label,
            'exceptions_supporting': exceptions_supporting,
            'exceptions_tone': exceptions_tone,
        },
        'empty_title': empty_title,
        'empty_description': empty_description,
    }


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
