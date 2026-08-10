from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.analytics.common.coercion import as_dict
from app.analytics.overview.schema import build_empty_overview_payload, classify_percent


@dataclass(frozen=True, slots=True)
class HealthEvidence:
    snapshot_summary: dict[str, Any]
    resource: dict[str, Any]
    capacity: dict[str, Any]
    storage: dict[str, Any]
    workload: dict[str, Any]
    forecast: dict[str, Any]
    alerts: dict[str, Any]
    resource_available: bool
    capacity_available: bool
    storage_available: bool
    workload_available: bool
    forecast_available: bool
    alerts_available: bool
    current_dataset_count: int
    expected_dataset_count: int
    evidence_available: bool
    evidence_complete: bool
    highest_pressure_resource: str | None
    max_pressure: float
    active_alerts: int
    firing_alerts: int
    pending_alerts: int
    critical_alerts: int
    warning_alerts: int
    recent_anomalies: int
    forecast_risk_count: int
    forecast_risk_value: str
    forecast_is_high: bool
    forecast_is_medium: bool
    pvc_risk_count: int
    workload_issue_count: int


def build_health_summary(payload: dict[str, Any]) -> dict[str, Any]:
    default = deepcopy(build_empty_overview_payload()['health_summary'])
    evidence = _collect_evidence(payload)
    return {
        **default,
        'cluster_health': {**default['cluster_health'], **_cluster_health(evidence)},
        'resource_pressure': {**default['resource_pressure'], **_resource_pressure(evidence)},
        'capacity_risk': {**default['capacity_risk'], **_capacity_risk(evidence)},
        'active_alerts': {**default['active_alerts'], **_active_alerts(evidence)},
        'forecast_risk': {**default['forecast_risk'], **_forecast_risk(evidence)},
        'top_risk_namespace': {
            **default['top_risk_namespace'],
            **_top_risk_namespace(evidence),
        },
    }


def _collect_evidence(payload: dict[str, Any]) -> HealthEvidence:
    summary = as_dict(payload.get('snapshot_summary'))
    resource = as_dict(payload.get('resource_snapshot'))
    capacity = as_dict(payload.get('capacity_snapshot'))
    storage = as_dict(payload.get('storage_snapshot'))
    workload = as_dict(payload.get('workload_snapshot'))
    forecast = as_dict(payload.get('forecast_snapshot'))
    alerts = as_dict(payload.get('alerts_snapshot'))
    availability = {
        'resource': bool(resource.get('available', False)),
        'capacity': bool(capacity.get('available', False)),
        'storage': bool(storage.get('available', False)),
        'workload': bool(workload.get('available', False)),
        'forecast': bool(forecast.get('available', False)),
        'alerts': bool(alerts.get('available', False)),
    }
    current_count = _as_int(summary.get('current_dataset_count'))
    expected_count = max(1, _as_int(summary.get('expected_dataset_count', 7)))
    pressure_resource, max_pressure = _highest_resource_pressure(resource, availability['resource'])
    alert_values = _alert_values(alerts, availability['alerts'])
    forecast_values = _forecast_values(forecast, availability['forecast'])
    return HealthEvidence(
        snapshot_summary=summary,
        resource=resource,
        capacity=capacity,
        storage=storage,
        workload=workload,
        forecast=forecast,
        alerts=alerts,
        resource_available=availability['resource'],
        capacity_available=availability['capacity'],
        storage_available=availability['storage'],
        workload_available=availability['workload'],
        forecast_available=availability['forecast'],
        alerts_available=availability['alerts'],
        current_dataset_count=current_count,
        expected_dataset_count=expected_count,
        evidence_available=_as_int(summary.get('available_dataset_count')) > 0,
        evidence_complete=current_count >= expected_count,
        highest_pressure_resource=pressure_resource,
        max_pressure=max_pressure,
        active_alerts=alert_values['firing'] + alert_values['pending'],
        firing_alerts=alert_values['firing'],
        pending_alerts=alert_values['pending'],
        critical_alerts=alert_values['critical'],
        warning_alerts=alert_values['warning'],
        recent_anomalies=alert_values['anomalies'],
        forecast_risk_count=forecast_values['count'],
        forecast_risk_value=forecast_values['value'],
        forecast_is_high=forecast_values['high'],
        forecast_is_medium=forecast_values['medium'],
        pvc_risk_count=_as_int(storage.get('pvc_risk_count')) if availability['storage'] else 0,
        workload_issue_count=_workload_issue_count(workload) if availability['workload'] else 0,
    )


