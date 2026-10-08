from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from app.artifact_registry.security.contracts import SUCCESSFUL_REGISTRY_SCAN_STATUSES
from app.artifact_registry.security.job_adapter import build_registry_security_sync_state
from app.artifact_registry.security.presentation_scope import (
    _security_scope_labels,
    _security_snapshot_context,
)
from app.artifact_registry.security.providers import registered_registry_security_collectors
from app.common.pagination import paginate_query, paginate_sequence
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.registry import (
    RegistryArtifact,
    RegistryProject,
    RegistryRepository,
    RegistryScanSnapshot,
    RegistryVulnerability,
    RegistryWorkloadBinding,
)

FRESHNESS_HOURS = 24


def _aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _freshness(observed_at: datetime | None) -> dict[str, str]:
    resolved = _aware_datetime(observed_at)
    if resolved is None:
        return {'label': 'Not Collected', 'tone': 'unknown'}
    if resolved < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS):
        return {'label': 'Stale', 'tone': 'warning'}
    return {'label': 'Current', 'tone': 'normal'}


def _providers() -> list[IntegrationInstance]:
    return (
        IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.name.asc())
        .all()
    )


def _capability_state(*, supported: bool, observed: bool, attempted: bool) -> dict[str, str]:
    if not supported:
        return {'key': 'unsupported', 'label': 'Unsupported', 'tone': 'unknown'}
    if observed:
        return {'key': 'supported_observed', 'label': 'Observed', 'tone': 'normal'}
    if attempted:
        return {'key': 'supported_unavailable', 'label': 'Unavailable', 'tone': 'warning'}
    return {'key': 'not_collected', 'label': 'Not Collected', 'tone': 'unknown'}


def _evidence_state(value: str | None, *, evidence: str) -> dict[str, str]:
    key = str(value or '').strip().lower()
    if evidence == 'signature':
        if key == 'signed':
            return {'label': 'Observed', 'tone': 'normal'}
        if key == 'unsigned':
            return {'label': 'Not Observed', 'tone': 'warning'}
        return {'label': 'Not Collected' if not key else 'Not Observed', 'tone': 'unknown'}
    if evidence == 'sbom':
        if key == 'available':
            return {'label': 'Available', 'tone': 'normal'}
        if key == 'observed':
            return {'label': 'Observed', 'tone': 'info'}
        return {'label': 'Not Collected' if not key else 'Not Available', 'tone': 'unknown'}
    return {'label': key.replace('_', ' ').title() if key else 'Not Collected', 'tone': 'unknown'}


def _scoped_sources(
    sources: list[IntegrationInstance],
    *,
    provider: str,
    source_id: int | None,
) -> list[IntegrationInstance]:
    scoped = sources
    if provider:
        scoped = [item for item in scoped if item.provider_key == provider]
    if source_id is not None:
        scoped = [item for item in scoped if int(item.id) == int(source_id)]
    return scoped


def _apply_source_scope(query: Any, source_ids: list[int], *, scoped: bool) -> Any:
    if source_ids:
        return query.filter(RegistryProject.integration_instance_id.in_(source_ids))
    if scoped:
        return query.filter(RegistryProject.integration_instance_id == -1)
    return query


