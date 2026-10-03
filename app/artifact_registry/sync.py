from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.extensions.db import db
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.models.harbor import HarborInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
    RegistryScanSnapshot,
    RegistryTag,
    RegistryVulnerability,
)

logger = logging.getLogger(__name__)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class ArtifactRecord:
    digest: str
    provider_native_id: str | None
    artifact_type: str | None
    media_type: str | None
    size_bytes: int | None
    push_time: datetime | None
    pull_time: datetime | None
    scan_status: str | None = None
    scan_completed_at: datetime | None = None
    vulnerability_summary: dict[str, int] = field(default_factory=dict)
    signature_status: str | None = None
    sbom_status: str | None = None
    scan_snapshot: dict[str, Any] | None = None
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)
    tags: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RepositoryRecord:
    name: str
    provider_native_id: str | None
    artifact_count: int | None
    pull_count: int | None
    description: str | None
    provider_created_at: datetime | None
    provider_updated_at: datetime | None
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProjectRecord:
    name: str
    provider_native_id: str | None
    public: bool | None
    repository_count: int | None
    repositories: list[RepositoryRecord] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)



_SEVERITIES = ('critical', 'high', 'medium', 'low', 'negligible', 'unknown')


def _severity(value: Any) -> str:
    key = str(value or 'unknown').strip().lower()
    return key if key in _SEVERITIES else 'unknown'


