from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)
from app.reports.export.html_pdf.normalization import sanitize_text

_PAGE_COUNT = 9
_RESOURCE_ORDER = ('cpu', 'memory', 'pods', 'pvc')
_RESOURCE_LABELS = {'cpu': 'CPU', 'memory': 'Memory', 'pods': 'Pods', 'pvc': 'PVC'}
_RESOURCE_COLORS = {'cpu': '#2563EB', 'memory': '#7C3AED', 'pods': '#15803D', 'pvc': '#D97706'}


def build_top_consumers_analysis_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    consumer_payload = _mapping(payload.get('consumer_payload'))
    source_rows = _sequence(consumer_payload.get('all_rows') or consumer_payload.get('rows'))
    normalized_rows = [_consumer_row(item) for item in source_rows if isinstance(item, Mapping)]
    normalized_rows = [item for item in normalized_rows if item['resource_type']]

    rows_by_resource: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in normalized_rows:
        rows_by_resource[item['resource_type']].append(item)
    for resource_rows in rows_by_resource.values():
        resource_rows.sort(key=lambda row: row['current_usage'], reverse=True)
        displayed_total = sum(max(row['current_usage'], 0.0) for row in resource_rows[:3])
        for row in resource_rows[:3]:
            row['displayed_share'] = (row['current_usage'] / displayed_total * 100.0) if displayed_total > 0 else None
            row['displayed_share_label'] = _percent(row['displayed_share']) if row['displayed_share'] is not None else 'Not Available'
            row['displayed_share_bar'] = min(max(row['displayed_share'] or 0.0, 0.0), 100.0)

    cpu_rows = rows_by_resource.get('cpu', [])[:3]
    memory_rows = rows_by_resource.get('memory', [])[:3]
    pod_rows = rows_by_resource.get('pods', [])[:3]
    pvc_rows = rows_by_resource.get('pvc', [])[:3]

    cpu_total = sum(row['current_usage'] for row in cpu_rows)
    memory_total = sum(row['current_usage'] for row in memory_rows)
    namespaces = sorted({row['namespace'] for row in cpu_rows + memory_rows if row['namespace'] not in {'-', 'Not Available'}})
    memory_namespaces = sorted({row['namespace'] for row in memory_rows if row['namespace'] not in {'-', 'Not Available'}})

    coverage = _mapping(consumer_payload.get('coverage'))
    complete_count = _int(coverage.get('complete_count'))
    partial_count = _int(coverage.get('partial_count'))
    unavailable_count = _int(coverage.get('unavailable_count'))
    coverage_label = f'{complete_count} of 4 Complete' if coverage else 'Not Available'
    coverage_tone = 'normal' if complete_count == 4 else 'warning'

    recommendations = _recommendations(consumer_payload, cpu_rows, memory_rows)
    namespace_rows = _namespace_rows(cpu_rows, memory_rows)
    comparison_rows = [
        _comparison_row(item, index)
        for index, item in enumerate((cpu_rows + memory_rows + pod_rows + pvc_rows)[:8], start=1)
    ]

    top_cpu = cpu_rows[0] if cpu_rows else None
    top_memory = memory_rows[0] if memory_rows else None
    memory_namespace_label = memory_namespaces[0] if len(memory_namespaces) == 1 else (
        f'{len(memory_namespaces)} Namespaces' if memory_namespaces else 'Not Available'
    )
    primary_interpretation = _primary_interpretation(cpu_rows, memory_rows)

    cluster = _mapping(payload.get('cluster'))
    environment = sanitize_text(cluster.get('environment'), fallback='Not Available')
    prometheus = _mapping(payload.get('prometheus_status'))
    source_evidence = _source_evidence(payload, prometheus)

    return {
        'presentation_version': 'v1.1-top-consumers-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': _PAGE_COUNT,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='single-line-technical-registers',
            unit_policy='resource-specific-normalized-units',
            ranking_policy='displayed-set-share-per-resource',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Top Consumers',
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'cover': {
            'environment': environment,
            'purpose': 'Support operational review of leading resource contributors, displayed concentration, ownership, and validation actions.',
            'context': 'Rankings describe the committed displayed consumer set. They do not establish complete namespace allocation or aggregate capacity pressure.',
        },
        'executive': {
            'metrics': [
                _metric('Displayed CPU', _display_total(cpu_rows, cpu_total), 'Top 3 total', 'info'),
                _metric('Displayed Memory', _display_total(memory_rows, memory_total), 'Top 3 total', 'warning'),
                _metric('CPU Namespaces', str(len({row['namespace'] for row in cpu_rows})), 'Displayed set', 'normal'),
                _metric('Memory Namespace', memory_namespace_label, 'Concentration', 'warning' if len(memory_namespaces) == 1 else 'muted'),
            ],
            'cpu_rows': cpu_rows,
            'memory_rows': memory_rows,
            'interpretation_title': primary_interpretation['title'],
            'interpretation_body': primary_interpretation['body'],
            'interpretation_note': primary_interpretation['note'],
            'tone': primary_interpretation['tone'],
            'decisions': recommendations[:4],
        },
        'cpu': _resource_page('CPU', cpu_rows, top_cpu, '#2563EB'),
        'memory': _resource_page('Memory', memory_rows, top_memory, '#7C3AED'),
        'namespace': {
            'metrics': [
                _metric('CPU Namespaces', str(len({row['namespace'] for row in cpu_rows})), 'Displayed', 'normal'),
                _metric('Memory Namespaces', str(len(memory_namespaces)), 'Displayed', 'warning' if len(memory_namespaces) == 1 else 'normal'),
                _metric('Displayed Records', str(len(cpu_rows) + len(memory_rows)), 'CPU + Memory', 'info'),
                _metric('Denominator', 'Partial', 'Displayed set only', 'warning'),
            ],
            'cpu_rows': _namespace_signal_rows(cpu_rows),
            'memory_rows': _namespace_signal_rows(memory_rows),
            'register': namespace_rows,
        },
        'comparison': {
            'metrics': [
                _metric('CPU Unit', _unit(cpu_rows, fallback='cores'), 'Normalized', 'info'),
                _metric('Memory Unit', _unit(memory_rows, fallback='GiB'), 'Normalized', 'warning'),
                _metric('Ranking Scope', 'Top 3', 'Per signal', 'normal'),
                _metric('Trend Evidence', 'N/A', 'Not Available', 'warning'),
            ],
            'rows': comparison_rows,
        },
        'risk': {
            'metrics': [
                _metric('Critical Risks', str(_risk_count(normalized_rows, 'critical')), 'Consumer pressure', 'critical' if _risk_count(normalized_rows, 'critical') else 'normal'),
                _metric('Review Risks', str(_risk_count(normalized_rows, 'warning')), 'Open', 'warning'),
                _metric('Evidence Gaps', str(partial_count + unavailable_count), 'Coverage', 'warning' if partial_count + unavailable_count else 'normal'),
                _metric('Validation Gates', str(len(recommendations)), 'Required', 'info'),
            ],
            'rows': _risk_rows(normalized_rows, recommendations),
        },
        'recommendations': {
            'metrics': _recommendation_metrics(recommendations),
            'rows': recommendations,
            'governance': [
                {'field': 'Primary Action', 'requirement': recommendations[0]['title'] if recommendations else 'Continue consumer evidence monitoring.'},
                {'field': 'Validation Criteria', 'requirement': 'Confirm expected workload behavior, accountable owner, ranking denominator, live metric, and approved response before closure.'},
                {'field': 'Assigned Owners', 'requirement': _owner_summary(recommendations)},
                {'field': 'Change Control', 'requirement': 'No infrastructure or workload change is authorized by this report alone.'},
            ],
        },
        'methodology': {
            'metrics': [
                _metric('Data Sources', str(len(source_evidence)), 'Committed', 'normal'),
                _metric('Coverage', coverage_label, 'Resource evidence', coverage_tone),
                _metric('Ranking Scope', 'Top 3', 'Per resource', 'info'),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ],
            'sources': source_evidence,
            'rules': [
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Memory Unit', 'setting': 'Source display / GiB normalization'},
                {'ref': 'M4', 'rule': 'Contribution Share', 'setting': 'Displayed top-set total'},
                {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ],
            'included': [
                'Committed displayed top-consumer records and normalized resource values.',
                'Displayed-set contribution shares calculated independently per resource.',
                'Namespace, pressure, request, limit, and recommendation evidence when committed.',
            ],
            'excluded': [
                'Complete namespace or cluster allocation denominator unless explicitly committed.',
                'Consumer-level historical direction and service objectives when unavailable.',
                'Live state after the data cut-off and uncommitted application ownership.',
            ],
            'limitations': [
                'Top-consumer ranking describes displayed records only.',
                'Different resource units are not combined into a single score.',
                'Validate all recommendations against live state before remediation.',
            ],
            'status_language': [
                {'ref': 'S1', 'title': 'Not Available', 'description': 'No committed evidence exists.'},
                {'ref': 'S2', 'title': 'Partial Coverage', 'description': 'Only part of the requested scope is represented.'},
                {'ref': 'S3', 'title': 'Current Only', 'description': 'A cut-off value exists without historical direction.'},
                {'ref': 'S4', 'title': 'Source Unavailable', 'description': 'The source was unreachable at the cut-off.'},
            ],
        },
    }


def _consumer_row(value: Mapping[str, Any]) -> dict[str, Any]:
    identity = _mapping(value.get('identity'))
    resource_type = sanitize_text(value.get('resource_type'), fallback='').lower()
    current_usage = _float(value.get('current_usage'))
    current_display = sanitize_text(value.get('current_display'), fallback='Not Available')
    if current_display == 'Not Available' and current_usage is not None:
        current_display = _format_usage(resource_type, current_usage)
    risk = _mapping(value.get('risk'))
    return {
        'ref': '',
        'resource_type': resource_type,
        'resource_label': _RESOURCE_LABELS.get(resource_type, sanitize_text(value.get('resource_label'), fallback=resource_type.title())),
        'identity': sanitize_text(identity.get('primary') or value.get('workload') or value.get('pod') or value.get('pvc_name'), fallback='Not Available'),
        'secondary_identity': sanitize_text(identity.get('secondary'), fallback=''),
        'namespace': sanitize_text(value.get('namespace'), fallback='Not Available'),
        'current_usage': current_usage or 0.0,
        'current_display': current_display,
        'unit': _unit_from_display(current_display, resource_type),
        'pressure_label': sanitize_text(value.get('pressure_display'), fallback='Not Available'),
        'pressure_percent': _float(value.get('pressure_percent')),
        'contribution_label': sanitize_text(value.get('contribution_display'), fallback='Not Available'),
        'request_display': sanitize_text(value.get('request_display'), fallback='Not Available'),
        'limit_display': sanitize_text(value.get('limit_display'), fallback='Not Available'),
        'risk_key': sanitize_text(risk.get('key'), fallback='unknown').lower(),
        'risk_label': sanitize_text(risk.get('label'), fallback='Unknown'),
        'recommendation': sanitize_text(value.get('recommendation'), fallback='Validate the displayed consumer against live state and workload intent.'),
        'color': _RESOURCE_COLORS.get(resource_type, '#7C3AED'),
        'displayed_share': None,
        'displayed_share_label': 'Not Available',
        'displayed_share_bar': 0.0,
    }


def _resource_page(label: str, rows: list[dict[str, Any]], top: dict[str, Any] | None, color: str) -> dict[str, Any]:
    total = sum(row['current_usage'] for row in rows)
    namespaces = sorted({row['namespace'] for row in rows})
    return {
        'metrics': [
            _metric(f'Top {label}', top['current_display'] if top else 'Not Available', top['risk_label'] if top else 'No Evidence', _tone_from_risk(top['risk_key']) if top else 'warning'),
            _metric('Displayed Total', _display_total(rows, total), f'Top {len(rows)}', 'info'),
            _metric('Namespaces', str(len(namespaces)), 'Displayed', 'normal'),
            _metric('Largest Share', top['displayed_share_label'] if top else 'Not Available', 'Displayed set', 'warning' if top else 'muted'),
        ],
        'rows': [_with_ref(row, index) for index, row in enumerate(rows, start=1)],
        'color': color,
        'assessment_title': f'{label} consumer evidence requires workload validation.' if rows else f'{label} consumer evidence is not available.',
        'assessment_body': (
            f'The displayed {label.lower()} set contains {len(rows)} record(s) across {len(namespaces)} namespace(s). '
            'Displayed share is calculated only from the published ranking set.'
            if rows else f'No committed {label.lower()} consumer record is available for the selected reporting boundary.'
        ),
        'assessment_note': 'Consumer concentration does not establish aggregate capacity pressure or authorize remediation.',
    }


def _with_ref(row: dict[str, Any], index: int) -> dict[str, Any]:
    item = dict(row)
    prefix = {'cpu': 'C', 'memory': 'M', 'pods': 'P', 'pvc': 'V'}.get(row['resource_type'], 'R')
    item['ref'] = f'{prefix}{index}'
    return item


def _namespace_signal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, float] = defaultdict(float)
    for row in rows:
        grouped[row['namespace']] += row.get('displayed_share') or 0.0
    return [
        {'namespace': namespace, 'share': share, 'share_label': _percent(share)}
        for namespace, share in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]


