from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_CAPACITY_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'Compute Capacity',
    'Scheduling Capacity',
    'Storage Capacity',
    'Capacity Forecast',
    'Capacity Risk Register',
    'Recommendation Plan',
    'Methodology and Evidence Boundary',
)

_RESOURCE_UNITS = {
    'cpu': 'cores',
    'memory': 'GiB',
    'pods': 'pods',
    'storage': 'GiB',
}

_RESOURCE_LABELS = {
    'cpu': 'CPU',
    'memory': 'Memory',
    'pods': 'Pods',
    'storage': 'Storage',
}

_RESOURCE_COLORS = {
    'cpu': '#2563EB',
    'memory': '#7C3AED',
    'pods': '#15803D',
}


def build_capacity_analysis_presentation(
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
    cluster = _mapping(payload.get('cluster'))
    cluster_info = _mapping(payload.get('cluster_info'))
    capacity_summary = _mapping(payload.get('capacity_summary'))
    allocation_summary = _mapping(payload.get('allocation_summary'))
    prometheus_status = _mapping(payload.get('prometheus_status'))
    forecast_payload = _mapping(payload.get('forecast_payload'))

    resources = {
        key: _capacity_resource(_mapping(capacity_summary.get(key)), key)
        for key in ('cpu', 'memory', 'pods', 'storage')
    }
    cpu = resources['cpu']
    memory = resources['memory']
    pods = resources['pods']
    storage = resources['storage']

    total_nodes = _int(cluster_info.get('total_nodes'))
    ready_nodes = _int(cluster_info.get('ready_nodes'))
    not_ready_nodes = _int(cluster_info.get('not_ready_nodes'))
    worker_nodes = _int(cluster_info.get('worker_nodes'))
    master_nodes = _int(cluster_info.get('master_nodes'))
    participation = _ratio_percent(ready_nodes, total_nodes)

    allocations = {
        key: _allocation_resource(_mapping(allocation_summary.get(key)), key)
        for key in ('cpu', 'memory', 'pods')
    }

    forecast_items = {
        str(item.get('key') or '').lower(): item
        for item in _sequence(forecast_payload.get('items'))
        if isinstance(item, Mapping)
    }
    projections = {
        key: _forecast_percent(_mapping(forecast_items.get(key)))
        for key in ('cpu', 'memory', 'pods')
    }
    forecast_rows = tuple(
        _forecast_row(
            f'T{index}',
            key,
            resources[key]['used_percent'],
            projections[key],
        )
        for index, key in enumerate(('cpu', 'memory', 'pods'), start=1)
    )
    forecast_chart = _capacity_forecast_chart_svg(
        resources=resources,
        forecast_items=forecast_items,
        projections=projections,
    )
    forecast_available = any(value is not None for value in projections.values())
    forecast_method = sanitize_text(
        forecast_payload.get('method_label') or forecast_payload.get('forecast_method'),
        fallback='Not Available',
    )

    risks = _risk_rows(
        payload=payload,
        resources=resources,
        allocations=allocations,
        total_nodes=total_nodes,
        ready_nodes=ready_nodes,
        projections=projections,
    )
    recommendations = _recommendation_rows(
        payload=payload,
        resources=resources,
        projections=projections,
        total_nodes=total_nodes,
        ready_nodes=ready_nodes,
    )
    source_rows = _source_rows(
        payload=payload,
        prometheus_status=prometheus_status,
        forecast_payload=forecast_payload,
        period_label=period_label,
    )

    available_resources = [item for item in resources.values() if item['evidence_available']]
    leading = max(available_resources, key=lambda item: item['used_percent'], default=None)
    evidence_gap_count = sum(1 for item in resources.values() if not item['evidence_available'])
    p1_count = sum(1 for item in recommendations if item['priority'] == 'P1')
    p2_count = sum(1 for item in recommendations if item['priority'] == 'P2')
    p3_count = sum(1 for item in recommendations if item['priority'] == 'P3')

    return {
        'page_count': len(_CAPACITY_PAGE_TITLES),
        'presentation_version': 'v1.0-capacity-analysis-publication',
        'layout_contract': {
            'paper': 'A4 Portrait',
            'page_count': 9,
            'fixed_page_canvas': True,
            'status_style': 'plain-colored-text',
            'table_policy': 'single-line-technical-registers',
            'missing_evidence_policy': 'explicit-not-available',
            'visual_style': 'kaori-capacity-analysis-v1.0',
        },
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Capacity Analysis',
        'report_subtitle': 'Kubernetes Operational Intelligence Report',
        'classification': classification,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'page_titles': _CAPACITY_PAGE_TITLES,
        'cover': {
            'cluster': sanitize_text(cluster.get('name'), fallback=cluster_scope),
            'environment': sanitize_text(cluster.get('environment'), fallback='Not Available'),
            'purpose': (
                'Support management and platform review of shared-capacity posture, committed '
                'headroom, evidence gaps, projected pressure, and validation gates.'
            ),
            'context': (
                'Use the report cut-off as the evidence boundary. Missing capacity evidence remains '
                'explicit and is never converted to zero or a healthy posture.'
            ),
        },
        'executive': {
            'metrics': (
                _metric('CPU Headroom', cpu['headroom_display'], cpu['status'], cpu['tone']),
                _metric('Memory Headroom', memory['headroom_display'], memory['status'], memory['tone']),
                _metric('Pod Headroom', pods['headroom_display'], pods['status'], pods['tone']),
                _metric(
                    'Storage Evidence',
                    storage['headroom_display'],
                    storage['status'],
                    storage['tone'],
                ),
            ),
            'resources': (
                {**cpu, 'label': 'CPU'},
                {**memory, 'label': 'Memory'},
                {**pods, 'label': 'Pods'},
                {
                    'key': 'nodes',
                    'label': 'Nodes',
                    'evidence_available': total_nodes > 0,
                    'used_percent': participation,
                    'used_display': f'{ready_nodes} / {total_nodes}' if total_nodes else 'Not Available',
                    'headroom_display': f'{not_ready_nodes} Not Ready' if total_nodes else 'Not Available',
                    'status': 'Current' if total_nodes and not not_ready_nodes else 'Review',
                    'tone': 'normal' if total_nodes and not not_ready_nodes else 'warning',
                },
            ),
            'interpretation_title': (
                f"{leading['label']} is the leading committed capacity signal."
                if leading
                else 'Capacity posture requires committed evidence.'
            ),
            'interpretation_body': _executive_interpretation(leading, evidence_gap_count),
            'interpretation_note': (
                f'{ready_nodes} of {total_nodes} nodes are ready at the committed cut-off. '
                f'{evidence_gap_count} capacity evidence gap(s) remain explicit.'
                if total_nodes
                else f'{evidence_gap_count} capacity evidence gap(s) remain explicit.'
            ),
            'findings': _executive_findings(
                resources=resources,
                projections=projections,
                total_nodes=total_nodes,
                ready_nodes=ready_nodes,
            ),
        },
        'compute': {
            'metrics': (
                _metric('CPU Used', cpu['used_display'], cpu['status'], cpu['tone']),
                _metric('CPU Headroom', cpu['headroom_display'], cpu['status'], cpu['tone']),
                _metric('Memory Used', memory['used_display'], memory['status'], memory['tone']),
                _metric('Memory Headroom', memory['headroom_display'], memory['status'], memory['tone']),
            ),
            'cpu': {**cpu, 'allocation': allocations['cpu']},
            'memory': {**memory, 'allocation': allocations['memory']},
            'register': (
                _compute_register_row('C1', cpu, projections['cpu']),
                _compute_register_row('C2', memory, projections['memory']),
            ),
            'decision': (
                'Do not infer aggregate expansion need from a single workload or allocation record. '
                'Validate sustained utilization, committed requests and limits, headroom, and the '
                'approved growth plan before changing worker capacity.'
            ),
        },
        'scheduling': {
            'metrics': (
                _metric('Pod Utilization', pods['used_display'], pods['status'], pods['tone']),
                _metric('Pod Headroom', pods['headroom_display'], pods['status'], pods['tone']),
                _metric(
                    'Ready Nodes',
                    f'{ready_nodes} / {total_nodes}' if total_nodes else 'Not Available',
                    'Current' if total_nodes and not not_ready_nodes else 'Review',
                    'normal' if total_nodes and not not_ready_nodes else 'warning',
                ),
                _metric(
                    'Not Ready',
                    str(not_ready_nodes) if total_nodes else 'Not Available',
                    'Clear' if total_nodes and not not_ready_nodes else 'Review',
                    'normal' if total_nodes and not not_ready_nodes else 'warning',
                ),
            ),
            'pods': {**pods, 'allocation': allocations['pods']},
            'nodes': {
                'total': total_nodes,
                'ready': ready_nodes,
                'not_ready': not_ready_nodes,
                'workers': worker_nodes,
                'control_plane': master_nodes,
                'participation': participation,
                'donut_svg': _participation_donut_svg(participation, ready_nodes, total_nodes),
            },
            'register': (
                {
                    'ref': 'P1',
                    'resource': 'Pods',
                    'used_state': pods['used_display'],
                    'capacity': pods['capacity_display'],
                    'headroom': pods['available_display'],
                    'status': pods['status'],
                    'tone': pods['tone'],
                },
                {
                    'ref': 'N1',
                    'resource': 'Nodes',
                    'used_state': f'{ready_nodes} Ready' if total_nodes else 'Not Available',
                    'capacity': f'{total_nodes} Total' if total_nodes else 'Not Available',
                    'headroom': f'{not_ready_nodes} Not Ready' if total_nodes else 'Not Available',
                    'status': 'Current' if total_nodes and not not_ready_nodes else 'Review',
                    'tone': 'normal' if total_nodes and not not_ready_nodes else 'warning',
                },
            ),
            'interpretation': (
                f'Pod utilization is {pods["used_display"]}, leaving {pods["headroom_display"]} '
                f'reported schedulable headroom. {ready_nodes} of {total_nodes} committed nodes are ready.'
                if pods['evidence_available'] and total_nodes
                else 'Scheduling conclusions remain limited to the committed evidence available at the cut-off.'
            ),
        },
        'storage': {
            'metrics': (
                _metric('Storage Used', storage['used_value_display'], storage['status'], storage['tone']),
                _metric('Storage Capacity', storage['capacity_value_display'], storage['status'], storage['tone']),
                _metric('Storage Headroom', storage['headroom_display'], storage['status'], storage['tone']),
                _metric(
                    'Evidence Status',
                    'Ready' if storage['evidence_available'] else 'Gap',
                    storage['status'],
                    storage['tone'],
                ),
            ),
            'resource': storage,
            'requirements': (
                {
                    'ref': 'S1',
                    'evidence': 'Used Capacity',
                    'definition': 'Committed storage use in bytes or GiB',
                    'status': 'Current' if storage['evidence_available'] else 'Missing',
                    'action': 'Monitor' if storage['evidence_available'] else 'Required',
                },
                {
                    'ref': 'S2',
                    'evidence': 'Total Capacity',
                    'definition': 'Committed allocatable storage capacity',
                    'status': 'Current' if storage['evidence_available'] else 'Missing',
                    'action': 'Monitor' if storage['evidence_available'] else 'Required',
                },
                {
                    'ref': 'S3',
                    'evidence': 'Headroom',
                    'definition': 'Derived from matching scope and units',
                    'status': 'Current' if storage['evidence_available'] else 'Missing',
                    'action': 'Monitor' if storage['evidence_available'] else 'Required',
                },
                {
                    'ref': 'S4',
                    'evidence': 'Risk Evidence',
                    'definition': 'PVC, PV, filesystem, and local-volume posture',
                    'status': 'Partial' if storage['evidence_available'] else 'Missing',
                    'action': 'Validate' if storage['evidence_available'] else 'Required',
                },
            ),
            'decision': (
                'Validate committed storage units, scope, and collection time before assigning a '
                'storage capacity status.'
                if storage['evidence_available']
                else 'Collect and commit storage used, total capacity, headroom, and risk evidence '
                'for the same reporting boundary before assigning a storage capacity status.'
            ),
        },
        'forecast': {
            'metrics': (
                _metric('CPU Projection', _optional_percent(projections['cpu']), _projection_status(projections['cpu']), _projection_tone(projections['cpu'])),
                _metric('Memory Projection', _optional_percent(projections['memory']), _projection_status(projections['memory']), _projection_tone(projections['memory'])),
                _metric('Pod Projection', _optional_percent(projections['pods']), _projection_status(projections['pods']), _projection_tone(projections['pods'])),
                _metric('Warning Threshold', '70%', 'Operating Band', 'warning'),
            ),
            'chart_svg': forecast_chart,
            'available': forecast_available,
            'rows': forecast_rows,
            'method': forecast_method,
            'interpretation': _forecast_interpretation(projections),
        },
        'risks': {
            'metrics': (
                _risk_metric(
                    'Critical Risks',
                    sum(1 for row in risks if row['tone'] == 'critical'),
                    'critical',
                ),
                _risk_metric(
                    'Review Risks',
                    sum(1 for row in risks if row['tone'] == 'warning'),
                    'warning',
                ),
                _metric(
                    'Evidence Gaps',
                    str(evidence_gap_count),
                    'Requires Review' if evidence_gap_count else 'Clear',
                    'warning' if evidence_gap_count else 'normal',
                ),
                _metric('Validation Gates', str(len(recommendations)), 'Required', 'info'),
            ),
            'rows': risks,
            'interpretation': _risk_interpretation(resources, risks),
        },
        'recommendations': {
            'metrics': (
                _metric('P1 Actions', str(p1_count), 'Open' if p1_count else 'None', 'critical' if p1_count else 'normal'),
                _metric('P2 Actions', str(p2_count), 'Open' if p2_count else 'None', 'warning' if p2_count else 'normal'),
                _metric('P3 Actions', str(p3_count), 'Planned' if p3_count else 'None', 'info' if p3_count else 'normal'),
                _metric('Validation Gates', str(len(recommendations)), 'Required', 'info'),
            ),
            'rows': recommendations,
            'governance': (
                {
                    'field': 'Primary Action',
                    'requirement': recommendations[0]['title'] if recommendations else 'Continue capacity monitoring.',
                },
                {
                    'field': 'Validation Criteria',
                    'requirement': 'Confirm unit, scope, cut-off, live metric, owner, and approved response before closure.',
                },
                {
                    'field': 'Assigned Owners',
                    'requirement': _owner_summary(recommendations),
                },
                {
                    'field': 'Change Control',
                    'requirement': 'No infrastructure or workload change is authorized by this report alone.',
                },
            ),
        },
        'methodology': {
            'metrics': (
                _metric('Data Sources', str(len(source_rows)), 'Active' if source_rows else 'Not Available', 'normal' if source_rows else 'muted'),
                _metric('Coverage', f'{total_nodes} Nodes' if total_nodes else 'Not Available', namespace_scope, 'normal' if total_nodes else 'muted'),
                _metric('Forecast Method', forecast_method, 'Committed' if forecast_available else 'Optional Evidence', 'info' if forecast_available else 'muted'),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ),
            'sources': source_rows,
            'rules': (
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Headroom Bands', 'setting': 'Healthy >= 40%'},
                {'ref': 'M4', 'rule': 'Forecast Method', 'setting': forecast_method},
                {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ),
            'references': (
                {
                    'ref': 'M3',
                    'title': 'Headroom Bands',
                    'description': 'Healthy at 40% or more, Watch below 40%, and Critical below 15% remaining headroom.',
                },
                {
                    'ref': 'M4',
                    'title': 'Forecast Method',
                    'description': (
                        f'{forecast_method} is used where committed historical evidence is available.'
                        if forecast_available
                        else 'Forecast evidence was not available; current capacity remains reportable.'
                    ),
                },
                {
                    'ref': 'M5',
                    'title': 'Missing Evidence',
                    'description': 'Unavailable capacity evidence remains explicit and is never converted to zero.',
                },
            ),
        },
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _ratio_percent(numerator: int, denominator: int) -> float:
    return numerator / denominator * 100 if denominator > 0 else 0.0


def _percent(value: float) -> str:
    return f'{max(0.0, value):.1f}%'


def _optional_percent(value: float | None) -> str:
    return _percent(value) if value is not None else 'Not Available'


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _risk_metric(label: str, count: int, tone: str) -> dict[str, str]:
    return _metric(
        label,
        str(count),
        'Open' if count else 'Clear',
        tone if count else 'normal',
    )


def _capacity_resource(item: Mapping[str, Any], key: str) -> dict[str, Any]:
    evidence_available = bool(item.get('evidence_available')) or _float(item.get('capacity')) > 0
    capacity = max(0.0, _float(item.get('capacity')))
    used = max(0.0, _float(item.get('used')))
    available = max(0.0, _float(item.get('available')))
    headroom = _float(item.get('headroom')) if evidence_available else None
    if evidence_available and headroom <= 0 and capacity > 0:
        headroom = max(0.0, min(100.0, available / capacity * 100))
    used_percent = max(0.0, min(100.0, 100.0 - headroom)) if headroom is not None else 0.0
    status, tone = _headroom_status(headroom)
    unit = _RESOURCE_UNITS[key]
    return {
        'key': key,
        'label': _RESOURCE_LABELS[key],
        'unit': unit,
        'evidence_available': evidence_available,
        'capacity': capacity,
        'used': used,
        'available': available,
        'headroom': headroom,
        'used_percent': used_percent,
        'used_display': _percent(used_percent) if evidence_available else 'Not Available',
        'headroom_display': _percent(headroom) if headroom is not None else 'Not Available',
        'capacity_display': _quantity(capacity, unit) if evidence_available else 'Not Available',
        'available_display': _quantity(available, unit) if evidence_available else 'Not Available',
        'used_value_display': _quantity(used, unit) if evidence_available else 'Not Available',
        'capacity_value_display': _quantity(capacity, unit) if evidence_available else 'Not Available',
        'status': status,
        'tone': tone,
    }


def _quantity(value: float, unit: str) -> str:
    if unit == 'pods':
        return f'{int(round(value))} Pods'
    if unit == 'cores':
        return f'{value:.2f} Cores'
    return f'{value:.2f} GiB'


def _headroom_status(headroom: float | None) -> tuple[str, str]:
    if headroom is None:
        return 'Not Available', 'muted'
    if headroom < 15:
        return 'Critical', 'critical'
    if headroom < 40:
        return 'Watch', 'warning'
    return 'Healthy', 'normal'


def _allocation_resource(section: Mapping[str, Any], key: str) -> dict[str, Any]:
    status = _mapping(section.get('status'))
    rows = []
    for item in _sequence(section.get('items')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'label': sanitize_text(item.get('label'), fallback='Capacity Signal'),
                'display': sanitize_text(item.get('display'), fallback='Not Available'),
                'percent': max(0.0, min(_float(item.get('percent')), 100.0)),
                'tone': sanitize_text(item.get('tone'), fallback='muted'),
            }
        )
    return {
        'key': key,
        'title': sanitize_text(section.get('title'), fallback=_RESOURCE_LABELS[key]),
        'available': bool(section.get('available')),
        'unit': sanitize_text(section.get('unit'), fallback=_RESOURCE_UNITS[key]),
        'status': sanitize_text(status.get('label'), fallback='Unknown'),
        'tone': sanitize_text(status.get('tone'), fallback='muted'),
        'items': tuple(rows),
    }


def _forecast_percent(item: Mapping[str, Any]) -> float | None:
    if not item:
        return None
    for key in ('projected_percent', 'projection_percent', 'projected_value'):
        if item.get(key) is not None:
            return max(0.0, _float(item.get(key)))
    points = _forecast_points_percent(item)
    return points[-1] if points else None


def _history_percent(item: Mapping[str, Any]) -> list[float]:
    values = []
    for point in _sequence(item.get('historical_points')):
        if isinstance(point, Mapping):
            value = point.get('percent', point.get('value'))
            if value is not None:
                values.append(max(0.0, _float(value)))
    return values


def _forecast_points_percent(item: Mapping[str, Any]) -> list[float]:
    values = []
    for point in _sequence(item.get('forecast_points')):
        if isinstance(point, Mapping):
            value = point.get('percent', point.get('value'))
            if value is not None:
                values.append(max(0.0, _float(value)))
    return values


def _forecast_row(
    ref: str,
    key: str,
    current: float,
    projection: float | None,
) -> dict[str, str]:
    return {
        'ref': ref,
        'resource': _RESOURCE_LABELS[key],
        'current': _percent(current),
        'projection': _optional_percent(projection),
        'assessment': _projection_status(projection),
        'tone': _projection_tone(projection),
    }


def _projection_status(value: float | None) -> str:
    if value is None:
        return 'Not Available'
    if value >= 85:
        return 'Critical'
    if value >= 70:
        return 'Review'
    return 'Stable'


def _projection_tone(value: float | None) -> str:
    if value is None:
        return 'muted'
    if value >= 85:
        return 'critical'
    if value >= 70:
        return 'warning'
    return 'normal'


def _capacity_forecast_chart_svg(
    *,
    resources: Mapping[str, Mapping[str, Any]],
    forecast_items: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, float | None],
) -> str:
    if not any(value is not None for value in projections.values()):
        return _empty_chart_svg(
            'Committed forecast evidence was not available at the report cut-off.',
            'Capacity forecast unavailable',
        )

    width, height = 720, 250
    left, right, top, bottom = 58, 24, 22, 40
    inner_w = width - left - right
    inner_h = height - top - bottom
    split_x = left + inner_w * 0.68

    def point(value: float, x: float) -> tuple[float, float]:
        return x, top + inner_h * (1 - min(max(value, 0.0), 100.0) / 100.0)

    svg: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Capacity projection outlook">',
        '<style>.axis{font:11px Inter,sans-serif;fill:#64748B}</style>',
        '<rect x="1" y="1" width="718" height="248" fill="#FFFFFF" stroke="#E2E8F0"/>',
    ]
    for tick in (0, 25, 50, 70, 85):
        y = point(tick, left)[1]
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + inner_w}" y2="{y:.1f}" stroke="#E2E8F0"/>')
        svg.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>')
    for threshold, color in ((70, '#D97706'), (85, '#DC2626')):
        y = point(threshold, left)[1]
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + inner_w}" y2="{y:.1f}" stroke="{color}" stroke-dasharray="5 5"/>')
    svg.append(f'<line x1="{split_x:.1f}" y1="{top}" x2="{split_x:.1f}" y2="{top + inner_h}" stroke="#A78BFA" stroke-dasharray="4 4"/>')

    for key in ('memory', 'pods', 'cpu'):
        item = _mapping(forecast_items.get(key))
        history = _history_percent(item)
        projection_points = _forecast_points_percent(item)
        current = _float(resources[key].get('used_percent'))
        projected = projections[key]
        if not history:
            history = [current, current]
        history = history[-12:]
        history_xs = [left + (split_x - left) * index / max(len(history) - 1, 1) for index in range(len(history))]
        history_points = [point(value, x) for x, value in zip(history_xs, history)]
        color = _RESOURCE_COLORS[key]
        svg.append(
            f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in history_points)}" '
            f'fill="none" stroke="{color}" stroke-width="3"/>'
        )
        if projected is not None:
            future_values = projection_points or [projected]
            future_values = future_values[-8:]
            future_xs = [split_x + (left + inner_w - split_x) * (index + 1) / len(future_values) for index in range(len(future_values))]
            future_points = [point(value, x) for x, value in zip(future_xs, future_values)]
            start_point = point(current, split_x)
            svg.append(
                f'<polyline points="{start_point[0]:.1f},{start_point[1]:.1f} '
                f'{" ".join(f"{x:.1f},{y:.1f}" for x, y in future_points)}" '
                f'fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="8 6"/>'
            )
            end_x, end_y = future_points[-1]
            svg.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="{color}"/>')
            svg.append(f'<text x="{end_x - 4:.1f}" y="{end_y - 8:.1f}" text-anchor="end" style="font:12px Inter,sans-serif;font-weight:700;fill:{color}">{projected:.1f}%</text>')

    svg.extend(
        [
            f'<text x="{left}" y="{height - 15}" class="axis">Historical Start</text>',
            f'<text x="{split_x:.1f}" y="{height - 15}" text-anchor="middle" class="axis">Cut-off</text>',
            f'<text x="{left + inner_w}" y="{height - 15}" text-anchor="end" class="axis">Horizon</text>',
            '</svg>',
        ]
    )
    return ''.join(svg)


