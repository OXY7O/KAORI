"""Security Posture reads qualified committed evidence from existing domains.

Initial source: Registry scanner findings correlated with Kubernetes runtime.
Provider engines and source-domain evidence remain authoritative.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select

from app.artifact_registry.correlation_sync_jobs import correlation_prerequisites
from app.artifact_registry.presentation_common import _human_time
from app.artifact_registry.presentation_runtime import _runtime_snapshot_state
from app.artifact_registry.security.contracts import SUCCESSFUL_REGISTRY_SCAN_STATUSES
from app.artifact_registry.security.presentation import _aware_datetime, _providers
from app.common.pagination import paginate_query, paginate_sequence, positive_int
from app.models.registry import (
    RegistryArtifact,
    RegistryProject,
    RegistryRepository,
    RegistryScanSnapshot,
    RegistryVulnerability,
    RegistryWorkloadBinding,
)

_SCAN_WINDOW = timedelta(hours=24)
_SEVERITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'negligible': 4}


def _scanner_coverage_state(
    *,
    source_count: int,
    artifact_total: int,
    scanned_artifacts: int,
    oldest_scan: datetime | None,
) -> dict[str, str]:
    """Distinguish missing, partial and stale source evidence without all-clear claims."""
    observed = _aware_datetime(oldest_scan)
    if not source_count or observed is None:
        return {'label': 'Not Collected', 'tone': 'unknown'}
    recent = observed >= datetime.now(UTC) - _SCAN_WINDOW
    partial = scanned_artifacts < artifact_total
    if partial and not recent:
        return {'label': 'Partial / Stale', 'tone': 'warning'}
    if partial:
        return {'label': 'Partial', 'tone': 'warning'}
    if not recent:
        return {'label': 'Stale', 'tone': 'warning'}
    return {'label': 'Observed', 'tone': 'normal'}


def _scanner_findings(source_ids: list[int]) -> Any:
    """Latest usable successful scan, qualified by active source ownership."""
    latest_success = (
        select(func.max(RegistryScanSnapshot.id).label('id'))
        .where(func.lower(RegistryScanSnapshot.status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES))
        .group_by(RegistryScanSnapshot.artifact_id)
        .subquery()
    )
    return (
        RegistryVulnerability.query.join(
            RegistryScanSnapshot,
            RegistryVulnerability.scan_snapshot_id == RegistryScanSnapshot.id,
        )
        .join(latest_success, RegistryScanSnapshot.id == latest_success.c.id)
        .join(RegistryArtifact, RegistryScanSnapshot.artifact_id == RegistryArtifact.id)
        .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
        .filter(RegistryProject.integration_instance_id.in_(source_ids))
    )


def build_security_posture(
    *,
    can_view_registry: bool,
    search: str = '',
    severity: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    """Paginated cross-domain read projection; never a scanner or global all-clear."""
    if not can_view_registry:
        _, pagination = paginate_sequence([], page=page, per_page=per_page)
        return {
            'rows': [],
            'pagination': pagination,
            'search': search,
            'severity': '',
            'severity_options': tuple(_SEVERITY_RANK),
            'sources': 0,
            'authorized_registry': False,
            'affected_artifacts': 0,
            'artifacts_total': 0,
            'scanned_artifacts': 0,
            'last_scan': None,
            'scan_updated_label': 'Not Collected',
            'scan_status': {'label': 'No Authorized Sources', 'tone': 'unknown'},
            'runtime_status': {
                'status': 'Not Collected',
                'tone': 'unknown',
                'description': 'No authorized committed Registry source.',
            },
            'has_complete_security_evidence': False,
        }
    sources = _providers()
    source_ids = [int(source.id) for source in sources]
    q = str(search or '').strip().upper()[:100]
    severity_value = str(severity or '').strip().lower()
    if severity_value not in _SEVERITY_RANK:
        severity_value = ''

    scoped_findings = _scanner_findings(source_ids)
    affected_digest_count = int(
        scoped_findings.with_entities(func.count(func.distinct(RegistryScanSnapshot.artifact_id))).scalar() or 0
    )
    all_cve_ids = func.upper(RegistryVulnerability.vulnerability_id)
    cve_findings = scoped_findings.filter(all_cve_ids.like('CVE-%'))
    if q:
        literal = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        cve_findings = cve_findings.filter(all_cve_ids.like(f'%{literal}%', escape='\\'))
    if severity_value:
        cve_findings = cve_findings.filter(func.lower(RegistryVulnerability.severity) == severity_value)

    rank = case(
        *[(func.lower(RegistryVulnerability.severity) == key, index) for key, index in _SEVERITY_RANK.items()],
        else_=5,
    )
    grouped = (
        cve_findings.outerjoin(
            RegistryWorkloadBinding,
            RegistryWorkloadBinding.artifact_id == RegistryScanSnapshot.artifact_id,
        )
        .with_entities(
            all_cve_ids.label('cve_id'),
            func.min(rank).label('severity_rank'),
            func.count(func.distinct(RegistryVulnerability.id)).label('finding_count'),
            func.count(func.distinct(RegistryScanSnapshot.artifact_id)).label('artifact_count'),
            func.count(func.distinct(RegistryWorkloadBinding.id)).label('binding_count'),
            func.count(
                func.distinct(
                    case((RegistryWorkloadBinding.match_type == 'digest', RegistryWorkloadBinding.id), else_=None)
                )
            ).label('digest_binding_count'),
            func.count(
                func.distinct(
                    case((RegistryWorkloadBinding.match_type != 'digest', RegistryWorkloadBinding.id), else_=None)
                )
            ).label('reference_binding_count'),
            func.max(RegistryScanSnapshot.observed_at).label('observed_at'),
        )
        .group_by(all_cve_ids)
    )
    page_rows, pagination = paginate_query(
        grouped.order_by(func.min(rank).asc(), all_cve_ids.asc()),
        page=positive_int(page),
        per_page=per_page,
    )
    rows = [
        {
            'cve_id': row.cve_id,
            'impact_available': bool(re.fullmatch(r'CVE-[0-9]{4}-[0-9]{4,}', row.cve_id or '')),
            'severity': next(
                (key.title() for key, order in _SEVERITY_RANK.items() if order == row.severity_rank), 'Unknown'
            ),
            'finding_count': int(row.finding_count or 0),
            'artifact_count': int(row.artifact_count or 0),
            'binding_count': int(row.binding_count or 0),
            'digest_binding_count': int(row.digest_binding_count or 0),
            'reference_binding_count': int(row.reference_binding_count or 0),
            'observed_at': row.observed_at,
        }
        for row in page_rows
    ]
    scanned_artifacts = 0
    artifacts_total = 0
    last_scan = None
    oldest_scan = None
    if source_ids:
        artifacts_total = int(
            RegistryArtifact.query.join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
            .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
            .filter(RegistryProject.integration_instance_id.in_(source_ids))
            .count()
        )
        scan_artifact_ids = (
            select(func.max(RegistryScanSnapshot.id).label('id'))
            .where(func.lower(RegistryScanSnapshot.status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES))
            .group_by(RegistryScanSnapshot.artifact_id)
            .subquery()
        )
        usable_scans = (
            RegistryScanSnapshot.query.join(scan_artifact_ids, RegistryScanSnapshot.id == scan_artifact_ids.c.id)
            .join(RegistryArtifact, RegistryScanSnapshot.artifact_id == RegistryArtifact.id)
            .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
            .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
            .filter(RegistryProject.integration_instance_id.in_(source_ids))
        )
        scanned_artifacts = usable_scans.order_by(None).count()
        last_scan = usable_scans.with_entities(func.max(RegistryScanSnapshot.observed_at)).scalar()
        oldest_scan = usable_scans.with_entities(func.min(RegistryScanSnapshot.observed_at)).scalar()

    oldest_observed = _aware_datetime(oldest_scan)
    recent = bool(oldest_observed and oldest_observed >= datetime.now(UTC) - _SCAN_WINDOW)
    scan_status = _scanner_coverage_state(
        source_count=len(sources),
        artifact_total=artifacts_total,
        scanned_artifacts=scanned_artifacts,
        oldest_scan=oldest_scan,
    )

    # Read the existing signed materialization status; never reimplement its
    # signature, freshness or failure semantics.
    correlation = (
        _runtime_snapshot_state(correlation_prerequisites())
        if source_ids
        else {'status': 'Not Collected', 'tone': 'unknown', 'description': 'No authorized committed Registry source.'}
    )
    return {
        'rows': rows,
        'pagination': pagination,
        'search': search,
        'severity': severity_value,
        'severity_options': ('critical', 'high', 'medium', 'low', 'negligible'),
        'sources': len(sources),
        'authorized_registry': can_view_registry,
        'affected_artifacts': affected_digest_count,
        'artifacts_total': artifacts_total,
        'scanned_artifacts': scanned_artifacts,
        'last_scan': last_scan,
        'scan_updated_label': f'Updated {_human_time(last_scan)}' if last_scan else 'Not Collected',
        'scan_status': scan_status,
        'runtime_status': correlation,
        'has_complete_security_evidence': bool(
            source_ids
            and last_scan
            and recent
            and scanned_artifacts == artifacts_total
            and correlation['status'] == 'Ready'
        ),
    }