def _namespace_rows(cpu_rows: list[dict[str, Any]], memory_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index = 1
    for resource, rows in (('CPU', cpu_rows), ('Memory', memory_rows)):
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            bucket = grouped.setdefault(row['namespace'], {'value': 0.0, 'share': 0.0, 'unit': row['unit']})
            bucket['value'] += row['current_usage']
            bucket['share'] += row.get('displayed_share') or 0.0
        for namespace, bucket in sorted(grouped.items(), key=lambda item: item[1]['value'], reverse=True):
            result.append({
                'ref': f'N{index}',
                'namespace': namespace,
                'signal': resource,
                'value': _format_with_unit(bucket['value'], bucket['unit']),
                'share': _percent(bucket['share']),
                'status': 'Review',
                'tone': 'warning',
            })
            index += 1
    return result


def _comparison_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'X{index}',
        'identity': row['identity'],
        'namespace': row['namespace'],
        'signal': row['resource_label'],
        'value': row['current_display'],
        'evidence': 'Current Only',
    }


def _risk_rows(rows: list[dict[str, Any]], recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    risky = [row for row in rows if row['risk_key'] in {'critical', 'warning'}]
    for index, row in enumerate(risky[:3], start=1):
        priority = 'P1' if row['risk_key'] == 'critical' else 'P2'
        result.append({
            'ref': f'R{index}', 'risk': f"{row['resource_label']} Consumer: {row['identity']}",
            'priority': priority, 'impact': 'High' if priority == 'P1' else 'Medium',
            'owner': 'Platform Operations', 'status': 'Open', 'tone': _tone_from_risk(row['risk_key']),
        })
    defaults = [
        ('Displayed Denominator Limit', 'P2', 'Medium', 'Observability Owner', 'Review'),
        ('Consumer Trend Evidence', 'P3', 'Low', 'Observability Owner', 'Missing'),
        ('Application Owner Mapping', 'P3', 'Low', 'Application Owner', 'Missing'),
    ]
    for title, priority, impact, owner, status in defaults:
        if len(result) >= 5:
            break
        result.append({'ref': f'R{len(result)+1}', 'risk': title, 'priority': priority, 'impact': impact, 'owner': owner, 'status': status, 'tone': 'warning' if priority == 'P2' else 'muted'})
    return result


def _recommendations(payload: Mapping[str, Any], cpu_rows: list[dict[str, Any]], memory_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = _sequence(payload.get('actionable_recommendations'))
    items: list[dict[str, Any]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            continue
        title = sanitize_text(value.get('title'), fallback='Review Top Consumer Evidence')
        description = sanitize_text(value.get('description'), fallback='Validate the displayed record against live state and expected workload behavior.')
        priority = _priority(value.get('priority') or value.get('severity'))
        items.append({
            'ref': f'A{len(items)+1}', 'priority': priority, 'title': title, 'description': description,
            'owner': sanitize_text(value.get('owner'), fallback='Platform Operations'),
            'target': 'This Week' if priority == 'P1' else ('Next Week' if priority == 'P2' else 'This Month'),
            'status': 'Open' if priority in {'P1', 'P2'} else 'Planned',
            'tone': 'critical' if priority == 'P1' else ('warning' if priority == 'P2' else 'info'),
        })
        if len(items) >= 5:
            break
    defaults = []
    if cpu_rows:
        defaults.append(('P2', 'Validate Highest CPU Consumer', f"Confirm whether {cpu_rows[0]['identity']} is expected for the selected scope and reporting window.", 'Platform Operations'))
    if memory_rows:
        defaults.append(('P2', 'Validate Memory Concentration', f"Confirm whether the displayed {memory_rows[0]['namespace']} memory concentration is expected.", 'Platform Operations'))
    defaults.extend([
        ('P2', 'Confirm Displayed Denominator', 'Document whether the published ranking set represents complete or partial resource evidence.', 'Observability Owner'),
        ('P3', 'Restore Consumer Trend Evidence', 'Commit consumer-level historical direction before concluding sustained growth or decline.', 'Observability Owner'),
        ('P3', 'Map Application Ownership', 'Resolve committed application ownership before assigning workload changes.', 'Application Owner'),
    ])
    existing = {item['title'] for item in items}
    for priority, title, description, owner in defaults:
        if title in existing or len(items) >= 5:
            continue
        items.append({
            'ref': f'A{len(items)+1}', 'priority': priority, 'title': title, 'description': description,
            'owner': owner, 'target': 'Next Week' if priority == 'P2' else 'This Month',
            'status': 'Open' if priority == 'P2' else 'Planned',
            'tone': 'warning' if priority == 'P2' else 'info',
        })
    items.sort(key=lambda item: (int(item['priority'][1]), item['ref']))
    for index, item in enumerate(items, start=1):
        item['ref'] = f'A{index}'
    return items


def _recommendation_metrics(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        _metric('P1 Actions', str(sum(1 for item in items if item['priority'] == 'P1')), 'Immediate', 'critical' if any(item['priority'] == 'P1' for item in items) else 'normal'),
        _metric('P2 Actions', str(sum(1 for item in items if item['priority'] == 'P2')), 'Open', 'warning'),
        _metric('P3 Actions', str(sum(1 for item in items if item['priority'] == 'P3')), 'Planned', 'info'),
        _metric('Validation Gates', str(len(items)), 'Required', 'info'),
    ]


def _primary_interpretation(cpu_rows: list[dict[str, Any]], memory_rows: list[dict[str, Any]]) -> dict[str, str]:
    if memory_rows and len({row['namespace'] for row in memory_rows}) == 1:
        namespace = memory_rows[0]['namespace']
        return {
            'title': f'Displayed memory concentration is localized in {namespace}.',
            'body': f'All {len(memory_rows)} displayed memory records belong to {namespace}. Displayed CPU contribution spans {len({row["namespace"] for row in cpu_rows})} namespace(s).',
            'note': 'The report explains the displayed ranking set only; it is not complete namespace allocation.',
            'tone': 'warning',
        }
    if cpu_rows or memory_rows:
        return {
            'title': 'Displayed consumers require ownership and live-state validation.',
            'body': 'Review the leading records independently from aggregate utilization and capacity posture.',
            'note': 'A top rank does not by itself indicate abnormal behavior or authorize remediation.',
            'tone': 'warning',
        }
    return {
        'title': 'Top-consumer evidence is not available.',
        'body': 'No committed consumer row is available for the selected reporting boundary.',
        'note': 'Do not infer zero consumption from missing evidence.',
        'tone': 'muted',
    }


def _source_evidence(payload: Mapping[str, Any], prometheus: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = _sequence(payload.get('source_evidence'))
    result = []
    for value in raw:
        if isinstance(value, Mapping):
            result.append({
                'source': sanitize_text(value.get('source'), fallback='Consumer Evidence'),
                'freshness': sanitize_text(value.get('freshness'), fallback='At report cut-off'),
                'last_collected': sanitize_text(value.get('last_collected'), fallback='At report cut-off'),
            })
    if not result:
        result = [
            {
                'source': 'Prometheus Consumer Evidence',
                'freshness': _response_time(prometheus),
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Committed Top Consumer Records',
                'freshness': 'Displayed resource rows',
                'last_collected': 'At report cut-off',
            },
        ]
    return result[:4]


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _display_total(rows: list[dict[str, Any]], total: float) -> str:
    if not rows:
        return 'Not Available'
    return _format_with_unit(total, _unit(rows, fallback=''))


def _format_usage(resource_type: str, value: float) -> str:
    if resource_type == 'cpu':
        return f'{value:.2f} cores'
    if resource_type in {'memory', 'pvc'}:
        gib = value / (1024**3) if value > 1024**2 else value
        return f'{gib:.2f} GiB'
    if resource_type == 'pods':
        return f'{value:.0f} pods'
    return f'{value:.2f}'


def _format_with_unit(value: float, unit: str) -> str:
    if unit in {'cores', 'core'}:
        return f'{value:.2f} cores'
    if unit in {'GiB', 'MiB', 'KiB', 'bytes'}:
        return f'{value:.2f} {unit}'
    if unit in {'pods', 'pod'}:
        return f'{value:.0f} pods'
    return f'{value:.2f} {unit}'.strip()


def _unit(rows: list[dict[str, Any]], fallback: str) -> str:
    return rows[0]['unit'] if rows else fallback


def _unit_from_display(display: str, resource_type: str) -> str:
    tokens = display.replace(',', '').split()
    if len(tokens) >= 2:
        return ' '.join(tokens[1:])
    return {'cpu': 'cores', 'memory': 'GiB', 'pods': 'pods', 'pvc': 'GiB'}.get(resource_type, '')


def _priority(value: Any) -> str:
    normalized = sanitize_text(value, fallback='P3').lower()
    if normalized in {'p1', 'critical', 'high'}:
        return 'P1'
    if normalized in {'p2', 'warning', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def _tone_from_risk(value: str) -> str:
    return {'critical': 'critical', 'warning': 'warning', 'normal': 'normal', 'healthy': 'normal'}.get(value, 'muted')


def _risk_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(1 for row in rows if row['risk_key'] == key)


def _owner_summary(items: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item['owner']] += 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No assigned action.'


def _response_time(value: Mapping[str, Any]) -> str:
    response = value.get('response_time_ms')
    return f'{_int(response)} ms' if response is not None else 'At report cut-off'


def _percent(value: float | None) -> str:
    return f'{value:.1f}%' if value is not None else 'Not Available'


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _float(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