def _empty_chart_svg(message: str, aria_label: str) -> str:
    return f'''<svg viewBox="0 0 720 250" role="img" aria-label="{escape(aria_label)}">
<rect x="1" y="1" width="718" height="248" fill="#F8FAFC" stroke="#E2E8F0"/>
<text x="360" y="118" text-anchor="middle" style="font:700 15px Inter,sans-serif;fill:#475569">Forecast Evidence Not Available</text>
<text x="360" y="143" text-anchor="middle" style="font:12px Inter,sans-serif;fill:#64748B">{escape(message)}</text>
</svg>'''


def _participation_donut_svg(percent: float, ready_nodes: int, total_nodes: int) -> str:
    value = max(0.0, min(percent, 100.0))
    circumference = 2 * 3.141592653589793 * 52
    if value <= 0:
        progress = ''
    elif value >= 100:
        progress = '<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" stroke-width="18"/>'
    else:
        length = value / 100 * circumference
        progress = (
            f'<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" '
            f'stroke-width="18" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            'transform="rotate(-90 78 78)"/>'
        )
    label = f'{ready_nodes} / {total_nodes}' if total_nodes else 'N/A'
    return f'''<svg viewBox="0 0 156 156" role="img" aria-label="Node participation {value:.0f} percent">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="18"/>{progress}
<text x="78" y="75" text-anchor="middle" font-family="Inter, sans-serif" font-size="22" font-weight="700" fill="#1E293B">{escape(label)}</text>
<text x="78" y="94" text-anchor="middle" font-family="Inter, sans-serif" font-size="10" fill="#475569">Ready Nodes</text></svg>'''