def _snapshot_status(
    *,
    artifact_total: int,
    evidence_count: int,
    latest_job: JobExecution | None,
    latest_success: JobExecution | None,
    latest_evidence_at: datetime | None,
) -> dict[str, Any]:
    successful_at = (
        latest_success.completed_at
        if latest_success is not None and latest_success.completed_at is not None
        else latest_evidence_at
    )
    successful_at = _aware_datetime(successful_at)
    latest_status = str(latest_job.status or '') if latest_job is not None else ''
    refresh_failed = bool(
        latest_job is not None
        and latest_status == 'failed'
        and (latest_success is None or latest_job.created_at > latest_success.created_at)
    )
    refreshing = bool(latest_job is not None and latest_job.is_active)
    partial = latest_status == 'partially_succeeded'
    stale = bool(successful_at is not None and successful_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS))

    if artifact_total == 0:
        label, tone = 'Inventory Required', 'warning'
        description = 'Committed artifact inventory is required before security evidence can be evaluated.'
    elif evidence_count == 0 and successful_at is None:
        label, tone = 'Not Collected', 'unknown'
        description = 'No committed security evidence for this Registry scope.'
    elif refresh_failed:
        label, tone = 'Refresh Failed', 'warning'
        description = 'The latest refresh failed; KAORI retains the last successful committed security evidence.'
    elif refreshing:
        label, tone = 'Refreshing', 'info'
        description = 'A Security Sync is active while the last committed evidence remains available.'
    elif stale:
        label, tone = 'Stale', 'warning'
        description = 'Committed security evidence is older than the current freshness window.'
    elif partial or evidence_count < artifact_total:
        label, tone = 'Partial', 'warning'
        description = 'Committed security evidence exists, but coverage is incomplete for the current Registry scope.'
    else:
        label, tone = 'Ready', 'normal'
        description = 'Committed security evidence is current for the active Registry scope.'

    gap_count = max(artifact_total - evidence_count, 0)
    if refresh_failed:
        exceptions_label = 'Refresh Failed'
        exceptions_supporting = 'Last successful evidence retained.'
        exceptions_tone = 'warning'
    elif partial:
        exceptions_label = 'Partial Refresh'
        exceptions_supporting = 'One or more Registry sources need review.'
        exceptions_tone = 'warning'
    elif gap_count:
        exceptions_label = f'{gap_count} Coverage Gaps'
        exceptions_supporting = 'Artifacts missing security evidence.'
        exceptions_tone = 'warning'
    else:
        exceptions_label = 'No Exceptions'
        exceptions_supporting = 'No snapshot exception detected.'
        exceptions_tone = 'normal'

    return {
        'status': label,
        'tone': tone,
        'description': description,
        'latest_collected_at': successful_at,
        'exceptions_label': exceptions_label,
        'exceptions_supporting': exceptions_supporting,
        'exceptions_tone': exceptions_tone,
    }


