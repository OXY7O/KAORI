from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from app.artifact_registry.collectors import InventoryProgressCallback
from app.artifact_registry.security.contracts import (
    RegistryArtifactSecurityEvidence,
    RegistrySecurityEvidence,
    RegistrySecurityTarget,
)
from app.artifact_registry.security.providers import (
    RegistrySecurityCollector,
    SecurityTargetCurrentPredicate,
)
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.integrations.registry.providers.harbor.exceptions import (
    HarborAuthError,
    HarborConnectionError,
    HarborResponseError,
)
from app.models.harbor import HarborInstance

_SEVERITIES = ('critical', 'high', 'medium', 'low', 'negligible', 'unknown')
_SECURITY_DISCOVERY_PAGE_SIZES = (20, 10)
_SECURITY_TRANSPORT_RETRIES = 2
_MAX_REPOSITORY_FAILURE_EVIDENCE = 50


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


def _scan_identity_changed(
    target: RegistrySecurityTarget,
    *,
    scan_status: str | None,
    scan_completed_at: datetime | None,
    vulnerability_summary: dict[str, int],
) -> bool:
    if not target.has_scan_snapshot:
        return True
    if target.scan_status != scan_status:
        return True

    # Harbor scan completion time is the strongest available change marker. When
    # either side exposes it, do not let summary-shape differences force a full
    # vulnerability report fetch on every scheduled refresh.
    if target.scan_completed_at is not None or scan_completed_at is not None:
        return target.scan_completed_at != scan_completed_at

    # Older/limited Harbor responses may omit completion time. Fall back to the
    # normalized severity summary so changed scan evidence can still be detected.
    return dict(target.vulnerability_summary or {}) != dict(vulnerability_summary or {})


def _list_repository_security_artifacts(
    client: Any,
    *,
    project_name: str,
    repository_name: str,
    processed: int,
    total: int,
    progress_callback: InventoryProgressCallback | None,
) -> list[dict[str, Any]]:
    """Load one repository's enriched security projection with bounded page-size fallback.

    Harbor can take materially longer to render scan/SBOM/signature overviews than
    normal inventory pages. The configured per-request timeout remains authoritative;
    KAORI reduces the enriched page size once before declaring the repository
    unavailable for this refresh.
    """

    last_error: HarborConnectionError | HarborResponseError | None = None
    for attempt, page_size in enumerate(_SECURITY_DISCOVERY_PAGE_SIZES):
        if attempt and progress_callback is not None:
            progress_callback(
                processed,
                total,
                f'{project_name}/{repository_name} · retrying {page_size} enriched artifacts/page',
            )
        try:
            return client.list_all_artifacts(
                project_name_or_id=project_name,
                repository_name=repository_name,
                page_size=page_size,
                with_scan_overview=True,
                with_sbom_overview=True,
                with_signature=True,
                with_immutable_status=False,
                page_callback=(
                    (
                        lambda page: progress_callback(
                            processed,
                            total,
                            f'{project_name}/{repository_name} · discovering security page {page}',
                        )
                    )
                    if progress_callback is not None
                    else None
                ),
            )
        except HarborAuthError:
            # Authentication is source-wide authority and must remain fail-fast.
            raise
        except (HarborConnectionError, HarborResponseError) as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return []


def _retained_repository_target(
    target: RegistrySecurityTarget,
    *,
    project_name: str,
    repository_name: str,
    error: Exception,
) -> RegistryArtifactSecurityEvidence:
    return RegistryArtifactSecurityEvidence(
        artifact_id=target.artifact_id,
        scan_status=target.scan_status,
        scan_completed_at=target.scan_completed_at,
        vulnerability_summary=dict(target.vulnerability_summary or {}),
        signature_status=target.signature_status,
        sbom_status=target.sbom_status,
        reuse_existing_scan=bool(target.has_scan_snapshot),
        provider_metadata={
            'provider_evidence': 'repository_security_refresh_unavailable',
            'project_name': project_name,
            'repository_name': repository_name,
            'refresh_error_type': type(error).__name__,
            'refresh_error': str(error)[:500],
        },
    )


