from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryAnalyticsSnapshot,
    RegistryArtifact,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryRepository,
    RegistryWorkloadBinding,
)


def _finding(
    rule: dict[str, Any],
    *,
    finding_key: str,
    title: str,
    summary: str,
    condition_summary: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    row = dict(rule)
    row.update(
        {
            'rule_key': finding_key,
            'title': title,
            'summary': summary,
            'condition_summary': condition_summary,
            'status': 'available',
            'evidence': evidence,
        }
    )
    return row


def _identity(project: RegistryProject) -> tuple[IntegrationInstance | None, str, str]:
    identity = IntegrationInstance.query.filter_by(
        id=project.integration_instance_id,
        integration_type='registry',
    ).first()
    if identity is None:
        return None, '', 'Registry'
    metadata = identity.metadata_json if isinstance(identity.metadata_json, dict) else {}
    provider_key = str(identity.provider_key or '').strip().lower()
    provider_label = str(metadata.get('provider_label') or provider_key.replace('_', ' ').title() or 'Registry')
    return identity, provider_key, provider_label


def _artifact_evidence(
    artifact: RegistryArtifact,
    *,
    identity: IntegrationInstance,
    provider_key: str,
    provider_label: str,
) -> dict[str, Any]:
    bindings = RegistryWorkloadBinding.query.filter_by(artifact_id=artifact.id).all()
    summary = artifact.vulnerability_summary if isinstance(artifact.vulnerability_summary, dict) else {}
    return {
        'asset_key': str(identity.id),
        'registry_instance_id': str(identity.id),
        'registry_instance_name': identity.name,
        'provider_key': provider_key,
        'provider_label': provider_label,
        'project_name': artifact.repository.project.name,
        'repository_name': artifact.repository.name,
        'artifact_id': str(artifact.id),
        'artifact_digest': artifact.digest,
        'tags': [tag.name for tag in artifact.tags],
        'scan_status': artifact.scan_status or 'not_observed',
        'critical_count': int(summary.get('critical') or 0),
        'high_count': int(summary.get('high') or 0),
        'runtime_binding_count': len(bindings),
        'runtime_namespaces': sorted({binding.namespace for binding in bindings}),
        'runtime_workloads': sorted(
            {
                f'{binding.namespace}/{binding.workload_name or binding.pod_name}'
                for binding in bindings
            }
        ),
        'inventory_observed_at': artifact.observed_at.isoformat(),
    }


def _artifact_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts = RegistryArtifact.query.options(
        joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
        selectinload(RegistryArtifact.tags),
    ).all()
    findings: list[dict[str, Any]] = []
    for artifact in artifacts:
        identity, provider_key, provider_label = _identity(artifact.repository.project)
        if identity is None:
            continue
        bindings = RegistryWorkloadBinding.query.filter_by(artifact_id=artifact.id).all()
        if not bindings:
            continue
        evidence = _artifact_evidence(
            artifact,
            identity=identity,
            provider_key=provider_key,
            provider_label=provider_label,
        )
        critical = int(evidence['critical_count'])
        if critical > 0:
            rule = rules.get('registry.security.critical_runtime_vulnerability')
            if rule is not None:
                findings.append(
                    _finding(
                        rule,
                        finding_key=f'{rule["rule_key"]}:{artifact.id}',
                        title=f'{critical} critical finding(s) affect a running Registry artifact',
                        summary=(
                            f'{artifact.repository.project.name}/{artifact.repository.name}@{artifact.digest[:20]}… '
                            f'has {critical} critical vulnerability finding(s) and {len(bindings)} committed runtime binding(s).'
                        ),
                        condition_summary=(
                            'Critical vulnerability evidence and committed Kubernetes runtime usage are both present '
                            'for the same immutable artifact digest.'
                        ),
                        evidence=evidence,
                    )
                )

        if not str(artifact.scan_status or '').strip():
            rule = rules.get('registry.security.scan_evidence_missing')
            if rule is not None:
                findings.append(
                    _finding(
                        rule,
                        finding_key=f'{rule["rule_key"]}:{artifact.id}',
                        title='Running Registry artifact has no scan evidence',
                        summary=(
                            f'{artifact.repository.project.name}/{artifact.repository.name}@{artifact.digest[:20]}… '
                            f'is referenced at runtime but no scan status is committed.'
                        ),
                        condition_summary='Runtime binding count is positive while Registry scan_status is not observed.',
                        evidence=evidence,
                    )
                )

    tag_rule = rules.get('registry.runtime.tag_only_correlation')
    if tag_rule is not None:
        for binding in RegistryWorkloadBinding.query.filter_by(match_type='tag').all():
            artifact = RegistryArtifact.query.options(
                joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            ).filter_by(id=binding.artifact_id).first()
            if artifact is None:
                continue
            identity, provider_key, provider_label = _identity(artifact.repository.project)
            if identity is None:
                continue
            evidence = _artifact_evidence(
                artifact,
                identity=identity,
                provider_key=provider_key,
                provider_label=provider_label,
            )
            evidence.update(
                {
                    'match_type': binding.match_type,
                    'match_confidence': binding.confidence,
                    'image_reference': binding.image_reference,
                    'cluster_id': binding.cluster_id,
                    'namespace': binding.namespace,
                    'pod_name': binding.pod_name,
                }
            )
            findings.append(
                _finding(
                    tag_rule,
                    finding_key=f'{tag_rule["rule_key"]}:{binding.id}',
                    title=f'{binding.namespace}/{binding.pod_name} resolves Registry identity through a tag',
                    summary=(
                        f'Runtime image reference {binding.image_reference} matched the Registry artifact with '
                        f'{binding.confidence} confidence because no immutable digest was available.'
                    ),
                    condition_summary='RegistryWorkloadBinding match_type is tag rather than digest.',
                    evidence=evidence,
                )
            )
    return findings


def _governance_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('registry.governance.public_project_without_immutability')
    if rule is None:
        return []
    rows = RegistryProjectGovernance.query.options(
        joinedload(RegistryProjectGovernance.project)
    ).filter(
        RegistryProjectGovernance.immutability_status == 'not_configured'
    ).all()
    findings: list[dict[str, Any]] = []
    for row in rows:
        project = row.project
        if project.public is not True:
            continue
        identity, provider_key, provider_label = _identity(project)
        if identity is None:
            continue
        evidence = {
            'asset_key': str(identity.id),
            'registry_instance_id': str(identity.id),
            'registry_instance_name': identity.name,
            'provider_key': provider_key,
            'provider_label': provider_label,
            'project_id': str(project.id),
            'project_name': project.name,
            'project_public': True,
            'immutability_status': row.immutability_status,
            'retention_status': row.retention_status,
            'governance_observed_at': row.observed_at.isoformat(),
        }
        findings.append(
            _finding(
                rule,
                finding_key=f'{rule["rule_key"]}:{project.id}',
                title=f'{project.name} is public without configured immutability',
                summary=(
                    f'Committed Registry governance shows public project {project.name} with no configured '
                    'immutability rule.'
                ),
                condition_summary='Project public=true and committed immutability_status=not_configured.',
                evidence=evidence,
            )
        )
    return findings


def _forecast_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    identities = IntegrationInstance.query.filter_by(integration_type='registry').all()
    for identity in identities:
        snapshot = (
            RegistryAnalyticsSnapshot.query.filter_by(
                integration_instance_id=identity.id,
                status='ready',
            )
            .order_by(RegistryAnalyticsSnapshot.generated_at.desc(), RegistryAnalyticsSnapshot.id.desc())
            .first()
        )
        if snapshot is None or not isinstance(snapshot.payload_json, dict):
            continue
        expires_at = snapshot.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) > expires_at:
                continue
        capacity = snapshot.payload_json.get('capacity')
        forecasts = capacity.get('project_forecasts') if isinstance(capacity, dict) else None
        if not isinstance(forecasts, list):
            continue
        metadata = identity.metadata_json if isinstance(identity.metadata_json, dict) else {}
        provider_key = str(identity.provider_key or '').strip().lower()
        provider_label = str(metadata.get('provider_label') or provider_key.replace('_', ' ').title())
        for forecast in forecasts:
            if not isinstance(forecast, dict):
                continue
            days = forecast.get('days_to_quota')
            growth = forecast.get('growth_bytes_per_day')
            if not isinstance(days, (int, float)) or not isinstance(growth, (int, float)):
                continue
            if float(growth) <= 0 or float(days) > 90:
                continue
            rule_key = (
                'registry.capacity.quota_exhaustion_critical'
                if float(days) <= 30
                else 'registry.capacity.quota_exhaustion_review'
            )
            rule = rules.get(rule_key)
            if rule is None:
                continue
            project_name = str(forecast.get('project_name') or 'Registry project')
            evidence = {
                'asset_key': str(identity.id),
                'registry_instance_id': str(identity.id),
                'registry_instance_name': identity.name,
                'provider_key': provider_key,
                'provider_label': provider_label,
                'project_name': project_name,
                'quota_bytes': forecast.get('quota_bytes'),
                'usage_bytes': forecast.get('usage_bytes'),
                'utilization_percent': forecast.get('utilization_percent'),
                'growth_bytes_per_day': growth,
                'days_to_quota': days,
                'analytics_snapshot_id': snapshot.id,
                'analytics_generated_at': snapshot.generated_at.isoformat(),
            }
            findings.append(
                _finding(
                    rule,
                    finding_key=f'{rule["rule_key"]}:{identity.id}:{project_name}',
                    title=f'{project_name} quota may exhaust in {float(days):.1f} days',
                    summary=(
                        f'Committed Registry analytics projects {project_name} quota exhaustion in '
                        f'{float(days):.1f} days at the current observed growth rate.'
                    ),
                    condition_summary=(
                        f'Worker-materialized days_to_quota={float(days):.1f} with positive project usage growth.'
                    ),
                    evidence=evidence,
                )
            )
    return findings


def build_registry_recommendation_findings(
    rules: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate committed Registry facts through central Intelligence ownership."""

    findings: list[dict[str, Any]] = []
    findings.extend(_artifact_findings(rules))
    findings.extend(_governance_findings(rules))
    findings.extend(_forecast_findings(rules))
    return findings