def _security_scope_evidence(
    *,
    sources: list[IntegrationInstance],
    scoped_sources: list[IntegrationInstance],
    explicit_scope: bool,
    view: str,
) -> dict[str, Any]:
    source_ids = [int(item.id) for item in scoped_sources]
    scoped = explicit_scope or not sources
    artifact_scope = RegistryArtifact.query.join(
        RegistryRepository,
        RegistryArtifact.repository_id == RegistryRepository.id,
    ).join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
    artifact_scope = _apply_source_scope(artifact_scope, source_ids, scoped=scoped)
    evidence_filter = or_(
        RegistryArtifact.scan_status.isnot(None),
        RegistryArtifact.signature_status.isnot(None),
        RegistryArtifact.sbom_status.isnot(None),
    )
    artifact_total = artifact_scope.order_by(None).count()
    evidence_count = artifact_scope.filter(evidence_filter).order_by(None).count()
    scanned_artifacts = (
        artifact_scope.filter(func.lower(RegistryArtifact.scan_status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES))
        .order_by(None)
        .count()
    )
    signature_observed = (
        artifact_scope.filter(func.lower(RegistryArtifact.signature_status) == 'signed').order_by(None).count()
    )
    sbom_available = (
        artifact_scope.filter(func.lower(RegistryArtifact.sbom_status) == 'available').order_by(None).count()
    )
    coverage_gaps = (
        artifact_scope.filter(
            or_(
                RegistryArtifact.signature_status.is_(None),
                func.lower(RegistryArtifact.signature_status) != 'signed',
                RegistryArtifact.sbom_status.is_(None),
                func.lower(RegistryArtifact.sbom_status) != 'available',
            )
        )
        .order_by(None)
        .count()
    )

    latest_snapshot_ids = (
        RegistryScanSnapshot.query.with_entities(func.max(RegistryScanSnapshot.id).label('id'))
        .group_by(RegistryScanSnapshot.artifact_id)
        .subquery()
    )
    finding_scope = (
        RegistryVulnerability.query.join(
            RegistryScanSnapshot,
            RegistryVulnerability.scan_snapshot_id == RegistryScanSnapshot.id,
        )
        .join(latest_snapshot_ids, RegistryScanSnapshot.id == latest_snapshot_ids.c.id)
        .join(RegistryArtifact, RegistryScanSnapshot.artifact_id == RegistryArtifact.id)
        .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
    )
    finding_scope = _apply_source_scope(finding_scope, source_ids, scoped=scoped)
    critical_total = (
        finding_scope.filter(func.lower(RegistryVulnerability.severity) == 'critical').order_by(None).count()
    )
    high_total = finding_scope.filter(func.lower(RegistryVulnerability.severity) == 'high').order_by(None).count()
    affected_artifacts = int(
        finding_scope.filter(func.lower(RegistryVulnerability.severity).in_(('critical', 'high')))
        .with_entities(func.count(func.distinct(RegistryScanSnapshot.artifact_id)))
        .scalar()
        or 0
    )
    runtime_scope = (
        RegistryWorkloadBinding.query.join(
            RegistryArtifact,
            RegistryWorkloadBinding.artifact_id == RegistryArtifact.id,
        )
        .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
        .join(RegistryScanSnapshot, RegistryScanSnapshot.artifact_id == RegistryArtifact.id)
        .join(latest_snapshot_ids, RegistryScanSnapshot.id == latest_snapshot_ids.c.id)
        .join(
            RegistryVulnerability,
            RegistryVulnerability.scan_snapshot_id == RegistryScanSnapshot.id,
        )
        .filter(func.lower(RegistryVulnerability.severity).in_(('critical', 'high')))
    )
    runtime_scope = _apply_source_scope(runtime_scope, source_ids, scoped=scoped)
    runtime_exposed = int(
        runtime_scope.with_entities(func.count(func.distinct(RegistryWorkloadBinding.id))).scalar() or 0
    )

    latest_job = (
        JobExecution.query.filter(JobExecution.job_type == 'artifact_registry_security')
        .order_by(JobExecution.created_at.desc())
        .first()
    )
    latest_success = (
        JobExecution.query.filter(
            JobExecution.job_type == 'artifact_registry_security',
            JobExecution.status.in_(('succeeded', 'partially_succeeded')),
        )
        .order_by(JobExecution.completed_at.desc(), JobExecution.created_at.desc())
        .first()
    )
    latest_scan_query = (
        RegistryScanSnapshot.query.join(
            RegistryArtifact,
            RegistryScanSnapshot.artifact_id == RegistryArtifact.id,
        )
        .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
    )
    latest_scan_query = _apply_source_scope(latest_scan_query, source_ids, scoped=scoped)
    latest_evidence_at = latest_scan_query.with_entities(func.max(RegistryScanSnapshot.observed_at)).scalar()
    coverage_count = scanned_artifacts if view == 'vulnerabilities' else evidence_count
    snapshot = _snapshot_status(
        artifact_total=artifact_total,
        evidence_count=coverage_count,
        latest_job=latest_job,
        latest_success=latest_success,
        latest_evidence_at=latest_evidence_at,
    )
    return {
        'artifact_scope': artifact_scope,
        'finding_scope': finding_scope,
        'evidence_filter': evidence_filter,
        'artifact_total': artifact_total,
        'evidence_count': evidence_count,
        'scanned_artifacts': scanned_artifacts,
        'signature_observed': signature_observed,
        'sbom_available': sbom_available,
        'coverage_gaps': coverage_gaps,
        'critical_total': critical_total,
        'high_total': high_total,
        'affected_artifacts': affected_artifacts,
        'runtime_exposed': runtime_exposed,
        'finding_total': finding_scope.order_by(None).count(),
        'coverage_count': coverage_count,
        'snapshot': snapshot,
    }


