from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload

from app.common.pagination import paginate_sequence
from app.models.integration import IntegrationInstance
from app.models.registry_artifact import RegistryArtifact, RegistryProject, RegistryRepository
from app.models.registry_security import (
    RegistryArtifactSecuritySnapshot,
    RegistrySecurityCollectionState,
    RegistryVulnerabilityFinding,
)


def _freshness(observed_at: datetime | None) -> dict[str, str]:
    if observed_at is None:
        return {'label': 'Not Collected', 'tone': 'unknown'}
    value = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC)
    age = max((datetime.now(UTC) - value.astimezone(UTC)).total_seconds(), 0)
    if age <= 3600:
        return {'label': 'Fresh', 'tone': 'normal'}
    if age <= 86400:
        return {'label': 'Aging', 'tone': 'warning'}
    return {'label': 'Stale', 'tone': 'critical'}


def _capability_state(value: str | None) -> dict[str, str]:
    key = str(value or 'not_collected').strip().lower()
    mapping = {
        'supported_observed': ('Supported · Observed', 'normal'),
        'supported_unavailable': ('Supported · Unavailable', 'warning'),
        'unsupported': ('Unsupported By Provider', 'unknown'),
        'not_collected': ('Not Collected', 'unknown'),
    }
    label, tone = mapping.get(key, ('Not Collected', 'unknown'))
    return {'key': key, 'label': label, 'tone': tone}


def _evidence_state(value: str | None) -> dict[str, str]:
    key = str(value or 'not_collected').strip().lower()
    mapping = {
        'observed': ('Observed', 'normal'),
        'unavailable': ('Unavailable', 'warning'),
        'unsupported': ('Unsupported', 'unknown'),
        'not_collected': ('Not Collected', 'unknown'),
        'not_evaluated': ('Not Evaluated', 'unknown'),
    }
    label, tone = mapping.get(key, (key.replace('_', ' ').title(), 'unknown'))
    return {'key': key, 'label': label, 'tone': tone}


def _sources() -> list[IntegrationInstance]:
    return (
        IntegrationInstance.query.filter(IntegrationInstance.integration_type == 'registry')
        .order_by(IntegrationInstance.name.asc())
        .all()
    )


def _base_context() -> dict[str, Any]:
    sources = _sources()
    states = RegistrySecurityCollectionState.query.all()
    latest = max((state.observed_at for state in states if state.observed_at), default=None)
    return {
        'setup_blocked': not sources,
        'inventory_required': bool(sources) and RegistryArtifact.query.count() == 0,
        'source_count': len(sources),
        'sources': [{'id': item.id, 'name': item.name, 'provider_key': item.provider_key} for item in sources],
        'providers': [
            {'value': key, 'label': key.replace('_', ' ').title()}
            for key in sorted({item.provider_key for item in sources})
        ],
        'collection_states': states,
        'latest_observed_at': latest,
        'freshness': _freshness(latest),
        'finding_count': sum(state.finding_count for state in states),
        'critical_count': sum(state.critical_count for state in states),
        'high_count': sum(state.high_count for state in states),
        'scanned_artifact_count': sum(state.scanned_artifact_count for state in states),
        'artifact_count': sum(state.artifact_count for state in states),
        'signature_observed_count': sum(state.signature_observed_count for state in states),
        'sbom_observed_count': sum(state.sbom_observed_count for state in states),
        'capabilities': {
            'vulnerability': [_capability_state(state.vulnerability_capability_state) for state in states],
            'signature': [_capability_state(state.signature_capability_state) for state in states],
            'sbom': [_capability_state(state.sbom_capability_state) for state in states],
        },
    }


@dataclass(frozen=True, slots=True)
class SecurityFilters:
    query: str = ''
    severity: str = ''
    provider: str = ''
    source_id: int | None = None
    page: int = 1
    per_page: int = 5