def _compute_register_row(
    ref: str,
    resource: Mapping[str, Any],
    projection: float | None,
) -> dict[str, str]:
    interpretation = 'No aggregate capacity action'
    if not resource.get('evidence_available'):
        interpretation = 'Restore committed evidence'
    elif resource.get('tone') in {'critical', 'warning'}:
        interpretation = 'Review constrained headroom'
    elif projection is not None and projection >= 70:
        interpretation = 'Track projected threshold exposure'
    return {
        'ref': ref,
        'resource': str(resource.get('label')),
        'used': str(resource.get('used_display')),
        'headroom': str(resource.get('headroom_display')),
        'status': str(resource.get('status')),
        'tone': str(resource.get('tone')),
        'interpretation': interpretation,
    }


def _executive_interpretation(
    leading: Mapping[str, Any] | None,
    evidence_gap_count: int,
) -> str:
    if leading is None:
        return 'Committed capacity evidence was not available for the selected reporting boundary.'
    text = (
        f"{leading['label']} is the highest available utilization signal at "
        f"{leading['used_display']} with {leading['headroom_display']} remaining headroom."
    )
    if evidence_gap_count:
        text += f' {evidence_gap_count} resource domain(s) remain unavailable and must not be interpreted as healthy.'
    return text


def _executive_findings(
    *,
    resources: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, float | None],
    total_nodes: int,
    ready_nodes: int,
) -> tuple[dict[str, str], ...]:
    findings: list[dict[str, str]] = []
    storage = resources['storage']
    if not storage['evidence_available']:
        findings.append(
            {
                'ref': 'F1',
                'priority': 'P2',
                'title': 'Restore Storage Capacity Evidence',
                'owner': 'Platform Operations',
                'status': 'Review',
                'tone': 'warning',
                'description': 'Collect committed storage used, capacity, headroom, and risk evidence.',
            }
        )
    memory = resources['memory']
    findings.append(
        {
            'ref': f'F{len(findings) + 1}',
            'priority': 'P2' if memory['tone'] == 'warning' or (projections['memory'] or 0) >= 70 else 'P3',
            'title': 'Review Memory Direction',
            'owner': 'Platform Operations',
            'status': 'Review' if (projections['memory'] or 0) >= 70 else 'Planned',
            'tone': 'warning' if (projections['memory'] or 0) >= 70 else 'info',
            'description': 'Retain current memory headroom and committed projection evidence in the next capacity gate.',
        }
    )
    findings.append(
        {
            'ref': f'F{len(findings) + 1}',
            'priority': 'P3',
            'title': 'Maintain Scheduling Capacity Evidence',
            'owner': 'Platform Operations',
            'status': 'Current' if total_nodes and ready_nodes == total_nodes else 'Review',
            'tone': 'normal' if total_nodes and ready_nodes == total_nodes else 'warning',
            'description': 'Keep pod headroom and node participation visible at the committed boundary.',
        }
    )
    return tuple(findings[:3])