def _security_source_capabilities(
    scoped_sources: list[IntegrationInstance],
    *,
    evidence_filter: Any,
) -> list[dict[str, Any]]:
    collectors = {collector.provider_key: collector for collector in registered_registry_security_collectors()}
    rows: list[dict[str, Any]] = []
    for source in scoped_sources:
        source_artifacts = (
            RegistryArtifact.query.join(
                RegistryRepository,
                RegistryArtifact.repository_id == RegistryRepository.id,
            )
            .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
            .filter(RegistryProject.integration_instance_id == int(source.id))
        )
        attempted = bool(source_artifacts.filter(evidence_filter).order_by(None).count())
        collector = collectors.get(source.provider_key)
        capabilities = collector.capabilities if collector is not None else frozenset()
        rows.append(
            {
                'source_name': source.name,
                'provider_label': source.provider_key.replace('_', ' ').title(),
                'artifact_count': source_artifacts.order_by(None).count(),
                'vulnerability': _capability_state(
                    supported='vulnerability' in capabilities,
                    observed=bool(
                        source_artifacts.filter(RegistryArtifact.scan_status.isnot(None)).order_by(None).count()
                    ),
                    attempted=attempted,
                ),
                'signature': _capability_state(
                    supported='signature' in capabilities,
                    observed=bool(
                        source_artifacts.filter(RegistryArtifact.signature_status.isnot(None)).order_by(None).count()
                    ),
                    attempted=attempted,
                ),
                'sbom': _capability_state(
                    supported='sbom' in capabilities,
                    observed=bool(
                        source_artifacts.filter(RegistryArtifact.sbom_status.isnot(None)).order_by(None).count()
                    ),
                    attempted=attempted,
                ),
            }
        )
    return rows


def _security_vulnerability_page(
    finding_scope: Any,
    *,
    source_by_id: dict[int, IntegrationInstance],
    severity_value: str,
    search_value: str,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], Any]:
    query = finding_scope.options(
        joinedload(RegistryVulnerability.scan_snapshot)
        .joinedload(RegistryScanSnapshot.artifact)
        .joinedload(RegistryArtifact.repository)
        .joinedload(RegistryRepository.project)
    )
    if severity_value:
        query = query.filter(func.lower(RegistryVulnerability.severity) == severity_value)
    if search_value:
        pattern = f'%{search_value}%'
        query = query.filter(
            or_(
                func.lower(RegistryVulnerability.vulnerability_id).like(pattern),
                func.lower(RegistryVulnerability.package).like(pattern),
                func.lower(func.coalesce(RegistryVulnerability.fixed_version, '')).like(pattern),
                func.lower(RegistryArtifact.digest).like(pattern),
                func.lower(RegistryRepository.name).like(pattern),
                func.lower(RegistryProject.name).like(pattern),
            )
        )
    severity_rank = case(
        (func.lower(RegistryVulnerability.severity) == 'critical', 0),
        (func.lower(RegistryVulnerability.severity) == 'high', 1),
        (func.lower(RegistryVulnerability.severity) == 'medium', 2),
        (func.lower(RegistryVulnerability.severity) == 'low', 3),
        (func.lower(RegistryVulnerability.severity) == 'negligible', 4),
        else_=5,
    )
    page_items, pagination = paginate_query(
        query.order_by(severity_rank.asc(), RegistryVulnerability.vulnerability_id.asc()),
        page=page,
        per_page=per_page,
    )
    artifact_ids = [int(item.scan_snapshot.artifact_id) for item in page_items]
    runtime_counts = {
        int(artifact_id): int(count)
        for artifact_id, count in (
            RegistryWorkloadBinding.query.with_entities(
                RegistryWorkloadBinding.artifact_id,
                func.count(RegistryWorkloadBinding.id),
            )
            .filter(RegistryWorkloadBinding.artifact_id.in_(artifact_ids))
            .group_by(RegistryWorkloadBinding.artifact_id)
            .all()
            if artifact_ids
            else []
        )
    }
    rows: list[dict[str, Any]] = []
    for item in page_items:
        scan_snapshot = item.scan_snapshot
        artifact = scan_snapshot.artifact
        repository = artifact.repository
        project = repository.project
        source = source_by_id.get(int(project.integration_instance_id))
        fixed_version = str(item.fixed_version or '').strip()
        rows.append(
            {
                'id': int(item.id),
                'artifact_id': int(artifact.id),
                'vulnerability_id': item.vulnerability_id,
                'severity': str(item.severity or 'unknown').lower(),
                'severity_label': str(item.severity or 'unknown').replace('_', ' ').title(),
                'package': item.package or 'Unknown Package',
                'installed_version': item.installed_version or 'Unknown',
                'fixed_version': fixed_version or 'No Fix Observed',
                'fix_available': bool(fixed_version),
                'digest': artifact.digest,
                'digest_short': (
                    artifact.digest if len(artifact.digest) <= 28 else f'{artifact.digest[:18]}…{artifact.digest[-8:]}'
                ),
                'repository': repository.name,
                'project': project.name,
                'provider_label': (source.provider_key.replace('_', ' ').title() if source is not None else 'Registry'),
                'source_name': source.name if source is not None else 'Unknown Source',
                'runtime_exposure_count': runtime_counts.get(int(artifact.id), 0),
                'observed_at': scan_snapshot.observed_at,
                'freshness': _freshness(scan_snapshot.observed_at),
            }
        )
    return rows, pagination


