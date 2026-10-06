from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.artifact_registry.security.contracts import registry_scan_evidence_ready
from app.extensions.db import db
from app.integrations.observability.alert_source.providers.alertmanager.application.consumer import (
    list_alerts_for_scope,
)
from app.integrations.observability.metrics_source.application.consumer import MetricsConsumer
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles.alerts_v1 import (
    ACTIVE_ALERTS_EXPRESSION,
)
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


def _alert_severity(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'critical', 'fatal', 'error', 'p1'}:
        return 'critical'
    if normalized in {'warning', 'warn', 'p2'}:
        return 'warning'
    if normalized in {'info', 'informational', 'notice', 'p3', 'p4'}:
        return 'info'
    return 'unknown'


def _alert_state(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'firing', 'active'}:
        return 'firing'
    if normalized in {'pending', 'unprocessed'}:
        return 'pending'
    if normalized in {'suppressed'}:
        return 'suppressed'
    if normalized in {'resolved', 'inactive'}:
        return 'resolved'
    return normalized or 'firing'


def _alert_target(labels: dict[str, Any]) -> str:
    for key in ('project_name', 'project', 'repository', 'service', 'deployment', 'instance', 'job'):
        value = str(labels.get(key) or '').strip()
        if value:
            return value
    return '-'


def _alert_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    fingerprint = str(row.get('fingerprint') or '').strip()
    if fingerprint:
        return ('fingerprint', fingerprint)
    labels = row.get('labels') if isinstance(row.get('labels'), dict) else {}
    stable_labels = tuple(
        sorted(
            (str(key), str(value))
            for key, value in labels.items()
            if str(key).lower() not in {'alertstate', '__replica__'}
        )
    )
    return (
        str(row.get('name') or '').casefold(),
        str(row.get('target') or '').casefold(),
        stable_labels,
    )


def _deduplicate_alert_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        selected.setdefault(_alert_identity(row), row)
    return list(selected.values())


def _alertmanager_rows(items: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        labels = dict(item.get('labels') or {}) if isinstance(item.get('labels'), dict) else {}
        annotations = (
            dict(item.get('annotations') or {}) if isinstance(item.get('annotations'), dict) else {}
        )
        status_payload = item.get('status') if isinstance(item.get('status'), dict) else {}
        raw_state = item.get('state')
        if raw_state is None and isinstance(item.get('status'), str):
            raw_state = item.get('status')
        if raw_state is None:
            raw_state = status_payload.get('state')
        rows.append(
            {
                'name': str(
                    item.get('alert_name')
                    or item.get('alertname')
                    or labels.get('alertname')
                    or item.get('name')
                    or 'Unknown Alert'
                ),
                'severity': _alert_severity(item.get('severity') or labels.get('severity')),
                'state': _alert_state(raw_state),
                'target': _alert_target(labels),
                'summary': str(
                    item.get('summary')
                    or annotations.get('summary')
                    or annotations.get('description')
                    or '-'
                ),
                'starts_at': item.get('starts_at') or item.get('startsAt'),
                'receiver': str(item.get('receiver') or '-'),
                'silenced': bool(item.get('silenced')) or bool(status_payload.get('silencedBy')),
                'inhibited': bool(item.get('inhibited')) or bool(status_payload.get('inhibitedBy')),
                'fingerprint': str(item.get('fingerprint') or ''),
                'labels': labels,
                'source': 'Alertmanager',
                'source_key': 'alertmanager',
            }
        )
    return _deduplicate_alert_rows(rows)


def _metrics_alert_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _vector(payload):
        labels = dict(item.get('metric') or {}) if isinstance(item.get('metric'), dict) else {}
        rows.append(
            {
                'name': str(labels.get('alertname') or 'Unknown Alert'),
                'severity': _alert_severity(labels.get('severity')),
                'state': _alert_state(labels.get('alertstate')),
                'target': _alert_target(labels),
                'summary': str(labels.get('alertname') or 'Metrics alert evidence'),
                'starts_at': None,
                'receiver': '-',
                'silenced': False,
                'inhibited': False,
                'fingerprint': '',
                'labels': labels,
                'source': 'Metrics Source',
                'source_key': 'metrics_source',
            }
        )
    return _deduplicate_alert_rows(rows)


def _alert_evidence(identity: IntegrationInstance) -> dict[str, Any]:
    alertmanager = list_alerts_for_scope(
        scope_type='registry_instance',
        scope_key=str(identity.id),
        required_capabilities=('alerts_v2',),
    )
    if alertmanager.get('connected'):
        return {
            'status': 'ready',
            'resolved_source': 'alertmanager',
            'source_label': 'Alertmanager',
            'fallback_used': bool(alertmanager.get('fallback_used')),
            'detail': 'Alertmanager is the committed primary alert evidence source.',
            'rows': _alertmanager_rows(alertmanager.get('alerts') or []),
            'source_errors': alertmanager.get('source_errors') or [],
        }

    alertmanager_error = str(alertmanager.get('error') or 'Alertmanager unavailable.')
    try:
        consumer = MetricsConsumer.for_asset(
            scope_type='registry_instance',
            scope_key=identity.id,
            scope_name=identity.name,
        )
        metrics_payload = consumer.query(ACTIVE_ALERTS_EXPRESSION, retry_count=0)
    except MetricsSourceError as exc:
        return {
            'status': 'unavailable',
            'resolved_source': 'none',
            'source_label': 'Unavailable',
            'fallback_used': False,
            'detail': f'Alertmanager: {alertmanager_error} Metrics Source: {exc}',
            'rows': [],
            'source_errors': [alertmanager_error, str(exc)],
        }

    return {
        'status': 'ready',
        'resolved_source': 'metrics_source',
        'source_label': consumer.config.name,
        'fallback_used': True,
        'detail': (
            f'Alertmanager was unavailable: {alertmanager_error} '
            'Metrics Source active-alert evidence was materialized as fallback.'
        ),
        'rows': _metrics_alert_rows(metrics_payload),
        'source_errors': [alertmanager_error],
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
    scanned = sum(registry_scan_evidence_ready(artifact.scan_status) for artifact in artifacts)
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
        artifact.id in runtime_artifact_ids and not registry_scan_evidence_ready(artifact.scan_status)
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
    alerts = _alert_evidence(identity)
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
        'alerts': alerts,
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