def _risk_rows(
    *,
    payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
    allocations: Mapping[str, Mapping[str, Any]],
    total_nodes: int,
    ready_nodes: int,
    projections: Mapping[str, float | None],
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in _sequence(payload.get('risk_summary')):
        if not isinstance(item, Mapping):
            continue
        key = str(item.get('resource') or '').lower()
        if key not in resources:
            continue
        resource = resources[key]
        status = _mapping(item.get('status'))
        tone = sanitize_text(status.get('tone'), fallback=resource['tone'])
        label = sanitize_text(status.get('label'), fallback=resource['status'])
        if not resource['evidence_available']:
            title = f'{resource["label"]} Evidence Gap'
            impact = 'Medium'
            priority = 'P2'
            tone = 'warning'
            label = 'Open'
            description = f'Committed {resource["label"].lower()} capacity evidence is unavailable.'
        else:
            title = f'{resource["label"]} Headroom'
            impact = 'High' if tone == 'critical' else 'Medium' if tone == 'warning' else 'Low'
            priority = 'P1' if tone == 'critical' else 'P2' if tone == 'warning' else 'P3'
            description = f'{resource["headroom_display"]} remaining committed headroom.'
        rows.append(
            {
                'ref': f'R{len(rows) + 1}',
                'title': title,
                'priority': priority,
                'impact': impact,
                'owner': 'Platform Operations',
                'status': label,
                'tone': tone,
                'description': description,
            }
        )

    for key in ('cpu', 'memory', 'pods'):
        allocation = allocations[key]
        if allocation['tone'] not in {'warning', 'critical'}:
            continue
        rows.append(
            {
                'ref': f'R{len(rows) + 1}',
                'title': f'{_RESOURCE_LABELS[key]} Allocation Pressure',
                'priority': 'P1' if allocation['tone'] == 'critical' else 'P2',
                'impact': 'High' if allocation['tone'] == 'critical' else 'Medium',
                'owner': 'Platform Operations',
                'status': allocation['status'],
                'tone': allocation['tone'],
                'description': f'Allocation status is {allocation["status"]}; validate requests, limits, actual use, and peak use.',
            }
        )

    if total_nodes and ready_nodes < total_nodes:
        rows.append(
            {
                'ref': f'R{len(rows) + 1}',
                'title': 'Node Participation Gap',
                'priority': 'P2',
                'impact': 'Medium',
                'owner': 'Platform Operations',
                'status': 'Open',
                'tone': 'warning',
                'description': f'{total_nodes - ready_nodes} node(s) are not ready and excluded from active capacity assumptions.',
            }
        )
    if projections['memory'] is not None and projections['memory'] >= 70:
        rows.append(
            {
                'ref': f'R{len(rows) + 1}',
                'title': 'Memory Forecast Threshold',
                'priority': 'P2',
                'impact': 'Medium',
                'owner': 'Platform Operations',
                'status': 'Review',
                'tone': 'warning',
                'description': f'Memory projects to {_percent(projections["memory"])} within the committed planning horizon.',
            }
        )

    if not rows:
        rows.append(
            {
                'ref': 'R1',
                'title': 'Capacity Baseline',
                'priority': 'P3',
                'impact': 'Low',
                'owner': 'Platform Operations',
                'status': 'Current',
                'tone': 'normal',
                'description': 'No critical or warning capacity condition was detected.',
            }
        )
    return tuple(rows[:6])


def _recommendation_rows(
    *,
    payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, float | None],
    total_nodes: int,
    ready_nodes: int,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for card in _sequence(payload.get('recommendation_cards')):
        if not isinstance(card, Mapping):
            continue
        title = sanitize_text(card.get('title'), fallback='Review Capacity Evidence')
        description = sanitize_text(card.get('description'), fallback='Validate the committed capacity evidence.')
        priority = _priority_code(card.get('priority'))
        owner = 'Observability Owner' if 'coverage' in title.lower() or 'prometheus' in title.lower() else 'Platform Operations'
        rows.append(
            {
                'ref': f'A{len(rows) + 1}',
                'priority': priority,
                'title': title,
                'owner': owner,
                'target': 'This Week' if priority == 'P1' else 'Next Week' if priority == 'P2' else 'This Month',
                'status': 'Open' if priority in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if priority == 'P1' else 'warning' if priority == 'P2' else 'info',
                'description': description,
            }
        )

    fallback: list[tuple[str, str, str, str]] = []
    if not resources['storage']['evidence_available']:
        fallback.append(
            (
                'P2',
                'Restore Storage Capacity Evidence',
                'Commit storage used, total capacity, headroom, and risk evidence for the selected boundary.',
                'Platform Operations',
            )
        )
    fallback.extend(
        [
            (
                'P2' if (projections['memory'] or 0) >= 70 else 'P3',
                'Review Memory Growth Direction',
                'Validate current memory headroom and committed forecast threshold exposure.',
                'Platform Operations',
            ),
            (
                'P3',
                'Validate Pod Capacity Scope',
                'Confirm pod utilization, capacity, and remaining slots share a documented scope.',
                'Platform Operations',
            ),
            (
                'P3',
                'Maintain Node Participation Evidence',
                'Keep not-ready nodes visible and excluded from active capacity assumptions.',
                'Platform Operations',
            ),
            (
                'P3',
                'Maintain Capacity Dataset Coverage',
                'Maintain committed utilization, allocation, forecast, and freshness evidence.',
                'Observability Owner',
            ),
        ]
    )

    existing = {row['title'].lower() for row in rows}
    for priority, title, description, owner in fallback:
        if title.lower() in existing:
            continue
        rows.append(
            {
                'ref': f'A{len(rows) + 1}',
                'priority': priority,
                'title': title,
                'owner': owner,
                'target': 'Next Week' if priority == 'P2' else 'This Month',
                'status': 'Open' if priority == 'P2' else 'Planned',
                'tone': 'warning' if priority == 'P2' else 'info',
                'description': description,
            }
        )
        existing.add(title.lower())
        if len(rows) >= 5:
            break

    if total_nodes and ready_nodes < total_nodes and len(rows) < 5:
        rows.append(
            {
                'ref': f'A{len(rows) + 1}',
                'priority': 'P2',
                'title': 'Restore Ready Node Participation',
                'owner': 'Platform Operations',
                'target': 'Next Week',
                'status': 'Open',
                'tone': 'warning',
                'description': 'Restore or formally exclude not-ready nodes before relying on schedulable capacity.',
            }
        )

    priority_order = {'P1': 0, 'P2': 1, 'P3': 2}
    selected = sorted(
        rows,
        key=lambda row: (priority_order.get(row['priority'], 3), row['title']),
    )[:5]
    for index, row in enumerate(selected, start=1):
        row['ref'] = f'A{index}'
    return tuple(selected)


def _priority_code(value: Any) -> str:
    normalized = sanitize_text(value, fallback='Info').lower()
    if normalized in {'p1', 'critical', 'urgent', 'high'}:
        return 'P1'
    if normalized in {'p2', 'warning', 'review', 'medium'}:
        return 'P2'
    return 'P3'


def _owner_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        owner = sanitize_text(row.get('owner'), fallback='Unassigned')
        counts[owner] = counts.get(owner, 0) + 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No action owner assigned.'


def _source_rows(
    *,
    payload: Mapping[str, Any],
    prometheus_status: Mapping[str, Any],
    forecast_payload: Mapping[str, Any],
    period_label: str,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in _sequence(payload.get('source_evidence')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'source': sanitize_text(item.get('source'), fallback='Capacity Evidence'),
                'freshness': sanitize_text(item.get('freshness'), fallback='Not Available'),
                'last_collected': _format_datetime(item.get('last_collected')),
            }
        )
    if not rows:
        rows = [
            {
                'source': 'Prometheus Observation Cache',
                'freshness': _latency(prometheus_status.get('response_time_ms')),
                'last_collected': _format_datetime(prometheus_status.get('last_checked_at')),
            },
            {
                'source': 'Kubernetes Cluster Scope',
                'freshness': 'Committed',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Capacity Analysis Evidence',
                'freshness': period_label,
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Forecast Evidence',
                'freshness': sanitize_text(forecast_payload.get('forecast_horizon'), fallback='Not Available'),
                'last_collected': _format_datetime(forecast_payload.get('generated_at')),
            },
        ]
    return tuple(rows[:4])


def _format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.strftime('%d %b %Y %H:%M UTC')
    text = sanitize_text(value, fallback='Not Available')
    return text


def _latency(value: Any) -> str:
    try:
        return f'{float(value):.0f} ms'
    except (TypeError, ValueError):
        return 'Not Available'


def _forecast_interpretation(projections: Mapping[str, float | None]) -> str:
    available = {key: value for key, value in projections.items() if value is not None}
    if not available:
        return 'Committed forecast evidence was not available; planning conclusions remain limited to current capacity.'
    constrained_key, constrained_value = max(available.items(), key=lambda item: item[1])
    if constrained_value >= 85:
        return f'{_RESOURCE_LABELS[constrained_key]} projects into the critical operating band and requires an approved response.'
    if constrained_value >= 70:
        return f'{_RESOURCE_LABELS[constrained_key]} projects into the warning band and requires planning review.'
    return 'No displayed resource is projected to enter the warning band within the committed planning horizon.'


def _risk_interpretation(
    resources: Mapping[str, Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> str:
    if any(row.get('tone') == 'critical' for row in rows):
        return 'At least one capacity condition is critical and requires immediate validation against live state.'
    gaps = [item['label'] for item in resources.values() if not item['evidence_available']]
    if gaps:
        return f'Current available signals do not indicate critical saturation, but {", ".join(gaps)} evidence is incomplete.'
    if any(row.get('tone') == 'warning' for row in rows):
        return 'Available capacity remains serviceable, with review items that require ownership and validation.'
    return 'Available capacity evidence is healthy within the committed reporting boundary.'