def _security_supply_evidence_page(
    artifact_scope: Any,
    *,
    source_by_id: dict[int, IntegrationInstance],
    snapshot: dict[str, Any],
    search_value: str,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], Any]:
    query = artifact_scope
    if search_value:
        pattern = f'%{search_value}%'
        query = query.filter(
            or_(
                func.lower(RegistryArtifact.digest).like(pattern),
                func.lower(RegistryRepository.name).like(pattern),
                func.lower(RegistryProject.name).like(pattern),
            )
        )
    page_items, pagination = paginate_query(
        query.order_by(
            RegistryProject.name.asc(),
            RegistryRepository.name.asc(),
            RegistryArtifact.digest.asc(),
        ),
        page=page,
        per_page=per_page,
    )
    rows: list[dict[str, Any]] = []
    for artifact in page_items:
        repository = artifact.repository
        project = repository.project
        source = source_by_id.get(int(project.integration_instance_id))
        rows.append(
            {
                'id': int(artifact.id),
                'digest': artifact.digest,
                'digest_short': (
                    artifact.digest if len(artifact.digest) <= 28 else f'{artifact.digest[:18]}…{artifact.digest[-8:]}'
                ),
                'repository': repository.name,
                'project': project.name,
                'provider_label': (source.provider_key.replace('_', ' ').title() if source is not None else 'Registry'),
                'source_name': source.name if source is not None else 'Unknown Source',
                'signature': _evidence_state(artifact.signature_status, evidence='signature'),
                'trust': {'label': 'Not Evaluated', 'tone': 'unknown'},
                'sbom': _evidence_state(artifact.sbom_status, evidence='sbom'),
                'snapshot_label': snapshot['status'],
                'snapshot_tone': snapshot['tone'],
                'observed_at': snapshot['latest_collected_at'],
            }
        )
    return rows, pagination


