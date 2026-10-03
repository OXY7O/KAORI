from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.artifact_registry.collectors import get_registry_collector
from app.artifact_registry.contracts import ProjectRecord, RegistryInventoryEvidence
from app.extensions.db import db
from app.integrations.kernel.registry import get_integration
from app.models.integration import IntegrationInstance
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
    identity: IntegrationInstance,
    evidence: RegistryInventoryEvidence,
    *,
    observed_at: datetime,
) -> dict[str, int]:
    integration_instance_id = int(identity.id)
    projects: list[ProjectRecord] = evidence.projects
    state = _lock_collection_state(integration_instance_id)
    existing_count = RegistryProject.query.filter_by(integration_instance_id=integration_instance_id).count()
    if existing_count and not projects:
        raise RuntimeError(
            'Registry project discovery returned zero projects while a previous committed snapshot exists. '
            'KAORI preserved the previous snapshot; verify provider scope and health before retrying.'
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
                digest_algorithm = artifact_record.digest.split(':', 1)[0] if ':' in artifact_record.digest else 'unknown'
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
                        db.session.add(RegistryVulnerability(
                            scan_snapshot_id=snapshot.id,
                            vulnerability_id=finding['vulnerability_id'],
                            package=finding['package'],
                            installed_version=finding['installed_version'],
                            fixed_version=finding['fixed_version'],
                            severity=finding['severity'],
                            description=finding['description'],
                            provider_metadata=finding['provider_metadata'],
                        ))
                for raw_tag in artifact_record.tags:
                    tag_name = str(raw_tag.get('name') or '').strip()
                    if not tag_name:
                        continue
                    db.session.add(RegistryTag(
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
                    ))
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
        **(evidence.provider_metadata or {}),
        'provider_key': identity.provider_key,
        'integration_instance_id': integration_instance_id,
    }
    db.session.flush()
    return dict(state.counts)


def sync_registry_inventory(identity: IntegrationInstance) -> dict[str, Any]:
    if identity.integration_type != 'registry':
        raise RuntimeError('Artifact Registry inventory requires a canonical Registry integration identity.')
    if not identity.enabled or identity.lifecycle_status != 'active':
        raise RuntimeError('The Registry integration is not active for inventory synchronization.')
    if identity.readiness_status != 'ready':
        raise RuntimeError('Run Registry provider Full Validation successfully before Artifact Registry inventory synchronization.')

    provider_module = get_integration('registry')
    provider_record = provider_module.require_record_for_canonical(int(identity.id))
    collector = get_registry_collector(identity.provider_key)
    observed_at = datetime.now(UTC)
    state = _lock_collection_state(int(identity.id))
    state.status = 'collecting'
    state.last_started_at = observed_at
    state.last_error = None
    db.session.flush()
    try:
        evidence = collector.collect(provider_record)
        counts = commit_registry_inventory(identity, evidence, observed_at=observed_at)
        db.session.commit()
        try:
            from app.artifact_registry.correlation import refresh_registry_workload_bindings
            correlation = refresh_registry_workload_bindings(integration_instance_id=int(identity.id))
        except Exception as correlation_exc:
            db.session.rollback()
            logger.exception('Artifact Registry runtime correlation failed for Registry instance %s.', identity.id)
            correlation = {
                'status': 'failed',
                'error_type': type(correlation_exc).__name__,
                'message': str(correlation_exc)[:1000],
            }
    except Exception as exc:
        db.session.rollback()
        state = _lock_collection_state(int(identity.id))
        state.status = 'failed'
        state.last_error = str(exc)[:2000]
        db.session.commit()
        logger.exception('Artifact Registry synchronization failed for Registry instance %s (%s).', identity.id, identity.provider_key)
        raise
    return {
        'integration_instance_id': int(identity.id),
        'instance_name': identity.name,
        'provider_key': identity.provider_key,
        'observed_at': observed_at.isoformat(),
        'correlation': correlation,
        **counts,
    }
