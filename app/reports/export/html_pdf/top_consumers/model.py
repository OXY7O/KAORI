from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

PAGE_COUNT = 9
RESOURCE_LABELS = {'cpu': 'CPU', 'memory': 'Memory', 'pods': 'Pods', 'pvc': 'PVC'}
RESOURCE_COLORS = {'cpu': '#2563EB', 'memory': '#7C3AED', 'pods': '#15803D', 'pvc': '#D97706'}


@dataclass(slots=True)
class TopConsumersState:
    consumer_payload: Mapping[str, Any]
    normalized_rows: list[dict[str, Any]]
    cpu_rows: list[dict[str, Any]]
    memory_rows: list[dict[str, Any]]
    pod_rows: list[dict[str, Any]]
    pvc_rows: list[dict[str, Any]]
    cpu_total: float
    memory_total: float
    memory_namespaces: list[str]
    complete_count: int
    partial_count: int
    unavailable_count: int
    coverage_label: str
    coverage_tone: str
    namespace_rows: list[dict[str, Any]]
    cpu_namespace_rows: list[dict[str, Any]]
    memory_namespace_rows: list[dict[str, Any]]
    comparison_rows: list[dict[str, Any]]
    top_cpu: dict[str, Any] | None
    top_memory: dict[str, Any] | None
    memory_namespace_label: str
    environment: str
    metrics_source: Mapping[str, Any]


def build_top_consumers_state(payload: Mapping[str, Any]) -> TopConsumersState:
    consumer_payload = mapping(payload.get('consumer_payload'))
    source_rows = sequence(consumer_payload.get('all_rows') or consumer_payload.get('rows'))
    normalized_rows = [consumer_row(item) for item in source_rows if isinstance(item, Mapping)]
    normalized_rows = [item for item in normalized_rows if item['resource_type']]
    rows_by_resource = prepare_rows_by_resource(normalized_rows)

    cpu_rows = rows_by_resource.get('cpu', [])[:3]
    memory_rows = rows_by_resource.get('memory', [])[:3]
    pod_rows = rows_by_resource.get('pods', [])[:3]
    pvc_rows = rows_by_resource.get('pvc', [])[:3]
    cpu_total = sum(row['current_usage'] for row in cpu_rows)
    memory_total = sum(normalized_usage_value(row) for row in memory_rows)
    memory_namespaces = sorted(
        {row['namespace'] for row in memory_rows if row['namespace'] not in {'-', 'Not Available'}}
    )

    coverage = mapping(consumer_payload.get('coverage'))
    complete_count = integer(coverage.get('complete_count'))
    partial_count = integer(coverage.get('partial_count'))
    unavailable_count = integer(coverage.get('unavailable_count'))
    coverage_label = f'{complete_count} of 4 Complete' if coverage else 'Not Available'
    coverage_tone = 'normal' if complete_count == 4 else 'warning'

    namespace_rows = namespace_rows_for(cpu_rows, memory_rows)
    comparison_rows = [
        comparison_row(item, index)
        for index, item in enumerate((cpu_rows + memory_rows + pod_rows + pvc_rows)[:8], start=1)
    ]
    memory_namespace_label = (
        memory_namespaces[0]
        if len(memory_namespaces) == 1
        else (f'{len(memory_namespaces)} Namespaces' if memory_namespaces else 'Not Available')
    )
    cluster = mapping(payload.get('cluster'))

    return TopConsumersState(
        consumer_payload=consumer_payload,
        normalized_rows=normalized_rows,
        cpu_rows=cpu_rows,
        memory_rows=memory_rows,
        pod_rows=pod_rows,
        pvc_rows=pvc_rows,
        cpu_total=cpu_total,
        memory_total=memory_total,
        memory_namespaces=memory_namespaces,
        complete_count=complete_count,
        partial_count=partial_count,
        unavailable_count=unavailable_count,
        coverage_label=coverage_label,
        coverage_tone=coverage_tone,
        namespace_rows=namespace_rows,
        cpu_namespace_rows=[item for item in namespace_rows if item['signal'] == 'CPU'],
        memory_namespace_rows=[item for item in namespace_rows if item['signal'] == 'Memory'],
        comparison_rows=comparison_rows,
        top_cpu=cpu_rows[0] if cpu_rows else None,
        top_memory=memory_rows[0] if memory_rows else None,
        memory_namespace_label=memory_namespace_label,
        environment=sanitize_text(cluster.get('environment'), fallback='Not Available'),
        metrics_source=mapping(payload.get('metrics_source_status')),
    )


