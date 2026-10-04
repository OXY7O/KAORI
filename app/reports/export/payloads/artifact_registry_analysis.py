from __future__ import annotations

from typing import Any

from app.artifact_registry.presentation import build_overview
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
    RegistryRepository,
    RegistryWebhookEndpoint,
    RegistryWorkloadBinding,
)
from app.models.report import Report
from app.reports.catalog import require_artifact_registry_instance, validate_report_instance


def _query_artifacts(instance_id: int) -> list[RegistryArtifact]:
    return (
        RegistryArtifact.query.join(RegistryRepository)
        .join(RegistryProject)
        .filter(RegistryProject.integration_instance_id == instance_id)
        .all()
    )


def _governance_payload(instance_id: int) -> dict[str, Any]:
    state = db.session.get(RegistryGovernanceState, instance_id)
    project_rows = (
        RegistryProjectGovernance.query.join(RegistryProject)
        .filter(RegistryProject.integration_instance_id == instance_id)
        .all()
    )
    replication = RegistryReplicationPolicy.query.filter_by(integration_instance_id=instance_id).all()
    webhook = db.session.get(RegistryWebhookEndpoint, instance_id)
    return {
        'collection_status': state.status if state is not None else 'not_collected',
        'committed_at': state.last_committed_at if state is not None else None,
        'project_policy_count': len(project_rows),
        'retention_configured': sum(item.retention_status == 'configured' for item in project_rows),
        'immutability_configured': sum(item.immutability_status == 'configured' for item in project_rows),
        'replication_policy_count': len(replication),
        'replication_enabled': sum(bool(item.enabled) for item in replication),
        'webhook_status': 'ready' if webhook and webhook.enabled and webhook.token_digest else 'not_configured',
    }


def get_report_artifact_registry_analysis_payload(report: Report) -> dict[str, Any]:
    """Build one governed Registry analytics payload from committed KAORI state."""

    validate_report_instance(report)
    scope_id = require_artifact_registry_instance(report)
    try:
        instance_id = int(scope_id)
    except (TypeError, ValueError):
        return {'_error': 'The selected Artifact Registry integration is invalid.'}

    instance = db.session.get(IntegrationInstance, instance_id)
    if instance is None or instance.integration_type != 'registry':
        return {'_error': 'The selected Artifact Registry integration no longer exists.'}

    overview = build_overview(provider_id=instance_id)
    state = db.session.get(RegistryCollectionState, instance_id)
    artifacts = _query_artifacts(instance_id)
    signed_count = sum(str(item.signature_status or '').lower() in {'signed', 'verified', 'valid'} for item in artifacts)
    sbom_count = sum(str(item.sbom_status or '').lower() in {'available', 'ready', 'present'} for item in artifacts)
    runtime_count = (
        RegistryWorkloadBinding.query.join(RegistryArtifact)
        .join(RegistryRepository)
        .join(RegistryProject)
        .filter(RegistryProject.integration_instance_id == instance_id)
        .count()
    )

    capacity = dict(overview.get('capacity') or {})
    alerts = dict(overview.get('alerts') or {})
    recommendations = list(overview.get('recommended_actions') or [])
    top_consumers = list(overview.get('top_consumers') or [])
    forecast = dict(overview.get('forecast') or {})

    security = {
        'artifacts': int(overview.get('artifact_count') or 0),
        'scanned': int(overview.get('scanned_count') or 0),
        'scan_coverage': overview.get('scan_coverage'),
        'critical_findings': int(overview.get('critical_findings') or 0),
        'high_findings': int(overview.get('high_findings') or 0),
        'signed_artifacts': signed_count,
        'sbom_available': sbom_count,
    }
    runtime = {
        'bindings': runtime_count,
        'digest_bindings': int(overview.get('digest_runtime_binding_count') or 0),
        'correlation_status': 'Available' if runtime_count else 'No Runtime Correlation',
    }
    governance = _governance_payload(instance_id)

    return {
        'selected_registry': {
            'id': instance.id,
            'name': instance.name,
            'provider': instance.provider_key,
            'environment': instance.environment or 'Not Set',
        },
        'summary': {
            'projects': int(overview.get('project_count') or 0),
            'repositories': int(overview.get('repository_count') or 0),
            'artifacts': int(overview.get('artifact_count') or 0),
            'storage': str(overview.get('total_size') or '0 B'),
            'posture': str((overview.get('posture') or {}).get('label') or 'Unknown'),
        },
        'artifact_registry_capacity_usage': {
            **capacity,
            'forecast': forecast,
            'top_consumers': top_consumers,
        },
        'artifact_registry_security_posture': security,
        'artifact_registry_runtime_usage': runtime,
        'artifact_registry_governance_posture': governance,
        'artifact_registry_alerts_actions': {
            'summary': {
                'critical': int(alerts.get('critical') or 0),
                'warning': int(alerts.get('warning') or 0),
                'info': int(alerts.get('info') or 0),
                'total': int(alerts.get('total') or 0),
                'catalog_rules': int(alerts.get('catalog_rules') or 0),
            },
            'alerts': list(alerts.get('rows') or []),
            'recommendations': recommendations,
        },
        'alerts': list(alerts.get('rows') or []),
        'recommendations': recommendations,
        'actionable_recommendations': recommendations,
        'top_consumers': top_consumers,
        'forecast': forecast,
        'evidence_boundary': {
            'registry_source': 'Committed Artifact Registry inventory and analytics',
            'alert_source': 'KAORI Alert Intelligence',
            'recommendation_source': 'KAORI Intelligence catalog',
            'provider_authority': instance.provider_key,
            'live_provider_requests': 'Excluded during report rendering',
            'data_cutoff': state.last_committed_at if state is not None else None,
        },
        'source_status': {
            'label': str((overview.get('posture') or {}).get('label') or 'Unknown'),
            'description': 'Report content is rendered from committed KAORI Registry state.',
        },
        'data_cutoff': state.last_committed_at if state is not None else None,
        'collected_at': state.last_committed_at if state is not None else None,
    }
