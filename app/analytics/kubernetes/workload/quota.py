from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.analytics.kubernetes.common.base_service import raw_percent, safe_percent, safe_round
from app.analytics.kubernetes.workload.formatting import (
    REQUIRED_QUOTA_KEYS,
    build_resource_quota_items,
    format_count,
    format_cpu_core,
    format_decimal,
    format_memory_gib,
    resource_quota_label,
)
from app.analytics.shared.coercion import safe_float

QuotaMap = dict[str, dict[str, dict[str, float]]]


def parse_resource_quota_map(
    result: list[dict[str, Any]],
    extract_value: Callable[[dict[str, Any]], float],
) -> QuotaMap:
    values: QuotaMap = {}
    for item in result:
        metric = item.get('metric', {})
        if not isinstance(metric, dict):
            continue
        namespace = metric.get('namespace', '')
        quota_name = metric.get('resourcequota') or metric.get('quota') or ''
        resource = metric.get('resource', '')
        if not all(isinstance(value, str) and value for value in (namespace, quota_name, resource)):
            continue
        current = values.setdefault(namespace, {}).setdefault(quota_name, {}).get(resource, 0.0)
        values[namespace][quota_name][resource] = max(current, extract_value(item))
    return values


def build_tenant_scope_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_namespaces = len(rows)
    evidence_available = total_namespaces > 0
    covered_namespaces = sum(1 for row in rows if row.get('quota_status', {}).get('label') in {'Complete', 'Partial'})
    near_limit_count = sum(
        1 for row in rows if row.get('quota_pressure_available') and safe_float(row.get('quota_usage_percent')) >= 75
    )
    efficiency_risk_count = sum(
        1
        for row in rows
        if row.get('quota_pressure_available')
        and row.get('runtime_demand_available')
        and safe_float(row.get('quota_usage_percent')) >= 75
        and safe_float(row.get('actual_usage_percent')) < 40
    )
    coverage = safe_percent(covered_namespaces, total_namespaces)
    coverage_display = format_decimal(coverage) if evidence_available else 'N/A'
    return {
        'scope_evidence_available': evidence_available,
        'scope_total': total_namespaces,
        'scope_covered': covered_namespaces,
        'scope_quota_coverage_percent': safe_round(coverage, 2),
        'scope_quota_coverage_display': coverage_display,
        'scope_near_limit_count': near_limit_count,
        'scope_efficiency_risk_count': efficiency_risk_count,
        'summary_cards': [
            {
                'label': 'Namespaces',
                'value': total_namespaces if evidence_available else 'N/A',
                'caption': 'Top-Level Active Scope' if evidence_available else 'No Committed Namespace Evidence',
                'icon': 'network',
            },
            {
                'label': 'Quota Coverage',
                'value': f'{coverage_display}%' if evidence_available else 'N/A',
                'caption': (
                    f'{covered_namespaces} of {total_namespaces} Namespaces'
                    if evidence_available
                    else 'Coverage Evidence Unavailable'
                ),
                'icon': 'shield-check',
            },
            {
                'label': 'Quota Near Limit',
                'value': near_limit_count if evidence_available else 'N/A',
                'caption': '75% or Higher' if evidence_available else 'Pressure Evidence Unavailable',
                'icon': 'triangle-alert',
            },
            {
                'label': 'Allocation Efficiency Risk',
                'value': efficiency_risk_count if evidence_available else 'N/A',
                'caption': (
                    'High Allocation, Low Runtime Demand' if evidence_available else 'Runtime Evidence Unavailable'
                ),
                'icon': 'activity',
            },
        ],
    }