def prepare_rows_by_resource(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        grouped[item['resource_type']].append(item)
    for resource_rows in grouped.values():
        resource_rows.sort(key=lambda row: row['current_usage'], reverse=True)
        displayed = resource_rows[:3]
        total = sum(max(normalized_usage_value(row), 0.0) for row in displayed)
        for row in displayed:
            share = normalized_usage_value(row) / total * 100.0 if total > 0 else None
            row['displayed_share'] = share
            row['displayed_share_label'] = percent(share) if share is not None else 'Not Available'
            row['displayed_share_bar'] = min(max(share or 0.0, 0.0), 100.0)
    return grouped


def consumer_row(value: Mapping[str, Any]) -> dict[str, Any]:
    identity = mapping(value.get('identity'))
    resource_type = sanitize_text(value.get('resource_type'), fallback='').lower()
    current_usage = number(value.get('current_usage'))
    current_display = sanitize_text(value.get('current_display'), fallback='Not Available')
    if current_display == 'Not Available' and current_usage is not None:
        current_display = format_usage(resource_type, current_usage)
    risk = mapping(value.get('risk'))
    return {
        'ref': '',
        'resource_type': resource_type,
        'resource_label': RESOURCE_LABELS.get(
            resource_type, sanitize_text(value.get('resource_label'), fallback=resource_type.title())
        ),
        'identity': sanitize_text(
            identity.get('primary') or value.get('workload') or value.get('pod') or value.get('pvc_name'),
            fallback='Not Available',
        ),
        'secondary_identity': sanitize_text(identity.get('secondary'), fallback=''),
        'namespace': sanitize_text(value.get('namespace'), fallback='Not Available'),
        'current_usage': current_usage or 0.0,
        'current_display': current_display,
        'unit': unit_from_display(current_display, resource_type),
        'pressure_label': sanitize_text(value.get('pressure_display'), fallback='Not Available'),
        'pressure_percent': number(value.get('pressure_percent')),
        'contribution_label': sanitize_text(value.get('contribution_display'), fallback='Not Available'),
        'request_display': sanitize_text(value.get('request_display'), fallback='Not Available'),
        'limit_display': sanitize_text(value.get('limit_display'), fallback='Not Available'),
        'risk_key': sanitize_text(risk.get('key'), fallback='unknown').lower(),
        'risk_label': sanitize_text(risk.get('label'), fallback='Unknown'),
        'recommendation': sanitize_text(
            value.get('recommendation'),
            fallback='Validate the displayed consumer against live state and workload intent.',
        ),
        'color': RESOURCE_COLORS.get(resource_type, '#7C3AED'),
        'displayed_share': None,
        'displayed_share_label': 'Not Available',
        'displayed_share_bar': 0.0,
    }


def resource_page(
    label: str,
    rows: list[dict[str, Any]],
    top: dict[str, Any] | None,
    color: str,
) -> dict[str, Any]:
    total = sum(normalized_usage_value(row) for row in rows)
    namespaces = sorted({row['namespace'] for row in rows})
    return {
        'metrics': [
            metric(
                f'Top {label}',
                top['current_display'] if top else 'Not Available',
                top['risk_label'] if top else 'No Evidence',
                tone_from_risk(top['risk_key']) if top else 'warning',
            ),
            metric('Displayed Total', display_total(rows, total), f'Top {len(rows)}', 'info'),
            metric('Namespaces', str(len(namespaces)), 'Displayed', 'normal'),
            metric(
                'Largest Share',
                top['displayed_share_label'] if top else 'Not Available',
                'Displayed set',
                'warning' if top else 'muted',
            ),
        ],
        'rows': [with_ref(row, index) for index, row in enumerate(rows, start=1)],
        'color': color,
        'assessment_title': f'{label} consumer evidence requires workload validation.'
        if rows
        else f'{label} consumer evidence is not available.',
        'assessment_body': (
            f'The displayed {label.lower()} set contains {len(rows)} record(s) across {len(namespaces)} namespace(s). '
            'Displayed share is calculated only from the published ranking set.'
            if rows
            else f'No committed {label.lower()} consumer record is available for the selected reporting boundary.'
        ),
        'assessment_note': (
            'Consumer concentration does not establish aggregate capacity pressure or authorize remediation.'
        ),
    }


def with_ref(row: dict[str, Any], index: int) -> dict[str, Any]:
    item = dict(row)
    prefix = {'cpu': 'C', 'memory': 'M', 'pods': 'P', 'pvc': 'V'}.get(row['resource_type'], 'R')
    item['ref'] = f'{prefix}{index}'
    return item


def namespace_rows_for(cpu_rows: list[dict[str, Any]], memory_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index = 1
    for resource, rows in (('CPU', cpu_rows), ('Memory', memory_rows)):
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            bucket = grouped.setdefault(row['namespace'], {'value': 0.0, 'share': 0.0, 'unit': row['unit']})
            bucket['value'] += normalized_usage_value(row)
            bucket['share'] += row.get('displayed_share') or 0.0
        for namespace, bucket in sorted(grouped.items(), key=lambda item: item[1]['value'], reverse=True):
            result.append(
                {
                    'ref': f'N{index}',
                    'namespace': namespace,
                    'signal': resource,
                    'value': format_with_unit(bucket['value'], bucket['unit']),
                    'share': bucket['share'],
                    'share_label': percent(bucket['share']),
                    'status': 'Review',
                    'tone': 'warning',
                }
            )
            index += 1
    return result


def comparison_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'X{index}',
        'identity': row['identity'],
        'namespace': row['namespace'],
        'signal': row['resource_label'],
        'value': row['current_display'],
        'evidence': 'Current Only',
    }


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def normalized_usage_value(row: Mapping[str, Any]) -> float:
    value = number(row.get('current_usage')) or 0.0
    unit_label = sanitize_text(row.get('unit'), fallback='')
    if unit_label == 'GiB' and value > 1024**2:
        return value / (1024**3)
    if unit_label == 'MiB' and value > 1024:
        return value / (1024**2)
    if unit_label == 'KiB' and value > 1024:
        return value / 1024
    return value


def display_total(rows: list[dict[str, Any]], total: float) -> str:
    if not rows:
        return 'Not Available'
    normalized_total = sum(normalized_usage_value(row) for row in rows)
    return format_with_unit(normalized_total, unit(rows, fallback=''))


def format_usage(resource_type: str, value: float) -> str:
    if resource_type == 'cpu':
        return f'{value:.2f} cores'
    if resource_type in {'memory', 'pvc'}:
        gib = value / (1024**3) if value > 1024**2 else value
        return f'{gib:.2f} GiB'
    if resource_type == 'pods':
        return f'{value:.0f} pods'
    return f'{value:.2f}'


def format_with_unit(value: float, unit_label: str) -> str:
    if unit_label in {'cores', 'core'}:
        return f'{value:.2f} cores'
    if unit_label in {'GiB', 'MiB', 'KiB', 'bytes'}:
        return f'{value:.2f} {unit_label}'
    if unit_label in {'pods', 'pod'}:
        return f'{value:.0f} pods'
    return f'{value:.2f} {unit_label}'.strip()


def unit(rows: list[dict[str, Any]], fallback: str) -> str:
    return rows[0]['unit'] if rows else fallback


def unit_from_display(display: str, resource_type: str) -> str:
    tokens = display.replace(',', '').split()
    if len(tokens) >= 2:
        return ' '.join(tokens[1:])
    return {'cpu': 'cores', 'memory': 'GiB', 'pods': 'pods', 'pvc': 'GiB'}.get(resource_type, '')


def tone_from_risk(value: str) -> str:
    return {'critical': 'critical', 'warning': 'warning', 'normal': 'normal', 'healthy': 'normal'}.get(value, 'muted')


def risk_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(1 for row in rows if row['risk_key'] == key)


def percent(value: float | None) -> str:
    return f'{value:.1f}%' if value is not None else 'Not Available'


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def number(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
