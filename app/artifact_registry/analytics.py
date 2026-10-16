from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.artifact_registry.analytics_history import (
    REGISTRY_HISTORY_WINDOWS,
    collect_registry_metric_history,
)
from app.artifact_registry.correlation import runtime_input_signature
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
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryRepository,
    RegistryWorkloadBinding,
)


def _vector(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data') if isinstance(payload, dict) else None
    result = data.get('result') if isinstance(data, dict) else None
    return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []


def _valid_instant_vector(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get('status') != 'success':
        return False
    data = payload.get('data')
    return (
        isinstance(data, dict)
        and data.get('resultType') == 'vector'
        and isinstance(data.get('result'), list)
        and all(isinstance(item, dict) for item in data['result'])
    )


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
        raw_metric = item.get('metric')
        metric = raw_metric if isinstance(raw_metric, dict) else {}
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
        result = consumer.query(get_registry_query_expression(key))
        if not _valid_instant_vector(result):
            return None, 'Invalid or unsupported Metrics Source instant-vector result.'
        return result, None
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

    observed = len(project_queries) + len(scalar_queries) - len(gaps)
    return {
        'status': 'unavailable' if not observed else ('partial' if gaps else 'ready'),
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
    raw_labels = row.get('labels')
    labels = raw_labels if isinstance(raw_labels, dict) else {}
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
        raw_labels = item.get('labels')
        labels = dict(raw_labels) if isinstance(raw_labels, dict) else {}
        raw_annotations = item.get('annotations')
        annotations = dict(raw_annotations) if isinstance(raw_annotations, dict) else {}
        raw_status = item.get('status')
        status_payload = raw_status if isinstance(raw_status, dict) else {}
        raw_state = item.get('state')
        if raw_state is None and isinstance(raw_status, str):
            raw_state = raw_status
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
                    item.get('summary') or annotations.get('summary') or annotations.get('description') or '-'
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
        raw_metric = item.get('metric')
        labels = dict(raw_metric) if isinstance(raw_metric, dict) else {}
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
        raw_alerts = alertmanager.get('alerts')
        if not isinstance(raw_alerts, list) or any(not isinstance(item, dict) for item in raw_alerts):
            return {
                'status': 'unavailable',
                'resolved_source': 'alertmanager',
                'source_label': 'Unavailable',
                'fallback_used': False,
                'detail': 'Alertmanager returned malformed successful alert evidence.',
                'rows': [],
                'source_errors': ['Malformed Alertmanager alert record list.'],
            }
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

    if not _valid_instant_vector(metrics_payload):
        return {
            'status': 'unavailable',
            'resolved_source': 'metrics_source',
            'source_label': 'Unavailable',
            'fallback_used': True,
            'detail': 'Metrics Source fallback returned malformed active-alert evidence.',
            'rows': [],
            'source_errors': [alertmanager_error, 'Invalid active-alert Metrics Source response.'],
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
            time_range='current',
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


def _registry_bounded_state(identity_id: int, generated_at: datetime) -> dict[str, Any]:
    """Bounded SQL projection of one committed Registry source without ORM estate hydration."""
    project_count = RegistryProject.query.filter_by(integration_instance_id=identity_id).count()
    repositories = RegistryRepository.query.join(
        RegistryProject, RegistryRepository.project_id == RegistryProject.id
    ).filter(RegistryProject.integration_instance_id == identity_id)
    repository_count = repositories.count()
    artifacts = (
        RegistryArtifact.query.join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
        .filter(RegistryProject.integration_instance_id == identity_id)
    )

    bindings = (
        RegistryWorkloadBinding.query.join(RegistryArtifact, RegistryWorkloadBinding.artifact_id == RegistryArtifact.id)
        .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
        .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
        .filter(RegistryProject.integration_instance_id == identity_id)
    )
    binding_count = bindings.count()
    tag_only_count = bindings.filter(RegistryWorkloadBinding.match_type == 'tag').count()
    running_count = int(
        bindings.with_entities(func.count(func.distinct(RegistryWorkloadBinding.artifact_id))).scalar() or 0
    )
    runtime_ids = bindings.with_entities(RegistryWorkloadBinding.artifact_id).distinct().subquery()
    rows = artifacts.with_entities(
        RegistryArtifact.id,
        RegistryArtifact.size_bytes,
        RegistryArtifact.scan_status,
        RegistryArtifact.vulnerability_summary,
        RegistryArtifact.signature_status,
        RegistryArtifact.sbom_status,
        RegistryArtifact.pull_time,
        RegistryArtifact.push_time,
        RegistryArtifact.id.in_(select(runtime_ids.c.artifact_id)).label('used_at_runtime'),
    ).yield_per(250)

    counts = {
        'artifacts': 0,
        'total_size_bytes': 0,
        'stale_candidate_count': 0,
        'scanned_artifacts': 0,
        'critical_findings': 0,
        'high_findings': 0,
        'signed_artifacts': 0,
        'sbom_artifacts': 0,
        'critical_runtime_artifacts': 0,
        'runtime_scan_gaps': 0,
        'unsigned_runtime_artifacts': 0,
    }
    stale_cutoff = generated_at - timedelta(days=90)
    for artifact_id, size, scan, findings, signature, sbom, pull_at, push_at, running in rows:
        del artifact_id
        counts['artifacts'] += 1
        counts['total_size_bytes'] += int(size or 0)
        scan_ready = bool(registry_scan_evidence_ready(scan))
        counts['scanned_artifacts'] += int(scan_ready)
        counts['signed_artifacts'] += int(signature == 'signed')
        counts['sbom_artifacts'] += int(sbom == 'available')
        summary = findings if isinstance(findings, dict) and scan_ready else {}
        critical = int(summary.get('critical') or 0)
        high = int(summary.get('high') or 0)
        counts['critical_findings'] += critical
        counts['high_findings'] += high
        counts['critical_runtime_artifacts'] += int(bool(running) and critical > 0)
        counts['runtime_scan_gaps'] += int(bool(running) and not scan_ready)
        counts['unsigned_runtime_artifacts'] += int(bool(running) and signature == 'unsigned')
        last_use = pull_at or push_at
        if last_use is not None:
            observed = last_use if last_use.tzinfo else last_use.replace(tzinfo=UTC)
            counts['stale_candidate_count'] += int(not running and observed < stale_cutoff)

    assessed = RegistryProjectGovernance.query.join(
        RegistryProject, RegistryProjectGovernance.project_id == RegistryProject.id
    ).filter(RegistryProject.integration_instance_id == identity_id)
    governance_counts = {
        'projects_assessed': assessed.count(),
        'retention_configured': assessed.filter(RegistryProjectGovernance.retention_status == 'configured').count(),
        'immutability_configured': assessed.filter(
            RegistryProjectGovernance.immutability_status == 'configured'
        ).count(),
        'retention_not_configured': assessed.filter(
            RegistryProjectGovernance.retention_status == 'not_configured'
        ).count(),
        'immutability_not_configured': assessed.filter(
            RegistryProjectGovernance.immutability_status == 'not_configured'
        ).count(),
    }
    inventory = {
        'projects': project_count,
        'repositories': repository_count,
        **{key: counts[key] for key in ('artifacts', 'total_size_bytes', 'stale_candidate_count')},
    }
    security = {
        'scanned_artifacts': counts['scanned_artifacts'],
        'scan_coverage_percent': round(100 * counts['scanned_artifacts'] / counts['artifacts'], 1)
        if counts['artifacts']
        else None,
        'critical_findings': counts['critical_findings'],
        'high_findings': counts['high_findings'],
        'signed_artifacts': counts['signed_artifacts'],
        'signature_coverage_percent': round(100 * counts['signed_artifacts'] / counts['artifacts'], 1)
        if counts['artifacts']
        else None,
        'sbom_artifacts': counts['sbom_artifacts'],
        'sbom_coverage_percent': round(100 * counts['sbom_artifacts'] / counts['artifacts'], 1)
        if counts['artifacts']
        else None,
    }
    runtime = {
        'bindings': binding_count,
        'running_artifacts': running_count,
        'critical_runtime_artifacts': counts['critical_runtime_artifacts'],
        'tag_only_bindings': tag_only_count,
        'runtime_scan_gaps': counts['runtime_scan_gaps'],
        'unsigned_runtime_artifacts': counts['unsigned_runtime_artifacts'],
    }
    inventory_state = db.session.get(RegistryCollectionState, identity_id)
    governance_state = db.session.get(RegistryGovernanceState, identity_id)
    latest_binding = bindings.with_entities(func.max(RegistryWorkloadBinding.observed_at)).scalar()
    latest_scan = artifacts.with_entities(func.max(RegistryArtifact.scan_completed_at)).scalar()
    return {
        'inventory': inventory,
        'security': security,
        'runtime': runtime,
        'governance': governance_counts,
        'evidence': {
            'source': 'committed_registry_state',
            'metrics_source_optional': True,
            'provider_queries_on_page_load': False,
            'inventory_committed_at': (
                inventory_state.last_committed_at.isoformat()
                if inventory_state and inventory_state.last_committed_at
                else None
            ),
            'governance_committed_at': (
                governance_state.last_committed_at.isoformat()
                if governance_state and governance_state.last_committed_at
                else None
            ),
            'governance_status': governance_state.status if governance_state else 'not_collected',
            'runtime_observed_at': latest_binding.isoformat() if latest_binding else None,
            'correlation_input_signature': runtime_input_signature(db.session()),
            'security_latest_scan_at': latest_scan.isoformat() if latest_scan else None,
            'security_assessed_count': counts['scanned_artifacts'],
        },
    }


def _growth_payload(
    previous: RegistryAnalyticsSnapshot | None,
    *,
    generated_at: datetime,
    artifact_count: int,
    total_size: int,
) -> tuple[dict[str, Any], float | None]:
    previous_inventory = (
        previous.payload_json.get('inventory') if previous and isinstance(previous.payload_json, dict) else {}
    )
    elapsed_days = _days_between(previous, generated_at)
    old_artifacts = (previous_inventory or {}).get('artifacts')
    old_size = (previous_inventory or {}).get('total_size_bytes')
    artifact_delta = artifact_count - int(old_artifacts) if old_artifacts is not None else 0
    size_delta = total_size - int(old_size) if old_size is not None else 0
    return (
        {
            'elapsed_days': elapsed_days,
            'artifact_delta': artifact_delta,
            'size_delta_bytes': size_delta,
            'artifact_growth_per_day': (artifact_delta / elapsed_days) if elapsed_days else None,
            'size_growth_bytes_per_day': (size_delta / elapsed_days) if elapsed_days else None,
        },
        elapsed_days,
    )


def _project_forecasts(
    metrics: dict[str, Any],
    previous_usage: dict[str, float],
    elapsed_days: float | None,
) -> list[dict[str, Any]]:
    current_usage = metrics.get('project_usage_bytes') if isinstance(metrics, dict) else {}
    current_quota = metrics.get('project_quota_bytes') if isinstance(metrics, dict) else {}
    if not isinstance(current_usage, dict) or not isinstance(current_quota, dict):
        return []

    forecasts: list[dict[str, Any]] = []
    for project_name, raw_usage in current_usage.items():
        try:
            usage = float(raw_usage)
            quota = float(current_quota.get(project_name) or 0)
        except (TypeError, ValueError):
            continue
        if quota <= 0:
            continue
        prior = previous_usage.get(project_name)
        growth_per_day = (usage - prior) / elapsed_days if prior is not None and elapsed_days else None
        if growth_per_day is not None and growth_per_day > 0 and quota > usage:
            days_to_quota = max((quota - usage) / growth_per_day, 0.0)
        else:
            days_to_quota = 0.0 if usage >= quota else None
        forecasts.append(
            {
                'project_name': project_name,
                'usage_bytes': usage,
                'quota_bytes': quota,
                'utilization_percent': (usage / quota) * 100.0,
                'growth_bytes_per_day': growth_per_day,
                'days_to_quota': days_to_quota,
            }
        )
    return forecasts


def materialize_registry_analytics(
    identity: IntegrationInstance,
    *,
    job_execution_id: int | None = None,
    time_range: str = 'current',
    freshness_minutes: int = 15,
    stale_grace_minutes: int = 1440,
) -> RegistryAnalyticsSnapshot:
    """Materialize Registry analytics from committed domain state plus bound Metrics Source."""

    if identity.integration_type != 'registry' or not identity.enabled or identity.lifecycle_status != 'active':
        raise ValueError('Registry analytics requires an active and enabled Registry source.')

    if time_range != 'current' and time_range not in REGISTRY_HISTORY_WINDOWS:
        raise ValueError('Unrecognized Registry history interval.')
    generated_at = datetime.now(UTC)
    previous = _previous_snapshot(identity.id)
    domain = _registry_bounded_state(identity.id, generated_at)
    inventory = domain['inventory']
    total_size = int(inventory['total_size_bytes'])
    growth, elapsed_days = _growth_payload(
        previous,
        generated_at=generated_at,
        artifact_count=int(inventory['artifacts']),
        total_size=total_size,
    )
    if time_range == 'current':
        metrics = _metrics_evidence(identity)
        history: dict[str, Any] | None = None
        prior_usage = _previous_project_usage(previous)
    else:
        history, metrics, measured_growth = collect_registry_metric_history(identity, time_range, now=generated_at)
        growth = measured_growth
        elapsed_days = measured_growth['elapsed_days']
        prior_usage = {
            project: point['first']
            for project, point in history.get('series', {}).get('project_usage_bytes', {}).items()
        }
    alerts = _alert_evidence(identity)
    project_forecasts = _project_forecasts(metrics, prior_usage, elapsed_days)
    payload = {
        **domain,
        'growth': growth,
        'capacity': {'project_forecasts': project_forecasts},
        'metrics': metrics,
        'alerts': alerts,
    }
    if history is not None:
        payload['history'] = history
    # An Inventory refresh racing with materialization must not bless the
    # earlier generation as current. Preserve the previously committed snapshot.
    inventory_state = db.session.get(RegistryCollectionState, int(identity.id))
    if inventory_state is not None:
        db.session.refresh(inventory_state)
    current_generation = (
        inventory_state.last_committed_at.isoformat() if inventory_state and inventory_state.last_committed_at else None
    )
    if current_generation != domain['evidence']['inventory_committed_at']:
        raise RuntimeError('Registry inventory generation changed during Analytics materialization.')
    if current_generation is None:
        raise RuntimeError('Registry Inventory has no usable committed generation for Analytics.')
    db.session.refresh(identity, attribute_names=['enabled', 'lifecycle_status'])
    if not identity.enabled or identity.lifecycle_status != 'active':
        raise RuntimeError('Registry source was disabled during Analytics materialization.')
    current_governance = db.session.get(RegistryGovernanceState, int(identity.id))
    if current_governance is not None:
        db.session.refresh(current_governance, attribute_names=['last_committed_at'])
    governance_generation = (
        current_governance.last_committed_at.isoformat()
        if current_governance and current_governance.last_committed_at
        else None
    )
    if governance_generation != domain['evidence']['governance_committed_at']:
        raise RuntimeError('Registry Governance changed during Analytics materialization.')
    if runtime_input_signature(db.session()) != domain['evidence']['correlation_input_signature']:
        raise RuntimeError('Registry or Kubernetes correlation inputs changed during Analytics materialization.')

    snapshot = RegistryAnalyticsSnapshot()
    snapshot.integration_instance_id = identity.id
    snapshot.time_range = time_range
    snapshot.payload_json = payload
    snapshot.status = 'ready'
    snapshot.generated_at = generated_at
    snapshot.expires_at = generated_at + timedelta(minutes=max(int(freshness_minutes), 1))
    snapshot.freshness_minutes = max(int(freshness_minutes), 1)
    snapshot.stale_grace_minutes = max(int(stale_grace_minutes), 1)
    snapshot.last_job_execution_id = job_execution_id
    db.session.add(snapshot)
    db.session.commit()
    return snapshot