def _security_finding_interpretation(evidence: dict[str, Any]) -> dict[str, str]:
    snapshot = evidence['snapshot']
    scanned_artifacts = evidence['scanned_artifacts']
    artifact_total = evidence['artifact_total']
    finding_total = evidence['finding_total']
    if snapshot['status'] == 'Not Collected':
        return {
            'title': 'Security Evidence Not Collected',
            'description': 'Run Security Sync before interpreting an empty vulnerability result.',
            'tone': 'unknown',
            'icon': 'clock-alert',
        }
    if snapshot['status'] == 'Refresh Failed':
        return {
            'title': 'Previous Findings Retained',
            'description': 'The latest refresh failed; committed findings still reflect the last successful Security Sync.',
            'tone': 'warning',
            'icon': 'shield-alert',
        }
    if scanned_artifacts == 0:
        return {
            'title': 'No Provider Scan Evidence',
            'description': 'Security Sync found no usable vulnerability scan evidence. KAORI does not trigger provider scans.',
            'tone': 'warning',
            'icon': 'scan-search',
        }
    if scanned_artifacts < artifact_total:
        return {
            'title': 'Partial Scan Coverage',
            'description': f'Findings cover {scanned_artifacts} of {artifact_total} artifacts with usable committed scan evidence.',
            'tone': 'warning',
            'icon': 'scan-search',
        }
    if finding_total == 0:
        return {
            'title': 'No Vulnerabilities Observed',
            'description': 'No findings were observed in the current committed scan evidence for this scope.',
            'tone': 'normal',
            'icon': 'shield-check',
        }
    return {
        'title': 'Committed Vulnerability Findings',
        'description': 'Findings reflect the latest committed provider scan evidence and current Registry scope.',
        'tone': 'critical' if evidence['critical_total'] else ('warning' if evidence['high_total'] else 'info'),
        'icon': 'shield-alert',
    }


def _security_finding_empty_state(
    evidence: dict[str, Any],
    *,
    filters_active: bool,
) -> dict[str, str]:
    if filters_active:
        return {
            'label': 'Filtered Security Evidence',
            'title': 'No Findings Match This View',
            'description': 'Adjust the active filters to review other committed vulnerability findings.',
        }
    if evidence['snapshot']['status'] == 'Not Collected':
        return {
            'label': 'Committed Security',
            'title': 'Security Evidence Not Collected',
            'description': 'Run Security Sync to collect provider security evidence for committed artifacts.',
        }
    if evidence['scanned_artifacts'] == 0:
        return {
            'label': 'Committed Security',
            'title': 'No Vulnerability Scan Evidence',
            'description': 'No usable provider scan evidence is committed for this scope. KAORI does not trigger scans.',
        }
    if evidence['finding_total'] == 0:
        return {
            'label': 'Committed Security',
            'title': 'No Vulnerabilities Observed',
            'description': 'No vulnerability findings were observed in the current committed scan evidence.',
        }
    return {
        'label': 'Committed Security',
        'title': 'No Findings Match This Page',
        'description': 'No committed vulnerability finding is available on this page.',
    }


def _security_posture(evidence: dict[str, Any]) -> dict[str, str]:
    if evidence['critical_total']:
        return {'label': 'Critical Findings', 'tone': 'critical'}
    if evidence['high_total']:
        return {'label': 'Review Required', 'tone': 'warning'}
    if evidence['artifact_total'] and evidence['scanned_artifacts'] < evidence['artifact_total']:
        return {'label': 'Coverage Incomplete', 'tone': 'warning'}
    if evidence['artifact_total']:
        return {'label': 'No High-Risk Findings', 'tone': 'normal'}
    return {'label': 'No Evidence', 'tone': 'unknown'}


