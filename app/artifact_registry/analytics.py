from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.db import db
from app.integrations.observability.metrics_source.application.consumer import MetricsConsumer
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles.registry_harbor_v1 import (
    get_registry_query_expression,
)
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryAnalyticsSnapshot,
    RegistryArtifact,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryRepository,
    RegistryWorkloadBinding,
)


def _vector(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data') if isinstance(payload, dict) else None
    result = data.get('result') if isinstance(data, dict) else None
    return [item for item in (result or []) if isinstance(item, dict)]


def _sample_value(item: dict[str, Any]) -> float | None:
    value = item.get('value')
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None


def _project_vector(payload: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in _vector(payload):
        metric = item.get('metric') if isinstance(item.get('metric'), dict) else {}
        project = str(metric.get('project_name') or '').strip()
        sample = _sample_value(item)
        if project and sample is not None:
            values[project] = sample
    return values


def _scalar(payload: dict[str, Any]) -> float | None:
    for item in _vector(payload):
        value = _sample_value(item)
        if value is not None:
            return value
    return None


def _metric_payload(
    consumer: MetricsConsumer,
    key: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return consumer.query(get_registry_query_expression(key)), None
    except MetricsSourceError as exc:
        return None, str(exc)


def _metrics_evidence(identity: IntegrationInstance) -> dict[str, Any]:
    try:
        consumer = MetricsConsumer.for_asset(
            scope_type='registry_instance',
            scope_key=identity.id,
            scope_name=identity.name,
        )
    except MetricsSourceError as exc:
        return {
            'status': 'unavailable',
            'detail': str(exc),
            'metrics_source': None,
            'binding_id': None,
            'project_usage_bytes': {},
            'project_quota_bytes': {},
            'project_artifacts': {},
            'project_pull_count': {},
            'capability_gaps': {},
        }

    values: dict[str, Any] = {}
    gaps: dict[str, str] = {}

    project_queries = {
        'project_usage_bytes': 'registry.project.quota.usage_bytes',
        'project_quota_bytes': 'registry.project.quota.bytes',
        'project_artifacts': 'registry.project.artifacts',
        'project_pull_count': 'registry.project.pull_count',
    }
    for field, key in project_queries.items():
        payload, error = _metric_payload(consumer, key)
        values[field] = _project_vector(payload or {})
        if error:
            gaps[key] = error

    scalar_queries = {
        'provider_health_value': 'registry.health',
        'component_up_value': 'registry.component.up',
        'projects_total_metric': 'registry.projects.total',
        'request_rate_per_second': 'registry.core.request_rate',
        'inflight_requests': 'registry.core.inflight',
        'backend_request_rate_per_second': 'registry.backend.request_rate',
        'task_queue_size': 'registry.task.queue_size',
    }
    for field, key in scalar_queries.items():
        payload, error = _metric_payload(consumer, key)
        values[field] = _scalar(payload or {})
        if error:
            gaps[key] = error

    return {
        'status': 'ready',
        'metrics_source': consumer.config.name,
        'binding_id': consumer.binding.id,
        'capability_gaps': gaps,
        **values,
    }

def _previous_snapshot(identity_id: int) -> RegistryAnalyticsSnapshot | None:
    return (
        RegistryAnalyticsSnapshot.query.filter_by(
            integration_instance_id=identity_id,
            status='ready',
        )
        .order_by(RegistryAnalyticsSnapshot.generated_at.desc(), RegistryAnalyticsSnapshot.id.desc())
        .first()
    )


def _previous_project_usage(previous: RegistryAnalyticsSnapshot | None) -> dict[str, float]:
    if previous is None or not isinstance(previous.payload_json, dict):
        return {}
    metrics = previous.payload_json.get('metrics')
    values = metrics.get('project_usage_bytes') if isinstance(metrics, dict) else None
    if not isinstance(values, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in values.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _days_between(previous: RegistryAnalyticsSnapshot | None, now: datetime) -> float | None:
    if previous is None:
        return None
    then = previous.generated_at
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    seconds = (now - then).total_seconds()
    return seconds / 86400.0 if seconds >= 300 else None


def materialize_registry_analytics(
    identity: IntegrationInstance,
    *,
    job_execution_id: int | None = None,
    freshness_minutes: int = 15,
    stale_grace_minutes: int = 1440,
) -> RegistryAnalyticsSnapshot:
    """Materialize Registry analytics from committed domain state plus bound Metrics Source."""

    if identity.integration_type != 'registry':
        raise ValueError('Registry analytics requires a Registry integration identity.')

    generated_at = datetime.now(UTC)
    previous = _previous_snapshot(identity.id)
    projects = RegistryProject.query.filter_by(integration_instance_id=identity.id).all()
    project_ids = [project.id for project in projects]
    repositories = (
        RegistryRepository.query.filter(RegistryRepository.project_id.in_(project_ids)).all()
        if project_ids else []
    )
    repository_ids = [repo.id for repo in repositories]
    artifacts = (
        RegistryArtifact.query.filter(RegistryArtifact.repository_id.in_(repository_ids)).all()
        if repository_ids else []
    )
    artifact_ids = [artifact.id for artifact in artifacts]
    bindings = (
        RegistryWorkloadBinding.query.filter(
            RegistryWorkloadBinding.artifact_id.in_(artifact_ids)
        ).all()
        if artifact_ids else []
    )
    governance_rows = (
        RegistryProjectGovernance.query.filter(
            RegistryProjectGovernance.project_id.in_(project_ids)
        ).all()
        if project_ids else []
    )

    total_size = sum(int(artifact.size_bytes or 0) for artifact in artifacts)
    scanned = sum(bool(str(artifact.scan_status or '').strip()) for artifact in artifacts)
    critical_findings = sum(
        int((artifact.vulnerability_summary or {}).get('critical') or 0)
        for artifact in artifacts
        if isinstance(artifact.vulnerability_summary, dict)
    )
    high_findings = sum(
        int((artifact.vulnerability_summary or {}).get('high') or 0)
        for artifact in artifacts
        if isinstance(artifact.vulnerability_summary, dict)
    )
    signed = sum(str(artifact.signature_status or '') == 'signed' for artifact in artifacts)
    sbom = sum(str(artifact.sbom_status or '') == 'available' for artifact in artifacts)
    runtime_artifact_ids = {binding.artifact_id for binding in bindings}
    critical_runtime = sum(
        artifact.id in runtime_artifact_ids
        and int((artifact.vulnerability_summary or {}).get('critical') or 0) > 0
        for artifact in artifacts
        if isinstance(artifact.vulnerability_summary, dict)
    )
    tag_only = sum(binding.match_type == 'tag' for binding in bindings)
    scan_gaps_runtime = sum(
        artifact.id in runtime_artifact_ids and not str(artifact.scan_status or '').strip()
        for artifact in artifacts
    )
    unsigned_runtime = sum(
        artifact.id in runtime_artifact_ids and str(artifact.signature_status or '') == 'unsigned'
        for artifact in artifacts
    )

    inactive_cutoff = generated_at - timedelta(days=90)
    stale_candidates = 0
    for artifact in artifacts:
        if artifact.id in runtime_artifact_ids:
            continue
        reference_time = artifact.pull_time or artifact.push_time
        if reference_time is None:
            continue
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        stale_candidates += int(reference_time < inactive_cutoff)

    previous_inventory = previous.payload_json.get('inventory') if previous and isinstance(previous.payload_json, dict) else {}
    elapsed_days = _days_between(previous, generated_at)
    artifact_delta = len(artifacts) - int((previous_inventory or {}).get('artifacts') or len(artifacts))
    size_delta = total_size - int((previous_inventory or {}).get('total_size_bytes') or total_size)
    growth = {
        'elapsed_days': elapsed_days,
        'artifact_delta': artifact_delta,
        'size_delta_bytes': size_delta,
        'artifact_growth_per_day': (artifact_delta / elapsed_days) if elapsed_days else None,
        'size_growth_bytes_per_day': (size_delta / elapsed_days) if elapsed_days else None,
    }

    metrics = _metrics_evidence(identity)
    previous_usage = _previous_project_usage(previous)
    project_forecasts: list[dict[str, Any]] = []
    current_usage = metrics.get('project_usage_bytes') if isinstance(metrics, dict) else {}
    current_quota = metrics.get('project_quota_bytes') if isinstance(metrics, dict) else {}
    if isinstance(current_usage, dict) and isinstance(current_quota, dict):
        for project_name, raw_usage in current_usage.items():
            try:
                usage = float(raw_usage)
                quota = float(current_quota.get(project_name) or 0)
            except (TypeError, ValueError):
                continue
            if quota <= 0:
                continue
            prior = previous_usage.get(project_name)
            growth_per_day = (
                (usage - prior) / elapsed_days
                if prior is not None and elapsed_days
                else None
            )
            days_to_quota = (
                max((quota - usage) / growth_per_day, 0.0)
                if growth_per_day is not None and growth_per_day > 0 and quota > usage
                else (0.0 if usage >= quota else None)
            )
            project_forecasts.append(
                {
                    'project_name': project_name,
                    'usage_bytes': usage,
                    'quota_bytes': quota,
                    'utilization_percent': (usage / quota) * 100.0,
                    'growth_bytes_per_day': growth_per_day,
                    'days_to_quota': days_to_quota,
                }
            )

    governance_assessed = len(governance_rows)
    immutable_configured = sum(row.immutability_status == 'configured' for row in governance_rows)
    retention_configured = sum(row.retention_status == 'configured' for row in governance_rows)
    payload = {
        'inventory': {
            'projects': len(projects),
            'repositories': len(repositories),
            'artifacts': len(artifacts),
            'total_size_bytes': total_size,
            'stale_candidate_count': stale_candidates,
        },
        'security': {
            'scanned_artifacts': scanned,
            'scan_coverage_percent': round((scanned / len(artifacts)) * 100, 1) if artifacts else 0.0,
            'critical_findings': critical_findings,
            'high_findings': high_findings,
            'signed_artifacts': signed,
            'signature_coverage_percent': round((signed / len(artifacts)) * 100, 1) if artifacts else 0.0,
            'sbom_artifacts': sbom,
            'sbom_coverage_percent': round((sbom / len(artifacts)) * 100, 1) if artifacts else 0.0,
        },
        'runtime': {
            'bindings': len(bindings),
            'running_artifacts': len(runtime_artifact_ids),
            'critical_runtime_artifacts': critical_runtime,
            'tag_only_bindings': tag_only,
            'runtime_scan_gaps': scan_gaps_runtime,
            'unsigned_runtime_artifacts': unsigned_runtime,
        },
        'governance': {
            'projects_assessed': governance_assessed,
            'retention_configured': retention_configured,
            'immutability_configured': immutable_configured,
        },
        'growth': growth,
        'capacity': {'project_forecasts': project_forecasts},
        'metrics': metrics,
        'evidence': {
            'source': 'committed_registry_state',
            'metrics_source_optional': True,
            'provider_queries_on_page_load': False,
        },
    }

    snapshot = RegistryAnalyticsSnapshot(
        integration_instance_id=identity.id,
        time_range='current',
        payload_json=payload,
        status='ready',
        generated_at=generated_at,
        expires_at=generated_at + timedelta(minutes=max(int(freshness_minutes), 1)),
        freshness_minutes=max(int(freshness_minutes), 1),
        stale_grace_minutes=max(int(stale_grace_minutes), 1),
        last_job_execution_id=job_execution_id,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot
