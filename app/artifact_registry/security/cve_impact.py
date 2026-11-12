from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import NotFound

from app.artifact_registry.correlation_sync_jobs import correlation_prerequisites
from app.artifact_registry.presentation_runtime import _runtime_match_state, _runtime_snapshot_state
from app.artifact_registry.security.contracts import SUCCESSFUL_REGISTRY_SCAN_STATUSES
from app.artifact_registry.security.presentation import _freshness, _providers
from app.common.pagination import paginate_query
from app.models.cluster import Cluster
from app.models.registry import (
    RegistryArtifact,
    RegistryProject,
    RegistryRepository,
    RegistryScanSnapshot,
    RegistryVulnerability,
    RegistryWorkloadBinding,
)

_CVE_PATTERN = re.compile(r'CVE-[0-9]{4}-[0-9]{4,}', re.ASCII)


def normalize_cve_id(value: str) -> str:
    """Accept an exact CVE identity; never silently broaden to a search term."""
    cve_id = str(value or '').strip().upper()
    if len(cve_id) > 64 or _CVE_PATTERN.fullmatch(cve_id) is None:
        raise NotFound('The requested CVE identifier is invalid.')
    return cve_id


def _literal_contains(value: str) -> str:
    """Escape SQL LIKE wildcards so committed-evidence search stays literal."""
    escaped = value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def build_cve_runtime_impact(
    cve_id: str,
    *,
    finding_page: int = 1,
    runtime_page: int = 1,
    per_page: int = 5,
    finding_per_page: int | None = None,
    runtime_per_page: int | None = None,
    finding_search: str = '',
    finding_severity: str = '',
    runtime_search: str = '',
    runtime_match: str = '',
) -> dict[str, Any]:
    """Read existing source-qualified scan and Kubernetes binding evidence only.

    A positive match is a scanner finding, not proof of exploitability. Missing
    evidence or correlation must never be presented as a clean application fleet.
    """
    canonical_cve = normalize_cve_id(cve_id)
    finding_search = str(finding_search or '').strip()[:128]
    runtime_search = str(runtime_search or '').strip()[:128]
    finding_severity = str(finding_severity or '').strip().lower()
    runtime_match = str(runtime_match or '').strip().lower()
    if finding_severity not in {'critical', 'high', 'medium', 'low', 'unknown'}:
        finding_severity = ''
    if runtime_match not in {'digest', 'other'}:
        runtime_match = ''
    sources = _providers()
    source_by_id = {int(source.id): source for source in sources}
    source_ids = list(source_by_id)

    # Latest *successful* scan per digest is the last-good scanner authority.
    # Never resurrect findings from an older successful scan after a newer
    # successful scan has removed them; failed refreshes remain visible as old.
    latest_success_ids = (
        select(func.max(RegistryScanSnapshot.id).label('id'))
        .where(func.lower(RegistryScanSnapshot.status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES))
        .group_by(RegistryScanSnapshot.artifact_id)
        .subquery()
    )
    findings = (
        RegistryVulnerability.query.join(
            RegistryScanSnapshot,
            RegistryVulnerability.scan_snapshot_id == RegistryScanSnapshot.id,
        )
        .join(latest_success_ids, RegistryScanSnapshot.id == latest_success_ids.c.id)
        .join(RegistryArtifact, RegistryScanSnapshot.artifact_id == RegistryArtifact.id)
        .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
        .filter(
            func.upper(RegistryVulnerability.vulnerability_id) == canonical_cve,
            RegistryProject.integration_instance_id.in_(source_ids),
        )
    )
    finding_count = findings.order_by(None).count()
    affected_artifacts = int(
        findings.with_entities(func.count(func.distinct(RegistryScanSnapshot.artifact_id))).scalar() or 0
    )

    matching_artifact_ids = (
        findings.with_entities(RegistryScanSnapshot.artifact_id.label('artifact_id')).distinct().subquery()
    )
    bindings = RegistryWorkloadBinding.query.filter(
        RegistryWorkloadBinding.artifact_id.in_(select(matching_artifact_ids.c.artifact_id))
    )
    binding_count = bindings.order_by(None).count()
    digest_count = bindings.filter(RegistryWorkloadBinding.match_type == 'digest').order_by(None).count()
    tag_count = binding_count - digest_count

    # Filters belong to their own evidence table. Keep global CVE and runtime
    # correlation/counts authoritative and source-qualified, not search-scoped.
    visible_findings = findings
    if finding_search:
        finding_pattern = _literal_contains(finding_search)
        matching_sources = [
            source_id
            for source_id, source in source_by_id.items()
            if finding_search.casefold() in source.name.casefold()
        ]
        visible_findings = visible_findings.filter(
            or_(
                RegistryRepository.name.ilike(finding_pattern, escape='\\'),
                RegistryProject.name.ilike(finding_pattern, escape='\\'),
                RegistryArtifact.digest.ilike(finding_pattern, escape='\\'),
                RegistryVulnerability.package.ilike(finding_pattern, escape='\\'),
                RegistryVulnerability.installed_version.ilike(finding_pattern, escape='\\'),
                RegistryProject.integration_instance_id.in_(matching_sources),
            )
        )
    if finding_severity:
        visible_findings = visible_findings.filter(
            func.lower(RegistryVulnerability.severity) == finding_severity
        )

    visible_bindings = bindings
    if runtime_search:
        runtime_pattern = _literal_contains(runtime_search)
        matching_clusters = select(Cluster.id).where(
            Cluster.name.ilike(runtime_pattern, escape='\\')
        )
        visible_bindings = visible_bindings.filter(
            or_(
                RegistryWorkloadBinding.cluster_id.ilike(runtime_pattern, escape='\\'),
                RegistryWorkloadBinding.cluster_id.in_(matching_clusters),
                RegistryWorkloadBinding.namespace.ilike(runtime_pattern, escape='\\'),
                RegistryWorkloadBinding.workload_name.ilike(runtime_pattern, escape='\\'),
                RegistryWorkloadBinding.pod_name.ilike(runtime_pattern, escape='\\'),
                RegistryWorkloadBinding.container_name.ilike(runtime_pattern, escape='\\'),
                RegistryWorkloadBinding.image_reference.ilike(runtime_pattern, escape='\\'),
            )
        )
    if runtime_match == 'digest':
        visible_bindings = visible_bindings.filter(RegistryWorkloadBinding.match_type == 'digest')
    elif runtime_match == 'other':
        visible_bindings = visible_bindings.filter(RegistryWorkloadBinding.match_type != 'digest')

    finding_items, finding_pagination = paginate_query(
        visible_findings.options(
            joinedload(RegistryVulnerability.scan_snapshot)
            .joinedload(RegistryScanSnapshot.artifact)
            .joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project)
        ).order_by(
            RegistryVulnerability.severity.asc(),
            RegistryVulnerability.id.asc(),
        ),
        page=finding_page,
        per_page=finding_per_page if finding_per_page is not None else per_page,
    )
    finding_rows = []
    for item in finding_items:
        scan = item.scan_snapshot
        artifact = scan.artifact
        repository = artifact.repository
        project = repository.project
        source = source_by_id.get(int(project.integration_instance_id))
        finding_rows.append(
            {
                'id': item.id,
                'artifact_id': artifact.id,
                'source': source.name if source else 'Unknown Source',
                'repository': repository.name,
                'project': project.name,
                'digest': artifact.digest,
                'package': item.package,
                'installed_version': item.installed_version,
                'fixed_version': item.fixed_version or 'No Fix Observed',
                'severity': str(item.severity or 'unknown').title(),
                'observed_at': scan.observed_at,
                'freshness': _freshness(scan.observed_at),
            }
        )

    binding_items, runtime_pagination = paginate_query(
        visible_bindings.order_by(
            RegistryWorkloadBinding.cluster_id.asc(),
            RegistryWorkloadBinding.namespace.asc(),
            RegistryWorkloadBinding.workload_name.asc(),
            RegistryWorkloadBinding.pod_name.asc(),
            RegistryWorkloadBinding.id.asc(),
        ),
        page=runtime_page,
        per_page=runtime_per_page if runtime_per_page is not None else per_page,
    )
    cluster_ids = {str(item.cluster_id) for item in binding_items}
    cluster_names = {
        str(cluster.id): cluster.name
        for cluster in (Cluster.query.filter(Cluster.id.in_(cluster_ids)).all() if cluster_ids else [])
    }
    runtime_rows = [
        {
            'id': item.id,
            'artifact_id': item.artifact_id,
            'cluster': cluster_names.get(str(item.cluster_id), str(item.cluster_id)),
            'namespace': item.namespace,
            'workload': item.workload_name or 'Not Mapped',
            'workload_type': item.workload_type or 'Unknown',
            'pod': item.pod_name,
            'container': item.container_name or 'Unknown',
            'match': _runtime_match_state(item.match_type, item.confidence),
            'observed_at': item.observed_at,
        }
        for item in binding_items
    ]

    correlation = _runtime_snapshot_state(correlation_prerequisites())
    # Missing/old/changed inputs can invalidate a zero-binding interpretation.
    evidence_ready = correlation['status'] == 'Ready'
    return {
        'cve_id': canonical_cve,
        'finding_count': finding_count,
        'affected_artifacts': affected_artifacts,
        'binding_count': binding_count,
        'digest_count': digest_count,
        'tag_count': tag_count,
        'finding_rows': finding_rows,
        'runtime_rows': runtime_rows,
        'finding_pagination': finding_pagination,
        'runtime_pagination': runtime_pagination,
        'correlation': correlation,
        'evidence_ready': evidence_ready,
        'source_count': len(sources),
        'filters': {
            'finding_search': finding_search,
            'finding_severity': finding_severity,
            'runtime_search': runtime_search,
            'runtime_match': runtime_match,
        },
    }
