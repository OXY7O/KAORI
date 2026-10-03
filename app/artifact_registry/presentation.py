from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload

from app.common.pagination import paginate_sequence
from app.models.integration import IntegrationInstance
from app.models.registry import RegistryArtifact, RegistryCollectionState, RegistryProject, RegistryRepository

FRESHNESS_HOURS = 24


def _fmt_bytes(value: int | None) -> str:
    if value is None:
        return 'Not Collected'
    size = float(max(value, 0))
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f'{int(size)} B' if index == 0 else f'{size:.2f} {units[index]}'


def _providers() -> list[IntegrationInstance]:
    return (
        IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.name.asc())
        .all()
    )


def _state_view(state: RegistryCollectionState | None) -> dict[str, Any]:
    if state is None or state.last_committed_at is None:
        return {'label': 'Not Collected', 'tone': 'unknown', 'observed_at': None, 'is_stale': False}
    stale = state.last_committed_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
    return {
        'label': 'Stale Snapshot' if stale else 'Current Snapshot',
        'tone': 'warning' if stale else 'normal',
        'observed_at': state.last_observed_at,
        'committed_at': state.last_committed_at,
        'is_stale': stale,
    }


def build_overview() -> dict[str, Any]:
    providers = _providers()
    states = RegistryCollectionState.query.all()
    projects = RegistryProject.query.count()
    repositories = RegistryRepository.query.count()
    artifacts = RegistryArtifact.query.count()
    tags = sum(len(item.tags) for item in RegistryArtifact.query.options(joinedload(RegistryArtifact.tags)).all())
    ready_states = [state for state in states if state.status == 'ready' and state.last_committed_at is not None]
    latest = max((state.last_committed_at for state in ready_states if state.last_committed_at), default=None)
    stale_count = sum(bool(_state_view(state)['is_stale']) for state in ready_states)
    if not providers:
        posture = {'label': 'Setup Required', 'tone': 'unknown'}
    elif not ready_states:
        posture = {'label': 'Inventory Pending', 'tone': 'warning'}
    elif stale_count:
        posture = {'label': 'Attention Required', 'tone': 'warning'}
    else:
        posture = {'label': 'Ready', 'tone': 'normal'}
    return {
        'setup': {'is_blocked': not providers, 'provider_count': len(providers)},
        'provider_count': len(providers),
        'project_count': projects,
        'repository_count': repositories,
        'artifact_count': artifacts,
        'tag_count': tags,
        'latest_committed_at': latest,
        'posture': posture,
        'snapshot_count': len(ready_states),
        'stale_snapshot_count': stale_count,
        'provider_rows': [
            {
                'id': provider.id,
                'name': provider.name,
                'provider_key': provider.provider_key,
                'provider_label': str((provider.metadata_json or {}).get('provider_label') or provider.provider_key.title()),
                'environment': provider.environment or 'Not Set',
                'readiness': provider.readiness_status or 'validation_required',
                'health': provider.health_status or 'unknown',
                'snapshot': _state_view(
                    next((state for state in states if state.integration_instance_id == provider.id), None)
                ),
            }
            for provider in providers
        ],
    }


def _project_row(item: RegistryProject) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'public': item.public,
        'repository_count': item.repository_count if item.repository_count is not None else len(item.repositories),
        'provider': item.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _repository_row(item: RegistryRepository) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'project': item.project.name,
        'artifact_count': item.artifact_count if item.artifact_count is not None else len(item.artifacts),
        'pull_count': item.pull_count,
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
        'observed_at': item.observed_at,
    }