def collect_harbor_security(
    instance: HarborInstance,
    targets: list[RegistrySecurityTarget],
    progress_callback: InventoryProgressCallback | None = None,
    target_is_current: SecurityTargetCurrentPredicate | None = None,
) -> RegistrySecurityEvidence:
    """Collect Harbor security evidence incrementally from committed artifact identities."""

    client = build_client(instance, transport_retries=_SECURITY_TRANSPORT_RETRIES)
    total = len(targets)
    processed = 0
    refreshed_reports = 0
    reused_reports = 0
    stale_target_skip_count = 0
    records: list[RegistryArtifactSecurityEvidence] = []
    repository_failures: list[dict[str, str]] = []
    successful_repositories = 0
    grouped: dict[tuple[str, str], list[RegistrySecurityTarget]] = defaultdict(list)

    if progress_callback is not None:
        progress_callback(0, total, 'Security Discovery')

    for target in targets:
        if target_is_current is not None and not target_is_current(target):
            stale_target_skip_count += 1
            processed += 1
            if progress_callback is not None:
                progress_callback(
                    processed,
                    total,
                    f'{target.project_name}/{target.repository_name}@{target.digest[:20]} · skipped stale',
                )
            continue
        grouped[(target.project_name, target.repository_name)].append(target)

    for (project_name, repository_name), repository_targets in grouped.items():
        current_repository_targets: list[RegistrySecurityTarget] = []
        for target in repository_targets:
            if target_is_current is not None and not target_is_current(target):
                stale_target_skip_count += 1
                processed += 1
                if progress_callback is not None:
                    progress_callback(
                        processed,
                        total,
                        f'{project_name}/{repository_name}@{target.digest[:20]} · skipped stale',
                    )
                continue
            current_repository_targets.append(target)
        if not current_repository_targets:
            continue
        repository_targets = current_repository_targets
        try:
            raw_artifacts = _list_repository_security_artifacts(
                client,
                project_name=project_name,
                repository_name=repository_name,
                processed=processed,
                total=total,
                progress_callback=progress_callback,
            )
        except HarborAuthError:
            raise
        except (HarborConnectionError, HarborResponseError) as exc:
            repository_failures.append(
                {
                    'project_name': project_name,
                    'repository_name': repository_name,
                    'error_type': type(exc).__name__,
                    'message': str(exc)[:500],
                }
            )
            for target in repository_targets:
                if target_is_current is not None and not target_is_current(target):
                    stale_target_skip_count += 1
                    processed += 1
                    if progress_callback is not None:
                        progress_callback(
                            processed,
                            total,
                            f'{project_name}/{repository_name}@{target.digest[:20]} · skipped stale',
                        )
                    continue
                records.append(
                    _retained_repository_target(
                        target,
                        project_name=project_name,
                        repository_name=repository_name,
                        error=exc,
                    )
                )
                reused_reports += int(target.has_scan_snapshot)
                processed += 1
                if progress_callback is not None:
                    progress_callback(
                        processed,
                        total,
                        f'{project_name}/{repository_name}@{target.digest[:20]} · retained',
                    )
            continue

        successful_repositories += 1
        raw_by_digest = {
            str(item.get('digest') or '').strip(): item
            for item in raw_artifacts
            if str(item.get('digest') or '').strip()
        }

        for target in repository_targets:
            if target_is_current is not None and not target_is_current(target):
                stale_target_skip_count += 1
                processed += 1
                if progress_callback is not None:
                    progress_callback(
                        processed,
                        total,
                        f'{project_name}/{repository_name}@{target.digest[:20]} · skipped stale',
                    )
                continue

            raw = raw_by_digest.get(target.digest)
            if raw is None:
                records.append(
                    RegistryArtifactSecurityEvidence(
                        artifact_id=target.artifact_id,
                        scan_status=target.scan_status,
                        scan_completed_at=target.scan_completed_at,
                        vulnerability_summary=dict(target.vulnerability_summary or {}),
                        signature_status=target.signature_status,
                        sbom_status=target.sbom_status,
                        reuse_existing_scan=bool(target.has_scan_snapshot),
                        provider_metadata={'provider_evidence': 'artifact_not_observed_in_security_refresh'},
                    )
                )
                reused_reports += int(target.has_scan_snapshot)
            else:
                scan = _scan_overview(raw.get('scan_overview'))
                if scan is None and target.has_scan_snapshot:
                    scan_status = target.scan_status
                    scan_completed_at = target.scan_completed_at
                    scan_summary = dict(target.vulnerability_summary or {})
                    changed = False
                else:
                    scan_status = (
                        str((scan or {}).get('scan_status') or (scan or {}).get('status') or '').strip().lower()
                        or None
                    )
                    scan_completed_at = _parse_datetime((scan or {}).get('end_time'))
                    scan_summary = _summary_from_scan(scan)
                    changed = _scan_identity_changed(
                        target,
                        scan_status=scan_status,
                        scan_completed_at=scan_completed_at,
                        vulnerability_summary=scan_summary,
                    )
                signature_status = _artifact_signature_status(raw)
                sbom_status = _artifact_sbom_status(raw)

                vulnerabilities: list[dict[str, Any]] = []
                report_summary: dict[str, int] = {}
                report_meta: dict[str, Any] = {}
                report_error: str | None = None
                scan_snapshot: dict[str, Any] | None = None

                if scan is not None and changed:
                    try:
                        payload = client.get_vulnerability_report(
                            project_name_or_id=project_name,
                            repository_name=repository_name,
                            reference=target.digest,
                        )
                    except Exception as exc:
                        report_error = f'{type(exc).__name__}: {exc}'[:1000]
                    else:
                        vulnerabilities, report_summary, report_meta = _normalize_vulnerabilities(payload)
                    scanner_name, scanner_version = _scanner_identity(scan, report_meta)
                    if report_summary:
                        scan_summary = report_summary
                    scan_completed_at = _parse_datetime(
                        (scan or {}).get('end_time') or report_meta.get('generated_at')
                    )
                    scan_snapshot = {
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
                    refreshed_reports += 1
                elif target.has_scan_snapshot:
                    reused_reports += 1

                records.append(
                    RegistryArtifactSecurityEvidence(
                        artifact_id=target.artifact_id,
                        scan_status=scan_status,
                        scan_completed_at=scan_completed_at,
                        vulnerability_summary=scan_summary,
                        signature_status=signature_status,
                        sbom_status=sbom_status,
                        scan_snapshot=scan_snapshot,
                        vulnerabilities=vulnerabilities,
                        reuse_existing_scan=bool(target.has_scan_snapshot and not changed),
                        provider_metadata={
                            'project_name': project_name,
                            'repository_name': repository_name,
                            'scan_changed': changed,
                        },
                    )
                )

            processed += 1
            if progress_callback is not None:
                progress_callback(
                    processed,
                    total,
                    f'{project_name}/{repository_name}@{target.digest[:20]}',
                )

    if repository_failures and successful_repositories == 0:
        raise HarborConnectionError(
            'Harbor security discovery was unavailable for every committed repository; '
            'previous committed security evidence was retained.'
        )

    return RegistrySecurityEvidence(
        artifacts=records,
        provider_metadata={
            'provider_key': 'harbor',
            'source': 'harbor_api_v2',
            'refreshed_vulnerability_reports': refreshed_reports,
            'reused_vulnerability_reports': reused_reports,
            'repository_count': len(grouped),
            'successful_repository_count': successful_repositories,
            'repository_failure_count': len(repository_failures),
            'stale_target_skip_count': stale_target_skip_count,
            'repository_failures': repository_failures[:_MAX_REPOSITORY_FAILURE_EVIDENCE],
            'repository_failure_evidence_truncated': (
                len(repository_failures) > _MAX_REPOSITORY_FAILURE_EVIDENCE
            ),
            'security_discovery_page_sizes': list(_SECURITY_DISCOVERY_PAGE_SIZES),
        },
    )


collector = RegistrySecurityCollector(
    provider_key='harbor',
    collect=collect_harbor_security,
    capabilities=frozenset({'vulnerability', 'signature', 'sbom'}),
)
