from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.artifact_registry.collectors import RegistryInventoryCollector
from app.artifact_registry.contracts import (
    ArtifactRecord,
    ProjectRecord,
    RegistryInventoryEvidence,
    RepositoryRecord,
)
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.models.harbor import HarborInstance

_SEVERITIES = ('critical', 'high', 'medium', 'low', 'negligible', 'unknown')


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
                'installed_version': (
                    str(item.get('version') or item.get('installed_version') or 'unknown').strip() or 'unknown'
                ),
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
    return (
        rows,
        {key: value for key, value in counts.items() if value},
        {
            'generated_at': report.get('generated_at'),
            'artifact': report.get('artifact'),
            'scanner': report.get('scanner'),
        },
    )


def _scanner_identity(
    scan: dict[str, Any] | None,
    report_meta: dict[str, Any],
) -> tuple[str | None, str | None]:
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
        if severity == 'unknown' and str(key).strip().lower() != 'unknown':
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


def collect_harbor_inventory(instance: HarborInstance) -> RegistryInventoryEvidence:
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
                        vulnerability_rows, report_summary, report_meta = _normalize_vulnerabilities(
                            vulnerability_payload
                        )
                scanner_name, scanner_version = _scanner_identity(scan, report_meta)
                scan_status = (
                    str((scan or {}).get('scan_status') or (scan or {}).get('status') or '').strip().lower()
                    or None
                )
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
                        scan_completed_at=_parse_datetime(
                            (scan or {}).get('end_time') or report_meta.get('generated_at')
                        ),
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
                        tags=[
                            tag
                            for tag in (raw_artifact.get('tags') or [])
                            if isinstance(tag, dict)
                        ],
                        provider_metadata={
                            key: raw_artifact.get(key)
                            for key in ('manifest_media_type', 'project_id', 'repository_id', 'extra_attrs')
                            if raw_artifact.get(key) is not None
                        },
                    )
                )
            project.repositories.append(repository)
        projects.append(project)

    parsed = urlparse(instance.endpoint)
    return RegistryInventoryEvidence(
        projects=projects,
        provider_metadata={
            'provider_key': 'harbor',
            'source': 'harbor_api_v2',
            'provider_record_id': int(instance.id),
            'registry_host': (parsed.hostname or '').lower() or None,
            'registry_scheme': parsed.scheme or None,
        },
    )


collector = RegistryInventoryCollector(
    provider_key='harbor',
    collect=collect_harbor_inventory,
)