def get_effective_quota_resource(
    hard_objects: dict[str, dict[str, float]],
    used_objects: dict[str, dict[str, float]],
    resource: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for quota_name, hard_values in hard_objects.items():
        if resource not in hard_values:
            continue
        hard_value = safe_float(hard_values.get(resource))
        used_available = resource in used_objects.get(quota_name, {})
        used_value = safe_float(used_objects.get(quota_name, {}).get(resource))
        percent = safe_round(raw_percent(used_value, hard_value), 2) if used_available and hard_value > 0 else 0.0
        candidates.append(
            {
                'quota': quota_name,
                'hard': hard_value,
                'used': used_value,
                'used_available': used_available,
                'percent': percent,
            }
        )
    if not candidates:
        return {
            'quota': '',
            'hard': 0.0,
            'used': 0.0,
            'configured': False,
            'used_available': False,
            'percent': 0.0,
        }
    observed = [item for item in candidates if item['used_available'] and item['hard'] > 0]
    selected = (
        max(observed, key=lambda item: item['percent'])
        if observed
        else min(candidates, key=lambda item: item['hard'] if item['hard'] > 0 else float('inf'))
    )
    return {**selected, 'configured': True}


def tenant_quota_status(configured_keys: set[str], missing_keys: list[str]) -> dict[str, str]:
    if not configured_keys:
        return {'label': 'Missing', 'tone': 'warning'}
    if missing_keys:
        return {'label': 'Partial', 'tone': 'warning'}
    return {'label': 'Complete', 'tone': 'normal'}


def tenant_risk(
    quota_status: str,
    quota_usage_percent: float,
    actual_usage_percent: float,
    *,
    quota_pressure_available: bool,
    runtime_demand_available: bool,
) -> dict[str, str]:
    if quota_status == 'Missing':
        return {'label': 'Critical', 'tone': 'critical'}
    if quota_pressure_available and quota_usage_percent >= 90:
        return {'label': 'Critical', 'tone': 'critical'}
    if (
        quota_pressure_available
        and runtime_demand_available
        and quota_usage_percent >= 75
        and actual_usage_percent < 40
    ):
        return {'label': 'Medium', 'tone': 'warning'}
    if quota_pressure_available and quota_usage_percent >= 75:
        return {'label': 'High', 'tone': 'critical'}
    if quota_status == 'Partial':
        return {'label': 'Medium', 'tone': 'warning'}
    if not quota_pressure_available or not runtime_demand_available:
        return {'label': 'Unknown', 'tone': 'unknown'}
    return {'label': 'Low', 'tone': 'normal'}


def tenant_recommendation(
    quota_status: str,
    missing_keys: list[str],
    quota_usage_percent: float,
    actual_usage_percent: float,
    *,
    quota_pressure_available: bool,
    runtime_demand_available: bool,
) -> str:
    if quota_status == 'Missing':
        return 'Create ResourceQuota'
    if missing_keys:
        return 'Add missing quota keys'
    if not quota_pressure_available:
        return 'Restore quota usage evidence before changing boundaries'
    if quota_usage_percent >= 90:
        if runtime_demand_available and actual_usage_percent < 50:
            return 'Right-size workload requests before increasing quota'
        return 'Review allocation or increase quota'
    if quota_usage_percent >= 75 and runtime_demand_available and actual_usage_percent < 40:
        return 'Right-size requests and limits'
    if quota_usage_percent >= 75:
        return 'Monitor quota and review allocation'
    if not runtime_demand_available:
        return 'Restore runtime demand evidence'
    return 'Quota looks healthy'


def _pressure_signal(
    hard_objects: dict[str, dict[str, float]],
    used_objects: dict[str, dict[str, float]],
) -> tuple[float, str, str, bool]:
    signals: list[tuple[float, str, str]] = []
    for quota_name, hard_values in hard_objects.items():
        used_values = used_objects.get(quota_name, {})
        for key in REQUIRED_QUOTA_KEYS:
            denominator = safe_float(hard_values.get(key))
            if denominator <= 0 or key not in used_values:
                continue
            signals.append(
                (raw_percent(safe_float(used_values.get(key)), denominator), resource_quota_label(key), quota_name)
            )
    if not signals:
        return 0.0, 'Unavailable', '', False
    percent, resource, quota_name = max(signals, key=lambda item: item[0])
    return safe_round(percent, 2), resource, quota_name, True


def _runtime_signal(
    namespace: str,
    hard_objects: dict[str, dict[str, float]],
    cpu_actual: dict[str, float],
    memory_actual: dict[str, float],
    pod_actual: dict[str, float],
) -> tuple[float, str, str, bool]:
    signals: list[tuple[float, str, str]] = []
    actual_by_resource = (
        ('limits.cpu', 'CPU', cpu_actual),
        ('limits.memory', 'Memory', memory_actual),
        ('pods', 'Pods', pod_actual),
    )
    for quota_key, label, actual_values in actual_by_resource:
        if namespace not in actual_values:
            continue
        boundaries = [
            (safe_float(values.get(quota_key)), quota_name)
            for quota_name, values in hard_objects.items()
            if quota_key in values and safe_float(values.get(quota_key)) > 0
        ]
        if not boundaries:
            continue
        hard_value, quota_name = min(boundaries, key=lambda item: item[0])
        signals.append((raw_percent(safe_float(actual_values.get(namespace)), hard_value), label, quota_name))
    if not signals:
        return 0.0, 'Unavailable', '', False
    percent, resource, quota_name = max(signals, key=lambda item: item[0])
    return safe_round(percent, 2), resource, quota_name, True


def build_tenant_quota_summary(
    *,
    active_namespaces: dict[str, float],
    hard: QuotaMap,
    used: QuotaMap,
    cpu_actual: dict[str, float],
    memory_actual: dict[str, float],
    pod_actual: dict[str, float],
    selected_namespace: str = '',
) -> dict[str, Any]:
    namespace_names = (
        set(active_namespaces) | set(hard) | set(used) | set(cpu_actual) | set(memory_actual) | set(pod_actual)
    )
    rows = [
        _build_tenant_row(
            namespace,
            hard.get(namespace, {}),
            used.get(namespace, {}),
            cpu_actual,
            memory_actual,
            pod_actual,
        )
        for namespace in sorted(namespace_names)
        if not selected_namespace or namespace == selected_namespace
    ]
    return {**build_tenant_scope_summary(rows), 'rows': rows}


def _build_tenant_row(
    namespace: str,
    hard_objects: dict[str, dict[str, float]],
    used_objects: dict[str, dict[str, float]],
    cpu_actual: dict[str, float],
    memory_actual: dict[str, float],
    pod_actual: dict[str, float],
) -> dict[str, Any]:
    configured_keys = {key for values in hard_objects.values() for key in values}
    missing_keys = [key for key in REQUIRED_QUOTA_KEYS if key not in configured_keys]
    quota_status = tenant_quota_status(configured_keys, missing_keys)
    quota_percent, pressure_resource, pressure_object, quota_available = _pressure_signal(hard_objects, used_objects)
    resources = {key: get_effective_quota_resource(hard_objects, used_objects, key) for key in REQUIRED_QUOTA_KEYS}
    runtime_percent, runtime_resource, runtime_object, runtime_available = _runtime_signal(
        namespace,
        hard_objects,
        cpu_actual,
        memory_actual,
        pod_actual,
    )
    risk = tenant_risk(
        quota_status['label'],
        quota_percent,
        runtime_percent,
        quota_pressure_available=quota_available,
        runtime_demand_available=runtime_available,
    )
    recommendation = tenant_recommendation(
        quota_status['label'],
        missing_keys,
        quota_percent,
        runtime_percent,
        quota_pressure_available=quota_available,
        runtime_demand_available=runtime_available,
    )
    return _tenant_row_payload(
        namespace=namespace,
        hard_objects=hard_objects,
        used_objects=used_objects,
        resources=resources,
        cpu_actual=cpu_actual,
        memory_actual=memory_actual,
        pod_actual=pod_actual,
        quota_status=quota_status,
        missing_keys=missing_keys,
        quota_percent=quota_percent,
        pressure_resource=pressure_resource,
        pressure_object=pressure_object,
        quota_available=quota_available,
        runtime_percent=runtime_percent,
        runtime_resource=runtime_resource,
        runtime_object=runtime_object,
        runtime_available=runtime_available,
        risk=risk,
        recommendation=recommendation,
    )


def _tenant_row_payload(**data: Any) -> dict[str, Any]:
    namespace = str(data['namespace'])
    resources = data['resources']
    cpu_actual = data['cpu_actual']
    memory_actual = data['memory_actual']
    pod_actual = data['pod_actual']
    cpu_value = safe_float(cpu_actual.get(namespace))
    memory_value = safe_float(memory_actual.get(namespace))
    pod_value = safe_float(pod_actual.get(namespace))
    return {
        'namespace': namespace,
        'quota_status': data['quota_status'],
        'quota_object_count': len(data['hard_objects']),
        'quota_objects': [
            {
                'name': name,
                'hard_items': build_resource_quota_items(hard_values),
                'used_items': build_resource_quota_items(data['used_objects'].get(name, {})),
            }
            for name, hard_values in sorted(data['hard_objects'].items())
        ],
        'quota_pressure_available': data['quota_available'],
        'quota_pressure_resource': data['pressure_resource'],
        'quota_pressure_object': data['pressure_object'],
        'quota_usage_percent': data['quota_percent'],
        'quota_usage_percent_display': format_decimal(data['quota_percent']) if data['quota_available'] else 'N/A',
        'runtime_demand_available': data['runtime_available'],
        'runtime_demand_resource': data['runtime_resource'],
        'runtime_demand_object': data['runtime_object'],
        'actual_usage_percent': data['runtime_percent'],
        'actual_usage_percent_display': format_decimal(data['runtime_percent']) if data['runtime_available'] else 'N/A',
        'risk': data['risk'],
        'recommendation': data['recommendation'],
        'missing_keys': data['missing_keys'],
        'missing_key_labels': [resource_quota_label(key) for key in data['missing_keys']],
        'hard': {key: resources[key]['hard'] for key in REQUIRED_QUOTA_KEYS},
        'used': {key: resources[key]['used'] for key in REQUIRED_QUOTA_KEYS},
        'actual': {
            'cpu': format_cpu_core(cpu_value) if namespace in cpu_actual else 'N/A',
            'memory': format_memory_gib(memory_value) if namespace in memory_actual else 'N/A',
            'pods': format_count(pod_value) if namespace in pod_actual else 'N/A',
        },
        **_tenant_cpu_memory_fields(namespace, resources, cpu_actual, memory_actual),
        'workloads': format_count(pod_value) if namespace in pod_actual else 'N/A',
    }


def _tenant_cpu_memory_fields(
    namespace: str,
    resources: dict[str, dict[str, Any]],
    cpu_actual: dict[str, float],
    memory_actual: dict[str, float],
) -> dict[str, Any]:
    cpu_value = safe_float(cpu_actual.get(namespace))
    memory_value = safe_float(memory_actual.get(namespace))
    cpu_limit = resources['limits.cpu']
    cpu_request = resources['requests.cpu']
    memory_limit = resources['limits.memory']
    memory_request = resources['requests.memory']
    return {
        'cpu_quota': format_cpu_core(cpu_limit['hard']) if cpu_limit['configured'] else 'N/A',
        'cpu_requested': format_cpu_core(cpu_request['used']) if cpu_request['used_available'] else 'N/A',
        'cpu_limited': format_cpu_core(cpu_limit['used']) if cpu_limit['used_available'] else 'N/A',
        'cpu_actual': format_cpu_core(cpu_value) if namespace in cpu_actual else 'N/A',
        'cpu_actual_available': namespace in cpu_actual,
        'cpu_requested_percent': cpu_request['percent'],
        'cpu_limited_percent': cpu_limit['percent'],
        'cpu_actual_percent': safe_round(raw_percent(cpu_value, cpu_limit['hard']), 2)
        if namespace in cpu_actual and cpu_limit['hard'] > 0
        else 0.0,
        'memory_quota': format_memory_gib(memory_limit['hard']) if memory_limit['configured'] else 'N/A',
        'memory_requested': format_memory_gib(memory_request['used']) if memory_request['used_available'] else 'N/A',
        'memory_limited': format_memory_gib(memory_limit['used']) if memory_limit['used_available'] else 'N/A',
        'memory_actual': format_memory_gib(memory_value) if namespace in memory_actual else 'N/A',
        'memory_actual_available': namespace in memory_actual,
        'memory_requested_percent': memory_request['percent'],
        'memory_limited_percent': memory_limit['percent'],
        'memory_actual_percent': safe_round(raw_percent(memory_value, memory_limit['hard']), 2)
        if namespace in memory_actual and memory_limit['hard'] > 0
        else 0.0,
    }