def _cluster_health(evidence: HealthEvidence) -> dict[str, str]:
    critical = evidence.critical_alerts > 0 or evidence.max_pressure >= 90 or evidence.forecast_is_high
    warning = any(
        (
            evidence.active_alerts > 0,
            evidence.warning_alerts > 0,
            evidence.recent_anomalies > 0,
            evidence.max_pressure >= 75,
            evidence.pvc_risk_count > 0,
            evidence.workload_issue_count > 0,
            evidence.forecast_risk_count > 0,
            evidence.forecast_is_medium,
        )
    )
    if not evidence.evidence_available:
        return _signal('Unknown', 'unknown', 'gray', 'Committed analytics evidence is not available for this cluster.')
    if critical:
        return _signal(
            'Critical', 'critical', 'red', 'Critical signal detected from alerts, resource pressure, or forecast risk.'
        )
    if warning:
        return _signal(
            'Warning', 'warning', 'amber', 'Operational warning detected. Review the prioritized recommendations.'
        )
    if not evidence.evidence_complete:
        description = (
            f'No current risk is visible in available evidence, but only '
            f'{evidence.current_dataset_count}/{evidence.expected_dataset_count} datasets are current.'
        )
        return _signal('Limited', 'warning', 'amber', description)
    return _signal(
        'Healthy',
        'normal',
        'green',
        'All expected committed datasets are current and show no critical operational signal.',
    )


def _capacity_risk(evidence: HealthEvidence) -> dict[str, str]:
    availability = (
        evidence.resource_available,
        evidence.capacity_available,
        evidence.storage_available,
        evidence.workload_available,
        evidence.forecast_available,
    )
    if not any(availability):
        return _signal('Unknown', 'unknown', 'gray', 'Capacity evidence is not available yet.')
    score = _capacity_risk_score(evidence)
    if score >= 4:
        return _signal('High', 'critical', 'red', 'Multiple capacity indicators require immediate review.')
    if score > 0:
        return _signal('Medium', 'warning', 'amber', 'Capacity risk is present across one or more available signals.')
    if not all(availability):
        return _signal(
            'Limited',
            'warning',
            'amber',
            'Available capacity signals show no risk, but cross-domain evidence is incomplete.',
        )
    return _signal('Low', 'normal', 'green', 'Capacity risk is currently low across all expected signals.')


def _capacity_risk_score(evidence: HealthEvidence) -> int:
    return sum(
        (
            int(evidence.resource_available and evidence.max_pressure >= 75),
            int(evidence.resource_available and evidence.max_pressure >= 90),
            int(evidence.storage_available and evidence.pvc_risk_count > 0),
            int(evidence.forecast_available and (evidence.forecast_risk_count > 0 or evidence.forecast_is_medium)),
            2 * int(evidence.forecast_is_high),
            int(evidence.workload_available and evidence.workload_issue_count > 0),
            int(evidence.workload_available and evidence.workload_issue_count >= 10),
        )
    )


def _active_alerts(evidence: HealthEvidence) -> dict[str, str | int]:
    if not evidence.alerts_available:
        return _signal('N/A', 'unknown', 'gray', 'Committed alert evidence is not available yet.')
    if evidence.active_alerts > 0:
        status = 'critical' if evidence.critical_alerts else 'warning'
        tone = 'red' if evidence.critical_alerts else 'amber'
        description = (
            f'{evidence.firing_alerts} firing and {evidence.pending_alerts} pending alert(s). '
            f'{evidence.critical_alerts} critical, {evidence.warning_alerts} warning.'
        )
        return _signal(evidence.active_alerts, status, tone, description)
    if evidence.recent_anomalies > 0:
        return _signal(
            0,
            'warning',
            'amber',
            f'No firing alerts, but {evidence.recent_anomalies} anomaly candidate(s) detected.',
        )
    return _signal(0, 'normal', 'green', 'No firing or pending alert detected in the committed dataset.')


