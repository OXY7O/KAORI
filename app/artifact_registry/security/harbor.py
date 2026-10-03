from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.artifact_registry.security.contracts import (
    RegistryArtifactSecurityEvidence,
    RegistrySecurityEvidence,
    RegistryVulnerabilityEvidence,
)
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.integrations.registry.providers.harbor.exceptions import HarborResponseError
from app.models.harbor import HarborInstance
from app.models.registry_artifact import RegistryArtifact


def _datetime(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    text = str(value or '').strip()
    return text or None


def _severity(value: Any) -> str:
    normalized = str(value or 'unknown').strip().lower()
    return normalized if normalized in {'unknown', 'negligible', 'low', 'medium', 'high', 'critical'} else 'unknown'


def _cvss_score(item: dict[str, Any]) -> str | None:
    for key in ('cvss3', 'cvss2'):
        payload = item.get(key)
        if isinstance(payload, dict) and payload.get('score') not in {None, ''}:
            return str(payload.get('score'))
    score = item.get('cvss_score')
    return None if score in {None, ''} else str(score)


def _scan_report(addition: dict[str, Any]) -> dict[str, Any]:
    if 'vulnerabilities' in addition or 'scanner' in addition:
        return addition
    for value in addition.values():
        if isinstance(value, dict) and ('vulnerabilities' in value or 'scanner' in value):
            return value
    return {}


def _scan_overview(artifact: dict[str, Any]) -> dict[str, Any]:
    overview = artifact.get('scan_overview')
    if not isinstance(overview, dict):
        return {}
    for value in overview.values():
        if isinstance(value, dict):
            return value
    return {}


def _accessory_kind(accessory: dict[str, Any]) -> str:
    parts = [
        accessory.get('type'),
        accessory.get('artifact_type'),
        accessory.get('artifactType'),
        accessory.get('media_type'),
        accessory.get('mediaType'),
        accessory.get('annotations'),
    ]
    return ' '.join(str(item or '') for item in parts).lower()


def _supply_chain_state(artifact: dict[str, Any]) -> tuple[str, int, str, int, dict[str, Any]]:
    accessories = [item for item in artifact.get('accessories') or () if isinstance(item, dict)]
    signature_tokens = ('signature', 'cosign', 'notation', 'notary')
    sbom_tokens = ('sbom', 'spdx', 'cyclonedx', 'syft')
    signature_count = sum(any(token in _accessory_kind(item) for token in signature_tokens) for item in accessories)
    sbom_count = sum(any(token in _accessory_kind(item) for token in sbom_tokens) for item in accessories)
    return (
        'observed' if signature_count else 'unavailable',
        int(signature_count),
        'observed' if sbom_count else 'unavailable',
        int(sbom_count),
        {
            'provider_signed_flag': artifact.get('signed'),
            'accessory_count': len(accessories),
        },
    )


def _finding(item: dict[str, Any], *, observed_at: datetime) -> RegistryVulnerabilityEvidence | None:
    vulnerability_id = _text(item.get('id') or item.get('vulnerability_id'))
    if vulnerability_id is None:
        return None
    package = _text(item.get('package'))
    installed_version = _text(item.get('version') or item.get('installed_version'))
    fixed_version = _text(item.get('fix_version') or item.get('fixed_version'))
    finding_key = '|'.join(
        (
            vulnerability_id,
            package or '',
            installed_version or '',
        )
    )[:900]
    raw_links = item.get('links')
    links = tuple(str(link) for link in raw_links if str(link).strip()) if isinstance(raw_links, list) else ()
    return RegistryVulnerabilityEvidence(
        finding_key=finding_key,
        vulnerability_id=vulnerability_id,
        severity=_severity(item.get('severity')),
        package=package,
        installed_version=installed_version,
        fixed_version=fixed_version,
        fix_available=bool(fixed_version),
        cvss_score=_cvss_score(item),
        description=_text(item.get('description')),
        links=links,
        metadata={
            'cwe_ids': item.get('cwe_ids') or [],
            'vendor_attributes': item.get('vendor_attributes') or {},
            'observed_at': observed_at.isoformat(),
        },
    )


def _collect_artifact(
    client,
    artifact: RegistryArtifact,
    *,
    observed_at: datetime,
) -> RegistryArtifactSecurityEvidence:
    repository = artifact.repository
    project = repository.project
    try:
        detail = client.get_artifact(
            project_name_or_id=project.name,
            repository_name=repository.name,
            reference=artifact.digest,
        )
    except HarborResponseError as exc:
        if exc.status in {403, 404}:
            evidence_code = 'artifact_forbidden' if exc.status == 403 else 'artifact_not_found'
            return RegistryArtifactSecurityEvidence(
                artifact_id=artifact.id,
                vulnerability_state='unavailable',
                scan_status=evidence_code,
                signature_state='unavailable',
                sbom_state='unavailable',
                metadata={'provider_evidence': evidence_code},
            )
        raise

    try:
        addition = client.get_artifact_addition(
            project_name_or_id=project.name,
            repository_name=repository.name,
            reference=artifact.digest,
            addition='vulnerabilities',
        )
    except HarborResponseError as exc:
        if exc.status in {403, 404}:
            addition = {}
        else:
            raise

    report = _scan_report(addition)
    overview = _scan_overview(detail)
    vulnerability_rows = report.get('vulnerabilities') if isinstance(report.get('vulnerabilities'), list) else []
    findings = tuple(
        normalized
        for item in vulnerability_rows
        if isinstance(item, dict)
        for normalized in [_finding(item, observed_at=observed_at)]
        if normalized is not None
    )
    scanner = report.get('scanner') if isinstance(report.get('scanner'), dict) else {}
    signature_state, signature_count, sbom_state, sbom_count, supply_metadata = _supply_chain_state(detail)
    report_present = bool(report or overview)
    scan_status = _text(overview.get('scan_status') or report.get('scan_status')) or (
        'available' if report_present else 'not_available'
    )
    return RegistryArtifactSecurityEvidence(
        artifact_id=artifact.id,
        vulnerability_state='observed' if report_present else 'unavailable',
        scan_status=scan_status.lower().replace(' ', '_'),
        scan_severity=_severity(report.get('severity') or overview.get('severity')) if report_present else None,
        scanner_name=_text(scanner.get('name')),
        scanner_vendor=_text(scanner.get('vendor')),
        scanner_version=_text(scanner.get('version')),
        scan_started_at=_datetime(overview.get('start_time') or report.get('generated_at')),
        scan_completed_at=_datetime(overview.get('end_time') or report.get('generated_at')),
        signature_state=signature_state,
        signature_count=signature_count,
        trust_state='not_evaluated',
        sbom_state=sbom_state,
        sbom_count=sbom_count,
        findings=findings,
        metadata={
            **supply_metadata,
            'provider_scan_overview_present': bool(overview),
            'provider_vulnerability_report_present': bool(report),
        },
    )


def _capability_state(artifacts: tuple[RegistryArtifactSecurityEvidence, ...], field: str) -> str:
    if any(getattr(item, field) == 'observed' for item in artifacts):
        return 'supported_observed'
    return 'supported_unavailable'


def collect_harbor_security(
    source: HarborInstance,
    artifacts: list[RegistryArtifact],
) -> RegistrySecurityEvidence:
    """Collect scanner/accessory evidence without triggering scans or trust evaluation."""

    client = build_client(source)
    observed_at = datetime.now(UTC)
    rows = tuple(_collect_artifact(client, artifact, observed_at=observed_at) for artifact in artifacts)
    return RegistrySecurityEvidence(
        provider_key='harbor',
        integration_instance_id=source.integration_instance_id,
        observed_at=observed_at,
        vulnerability_capability_state=_capability_state(rows, 'vulnerability_state'),
        signature_capability_state=_capability_state(rows, 'signature_state'),
        sbom_capability_state=_capability_state(rows, 'sbom_state'),
        artifacts=rows,
    )