def build_inventory(*, resource: str, page: int, per_page: int, search: str = '') -> dict[str, Any]:
    resource = resource if resource in {'projects', 'repositories', 'artifacts'} else 'projects'
    search_value = search.strip().lower()
    if resource == 'repositories':
        items = RegistryRepository.query.options(
            joinedload(RegistryRepository.project),
            joinedload(RegistryRepository.artifacts),
        ).all()
        rows = [_repository_row(item) for item in items]
        filtered = [
            row
            for row in rows
            if not search_value or search_value in f"{row['name']} {row['project']}".lower()
        ]
    elif resource == 'artifacts':
        items = RegistryArtifact.query.options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            joinedload(RegistryArtifact.tags),
        ).all()
        rows = [_artifact_row(item) for item in items]
        filtered = [
            row
            for row in rows
            if not search_value
            or search_value
            in f"{row['digest']} {row['repository']} {row['project']} {' '.join(row['tags'])}".lower()
        ]
    else:
        items = RegistryProject.query.options(joinedload(RegistryProject.repositories)).all()
        rows = [_project_row(item) for item in items]
        filtered = [row for row in rows if not search_value or search_value in row['name'].lower()]
    paged, pagination = paginate_sequence(filtered, page=page, per_page=per_page)
    overview = build_overview()
    return {
        'resource': resource,
        'rows': paged,
        'pagination': pagination,
        'search': search,
        'total': len(filtered),
        'setup': overview['setup'],
        'overview': overview,
    }



def build_security(*, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    artifacts = RegistryArtifact.query.options(
        joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
    ).all()
    rows: list[dict[str, Any]] = []
    critical_total = high_total = scanned = signed = sbom_available = 0
    for artifact in artifacts:
        summary = artifact.vulnerability_summary if isinstance(artifact.vulnerability_summary, dict) else {}
        critical = int(summary.get('critical') or 0)
        high = int(summary.get('high') or 0)
        critical_total += critical
        high_total += high
        has_scan = bool(artifact.scan_status)
        scanned += int(has_scan)
        signature = str(artifact.signature_status or 'not_observed')
        sbom = str(artifact.sbom_status or 'not_observed')
        signed += int(signature == 'signed')
        sbom_available += int(sbom == 'available')
        scan_status = str(artifact.scan_status or 'not_scanned')
        scan_ready = scan_status in {'success', 'finished', 'completed'}
        rows.append(
            {
                'id': artifact.id,
                'digest': artifact.digest,
                'digest_short': artifact.digest if len(artifact.digest) <= 28 else f'{artifact.digest[:18]}…{artifact.digest[-8:]}',
                'repository': artifact.repository.name,
                'project': artifact.repository.project.name,
                'critical': critical,
                'high': high,
                'scan_label': scan_status.replace('_', ' ').title(),
                'scan_tone': 'normal' if scan_ready else ('unknown' if not has_scan else 'warning'),
                'signature_label': signature.replace('_', ' ').title(),
                'signature_tone': 'normal' if signature == 'signed' else ('warning' if signature == 'unsigned' else 'unknown'),
                'sbom_label': sbom.replace('_', ' ').title(),
                'sbom_tone': 'normal' if sbom == 'available' else ('info' if sbom == 'observed' else 'unknown'),
                'observed_at': artifact.observed_at,
            }
        )
    rows.sort(key=lambda item: (-item['critical'], -item['high'], item['project'], item['repository']))
    paged, pagination = paginate_sequence(rows, page=page, per_page=per_page)
    total = len(artifacts)
    coverage = round((scanned / total) * 100) if total else 0
    sbom_coverage = round((sbom_available / total) * 100) if total else 0
    if critical_total:
        posture = {'label': 'Critical Findings', 'tone': 'critical'}
    elif high_total:
        posture = {'label': 'Review Required', 'tone': 'warning'}
    elif total and scanned < total:
        posture = {'label': 'Coverage Incomplete', 'tone': 'warning'}
    elif total:
        posture = {'label': 'No High-Risk Findings', 'tone': 'normal'}
    else:
        posture = {'label': 'No Evidence', 'tone': 'unknown'}
    return {
        'setup': build_overview()['setup'],
        'total': total,
        'scanned': scanned,
        'scan_coverage': coverage,
        'critical': critical_total,
        'high': high_total,
        'signed': signed,
        'sbom_available': sbom_available,
        'sbom_coverage': sbom_coverage,
        'posture': posture,
        'rows': paged,
        'pagination': pagination,
    }
