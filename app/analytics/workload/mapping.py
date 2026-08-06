from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.analytics.common.base_service import safe_percent, safe_round
from app.analytics.common.coercion import safe_float
from app.analytics.workload.formatting import (
    format_cpu_core,
    format_decimal,
    format_memory_gib,
)


@dataclass(frozen=True)
class WorkloadMappingEvidence:
    cpu_requests: dict[str, float]
    cpu_limits: dict[str, float]
    cpu_current: dict[str, float]
    cpu_peak: dict[str, float]
    memory_requests: dict[str, float]
    memory_limits: dict[str, float]
    memory_current: dict[str, float]
    memory_peak: dict[str, float]
    owner_map: dict[str, dict[str, str]]
    qos_map: dict[str, str]


def parse_pod_owner_map(result: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for item in result:
        metric = item.get('metric', {})
        if not isinstance(metric, dict):
            continue
        namespace = metric.get('namespace', '')
        pod = metric.get('pod', '')
        owner_kind = metric.get('owner_kind', 'Pod')
        owner_name = metric.get('owner_name', pod)
        if not isinstance(namespace, str) or not namespace or not isinstance(pod, str) or not pod:
            continue
        owner_kind = owner_kind if isinstance(owner_kind, str) and owner_kind else 'Pod'
        owner_name = owner_name if isinstance(owner_name, str) and owner_name else pod
        if owner_kind == 'ReplicaSet':
            owner_kind = 'Deployment'
            owner_name = re.sub(r'-[a-z0-9]{8,10}$', '', owner_name)
        values[f'{namespace}/{pod}'] = {'kind': owner_kind, 'name': owner_name}
    return values


def parse_pod_qos_map(result: list[dict[str, Any]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in result:
        metric = item.get('metric', {})
        if not isinstance(metric, dict):
            continue
        namespace = metric.get('namespace', '')
        pod = metric.get('pod', '')
        qos_class = metric.get('qos_class', '')
        if all(isinstance(value, str) and value for value in (namespace, pod, qos_class)):
            values[f'{namespace}/{pod}'] = qos_class
    return values


def infer_workload_owner(pod_name: str) -> dict[str, str]:
    deployment = re.match(r'^(?P<name>.+)-[a-z0-9]{8,10}-[a-z0-9]{5}$', pod_name)
    if deployment:
        return {'kind': 'Workload', 'name': deployment.group('name')}
    stateful = re.match(r'^(?P<name>.+)-\d+$', pod_name)
    if stateful:
        return {'kind': 'Workload', 'name': stateful.group('name')}
    return {'kind': 'Workload', 'name': pod_name}


def request_coverage(cpu_observed: int, memory_observed: int, pod_count: int) -> dict[str, Any]:
    complete = min(cpu_observed, memory_observed)
    if pod_count <= 0:
        return {'label': 'Unknown', 'tone': 'unknown', 'observed': 0, 'total': 0}
    if cpu_observed == pod_count and memory_observed == pod_count:
        return {'label': 'Complete', 'tone': 'normal', 'observed': pod_count, 'total': pod_count}
    if cpu_observed == 0 and memory_observed == 0:
        return {'label': 'Missing', 'tone': 'critical', 'observed': 0, 'total': pod_count}
    return {'label': 'Partial', 'tone': 'warning', 'observed': complete, 'total': pod_count}


def limit_coverage(cpu_observed: int, memory_observed: int, pod_count: int) -> dict[str, Any]:
    if pod_count <= 0:
        return {'label': 'Unknown', 'tone': 'unknown', 'observed': 0, 'total': 0}
    if cpu_observed == pod_count and memory_observed == pod_count:
        return {'label': 'Complete', 'tone': 'normal', 'observed': pod_count, 'total': pod_count}
    if cpu_observed == 0 and memory_observed == 0:
        return {'label': 'Limits Unset', 'tone': 'warning', 'observed': 0, 'total': pod_count}
    if memory_observed < pod_count and cpu_observed == pod_count:
        return {'label': 'Memory Limit Missing', 'tone': 'warning', 'observed': memory_observed, 'total': pod_count}
    if cpu_observed < pod_count and memory_observed == pod_count:
        return {'label': 'CPU Limit Unset', 'tone': 'info', 'observed': cpu_observed, 'total': pod_count}
    return {'label': 'Partial', 'tone': 'warning', 'observed': min(cpu_observed, memory_observed), 'total': pod_count}


def resource_configuration(request: dict[str, Any], limit: dict[str, Any]) -> dict[str, str]:
    request_label = request.get('label', 'Unknown')
    limit_label = limit.get('label', 'Unknown')
    if request_label == 'Missing':
        return {'label': 'Requests Missing', 'tone': 'critical'}
    if request_label == 'Partial':
        return {'label': 'Requests Partial', 'tone': 'warning'}
    if request_label == 'Unknown':
        return {'label': 'Unknown', 'tone': 'unknown'}
    return {
        'Memory Limit Missing': {'label': 'Memory Limit Missing', 'tone': 'warning'},
        'Limits Unset': {'label': 'Limits Unset', 'tone': 'warning'},
        'CPU Limit Unset': {'label': 'CPU Limit Unset', 'tone': 'info'},
        'Partial': {'label': 'Limits Partial', 'tone': 'warning'},
    }.get(limit_label, {'label': 'Complete', 'tone': 'normal'})


def workload_qos(distribution: dict[str, int]) -> dict[str, str]:
    if not distribution:
        return {'label': 'Unknown'}
    if len(distribution) > 1:
        return {'label': 'Mixed'}
    return {'label': next(iter(distribution))}


def metrics_coverage(
    pod_count: int,
    cpu_current_observed: int,
    memory_current_observed: int,
    cpu_peak_observed: int,
    memory_peak_observed: int,
) -> dict[str, Any]:
    observed = (cpu_current_observed, memory_current_observed, cpu_peak_observed, memory_peak_observed)
    complete = min(observed)
    maximum = max(observed)
    if pod_count <= 0 or maximum == 0:
        return {
            'label': 'Unavailable', 'tone': 'unknown', 'observed': 0,
            'total': max(pod_count, 0),
            'description': 'No complete runtime and selected-window observations are available.',
        }
    if complete == pod_count:
        return {
            'label': 'Complete', 'tone': 'normal', 'observed': pod_count,
            'total': pod_count, 'description': f'{pod_count} of {pod_count} Pods',
        }
    return {
        'label': 'Partial', 'tone': 'warning', 'observed': complete,
        'total': pod_count, 'description': f'{complete} of {pod_count} Pods',
    }


def workload_recommendation(
    cpu_current_percent: float,
    cpu_peak_percent: float,
    memory_current_percent: float,
    memory_peak_percent: float,
    request_label: str,
    limit_label: str,
    metrics_label: str,
) -> str:
    if request_label == 'Missing':
        return 'Set CPU and memory requests'
    if request_label == 'Partial':
        return 'Complete CPU and memory requests'
    if limit_label == 'Memory Limit Missing':
        return 'Set memory limits according to workload policy'
    if limit_label == 'Limits Unset':
        return 'Review memory limit policy and confirm CPU limit intent'
    if limit_label == 'CPU Limit Unset':
        return 'Confirm the intentional CPU limit policy'
    if metrics_label != 'Complete':
        return 'Defer right-sizing until metrics coverage is complete'
    cpu_pressure = max(cpu_current_percent, cpu_peak_percent)
    memory_pressure = max(memory_current_percent, memory_peak_percent)
    if memory_pressure >= 90:
        return 'Increase memory request after validating selected-window demand'
    if cpu_pressure >= 90:
        return 'Increase CPU request after validating selected-window demand'
    if max(cpu_current_percent, cpu_peak_percent, memory_current_percent, memory_peak_percent) < 30:
        return 'Reduce CPU and memory requests after owner validation'
    if max(cpu_current_percent, cpu_peak_percent) < 30:
        return 'Reduce CPU request after owner validation'
    if max(memory_current_percent, memory_peak_percent) < 30:
        return 'Reduce memory request after owner validation'
    return 'No right-sizing action needed'


def workload_risk(request_label: str, limit_label: str, metrics_label: str, recommendation: str) -> dict[str, str]:
    recommendation_lower = recommendation.lower()
    if request_label in {'Missing', 'Partial'} or 'increase' in recommendation_lower:
        return {'label': 'High', 'tone': 'critical'}
    if limit_label in {'Memory Limit Missing', 'Limits Unset', 'Partial'}:
        return {'label': 'Medium', 'tone': 'warning'}
    if metrics_label == 'Unavailable':
        return {'label': 'Unknown', 'tone': 'unknown'}
    if metrics_label == 'Partial' or 'reduce' in recommendation_lower:
        return {'label': 'Medium', 'tone': 'warning'}
    return {'label': 'Low', 'tone': 'normal'}


def build_workload_scope_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    evidence_available = total > 0
    request_complete = sum(
        1 for row in rows if row.get('request_coverage', {}).get('label') == 'Complete'
    )
    coverage = safe_round(safe_percent(request_complete, total), 2)
    return {
        'scope_evidence_available': evidence_available,
        'scope_total': total,
        'scope_request_complete': request_complete,
        'scope_request_coverage_percent': coverage,
        'scope_request_coverage_display': f'{coverage:.2f}' if evidence_available else 'N/A',
        'scope_best_effort_count': sum(
            1 for row in rows if row.get('qos', {}).get('label') == 'BestEffort'
        ),
        'scope_high_risk_count': sum(
            1 for row in rows if row.get('risk', {}).get('label') in {'High', 'Critical'}
        ),
        'scope_complete_evidence_count': sum(
            1 for row in rows if row.get('metrics_coverage', {}).get('label') == 'Complete'
        ),
    }


def build_workload_mapping_payload(
    evidence: WorkloadMappingEvidence,
    selected_namespace: str = '',
) -> dict[str, Any]:
    cpu_requests = evidence.cpu_requests
    cpu_limits = evidence.cpu_limits
    cpu_current = evidence.cpu_current
    cpu_peak = evidence.cpu_peak
    memory_requests = evidence.memory_requests
    memory_limits = evidence.memory_limits
    memory_current = evidence.memory_current
    memory_peak = evidence.memory_peak
    owner_map = evidence.owner_map
    qos_map = evidence.qos_map
    signal_maps = (
        cpu_requests, cpu_limits, cpu_current, cpu_peak,
        memory_requests, memory_limits, memory_current, memory_peak,
    )
    keys = set(owner_map) | set(qos_map)
    for values in signal_maps:
        keys.update(values)
    aggregates: dict[str, dict[str, Any]] = {}
    for key in sorted(keys):
        namespace, _, pod = key.partition('/')
        if not namespace or not pod or (selected_namespace and namespace != selected_namespace):
            continue
        owner = owner_map.get(key, infer_workload_owner(pod))
        identity = f'{namespace}/{owner["kind"]}/{owner["name"]}'
        aggregate = aggregates.setdefault(identity, _empty_aggregate(namespace, pod, owner))
        if pod not in aggregate['pods']:
            aggregate['pods'].append(pod)
            aggregate['replicas'] += 1
        _accumulate_signals(aggregate, key, signal_maps)
        qos = qos_map.get(key, 'Unknown')
        aggregate['qos_distribution'][qos] = aggregate['qos_distribution'].get(qos, 0) + 1
    rows = [_build_mapping_row(item) for item in aggregates.values()]
    rows.sort(key=lambda row: (_risk_weight(row['risk']['label']), row['namespace'], row['type'], row['workload']))
    return {
        'rows': rows,
        'scope_summary': build_workload_scope_summary(rows),
        'filters': {
            'configuration': sorted({row['configuration_status']['label'] for row in rows}),
            'qos': sorted({row['qos']['label'] for row in rows}),
            'risk': sorted({row['risk']['label'] for row in rows}),
        },
    }


def _empty_aggregate(namespace: str, pod: str, owner: dict[str, str]) -> dict[str, Any]:
    return {
        'workload': owner['name'], 'type': owner['kind'], 'namespace': namespace,
        'replicas': 0, 'pods': [], 'qos_distribution': {},
        **{name: 0.0 for name in (
            'cpu_request_raw', 'cpu_limit_raw', 'cpu_current_raw', 'cpu_peak_sum_raw',
            'memory_request_raw', 'memory_limit_raw', 'memory_current_raw', 'memory_peak_sum_raw',
        )},
        **{name: 0 for name in (
            'cpu_request_pods', 'cpu_limit_pods', 'cpu_current_pods', 'cpu_peak_pods',
            'memory_request_pods', 'memory_limit_pods', 'memory_current_pods', 'memory_peak_pods',
        )},
    }


def _accumulate_signals(aggregate: dict[str, Any], key: str, signal_maps: tuple[dict[str, float], ...]) -> None:
    fields = (
        ('cpu_request_raw', 'cpu_request_pods', True),
        ('cpu_limit_raw', 'cpu_limit_pods', True),
        ('cpu_current_raw', 'cpu_current_pods', False),
        ('cpu_peak_sum_raw', 'cpu_peak_pods', False),
        ('memory_request_raw', 'memory_request_pods', True),
        ('memory_limit_raw', 'memory_limit_pods', True),
        ('memory_current_raw', 'memory_current_pods', False),
        ('memory_peak_sum_raw', 'memory_peak_pods', False),
    )
    for values, (value_field, count_field, require_positive) in zip(signal_maps, fields, strict=True):
        if key not in values:
            continue
        value = safe_float(values.get(key))
        if require_positive and value <= 0:
            continue
        aggregate[value_field] += value
        aggregate[count_field] += 1


def _build_mapping_row(item: dict[str, Any]) -> dict[str, Any]:
    pod_count = item['replicas']
    requests = request_coverage(item['cpu_request_pods'], item['memory_request_pods'], pod_count)
    limits = limit_coverage(item['cpu_limit_pods'], item['memory_limit_pods'], pod_count)
    metrics = metrics_coverage(
        pod_count, item['cpu_current_pods'], item['memory_current_pods'],
        item['cpu_peak_pods'], item['memory_peak_pods'],
    )
    availability = {
        'cpu_current': item['cpu_current_pods'] == pod_count and item['cpu_request_raw'] > 0,
        'cpu_peak': item['cpu_peak_pods'] == pod_count and item['cpu_request_raw'] > 0,
        'memory_current': item['memory_current_pods'] == pod_count and item['memory_request_raw'] > 0,
        'memory_peak': item['memory_peak_pods'] == pod_count and item['memory_request_raw'] > 0,
    }
    percentages = {
        'cpu_current': _percent(item['cpu_current_raw'], item['cpu_request_raw'], availability['cpu_current']),
        'cpu_peak': _percent(item['cpu_peak_sum_raw'], item['cpu_request_raw'], availability['cpu_peak']),
        'memory_current': _percent(item['memory_current_raw'], item['memory_request_raw'], availability['memory_current']),
        'memory_peak': _percent(item['memory_peak_sum_raw'], item['memory_request_raw'], availability['memory_peak']),
    }
    recommendation = workload_recommendation(
        percentages['cpu_current'], percentages['cpu_peak'],
        percentages['memory_current'], percentages['memory_peak'],
        requests['label'], limits['label'], metrics['label'],
    )
    risk = workload_risk(requests['label'], limits['label'], metrics['label'], recommendation)
    return {
        'workload': item['workload'], 'type': item['type'], 'namespace': item['namespace'],
        'replicas': pod_count, 'request_coverage': requests, 'limit_coverage': limits,
        'configuration_status': resource_configuration(requests, limits),
        'metrics_coverage': metrics, 'qos': workload_qos(item['qos_distribution']),
        'risk': risk, 'recommendation': recommendation,
        **_raw_and_display_fields(item, availability, percentages),
        'detail': {'pods': sorted(item['pods']), 'qos_distribution': item['qos_distribution']},
    }


def _percent(value: float, denominator: float, available: bool) -> float:
    return safe_round(safe_percent(value, denominator), 2) if available else 0.0


def _raw_and_display_fields(
    item: dict[str, Any],
    availability: dict[str, bool],
    percentages: dict[str, float],
) -> dict[str, Any]:
    raw_names = (
        'cpu_request_raw', 'cpu_limit_raw', 'cpu_current_raw', 'cpu_peak_sum_raw',
        'memory_request_raw', 'memory_limit_raw', 'memory_current_raw', 'memory_peak_sum_raw',
    )
    return {
        **{name: item[name] for name in raw_names},
        'cpu_request': format_cpu_core(item['cpu_request_raw']) if item['cpu_request_pods'] else 'Unset',
        'cpu_limit': format_cpu_core(item['cpu_limit_raw']) if item['cpu_limit_pods'] else 'Unset',
        'cpu_current': format_cpu_core(item['cpu_current_raw']) if item['cpu_current_pods'] else 'N/A',
        'cpu_peak_sum': format_cpu_core(item['cpu_peak_sum_raw']) if item['cpu_peak_pods'] else 'N/A',
        'memory_request': format_memory_gib(item['memory_request_raw']) if item['memory_request_pods'] else 'Unset',
        'memory_limit': format_memory_gib(item['memory_limit_raw']) if item['memory_limit_pods'] else 'Unset',
        'memory_current': format_memory_gib(item['memory_current_raw']) if item['memory_current_pods'] else 'N/A',
        'memory_peak_sum': format_memory_gib(item['memory_peak_sum_raw']) if item['memory_peak_pods'] else 'N/A',
        'cpu_request_utilization_available': availability['cpu_current'],
        'cpu_peak_request_utilization_available': availability['cpu_peak'],
        'memory_request_utilization_available': availability['memory_current'],
        'memory_peak_request_utilization_available': availability['memory_peak'],
        'cpu_request_utilization': percentages['cpu_current'],
        'cpu_request_utilization_display': format_decimal(percentages['cpu_current']) if availability['cpu_current'] else 'N/A',
        'cpu_peak_request_utilization': percentages['cpu_peak'],
        'cpu_peak_request_utilization_display': format_decimal(percentages['cpu_peak']) if availability['cpu_peak'] else 'N/A',
        'memory_request_utilization': percentages['memory_current'],
        'memory_request_utilization_display': format_decimal(percentages['memory_current']) if availability['memory_current'] else 'N/A',
        'memory_peak_request_utilization': percentages['memory_peak'],
        'memory_peak_request_utilization_display': format_decimal(percentages['memory_peak']) if availability['memory_peak'] else 'N/A',
    }


def _risk_weight(risk: str) -> int:
    return {'Critical': 0, 'High': 0, 'Medium': 1, 'Low': 2}.get(risk, 3)