def _forecast_risk(evidence: HealthEvidence) -> dict[str, str]:
    if not evidence.forecast_available:
        return _signal('Unknown', 'unknown', 'gray', 'Committed forecast evidence is not available yet.')
    if evidence.forecast_risk_count > 0 or evidence.forecast_is_medium or evidence.forecast_is_high:
        projected_raw = evidence.forecast.get('highest_projected_percent')
        projected = f'{_as_int(projected_raw)}%' if projected_raw is not None else 'an unavailable percentage'
        description = (
            f'{evidence.forecast.get("highest_projected_resource", "N/A")} projected at {projected} '
            f'within {evidence.forecast.get("forecast_horizon", "forecast window")}.'
        )
        status = 'critical' if evidence.forecast_is_high else 'warning'
        tone = 'red' if evidence.forecast_is_high else 'purple'
        return _signal(evidence.forecast_risk_value, status, tone, description)
    return _signal('Low', 'normal', 'green', 'No forecast risk detected in the committed dataset.')


def _top_risk_namespace(evidence: HealthEvidence) -> dict[str, str]:
    if not evidence.storage_available:
        return _signal('-', 'unknown', 'gray', 'Committed namespace storage evidence is not available yet.')
    namespace = str(evidence.storage.get('top_namespace') or '-')
    if namespace != '-' and evidence.pvc_risk_count > 0:
        return _signal(
            namespace,
            'warning',
            'blue',
            f'{evidence.pvc_risk_count} PVC risk item(s) detected. Highest storage namespace signal.',
        )
    if namespace != '-':
        return _signal(namespace, 'normal', 'blue', 'Highest storage usage namespace.')
    return _signal('-', 'unknown', 'gray', 'Namespace risk data is not present in the committed storage dataset.')


def _resource_pressure(evidence: HealthEvidence) -> dict[str, str]:
    if not evidence.highest_pressure_resource:
        return {}
    meta = classify_percent(evidence.max_pressure)
    return {
        'value': meta['label'],
        'status': meta['status'],
        'tone': meta['tone'],
        'description': (
            f'{evidence.highest_pressure_resource} is the highest signal at {int(round(evidence.max_pressure))}%.'
        ),
    }


def _highest_resource_pressure(resource: dict[str, Any], available: bool) -> tuple[str | None, float]:
    if not available:
        return None, 0.0
    pressures = {
        label: value
        for label, key in [('CPU', 'cpu'), ('Memory', 'memory'), ('Storage', 'storage'), ('Pods', 'pods')]
        if (value := _nested_percent(resource, key)) is not None
    }
    if not pressures:
        return None, 0.0
    highest = max(pressures, key=lambda label: pressures[label])
    return highest, pressures[highest]


def _alert_values(alerts: dict[str, Any], available: bool) -> dict[str, int]:
    keys = {
        'firing': 'firing_alerts',
        'pending': 'pending_alerts',
        'critical': 'critical_alerts',
        'warning': 'warning_alerts',
        'anomalies': 'recent_anomalies',
    }
    return {name: _as_int(alerts.get(key)) if available else 0 for name, key in keys.items()}


def _forecast_values(forecast: dict[str, Any], available: bool) -> dict[str, Any]:
    value = str(forecast.get('forecast_risk', 'Unknown'))
    normalized = value.lower()
    return {
        'count': _as_int(forecast.get('risk_count')) if available else 0,
        'value': value,
        'high': available and normalized in {'high', 'critical'},
        'medium': available and normalized in {'medium', 'warning'},
    }


def _workload_issue_count(workload: dict[str, Any]) -> int:
    return sum(
        _as_int(workload.get(key))
        for key in (
            'missing_cpu_requests',
            'missing_memory_requests',
            'memory_limits_missing',
            'over_provisioned',
            'under_provisioned',
        )
    )


def _nested_percent(payload: dict[str, Any], key: str) -> float | None:
    item = payload.get(key)
    if not isinstance(item, dict) or item.get('percent') is None:
        return None
    return _as_float(item.get('percent'))


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    return int(round(_as_float(value)))


def _signal(value: Any, status: str, tone: str, description: str) -> dict[str, Any]:
    return {'value': value, 'status': status, 'tone': tone, 'description': description}