def build_vulnerabilities(filters: SecurityFilters) -> dict[str, Any]:
    base = _base_context()
    rows: list[dict[str, Any]] = []
    query = RegistryVulnerabilityFinding.query.options(
        joinedload(RegistryVulnerabilityFinding.snapshot)
        .joinedload(RegistryArtifactSecuritySnapshot.artifact)
        .joinedload(RegistryArtifact.repository)
        .joinedload(RegistryRepository.project)
        .joinedload(RegistryProject.integration_instance)
    )
    for finding in query.all():
        snapshot = finding.snapshot
        artifact = snapshot.artifact
        repository = artifact.repository
        project = repository.project
        source = project.integration_instance
        rows.append(
            {
                'id': finding.id,
                'vulnerability_id': finding.vulnerability_id,
                'severity': finding.severity,
                'severity_label': finding.severity.title(),
                'package': finding.package or 'Not Observed',
                'installed_version': finding.installed_version or 'Not Observed',
                'fixed_version': finding.fixed_version or 'No Fix Observed',
                'fix_available': finding.fix_available,
                'artifact_digest': artifact.digest,
                'digest_short': artifact.digest if len(artifact.digest) <= 26 else f'{artifact.digest[:18]}…{artifact.digest[-7:]}',
                'repository_name': repository.name,
                'project_name': project.name,
                'source_id': source.id,
                'source_name': source.name,
                'provider_key': source.provider_key,
                'provider_label': source.provider_key.replace('_', ' ').title(),
                'observed_at': finding.observed_at,
                'freshness': _freshness(finding.observed_at),
            }
        )
    text = filters.query.strip().lower()
    filtered = [
        row
        for row in rows
        if (
            not text
            or text in ' '.join(
                str(row[key])
                for key in ('vulnerability_id', 'package', 'artifact_digest', 'repository_name', 'project_name', 'source_name')
            ).lower()
        )
        and (not filters.severity or row['severity'] == filters.severity)
        and (not filters.provider or row['provider_key'] == filters.provider)
        and (filters.source_id is None or row['source_id'] == filters.source_id)
    ]
    page_rows, pagination = paginate_sequence(filtered, page=filters.page, per_page=filters.per_page)
    return {
        **base,
        'rows': page_rows,
        'pagination': pagination,
        'total': len(filtered),
        'severity_options': [
            {'value': value, 'label': value.title()}
            for value in ('critical', 'high', 'medium', 'low', 'negligible', 'unknown')
        ],
    }


def build_supply_chain(filters: SecurityFilters) -> dict[str, Any]:
    base = _base_context()
    rows: list[dict[str, Any]] = []
    query = RegistryArtifactSecuritySnapshot.query.options(
        joinedload(RegistryArtifactSecuritySnapshot.artifact)
        .joinedload(RegistryArtifact.repository)
        .joinedload(RegistryRepository.project)
        .joinedload(RegistryProject.integration_instance)
    )
    for snapshot in query.all():
        artifact = snapshot.artifact
        repository = artifact.repository
        project = repository.project
        source = project.integration_instance
        rows.append(
            {
                'id': snapshot.id,
                'artifact_digest': artifact.digest,
                'digest_short': artifact.digest if len(artifact.digest) <= 26 else f'{artifact.digest[:18]}…{artifact.digest[-7:]}',
                'repository_name': repository.name,
                'project_name': project.name,
                'source_id': source.id,
                'source_name': source.name,
                'provider_key': source.provider_key,
                'provider_label': source.provider_key.replace('_', ' ').title(),
                'signature': _evidence_state(snapshot.signature_state),
                'signature_count': snapshot.signature_count,
                'trust': _evidence_state(snapshot.trust_state),
                'sbom': _evidence_state(snapshot.sbom_state),
                'sbom_count': snapshot.sbom_count,
                'vulnerability': _evidence_state(snapshot.vulnerability_state),
                'scan_status': snapshot.scan_status.replace('_', ' ').title(),
                'observed_at': snapshot.observed_at,
                'freshness': _freshness(snapshot.observed_at),
            }
        )
    text = filters.query.strip().lower()
    filtered = [
        row
        for row in rows
        if (
            not text
            or text in ' '.join(
                str(row[key])
                for key in ('artifact_digest', 'repository_name', 'project_name', 'source_name', 'provider_label')
            ).lower()
        )
        and (not filters.provider or row['provider_key'] == filters.provider)
        and (filters.source_id is None or row['source_id'] == filters.source_id)
    ]
    page_rows, pagination = paginate_sequence(filtered, page=filters.page, per_page=filters.per_page)
    return {**base, 'rows': page_rows, 'pagination': pagination, 'total': len(filtered)}
