from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload

from app.artifact_registry.collectors import InventoryProgressCallback
from app.artifact_registry.eligibility import registry_inventory_eligibility
from app.artifact_registry.security.contracts import RegistrySecurityEvidence, RegistrySecurityTarget
from app.artifact_registry.security.providers import (
    SecurityTargetCurrentPredicate,
    get_registry_security_collector,
)
from app.extensions.db import db
from app.integrations.kernel.registry import get_integration
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryRepository,
    RegistryScanSnapshot,
    RegistryVulnerability,
)

logger = logging.getLogger(__name__)


def _build_registry_security_target_current_predicate(
    identity: IntegrationInstance,
) -> SecurityTargetCurrentPredicate:
    integration_instance_id = int(identity.id)

    def is_current(target: RegistrySecurityTarget) -> bool:
        return (
            db.session.query(RegistryArtifact.id)
            .join(
                RegistryRepository,
                RegistryArtifact.repository_id == RegistryRepository.id,
            )
            .filter(
                RegistryArtifact.id == target.artifact_id,
                RegistryArtifact.digest == target.digest,
                RegistryRepository.name == target.repository_name,
                RegistryRepository.project.has(
                    integration_instance_id=integration_instance_id,
                    name=target.project_name,
                ),
            )
            .first()
            is not None
        )

    return is_current


def build_registry_security_targets(identity: IntegrationInstance) -> list[RegistrySecurityTarget]:
    artifacts = (
        RegistryArtifact.query.join(
            RegistryRepository,
            RegistryArtifact.repository_id == RegistryRepository.id,
        )
        .options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
        )
        .filter(
            RegistryRepository.project.has(
                integration_instance_id=int(identity.id),
            )
        )
        .order_by(RegistryArtifact.id.asc())
        .all()
    )
    artifact_ids = [artifact.id for artifact in artifacts]
    snapshot_artifact_ids = (
        {
            artifact_id
            for (artifact_id,) in db.session.query(RegistryScanSnapshot.artifact_id)
            .filter(RegistryScanSnapshot.artifact_id.in_(artifact_ids))
            .distinct()
            .all()
        }
        if artifact_ids
        else set()
    )
    return [
        RegistrySecurityTarget(
            artifact_id=int(artifact.id),
            project_name=artifact.repository.project.name,
            repository_name=artifact.repository.name,
            digest=artifact.digest,
            scan_status=artifact.scan_status,
            scan_completed_at=artifact.scan_completed_at,
            vulnerability_summary=(
                dict(artifact.vulnerability_summary) if isinstance(artifact.vulnerability_summary, dict) else {}
            ),
            signature_status=artifact.signature_status,
            sbom_status=artifact.sbom_status,
            has_scan_snapshot=artifact.id in snapshot_artifact_ids,
        )
        for artifact in artifacts
    ]


def _commit_security_evidence(
    evidence: RegistrySecurityEvidence,
    *,
    observed_at: datetime,
) -> dict[str, int]:
    artifact_ids = [item.artifact_id for item in evidence.artifacts]
    artifacts = (
        {
            artifact.id: artifact
            for artifact in RegistryArtifact.query.filter(RegistryArtifact.id.in_(artifact_ids)).all()
        }
        if artifact_ids
        else {}
    )

    artifact_count = refreshed_report_count = reused_report_count = finding_count = 0
    for item in evidence.artifacts:
        artifact = artifacts.get(item.artifact_id)
        if artifact is None:
            continue

        artifact.scan_status = item.scan_status
        artifact.scan_completed_at = item.scan_completed_at
        if item.vulnerability_summary or not item.reuse_existing_scan:
            artifact.vulnerability_summary = dict(item.vulnerability_summary or {})
        artifact.signature_status = item.signature_status
        artifact.sbom_status = item.sbom_status

        if item.scan_snapshot is not None and not item.reuse_existing_scan:
            snapshot_data = item.scan_snapshot
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
            for finding in item.vulnerabilities:
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
                finding_count += 1
            refreshed_report_count += 1
        elif item.reuse_existing_scan:
            reused_report_count += 1

        artifact_count += 1

    db.session.flush()
    return {
        'artifacts': artifact_count,
        'refreshed_reports': refreshed_report_count,
        'reused_reports': reused_report_count,
        'findings': finding_count,
    }


def sync_registry_security(
    identity: IntegrationInstance,
    *,
    progress_callback: InventoryProgressCallback | None = None,
) -> dict[str, Any]:
    if identity.integration_type != 'registry':
        raise RuntimeError('Artifact Registry security requires a canonical Registry integration identity.')

    collection_state = db.session.get(RegistryCollectionState, int(identity.id))
    if collection_state is None or collection_state.status != 'ready':
        raise RuntimeError('Committed Artifact Registry inventory is required before security synchronization.')

    provider_module = get_integration('registry')
    provider_record = provider_module.require_record_for_canonical(int(identity.id))
    eligibility = registry_inventory_eligibility(identity, provider_record=provider_record)
    if not eligibility.eligible:
        raise RuntimeError(eligibility.reason)

    targets = build_registry_security_targets(identity)
    target_is_current = _build_registry_security_target_current_predicate(identity)
    collector = get_registry_security_collector(identity.provider_key)
    observed_at = datetime.now(UTC)
    try:
        evidence = collector.collect(
            provider_record,
            targets,
            progress_callback,
            target_is_current,
        )
        counts = _commit_security_evidence(
            evidence,
            observed_at=observed_at,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            'Artifact Registry security synchronization failed for Registry instance %s (%s).',
            identity.id,
            identity.provider_key,
        )
        raise

    return {
        'integration_instance_id': int(identity.id),
        'instance_name': identity.name,
        'provider_key': identity.provider_key,
        'observed_at': observed_at.isoformat(),
        'provider_metadata': evidence.provider_metadata,
        **counts,
    }
