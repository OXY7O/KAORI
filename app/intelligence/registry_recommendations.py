from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.extensions.db import db
from app.integrations.registry.security_contracts import registry_scan_evidence_ready
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


def _active_registry_instances() -> dict[int, IntegrationInstance]:
    """Reuse the active provider eligibility boundary across Registry evaluators."""
    rows = IntegrationInstance.query.filter(
        IntegrationInstance.integration_type == 'registry',
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.lifecycle_status == 'active',
    ).all()
    return {int(row.id): row for row in rows}


def _identity(
    project: RegistryProject,
    identities: dict[int, IntegrationInstance] | None = None,
) -> tuple[IntegrationInstance | None, str, str]:
    if identities is None:
        identities = _active_registry_instances()
    identity = identities.get(int(project.integration_instance_id))
    if identity is None or not identity.enabled or identity.lifecycle_status != 'active':
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
    bindings: list[RegistryWorkloadBinding],
) -> dict[str, Any]:
    # Old vulnerability JSON does not constitute a valid assessed finding.
    scan_usable = bool(registry_scan_evidence_ready(artifact.scan_status))
    summary = (
        artifact.vulnerability_summary
        if scan_usable and isinstance(artifact.vulnerability_summary, dict)
        else {}
    )
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
            {f'{binding.namespace}/{binding.workload_name or binding.pod_name}' for binding in bindings}
        ),
        'inventory_observed_at': artifact.observed_at.isoformat(),
    }


def _artifact_pages(
    identities: dict[int, IntegrationInstance],
    *,
    page_size: int = 200,
):
    """Keyset bounded hydration, restricted to running active-source artifacts."""
    if not identities:
        return
    last_id = 0
    running_ids = db.session.query(RegistryWorkloadBinding.artifact_id).distinct()
    while True:
        page = (
            RegistryArtifact.query.join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
            .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
            .options(
                joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
                selectinload(RegistryArtifact.tags),
            )
            .filter(
                RegistryProject.integration_instance_id.in_(tuple(identities)),
                RegistryArtifact.id > last_id,
                RegistryArtifact.id.in_(running_ids),
            )
            .order_by(RegistryArtifact.id.asc())
            .limit(page_size)
            .all()
        )
        if not page:
            break
        artifact_ids = [item.id for item in page]
        grouped: dict[int, list[RegistryWorkloadBinding]] = defaultdict(list)
        for binding in RegistryWorkloadBinding.query.filter(
            RegistryWorkloadBinding.artifact_id.in_(artifact_ids)
        ).all():
            grouped[int(binding.artifact_id)].append(binding)
        for artifact in page:
            yield artifact, grouped[int(artifact.id)]
        last_id = int(page[-1].id)


def _artifact_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not any(key in rules for key in (
        'registry.security.critical_runtime_vulnerability',
        'registry.security.scan_evidence_missing',
        'registry.runtime.tag_only_correlation',
    )):
        return []
    identities = _active_registry_instances()
    findings: list[dict[str, Any]] = []
    for artifact, bindings in _artifact_pages(identities):
        identity, provider_key, provider_label = _identity(artifact.repository.project, identities)
        if identity is None or not bindings:
            continue
        evidence = _artifact_evidence(
            artifact,
            identity=identity,
            provider_key=provider_key,
            provider_label=provider_label,
            bindings=bindings,
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
                            f'has {critical} critical vulnerability finding(s) and '
                            f'{len(bindings)} committed runtime binding(s).'
                        ),
                        condition_summary=(
                            'Critical vulnerability evidence and committed Kubernetes runtime usage are both present '
                            'for the same immutable artifact digest.'
                        ),
                        evidence=evidence,
                    )
                )
        if not registry_scan_evidence_ready(artifact.scan_status):
            rule = rules.get('registry.security.scan_evidence_missing')
            if rule is not None:
                scan_label = str(artifact.scan_status or 'not_observed').replace('_', ' ')
                findings.append(
                    _finding(
                        rule,
                        finding_key=f'{rule["rule_key"]}:{artifact.id}',
                        title='Running Registry artifact has no usable scan evidence',
                        summary=(
                            f'{artifact.repository.project.name}/{artifact.repository.name}@{artifact.digest[:20]}… '
                            f'is referenced at runtime but committed scan status {scan_label!r} '
                            'is not usable evidence.'
                        ),
                        condition_summary=(
                            'Runtime binding count is positive while Registry scan_status is not a normalized '
                            'successful scan state.'
                        ),
                        evidence=evidence,
                    )
                )
        tag_rule = rules.get('registry.runtime.tag_only_correlation')
        if tag_rule is None:
            continue
        for binding in bindings:
            if binding.match_type != 'tag':
                continue
            tag_evidence = {
                **evidence,
                'match_type': binding.match_type,
                'match_confidence': binding.confidence,
                'image_reference': binding.image_reference,
                'cluster_id': binding.cluster_id,
                'namespace': binding.namespace,
                'pod_name': binding.pod_name,
            }
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
                    evidence=tag_evidence,
                )
            )
    return findings

def _governance_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('registry.governance.public_project_without_immutability')
    if rule is None:
        return []
    identities = _active_registry_instances()
    if not identities:
        return []
    rows = (
        RegistryProjectGovernance.query.join(
            RegistryProject, RegistryProjectGovernance.project_id == RegistryProject.id
        )
        .options(joinedload(RegistryProjectGovernance.project))
        .filter(
            RegistryProjectGovernance.immutability_status == 'not_configured',
            RegistryProject.integration_instance_id.in_(tuple(identities)),
        )
        .yield_per(200)
    )
    findings: list[dict[str, Any]] = []
    for row in rows:
        project = row.project
        if project.public is not True:
            continue
        identity, provider_key, provider_label = _identity(project, identities)
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
    identities = _active_registry_instances()
    for identity in identities.values():
        snapshot = (
            RegistryAnalyticsSnapshot.query.filter_by(
                integration_instance_id=identity.id,
                status='ready',
                time_range='current',
            )
            .order_by(RegistryAnalyticsSnapshot.generated_at.desc(), RegistryAnalyticsSnapshot.id.desc())
            .first()
        )
        if snapshot is None or not isinstance(snapshot.payload_json, dict):
            continue
        expires_at = snapshot.expires_at
        if expires_at is None:
            continue
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