def _scan_overview(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    values = [item for item in raw.values() if isinstance(item, dict)]
    if not values and any(key in raw for key in ('scan_status', 'status', 'summary')):
        values = [raw]
    return values[0] if values else None


def _vulnerability_report(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    if isinstance(raw.get('vulnerabilities'), list):
        return raw
    for value in raw.values():
        if isinstance(value, dict) and isinstance(value.get('vulnerabilities'), list):
            return value
    return None


def _normalize_vulnerabilities(raw: Any) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    report = _vulnerability_report(raw)
    if report is None:
        return [], {}, {}
    rows: list[dict[str, Any]] = []
    counts = {severity: 0 for severity in _SEVERITIES}
    for item in report.get('vulnerabilities') or []:
        if not isinstance(item, dict):
            continue
        severity = _severity(item.get('severity'))
        counts[severity] += 1
        rows.append(
            {
                'vulnerability_id': str(item.get('id') or item.get('cve_id') or 'unknown').strip() or 'unknown',
                'package': str(item.get('package') or item.get('package_name') or 'unknown').strip() or 'unknown',
                'installed_version': str(item.get('version') or item.get('installed_version') or 'unknown').strip() or 'unknown',
                'fixed_version': str(item.get('fix_version') or item.get('fixed_version') or '').strip() or None,
                'severity': severity,
                'description': str(item.get('description') or '').strip() or None,
                'provider_metadata': {
                    key: item.get(key)
                    for key in ('links', 'vendor_attributes', 'preferred_cvss', 'cwe_ids')
                    if item.get(key) is not None
                },
            }
        )
    return rows, {key: value for key, value in counts.items() if value}, {
        'generated_at': report.get('generated_at'),
        'artifact': report.get('artifact'),
        'scanner': report.get('scanner'),
    }


def _scanner_identity(scan: dict[str, Any] | None, report_meta: dict[str, Any]) -> tuple[str | None, str | None]:
    scanner = (scan or {}).get('scanner') or report_meta.get('scanner')
    if isinstance(scanner, dict):
        return (
            str(scanner.get('name') or scanner.get('vendor') or '').strip() or None,
            str(scanner.get('version') or '').strip() or None,
        )
    return (str(scanner).strip() or None, None) if scanner else (None, None)


def _summary_from_scan(scan: dict[str, Any] | None) -> dict[str, int]:
    summary = (scan or {}).get('summary')
    if not isinstance(summary, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, value in summary.items():
        severity = _severity(key)
        if severity == 'unknown' and str(key).strip().lower() not in {'unknown'}:
            continue
        parsed = _as_int(value)
        if parsed is not None:
            normalized[severity] = parsed
    return normalized


def _artifact_signature_status(raw: dict[str, Any]) -> str:
    signed = raw.get('signed')
    if isinstance(signed, bool):
        return 'signed' if signed else 'unsigned'
    signatures = raw.get('signatures')
    if isinstance(signatures, list):
        return 'signed' if signatures else 'unsigned'
    return 'not_observed'


def _artifact_sbom_status(raw: dict[str, Any]) -> str:
    overview = raw.get('sbom_overview')
    if isinstance(overview, dict) and overview:
        statuses = [
            str(item.get('scan_status') or item.get('status') or '').strip().lower()
            for item in overview.values()
            if isinstance(item, dict)
        ]
        if any(status in {'success', 'finished', 'completed'} for status in statuses):
            return 'available'
        return 'observed'
    return 'not_observed'


def _repository_name(project_name: str, value: Any) -> str:
    name = str(value or '').strip().strip('/')
    prefix = f'{project_name}/'
    return name[len(prefix):] if name.startswith(prefix) else name


def collect_harbor_inventory(instance: HarborInstance) -> list[ProjectRecord]:
    client = build_client(instance)
    projects: list[ProjectRecord] = []
    for raw_project in client.list_all_projects():
        project_name = str(raw_project.get('name') or '').strip()
        if not project_name:
            continue
        project = ProjectRecord(
            name=project_name,
            provider_native_id=str(raw_project.get('project_id') or '') or None,
            public=bool(raw_project.get('public')) if raw_project.get('public') is not None else None,
            repository_count=_as_int(raw_project.get('repo_count')),
            provider_metadata={
                key: raw_project.get(key)
                for key in ('creation_time', 'update_time', 'metadata', 'owner_id', 'owner_name')
                if raw_project.get(key) is not None
            },
        )
        for raw_repo in client.list_all_repositories(project_name_or_id=project_name):
            repo_name = _repository_name(project_name, raw_repo.get('name'))
            if not repo_name:
                continue
            repository = RepositoryRecord(
                name=repo_name,
                provider_native_id=str(raw_repo.get('id') or '') or None,
                artifact_count=_as_int(raw_repo.get('artifact_count')),
                pull_count=_as_int(raw_repo.get('pull_count')),
                description=str(raw_repo.get('description') or '').strip() or None,
                provider_created_at=_parse_datetime(raw_repo.get('creation_time')),
                provider_updated_at=_parse_datetime(raw_repo.get('update_time')),
                provider_metadata={
                    key: raw_repo.get(key)
                    for key in ('project_id',)
                    if raw_repo.get(key) is not None
                },
            )
            for raw_artifact in client.list_all_artifacts(
                project_name_or_id=project_name,
                repository_name=repo_name,
                with_scan_overview=True,
                with_sbom_overview=True,
                with_signature=True,
                with_immutable_status=True,
            ):
                digest = str(raw_artifact.get('digest') or '').strip()
                if not digest:
                    continue
                scan = _scan_overview(raw_artifact.get('scan_overview'))
                vulnerability_rows: list[dict[str, Any]] = []
                report_summary: dict[str, int] = {}
                report_meta: dict[str, Any] = {}
                report_error: str | None = None
                if scan is not None:
                    try:
                        vulnerability_payload = client.get_vulnerability_report(
                            project_name_or_id=project_name,
                            repository_name=repo_name,
                            reference=digest,
                        )
                    except Exception as exc:
                        report_error = f'{type(exc).__name__}: {exc}'[:1000]
                    else:
                        vulnerability_rows, report_summary, report_meta = _normalize_vulnerabilities(vulnerability_payload)
                scanner_name, scanner_version = _scanner_identity(scan, report_meta)
                scan_status = str((scan or {}).get('scan_status') or (scan or {}).get('status') or '').strip().lower() or None
                scan_summary = report_summary or _summary_from_scan(scan)
                repository.artifacts.append(
                    ArtifactRecord(
                        digest=digest,
                        provider_native_id=str(raw_artifact.get('id') or '') or None,
                        artifact_type=str(raw_artifact.get('type') or '').strip() or None,
                        media_type=str(raw_artifact.get('media_type') or '').strip() or None,
                        size_bytes=_as_int(raw_artifact.get('size')),
                        push_time=_parse_datetime(raw_artifact.get('push_time')),
                        pull_time=_parse_datetime(raw_artifact.get('pull_time')),
                        scan_status=scan_status,
                        scan_completed_at=_parse_datetime((scan or {}).get('end_time') or report_meta.get('generated_at')),
                        vulnerability_summary=scan_summary,
                        signature_status=_artifact_signature_status(raw_artifact),
                        sbom_status=_artifact_sbom_status(raw_artifact),
                        scan_snapshot=(
                            {
                                'scanner': scanner_name,
                                'scanner_version': scanner_version,
                                'report_id': str((scan or {}).get('report_id') or '').strip() or None,
                                'status': scan_status or 'not_scanned',
                                'severity_summary': scan_summary,
                                'provider_metadata': {
                                    'report_error': report_error,
                                    'scan_overview': scan,
                                    **report_meta,
                                },
                            }
                            if scan is not None
                            else None
                        ),
                        vulnerabilities=vulnerability_rows,
                        tags=[tag for tag in (raw_artifact.get('tags') or []) if isinstance(tag, dict)],
                        provider_metadata={
                            key: raw_artifact.get(key)
                            for key in ('manifest_media_type', 'project_id', 'repository_id', 'extra_attrs')
                            if raw_artifact.get(key) is not None
                        },
                    )
                )
            project.repositories.append(repository)
        projects.append(project)
    return projects


def _lock_collection_state(integration_instance_id: int) -> RegistryCollectionState:
    state = db.session.get(RegistryCollectionState, integration_instance_id)
    if state is None:
        state = RegistryCollectionState(integration_instance_id=integration_instance_id)
        db.session.add(state)
        db.session.flush()
    db.session.execute(
        select(RegistryCollectionState.integration_instance_id)
        .where(RegistryCollectionState.integration_instance_id == integration_instance_id)
        .with_for_update()
    ).scalar_one()
    return state


def commit_registry_inventory(
    instance: HarborInstance,
    projects: list[ProjectRecord],
    *,
    observed_at: datetime,
) -> dict[str, int]:
    integration_instance_id = int(instance.integration_instance_id)
    state = _lock_collection_state(integration_instance_id)
    existing_count = RegistryProject.query.filter_by(integration_instance_id=integration_instance_id).count()
    if existing_count and not projects:
        raise RuntimeError(
            'Harbor project discovery returned zero projects while a previous committed Registry snapshot exists. '
            'KAORI preserved the previous snapshot; verify credential scope and provider health before retrying.'
        )

    RegistryProject.query.filter_by(integration_instance_id=integration_instance_id).delete(synchronize_session=False)
    db.session.flush()

    project_count = repository_count = artifact_count = tag_count = 0
    for project_record in projects:
        project = RegistryProject(
            integration_instance_id=integration_instance_id,
            provider_native_id=project_record.provider_native_id,
            name=project_record.name,
            public=project_record.public,
            repository_count=project_record.repository_count,
            provider_metadata=project_record.provider_metadata,
            observed_at=observed_at,
        )
        db.session.add(project)
        db.session.flush()
        project_count += 1
        for repo_record in project_record.repositories:
            repository = RegistryRepository(
                project_id=project.id,
                provider_native_id=repo_record.provider_native_id,
                name=repo_record.name,
                artifact_count=repo_record.artifact_count,
                pull_count=repo_record.pull_count,
                description=repo_record.description,
                provider_created_at=repo_record.provider_created_at,
                provider_updated_at=repo_record.provider_updated_at,
                provider_metadata=repo_record.provider_metadata,
                observed_at=observed_at,
            )
            db.session.add(repository)
            db.session.flush()
            repository_count += 1
            for artifact_record in repo_record.artifacts:
                digest_algorithm = (
                    artifact_record.digest.split(':', 1)[0] if ':' in artifact_record.digest else 'unknown'
                )
                artifact = RegistryArtifact(
                    repository_id=repository.id,
                    provider_native_id=artifact_record.provider_native_id,
                    digest=artifact_record.digest,
                    digest_algorithm=digest_algorithm,
                    artifact_type=artifact_record.artifact_type,
                    media_type=artifact_record.media_type,
                    size_bytes=artifact_record.size_bytes,
                    push_time=artifact_record.push_time,
                    pull_time=artifact_record.pull_time,
                    scan_status=artifact_record.scan_status,
                    scan_completed_at=artifact_record.scan_completed_at,
                    vulnerability_summary=artifact_record.vulnerability_summary,
                    signature_status=artifact_record.signature_status,
                    sbom_status=artifact_record.sbom_status,
                    provider_metadata=artifact_record.provider_metadata,
                    observed_at=observed_at,
                )
                db.session.add(artifact)
                db.session.flush()
                artifact_count += 1
                if artifact_record.scan_snapshot is not None:
                    snapshot_data = artifact_record.scan_snapshot
                    snapshot = RegistryScanSnapshot(
                        artifact_id=artifact.id,
                        scanner=snapshot_data.get('scanner'),
                        scanner_version=snapshot_data.get('scanner_version'),
                        report_id=snapshot_data.get('report_id'),
                        status=str(snapshot_data.get('status') or 'not_scanned'),
                        severity_summary=snapshot_data.get('severity_summary') or {},
                        provider_metadata=snapshot_data.get('provider_metadata') or {},
                        observed_at=observed_at,
                    )
                    db.session.add(snapshot)
                    db.session.flush()
                    for finding in artifact_record.vulnerabilities:
                        db.session.add(
                            RegistryVulnerability(
                                scan_snapshot_id=snapshot.id,
                                vulnerability_id=finding['vulnerability_id'],
                                package=finding['package'],
                                installed_version=finding['installed_version'],
                                fixed_version=finding['fixed_version'],
                                severity=finding['severity'],
                                description=finding['description'],
                                provider_metadata=finding['provider_metadata'],
                            )
                        )
                for raw_tag in artifact_record.tags:
                    tag_name = str(raw_tag.get('name') or '').strip()
                    if not tag_name:
                        continue
                    db.session.add(
                        RegistryTag(
                            artifact_id=artifact.id,
                            name=tag_name,
                            provider_native_id=str(raw_tag.get('id') or '') or None,
                            push_time=_parse_datetime(raw_tag.get('push_time')),
                            pull_time=_parse_datetime(raw_tag.get('pull_time')),
                            provider_metadata={
                                key: raw_tag.get(key)
                                for key in ('immutable', 'signed')
                                if raw_tag.get(key) is not None
                            },
                            observed_at=observed_at,
                        )
                    )
                    tag_count += 1

    state.status = 'ready'
    state.last_observed_at = observed_at
    state.last_committed_at = datetime.now(UTC)
    state.last_error = None
    state.counts = {
        'projects': project_count,
        'repositories': repository_count,
        'artifacts': artifact_count,
        'tags': tag_count,
    }
    state.metadata_json = {
        'provider_key': instance.provider_key,
        'provider_connection_id': instance.id,
        'source': 'harbor_api_v2',
    }
    db.session.flush()
    return dict(state.counts)


def sync_registry_inventory(instance: HarborInstance) -> dict[str, Any]:
    canonical = instance.integration_instance
    if not canonical.enabled or canonical.lifecycle_status != 'active':
        raise RuntimeError('The Harbor Registry integration is not active for inventory synchronization.')
    if instance.readiness_status != 'ready':
        raise RuntimeError('Run Full Validation successfully before Artifact Registry inventory synchronization.')

    observed_at = datetime.now(UTC)
    state = _lock_collection_state(int(instance.integration_instance_id))
    state.status = 'collecting'
    state.last_started_at = observed_at
    state.last_error = None
    db.session.flush()
    try:
        projects = collect_harbor_inventory(instance)
        counts = commit_registry_inventory(instance, projects, observed_at=observed_at)
        db.session.commit()
        try:
            from app.artifact_registry.correlation import refresh_registry_workload_bindings

            correlation = refresh_registry_workload_bindings(
                integration_instance_id=int(instance.integration_instance_id)
            )
        except Exception as correlation_exc:
            db.session.rollback()
            logger.exception('Artifact Registry runtime correlation failed for Harbor instance %s.', instance.id)
            correlation = {
                'status': 'failed',
                'error_type': type(correlation_exc).__name__,
                'message': str(correlation_exc)[:1000],
            }
    except Exception as exc:
        db.session.rollback()
        state = _lock_collection_state(int(instance.integration_instance_id))
        state.status = 'failed'
        state.last_error = str(exc)[:2000]
        db.session.commit()
        logger.exception('Artifact Registry synchronization failed for Harbor instance %s.', instance.id)
        raise
    return {
        'integration_instance_id': int(instance.integration_instance_id),
        'instance_id': int(instance.id),
        'instance_name': instance.name,
        'observed_at': observed_at.isoformat(),
        'correlation': correlation,
        **counts,
    }
