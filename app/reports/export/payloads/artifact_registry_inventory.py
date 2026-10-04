from __future__ import annotations

from typing import Any

from sqlalchemy.orm import selectinload

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
)
from app.models.report import Report
from app.reports.catalog import require_artifact_registry_instance, validate_report_instance


def _severity_count(summary: dict[str, Any] | None, key: str) -> int:
    value = (summary or {}).get(key, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def get_report_artifact_registry_inventory_payload(report: Report) -> dict[str, Any]:
    """Return committed provider-neutral Artifact Registry evidence only."""

    validate_report_instance(report)
    scope_id = require_artifact_registry_instance(report)
    try:
        instance_id = int(scope_id)
    except (TypeError, ValueError):
        return {'_error': 'The selected Artifact Registry integration is invalid.'}

    instance = db.session.get(IntegrationInstance, instance_id)
    if instance is None or instance.integration_type != 'registry':
        return {'_error': 'The selected Artifact Registry integration no longer exists.'}

    state = db.session.get(RegistryCollectionState, instance_id)
    projects = (
        RegistryProject.query.options(
            selectinload(RegistryProject.repositories)
            .selectinload(RegistryRepository.artifacts)
            .selectinload(RegistryArtifact.tags)
        )
        .filter(RegistryProject.integration_instance_id == instance_id)
        .order_by(RegistryProject.name.asc())
        .all()
    )

    rows: list[dict[str, Any]] = []
    for project in projects:
        for repository in project.repositories or ():
            for artifact in repository.artifacts or ():
                summary = dict(artifact.vulnerability_summary or {})
                rows.append(
                    {
                        'registry': instance.name,
                        'environment': instance.environment or 'Not Set',
                        'project': project.name,
                        'repository': repository.name,
                        'digest': artifact.digest,
                        'tags': ', '.join(tag.name for tag in artifact.tags or ()) or 'Untagged',
                        'artifact_type': artifact.artifact_type or 'Not Available',
                        'media_type': artifact.media_type or 'Not Available',
                        'size_mib': round(float(artifact.size_bytes or 0) / (1024.0 * 1024.0), 2),
                        'scan_status': artifact.scan_status or 'not_collected',
                        'critical_findings': _severity_count(summary, 'critical'),
                        'high_findings': _severity_count(summary, 'high'),
                        'signature_status': artifact.signature_status or 'not_collected',
                        'sbom_status': artifact.sbom_status or 'not_collected',
                        'push_time': artifact.push_time,
                        'pull_time': artifact.pull_time,
                        'observed_at': artifact.observed_at,
                    }
                )

    cutoff = state.last_committed_at if state is not None else None
    return {
        'integration': {
            'id': instance.id,
            'name': instance.name,
            'provider': instance.provider_key,
            'environment': instance.environment or 'Not Set',
        },
        'inventory_assets': rows,
        'data_cutoff': cutoff,
        'collected_at': cutoff,
        'source_label': 'Artifact Registry Committed Inventory',
    }