def build_security(
    *,
    kind: str = 'vulnerabilities',
    section: str = '',
    search: str = '',
    severity: str = '',
    provider: str = '',
    source_id: int | None = None,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    view = 'supply_chain' if kind == 'supply_chain' else 'vulnerabilities'
    supply_section = str(section or 'capabilities').strip().lower()
    if supply_section not in {'capabilities', 'evidence'}:
        supply_section = 'capabilities'
    provider_value = provider.strip().lower()
    severity_value = severity.strip().lower()
    search_value = search.strip().lower()
    sources = _providers()
    scoped_sources = _scoped_sources(sources, provider=provider_value, source_id=source_id)
    source_by_id = {int(item.id): item for item in sources}
    evidence = _security_scope_evidence(
        sources=sources,
        scoped_sources=scoped_sources,
        explicit_scope=bool(provider_value or source_id is not None),
        view=view,
    )
    active_scope_label, source_label = _security_scope_labels(
        provider_value=provider_value,
        source_id=source_id,
        scoped_sources=scoped_sources,
    )
    snapshot_context = _security_snapshot_context(
        evidence,
        active_scope_label=active_scope_label,
        source_label=source_label,
        view=view,
    )
    source_capabilities = _security_source_capabilities(
        scoped_sources,
        evidence_filter=evidence['evidence_filter'],
    )
    capability_filtered = [
        row
        for row in source_capabilities
        if not search_value or search_value in f'{row["source_name"]} {row["provider_label"]}'.lower()
    ]
    capability_rows, capability_pagination = paginate_sequence(
        capability_filtered,
        page=page,
        per_page=per_page,
    )

    rows: list[dict[str, Any]] = []
    if view == 'vulnerabilities':
        rows, pagination = _security_vulnerability_page(
            evidence['finding_scope'],
            source_by_id=source_by_id,
            severity_value=severity_value,
            search_value=search_value,
            page=page,
            per_page=per_page,
        )
    elif supply_section == 'evidence':
        rows, pagination = _security_supply_evidence_page(
            evidence['artifact_scope'],
            source_by_id=source_by_id,
            snapshot=evidence['snapshot'],
            search_value=search_value,
            page=page,
            per_page=per_page,
        )
    else:
        _, pagination = paginate_sequence([], page=1, per_page=per_page)

    active_pagination = (
        capability_pagination if view == 'supply_chain' and supply_section == 'capabilities' else pagination
    )
    filters_active = bool(search_value or severity_value or provider_value or source_id is not None)
    return {
        'view': view,
        'supply_section': supply_section,
        'title': 'Vulnerabilities' if view == 'vulnerabilities' else 'Supply Chain',
        'description': (
            'Prioritize vulnerabilities by digest and Kubernetes runtime context.'
            if view == 'vulnerabilities'
            else 'Review provider signature and SBOM evidence without trust-policy claims.'
        ),
        'endpoint': (
            'artifact_registry.security' if view == 'vulnerabilities' else 'artifact_registry.security_supply_chain'
        ),
        'setup_blocked': not sources,
        'inventory_required': bool(sources) and RegistryArtifact.query.count() == 0,
        'snapshot': snapshot_context,
        'sync_state': build_registry_security_sync_state(),
        'finding_interpretation': _security_finding_interpretation(evidence),
        'finding_empty_state': _security_finding_empty_state(evidence, filters_active=filters_active),
        'finding_total': int(evidence['finding_total']),
        'posture': _security_posture(evidence),
        'artifact_total': evidence['artifact_total'],
        'evidence_count': evidence['evidence_count'],
        'scanned_artifacts': evidence['scanned_artifacts'],
        'critical': int(evidence['critical_total']),
        'high': int(evidence['high_total']),
        'affected_artifacts': evidence['affected_artifacts'],
        'runtime_exposed': evidence['runtime_exposed'],
        'signature_observed': int(evidence['signature_observed']),
        'sbom_available': int(evidence['sbom_available']),
        'coverage_gaps': int(evidence['coverage_gaps']),
        'source_count': len(scoped_sources),
        'sources': [
            {
                'id': int(item.id),
                'name': item.name,
                'provider_key': item.provider_key,
                'provider_label': item.provider_key.replace('_', ' ').title(),
            }
            for item in sources
        ],
        'providers': [
            {'value': key, 'label': key.replace('_', ' ').title()}
            for key in sorted({item.provider_key for item in sources})
        ],
        'source_capabilities': source_capabilities,
        'capability_rows': capability_rows,
        'capability_pagination': capability_pagination,
        'severity_options': [
            {'value': value, 'label': value.title()}
            for value in ('critical', 'high', 'medium', 'low', 'negligible', 'unknown')
        ],
        'filters': {
            'search': search,
            'severity': severity_value,
            'provider': provider_value,
            'source_id': source_id,
        },
        'rows': rows,
        'pagination': pagination,
        'active_pagination': active_pagination,
    }
