from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import joinedload

from app.artifact_registry.security.contracts import RegistryArtifactSecurityEvidence, RegistrySecurityEvidence
from app.artifact_registry.security.providers import collect_registry_security
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.registry_artifact import RegistryArtifact, RegistryProject, RegistryRepository
from app.models.registry_security import (
    RegistryArtifactSecuritySnapshot,
    RegistrySecurityCollectionState,
    RegistryVulnerabilityFinding,
)

logger = logging.getLogger(__name__)


def _state(instance_id: int) -> RegistrySecurityCollectionState:
    state = RegistrySecurityCollectionState.query.filter_by(integration_instance_id=instance_id).first()
    if state is None:
        state = RegistrySecurityCollectionState(integration_instance_id=instance_id)
        db.session.add(state)
        db.session.flush()
    return state


def _source_artifacts(instance_id: int) -> list[RegistryArtifact]:
    return (
        RegistryArtifact.query.join(RegistryArtifact.repository)
        .join(RegistryRepository.project)
        .options(
            joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project)
            .joinedload(RegistryProject.integration_instance)
        )
        .filter(RegistryProject.integration_instance_id == instance_id)
        .order_by(RegistryArtifact.id.asc())
        .all()
    )


def _severity_counts(item: RegistryArtifactSecurityEvidence) -> dict[str, int]:
    counts = {key: 0 for key in ('unknown', 'negligible', 'low', 'medium', 'high', 'critical')}
    for finding in item.findings:
        severity = finding.severity if finding.severity in counts else 'unknown'
        counts[severity] += 1
    return counts


def _commit_findings(
    snapshot: RegistryArtifactSecuritySnapshot,
    item: RegistryArtifactSecurityEvidence,
    *,
    observed_at: datetime,
) -> None:
    existing = {finding.finding_key: finding for finding in snapshot.findings}
    for evidence in item.findings:
        finding = existing.pop(evidence.finding_key, None)
        if finding is None:
            finding = RegistryVulnerabilityFinding(
                security_snapshot_id=snapshot.id,
                finding_key=evidence.finding_key,
                vulnerability_id=evidence.vulnerability_id,
            )
            db.session.add(finding)
        finding.vulnerability_id = evidence.vulnerability_id
        finding.severity = evidence.severity
        finding.package = evidence.package
        finding.installed_version = evidence.installed_version
        finding.fixed_version = evidence.fixed_version
        finding.fix_available = evidence.fix_available
        finding.cvss_score = evidence.cvss_score
        finding.description = evidence.description
        finding.links = list(evidence.links)
        finding.provider_metadata = dict(evidence.metadata or {})
        finding.observed_at = observed_at
    for stale in existing.values():
        db.session.delete(stale)


def _commit_snapshot(
    item: RegistryArtifactSecurityEvidence,
    *,
    observed_at: datetime,
) -> RegistryArtifactSecuritySnapshot:
    snapshot = RegistryArtifactSecuritySnapshot.query.filter_by(artifact_id=item.artifact_id).first()
    if snapshot is None:
        snapshot = RegistryArtifactSecuritySnapshot(artifact_id=item.artifact_id)
        db.session.add(snapshot)
        db.session.flush()
    counts = _severity_counts(item)
    snapshot.vulnerability_state = item.vulnerability_state
    snapshot.scan_status = item.scan_status
    snapshot.scan_severity = item.scan_severity
    snapshot.scanner_name = item.scanner_name
    snapshot.scanner_vendor = item.scanner_vendor
    snapshot.scanner_version = item.scanner_version
    snapshot.scan_started_at = item.scan_started_at
    snapshot.scan_completed_at = item.scan_completed_at
    snapshot.finding_count = len(item.findings)
    snapshot.fixable_count = sum(1 for finding in item.findings if finding.fix_available)
    snapshot.unknown_count = counts['unknown']
    snapshot.negligible_count = counts['negligible']
    snapshot.low_count = counts['low']
    snapshot.medium_count = counts['medium']
    snapshot.high_count = counts['high']
    snapshot.critical_count = counts['critical']
    snapshot.signature_state = item.signature_state
    snapshot.signature_count = item.signature_count
    snapshot.trust_state = item.trust_state
    snapshot.sbom_state = item.sbom_state
    snapshot.sbom_count = item.sbom_count
    snapshot.provider_metadata = dict(item.metadata or {})
    snapshot.observed_at = observed_at
    db.session.flush()
    _commit_findings(snapshot, item, observed_at=observed_at)
    return snapshot


def commit_registry_security(
    instance: IntegrationInstance,
    evidence: RegistrySecurityEvidence,
) -> dict[str, int]:
    snapshots = [_commit_snapshot(item, observed_at=evidence.observed_at) for item in evidence.artifacts]
    state = _state(instance.id)
    state.status = 'collected'
    state.vulnerability_capability_state = evidence.vulnerability_capability_state
    state.signature_capability_state = evidence.signature_capability_state
    state.sbom_capability_state = evidence.sbom_capability_state
    state.last_attempt_at = evidence.observed_at
    state.last_success_at = evidence.observed_at
    state.observed_at = evidence.observed_at
    state.last_error = None
    state.artifact_count = len(snapshots)
    state.scanned_artifact_count = sum(1 for item in snapshots if item.vulnerability_state == 'observed')
    state.vulnerable_artifact_count = sum(1 for item in snapshots if item.finding_count > 0)
    state.finding_count = sum(item.finding_count for item in snapshots)
    state.critical_count = sum(item.critical_count for item in snapshots)
    state.high_count = sum(item.high_count for item in snapshots)
    state.signature_observed_count = sum(1 for item in snapshots if item.signature_state == 'observed')
    state.sbom_observed_count = sum(1 for item in snapshots if item.sbom_state == 'observed')
    db.session.flush()
    return {
        'artifacts': state.artifact_count,
        'scanned_artifacts': state.scanned_artifact_count,
        'vulnerable_artifacts': state.vulnerable_artifact_count,
        'findings': state.finding_count,
        'critical': state.critical_count,
        'high': state.high_count,
        'signatures': state.signature_observed_count,
        'sboms': state.sbom_observed_count,
    }


def _record_failure(instance_id: int, exc: Exception) -> None:
    try:
        state = _state(instance_id)
        state.status = 'failed'
        state.last_attempt_at = datetime.now(UTC)
        state.last_error = str(exc)[:4000]
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Could not persist Registry security collection failure for instance %s.', instance_id)


def sync_registry_security(instance: IntegrationInstance) -> dict[str, object]:
    if not instance.enabled or instance.lifecycle_status != 'active':
        raise RuntimeError('Registry integration is not active for security synchronization.')
    if instance.readiness_status not in {'ready', 'degraded'}:
        raise RuntimeError('Run Full Validation before Artifact Registry security synchronization.')

    artifacts = _source_artifacts(instance.id)
    try:
        evidence = collect_registry_security(instance, artifacts)
        counts = commit_registry_security(instance, evidence)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        _record_failure(instance.id, exc)
        raise
    return {
        'integration_instance_id': instance.id,
        'provider_key': instance.provider_key,
        'instance_name': instance.name,
        'observed_at': evidence.observed_at.isoformat(),
        **counts,
    }
