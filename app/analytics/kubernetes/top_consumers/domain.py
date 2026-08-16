from __future__ import annotations

from dataclasses import fields
from typing import Any, TypeGuard

from app.analytics.kubernetes.top_consumers.contracts import (
    RESOURCE_LABELS,
    RISK_RANK,
    TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION,
)
from app.analytics.kubernetes.top_consumers.evidence import ScalarEvidence, TopConsumersEvidence, VectorEvidence
from app.analytics.kubernetes.top_consumers.rows import (
    build_compute_rows,
    build_owner_map,
    build_pod_rows,
    build_pvc_rows,
    format_bytes,
    format_cpu,
    pvc_key,
    semantic_state,
    vector_value_map,
)
from app.analytics.shared.coercion import safe_float, safe_int


def build_top_consumers_payload(
    *,
    evidence: TopConsumersEvidence,
    selected_namespace: str,
) -> dict[str, Any]:
    owner_map = build_owner_map(evidence.pod_owners)
    scope = build_scope(evidence)
    cpu_rows = build_compute_rows(
        usage=evidence.cpu_usage,
        requests=evidence.cpu_requests,
        limits=evidence.cpu_limits,
        owner_map=owner_map,
        resource_type='cpu',
        scope_total=evidence.cpu_total,
    )
    memory_rows = build_compute_rows(
        usage=evidence.memory_usage,
        requests=evidence.memory_requests,
        limits=evidence.memory_limits,
        owner_map=owner_map,
        resource_type='memory',
        scope_total=evidence.memory_total,
    )
    pod_rows = build_pod_rows(
        usage=evidence.pod_usage,
        scope_total=evidence.pod_total,
        capacity=evidence.pod_capacity,
    )
    pvc_rows = build_pvc_rows(
        usage=evidence.pvc_usage,
        capacity=evidence.pvc_capacity,
        scope_total=evidence.pvc_total,
    )
    rows_by_resource = {
        'cpu': cpu_rows,
        'memory': memory_rows,
        'pods': pod_rows,
        'pvc': pvc_rows,
    }
    all_rows = cpu_rows + memory_rows + pod_rows + pvc_rows
    coverage = build_multi_resource_coverage(
        evidence=evidence,
        rows_by_resource=rows_by_resource,
    )
    payload: dict[str, Any] = {
        'schema_version': TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION,
        'has_data': bool(all_rows),
        'message': build_evidence_message(
            evidence=evidence,
            has_rows=bool(all_rows),
        ),
        'scope': {
            'label': (f'Namespace · {selected_namespace}' if selected_namespace else 'Cluster'),
            'namespace': selected_namespace,
            'snapshot_dimension': 'namespace' if selected_namespace else 'cluster',
        },
        'scope_metrics': scope,
        'coverage': coverage,
        'summary': build_summary_cards(rows_by_resource),
        'overview': build_overview_payload(rows_by_resource, scope, coverage),
        'rows': [],
        'all_rows': all_rows,
        'pagination': empty_pagination(),
        'total_rows': len(all_rows),
        'scope_total_rows': len(all_rows),
        'evidence_errors': collect_evidence_errors(evidence),
    }
    payload['posture'] = build_page_posture(payload)
    return payload


def build_scope(evidence: TopConsumersEvidence) -> dict[str, dict[str, Any]]:
    pvc_capacity_values = vector_value_map(
        evidence.pvc_capacity,
        key_builder=pvc_key,
    )
    pvc_capacity_total = sum(pvc_capacity_values.values())
    return {
        'cpu': scope_metric(evidence.cpu_total, evidence.cpu_capacity),
        'memory': scope_metric(evidence.memory_total, evidence.memory_capacity),
        'pods': scope_metric(evidence.pod_total, evidence.pod_capacity),
        'pvc': {
            'total': evidence.pvc_total.value,
            'total_available': evidence.pvc_total.available,
            'capacity': pvc_capacity_total,
            'capacity_available': evidence.pvc_capacity.observed,
        },
    }


def scope_metric(
    total: ScalarEvidence,
    capacity: ScalarEvidence,
) -> dict[str, Any]:
    return {
        'total': total.value,
        'total_available': total.available,
        'capacity': capacity.value,
        'capacity_available': capacity.available,
    }


def build_multi_resource_coverage(
    *,
    evidence: TopConsumersEvidence,
    rows_by_resource: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    items = {
        'cpu': compute_coverage(
            usage=evidence.cpu_usage,
            requests=evidence.cpu_requests,
            limits=evidence.cpu_limits,
            total=evidence.cpu_total,
            capacity=evidence.cpu_capacity,
            rows=rows_by_resource['cpu'],
        ),
        'memory': compute_coverage(
            usage=evidence.memory_usage,
            requests=evidence.memory_requests,
            limits=evidence.memory_limits,
            total=evidence.memory_total,
            capacity=evidence.memory_capacity,
            rows=rows_by_resource['memory'],
        ),
        'pods': denominator_coverage(
            usage=evidence.pod_usage,
            total=evidence.pod_total,
            denominator=evidence.pod_capacity,
            rows=rows_by_resource['pods'],
        ),
        'pvc': pvc_coverage(
            usage=evidence.pvc_usage,
            total=evidence.pvc_total,
            capacity=evidence.pvc_capacity,
            rows=rows_by_resource['pvc'],
        ),
    }
    for key, state in items.items():
        state['resource_label'] = RESOURCE_LABELS[key]
    complete_count = sum(1 for item in items.values() if item['key'] == 'complete')
    unavailable_count = sum(1 for item in items.values() if item['key'] == 'unavailable')
    return {
        'items': items,
        'complete_count': complete_count,
        'partial_count': len(items) - complete_count - unavailable_count,
        'unavailable_count': unavailable_count,
        'label': f'{complete_count} of {len(items)} Resources Complete',
    }


def compute_coverage(
    *,
    usage: VectorEvidence,
    requests: VectorEvidence,
    limits: VectorEvidence,
    total: ScalarEvidence,
    capacity: ScalarEvidence,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    if not usage.observed:
        return evidence_state('unavailable')
    complete = requests.observed and limits.observed and capacity.available
    if rows:
        complete = complete and total.available
    return evidence_state('complete' if complete else 'partial')


def denominator_coverage(
    *,
    usage: VectorEvidence,
    total: ScalarEvidence,
    denominator: ScalarEvidence,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    if not usage.observed:
        return evidence_state('unavailable')
    complete = denominator.available
    if rows:
        complete = complete and total.available
    return evidence_state('complete' if complete else 'partial')


def pvc_coverage(
    *,
    usage: VectorEvidence,
    total: ScalarEvidence,
    capacity: VectorEvidence,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    if not usage.observed:
        return evidence_state('unavailable')
    complete = capacity.observed
    if rows:
        complete = complete and total.available and all(row.get('denominator_evidence_available') for row in rows)
    return evidence_state('complete' if complete else 'partial')


def build_summary_cards(
    rows_by_resource: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        'highest_cpu': build_summary_card(
            rows=rows_by_resource['cpu'],
            title='Highest CPU Consumption',
            selector='absolute',
        ),
        'highest_memory': build_summary_card(
            rows=rows_by_resource['memory'],
            title='Highest Memory Consumption',
            selector='absolute',
        ),
        'highest_pods': build_summary_card(
            rows=rows_by_resource['pods'],
            title='Highest Pod Density',
            selector='absolute',
        ),
        'highest_pvc': build_summary_card(
            rows=rows_by_resource['pvc'],
            title='Highest PVC Utilization',
            selector='pressure',
        ),
    }


def build_summary_card(
    *,
    rows: list[dict[str, Any]],
    title: str,
    selector: str,
) -> dict[str, Any]:
    if not rows:
        return empty_summary_card(title)
    key = 'pressure_percent' if selector == 'pressure' else 'current_usage'
    eligible = [row for row in rows if row.get(key) is not None]
    if not eligible:
        return {
            **empty_summary_card(title),
            'subtitle': 'Required denominator unavailable',
            'identity': rows[0].get('identity', {}),
        }
    top_row = max(eligible, key=lambda row: safe_float(row.get(key, 0)))
    if selector == 'pressure':
        value = str(top_row.get('pressure_display') or 'N/A')
        subtitle = f'{top_row.get("current_display", "N/A")} of {top_row.get("limit_display", "N/A")}'
    else:
        value = str(top_row.get('current_display') or 'N/A')
        subtitle = f'{top_row.get("contribution_display", "N/A")} of selected-scope consumption'
    return {
        'title': title,
        'value': value,
        'subtitle': subtitle,
        'identity': top_row.get('identity', {}),
        'risk': top_row.get('risk', semantic_state('unknown')),
    }


def empty_summary_card(title: str) -> dict[str, Any]:
    return {
        'title': title,
        'value': 'N/A',
        'subtitle': 'Evidence unavailable',
        'identity': {
            'entity_label': 'Consumer',
            'primary': 'No Data',
            'secondary': '',
            'tertiary': '',
        },
        'risk': semantic_state('unknown'),
    }


def build_overview_payload(
    rows_by_resource: dict[str, list[dict[str, Any]]],
    scope: dict[str, dict[str, Any]],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    definitions = {
        'cpu': ('CPU Consumers', 'Ranked by observed CPU consumption.', 'cpu', 'Cores'),
        'memory': (
            'Memory Consumers',
            'Ranked by observed memory consumption.',
            'memory-stick',
            'Bytes',
        ),
        'pods': (
            'Pod-Dense Namespaces',
            'Ranked by running Pod count within the selected scope.',
            'boxes',
            'Pods',
        ),
        'pvc': (
            'PVC Consumers',
            'Ranked by observed volume pressure.',
            'database',
            'Capacity',
        ),
    }
    rankings: list[dict[str, Any]] = []
    for key in ('cpu', 'memory', 'pods', 'pvc'):
        title, description, icon, unit = definitions[key]
        sort_key = 'pressure_percent' if key == 'pvc' else 'current_usage'
        rows = sorted(
            rows_by_resource[key],
            key=lambda row: safe_float(row.get(sort_key, -1)),
            reverse=True,
        )[:5]
        metric = scope[key]
        rankings.append(
            {
                'key': key,
                'title': title,
                'description': description,
                'icon': icon,
                'unit': unit,
                'total_value': format_scope_total(
                    key,
                    metric['total'],
                    available=bool(metric['total_available']),
                ),
                'capacity_value': format_scope_total(
                    key,
                    metric['capacity'],
                    available=bool(metric['capacity_available']),
                ),
                'capacity_label': (
                    'Ready Worker Capacity' if key in {'cpu', 'memory', 'pods'} else 'Observed Volume Capacity'
                ),
                'coverage': coverage['items'][key],
                'rows': [dict(row, rank=index) for index, row in enumerate(rows, start=1)],
            }
        )
    return {'rankings': rankings}


def build_page_posture(payload: dict[str, Any]) -> dict[str, str]:
    rows = list(payload.get('all_rows') or [])
    raw_coverage = payload.get('coverage')
    coverage = raw_coverage if isinstance(raw_coverage, dict) else {}
    incomplete = safe_int(coverage.get('partial_count', 0)) + safe_int(coverage.get('unavailable_count', 0))
    critical = [row for row in rows if (row.get('risk') or {}).get('key') == 'critical']
    warning = [row for row in rows if (row.get('risk') or {}).get('key') == 'warning']
    pressure_rows = [row for row in rows if row.get('pressure_percent') is not None]
    highest = max(
        pressure_rows,
        key=lambda row: safe_float(row.get('pressure_percent', 0)),
        default=None,
    )
    if not rows:
        state = {
            'label': 'Unknown',
            'tone': 'unknown',
            'icon': 'database-zap',
            'description': 'No eligible consumer evidence is available.',
        }
    elif critical:
        state = {
            'label': 'Critical',
            'tone': 'critical',
            'icon': 'shield-alert',
            'description': ('Critical consumer pressure or a confirmed request gap requires immediate review.'),
        }
    elif incomplete:
        state = {
            'label': 'Limited Evidence',
            'tone': 'warning',
            'icon': 'database-zap',
            'description': ('One or more resource evidence sets are partial or unavailable.'),
        }
    elif warning:
        state = {
            'label': 'Watch',
            'tone': 'warning',
            'icon': 'triangle-alert',
            'description': 'Consumer pressure requires operational review.',
        }
    else:
        state = {
            'label': 'Healthy',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': ('Complete consumer evidence is within the normal range.'),
        }
    state['highest_pressure'] = (
        f'{highest.get("resource_label", "Resource")} · {highest.get("pressure_display", "N/A")}' if highest else 'N/A'
    )
    return state


def evidence_state(key: str) -> dict[str, str]:
    states = {
        'complete': ('Complete', 'normal'),
        'partial': ('Partial', 'warning'),
        'unavailable': ('Unavailable', 'unknown'),
    }
    normalized = key if key in states else 'unavailable'
    label, tone = states[normalized]
    return {'key': normalized, 'label': label, 'tone': tone}


def format_scope_total(
    resource_type: str,
    value: float,
    *,
    available: bool,
) -> str:
    if not available:
        return 'N/A'
    if resource_type == 'cpu':
        return format_cpu(value)
    if resource_type in {'memory', 'pvc'}:
        return format_bytes(value)
    return f'{int(value)} Pods'


def build_evidence_message(
    *,
    evidence: TopConsumersEvidence,
    has_rows: bool,
) -> str | None:
    if has_rows:
        return None
    if collect_evidence_errors(evidence):
        return (
            'No eligible consumer records were committed because one or more '
            'Prometheus evidence queries were unavailable or failed.'
        )
    return 'No eligible active consumer records were observed in the selected scope.'


def collect_evidence_errors(
    evidence: TopConsumersEvidence,
) -> list[str]:
    errors: list[str] = []
    for field in fields(evidence):
        value = getattr(evidence, field.name)
        error = getattr(value, 'error', None)
        if error and error not in errors:
            errors.append(str(error))
    return errors


def empty_pagination(page: int = 1, per_page: int = 5) -> dict[str, Any]:
    return {
        'page': page,
        'current_page': page,
        'total_pages': 1,
        'total_items': 0,
        'per_page': per_page,
        'start_item': 0,
        'end_item': 0,
        'has_prev': False,
        'has_next': False,
        'prev_page': 1,
        'next_page': 1,
    }


def empty_payload(
    *,
    message: str,
    page: int,
    per_page: int,
) -> dict[str, Any]:
    coverage_items = {
        key: {
            **evidence_state('unavailable'),
            'resource_label': RESOURCE_LABELS[key],
        }
        for key in ('cpu', 'memory', 'pods', 'pvc')
    }
    summary = {
        key: empty_summary_card(title)
        for key, title in {
            'highest_cpu': 'Highest CPU Consumption',
            'highest_memory': 'Highest Memory Consumption',
            'highest_pods': 'Highest Pod Density',
            'highest_pvc': 'Highest PVC Utilization',
        }.items()
    }
    return {
        'schema_version': TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION,
        'has_data': False,
        'message': message,
        'scope': {
            'label': 'Cluster',
            'namespace': '',
            'snapshot_dimension': 'cluster',
        },
        'scope_metrics': {},
        'coverage': {
            'items': coverage_items,
            'complete_count': 0,
            'partial_count': 0,
            'unavailable_count': 4,
            'label': '0 of 4 Resources Complete',
        },
        'posture': {
            'label': 'Unknown',
            'tone': 'unknown',
            'icon': 'database-zap',
            'description': message,
            'highest_pressure': 'N/A',
        },
        'summary': summary,
        'overview': {'rankings': []},
        'rows': [],
        'all_rows': [],
        'pagination': empty_pagination(page, per_page),
        'actionable_recommendations': [],
        'recommendation_cards': [],
        'recommendation_count': 0,
        'recommendations': [],
        'total_rows': 0,
        'scope_total_rows': 0,
        'evidence_errors': [],
    }


def is_current_payload(payload: Any) -> TypeGuard[dict[str, Any]]:
    if not isinstance(payload, dict):
        return False
    if payload.get('schema_version') != TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION:
        return False
    required_mappings = (
        'scope',
        'scope_metrics',
        'coverage',
        'posture',
        'summary',
        'overview',
        'pagination',
    )
    if any(not isinstance(payload.get(field), dict) for field in required_mappings):
        return False
    return isinstance(payload.get('all_rows'), list)


def dominant_namespace_names(rows: list[dict[str, Any]]) -> list[str]:
    scores: dict[str, float] = {}
    for row in rows:
        namespace = str(row.get('namespace') or '')
        if not namespace:
            continue
        contribution = safe_float(row.get('contribution_percent', 0))
        risk = str((row.get('risk') or {}).get('key') or 'unknown')
        if contribution < 20 and risk not in {'warning', 'critical'}:
            continue
        scores[namespace] = scores.get(namespace, 0.0) + contribution + RISK_RANK.get(risk, 0) * 5
    ranked = sorted(
        scores.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    return [namespace for namespace, _ in ranked[:3]]
