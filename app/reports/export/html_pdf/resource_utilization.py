from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
)
from app.reports.export.html_pdf.normalization import sanitize_text

_RESOURCE_UTILIZATION_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'CPU Utilization',
    'Memory Utilization',
    'Pod and Node Utilization',
    'Utilization Distribution',
    'Trend Evidence',
    'Recommendation Plan',
    'Methodology and Evidence Boundary',
)

_RESOURCE_COLORS = {
    'cpu': '#2563EB',
    'memory': '#7C3AED',
    'pods': '#15803D',
}


def build_resource_utilization_presentation(
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
    summary = _mapping(payload.get('summary'))
    cluster = _mapping(payload.get('cluster'))
    cluster_info = _mapping(payload.get('cluster_info'))
    risk = _mapping(payload.get('risk_assessment'))
    prometheus_status = _mapping(payload.get('prometheus_status'))
    trends = _mapping(payload.get('trends'))
    forecast_payload = _mapping(payload.get('forecast_payload'))

    cpu = _resource_metric(summary, risk, 'cpu')
    memory = _resource_metric(summary, risk, 'memory')
    storage = _resource_metric(summary, risk, 'storage')
    pods = _resource_metric(summary, risk, 'pod', display_key='pods')

    total_nodes = _int(cluster_info.get('total_nodes'))
    ready_nodes = _int(cluster_info.get('ready_nodes'))
    not_ready_nodes = _int(cluster_info.get('not_ready_nodes'))
    node_participation = _ratio_percent(ready_nodes, total_nodes)

    cpu_consumers = _consumer_rows(_sequence(payload.get('top_cpu_consumers')), resource='CPU')
    memory_consumers = _consumer_rows(
        _sequence(payload.get('top_memory_consumers')),
        resource='Memory',
    )
    _normalize_consumer_bars(cpu_consumers)
    _normalize_consumer_bars(memory_consumers)

    forecast_items = {
        str(item.get('key') or '').lower(): item
        for item in _sequence(forecast_payload.get('items'))
        if isinstance(item, Mapping)
    }
    cpu_forecast = _mapping(forecast_items.get('cpu'))
    memory_forecast = _mapping(forecast_items.get('memory'))
    pod_forecast = _mapping(forecast_items.get('pods'))

    cpu_history = _history_percent(cpu_forecast) or _trend_values(trends.get('cpu'))
    memory_history = _history_percent(memory_forecast) or _trend_values(trends.get('memory'))
    pod_history = _history_percent(pod_forecast) or _trend_values(trends.get('pods'))

    cpu_projection = _forecast_percent(cpu_forecast)
    memory_projection = _forecast_percent(memory_forecast)
    pod_projection = _forecast_percent(pod_forecast)

    cpu_chart = _single_resource_chart_svg(
        cpu_history,
        projection=_forecast_points_percent(cpu_forecast),
        color=_RESOURCE_COLORS['cpu'],
        current=cpu['percent'],
        projected=cpu_projection,
        aria_label='CPU utilization direction',
    )
    memory_chart = _single_resource_chart_svg(
        memory_history,
        projection=_forecast_points_percent(memory_forecast),
        color=_RESOURCE_COLORS['memory'],
        current=memory['percent'],
        projected=memory_projection,
        aria_label='Memory utilization direction and projection',
    )
    trend_chart = _combined_trend_chart_svg(
        {
            'memory': {
                'history': memory_history,
                'projection': _forecast_points_percent(memory_forecast),
                'current': memory['percent'],
                'projected': memory_projection,
            },
            'pods': {
                'history': pod_history,
                'projection': _forecast_points_percent(pod_forecast),
                'current': pods['percent'],
                'projected': pod_projection,
            },
            'cpu': {
                'history': cpu_history,
                'projection': _forecast_points_percent(cpu_forecast),
                'current': cpu['percent'],
                'projected': cpu_projection,
            },
        }
    )

    leading = max((cpu, memory, pods), key=lambda item: item['percent'])
    forecast_method = sanitize_text(
        forecast_payload.get('method_label') or forecast_payload.get('forecast_method'),
        fallback='Not Available',
    )
    forecast_confidence = _forecast_confidence(forecast_items)

    recommendations = _recommendations(
        cpu=cpu,
        memory=memory,
        pods=pods,
        total_nodes=total_nodes,
        ready_nodes=ready_nodes,
        cpu_consumers=cpu_consumers,
        memory_projection=memory_projection,
        forecast_available=bool(forecast_items),
        prometheus_status=prometheus_status,
    )

    source_rows = _source_rows(payload, prometheus_status, forecast_payload, period_label)
    methodology = {
        'metrics': (
            _metric(
                'Data Sources',
                str(len(source_rows)),
                'Active' if source_rows else 'Not Available',
                'normal' if source_rows else 'muted',
            ),
            _metric(
                'Coverage',
                f'{total_nodes} Nodes' if total_nodes else 'Not Available',
                namespace_scope,
                'normal' if total_nodes else 'muted',
            ),
            _metric(
                'Forecast Method',
                forecast_method,
                'Committed' if forecast_items else 'Optional Evidence',
                'info' if forecast_items else 'muted',
            ),
            _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ),
        'sources': source_rows,
        'rules': (
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
            {'ref': 'M3', 'rule': 'Threshold Bands', 'setting': '70% / 85%'},
            {'ref': 'M4', 'rule': 'Forecast Method', 'setting': forecast_method},
            {'ref': 'M5', 'rule': 'Utilization Basis', 'setting': 'P95 + committed state'},
        ),
        'references': (
            {
                'ref': 'M3',
                'title': 'Threshold Bands',
                'description': 'Normal below 70%, warning from 70% to 84.9%, and critical at 85% or above.',
            },
            {
                'ref': 'M4',
                'title': 'Forecast Method',
                'description': (
                    f'{forecast_method} is used where committed historical evidence is available.'
                    if forecast_items
                    else 'Forecast evidence was not available; current utilization remains reportable.'
                ),
            },
            {
                'ref': 'M5',
                'title': 'Utilization Basis',
                'description': (
                    'Shared-resource posture uses committed summary metrics and P95 where the '
                    'dataset provides it.'
                ),
            },
        ),
    }

    return {
        'page_count': len(_RESOURCE_UTILIZATION_PAGE_TITLES),
        'presentation_version': 'v1.0-resource-utilization-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': {
            'paper': 'A4 Portrait',
            'page_count': 9,
            'fixed_page_canvas': True,
            'status_style': 'plain-colored-text',
            'table_policy': 'single-line-technical-registers',
            'visual_style': 'kaori-resource-utilization-v1',
        },
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Resource Utilization',
        'report_subtitle': 'Kubernetes Operational Intelligence Report',
        'classification': classification,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'page_titles': _RESOURCE_UTILIZATION_PAGE_TITLES,
        'cover': {
            'cluster': sanitize_text(cluster.get('name'), fallback=cluster_scope),
            'environment': sanitize_text(cluster.get('environment'), fallback='Not Available'),
            'purpose': (
                'Support operational review of shared-resource use, saturation direction, '
                'concentration, and accountable utilization actions.'
            ),
            'context': (
                'Use the report cut-off as the evidence boundary. Confirm live state, workload ownership, '
                'and approved change controls before remediation.'
            ),
        },
        'executive': {
            'metrics': (
                _metric('CPU P95', cpu['value'], cpu['status'], cpu['tone']),
                _metric('Memory P95', memory['value'], memory['status'], memory['tone']),
                _metric('Pod Utilization', pods['value'], pods['status'], pods['tone']),
                _metric(
                    'Coverage',
                    _percent(node_participation),
                    'Current' if total_nodes else 'Not Available',
                    'normal' if total_nodes and not not_ready_nodes else 'warning',
                ),
            ),
            'resources': (
                {**cpu, 'label': 'CPU'},
                {**memory, 'label': 'Memory'},
                {**pods, 'label': 'Pods'},
                {
                    'label': 'Nodes',
                    'percent': node_participation,
                    'value': f'{ready_nodes} / {total_nodes}' if total_nodes else 'Not Available',
                    'status': 'Current' if total_nodes and not not_ready_nodes else 'Review',
                    'tone': 'normal' if total_nodes and not not_ready_nodes else 'warning',
                },
            ),
            'leading_title': f"{leading['label']} is the leading shared-resource signal.",
            'leading_body': _leading_interpretation(leading),
            'leading_note': (
                'CPU and pod utilization remain within normal operating bands. '
                f'{ready_nodes} of {total_nodes} nodes are ready at the committed cut-off.'
                if total_nodes
                else 'Node participation evidence was not available at the committed cut-off.'
            ),
            'findings': _priority_findings(
                memory=memory,
                cpu_consumers=cpu_consumers,
                forecast_available=bool(forecast_items),
                source_rows=source_rows,
            ),
        },
        'cpu': {
            'metrics': (
                _metric('Current Signal', cpu['value'], cpu['status'], cpu['tone']),
                _metric('P95', cpu['value'], cpu['status'], cpu['tone']),
                _metric('Headroom', _percent(cpu['headroom']), 'Available', 'normal'),
                _metric(
                    'Highest Displayed',
                    _consumer_value(cpu_consumers, 0, unit='cores'),
                    'cores',
                    'warning' if cpu_consumers else 'muted',
                ),
            ),
            'chart_svg': cpu_chart,
            'chart_available': bool(cpu_history),
            'consumers': cpu_consumers[:3],
            'assessment_title': (
                'CPU pressure is not currently a capacity constraint.'
                if cpu['percent'] < 70
                else 'CPU utilization requires operational review.'
            ),
            'assessment_body': _cpu_assessment(cpu, cpu_consumers),
            'assessment_note': (
                'Low aggregate utilization can coexist with short-lived workload spikes; '
                'live-state validation remains required.'
            ),
            'decision': (
                'Validate whether the highest displayed CPU consumers are expected for the selected '
                'reporting boundary. Do not infer aggregate expansion need from a single consumer record.'
            ),
        },
        'memory': {
            'metrics': (
                _metric('Current Signal', memory['value'], memory['status'], memory['tone']),
                _metric('P95', memory['value'], memory['status'], memory['tone']),
                _metric(
                    'Headroom',
                    _percent(memory['headroom']),
                    'Available',
                    'normal' if memory['headroom'] > 15 else 'warning',
                ),
                _metric(
                    'Projection',
                    _optional_percent(memory_projection),
                    _forecast_eta(memory_forecast),
                    (
                        'warning'
                        if memory_projection is not None and memory_projection >= 70
                        else 'info'
                    ),
                ),
            ),
            'chart_svg': memory_chart,
            'chart_available': bool(memory_history),
            'projection_available': memory_projection is not None,
            'consumers': memory_consumers[:3],
            'assessment_title': _memory_assessment_title(memory, memory_projection),
            'assessment_body': _memory_assessment_body(memory, memory_projection),
            'assessment_note': (
                'Projection supports planning, not autonomous remediation. Approved deployments and '
                'infrastructure changes remain outside the model.'
            ),
            'decision': (
                'Confirm whether the displayed memory concentration is expected and include any forecast '
                'threshold exposure in the next capacity planning gate.'
            ),
        },
        'pod_node': {
            'metrics': (
                _metric('Pod Utilization', pods['value'], pods['status'], pods['tone']),
                _metric('Pod Headroom', _percent(pods['headroom']), 'Available', 'normal'),
                _metric(
                    'Ready Nodes',
                    f'{ready_nodes} / {total_nodes}' if total_nodes else 'Not Available',
                    'Current' if not not_ready_nodes else 'Review',
                    'normal' if total_nodes and not not_ready_nodes else 'warning',
                ),
                _metric(
                    'Not Ready',
                    str(not_ready_nodes),
                    'Clear' if not not_ready_nodes else 'Review',
                    'normal' if not not_ready_nodes else 'critical',
                ),
            ),
            'pods_used': pods['percent'],
            'pods_headroom': pods['headroom'],
            'pod_capacity': _int(summary.get('pod_capacity')),
            'pod_count': _int(summary.get('pod_count')),
            'ready_nodes': ready_nodes,
            'not_ready_nodes': not_ready_nodes,
            'total_nodes': total_nodes,
            'participation': node_participation,
            'node_donut_svg': _participation_donut_svg(node_participation, ready_nodes),
            'register': (
                {
                    'ref': 'P1',
                    'resource': 'Pods',
                    'used': pods['value'],
                    'capacity': (
                        f"{_int(summary.get('pod_capacity'))} Total"
                        if summary.get('pod_capacity') is not None
                        else 'Not Available'
                    ),
                    'headroom': (
                        f"{max(_int(summary.get('pod_capacity')) - _int(summary.get('pod_count')), 0)} "
                        'Remaining'
                        if summary.get('pod_capacity') is not None
                        else 'Not Available'
                    ),
                    'status': pods['status'],
                    'tone': pods['tone'],
                },
                {
                    'ref': 'N1',
                    'resource': 'Nodes',
                    'used': f'{ready_nodes} Ready' if total_nodes else 'Not Available',
                    'capacity': f'{total_nodes} Total' if total_nodes else 'Not Available',
                    'headroom': f'{not_ready_nodes} Not Ready' if total_nodes else 'Not Available',
                    'status': 'Current' if total_nodes and not not_ready_nodes else 'Review',
                    'tone': 'normal' if total_nodes and not not_ready_nodes else 'warning',
                },
            ),
            'interpretation': (
                f"Pod utilization is {_percent(pods['percent'])}, leaving "
                f"{_percent(pods['headroom'])} schedulable headroom. "
                f'{ready_nodes} of {total_nodes} committed nodes are ready.'
                if total_nodes
                else 'Pod utilization is available, but node participation evidence was not returned.'
            ),
        },
        'distribution': {
            'memory_total': sum(item['raw_value'] for item in memory_consumers[:3]),
            'memory_donut_svg': _donut_svg(memory_consumers[:3]),
            'memory_consumers': memory_consumers[:3],
            'cpu_consumers': cpu_consumers[:3],
            'register': _consumer_register(memory_consumers[:3], cpu_consumers[:3]),
            'interpretation': _distribution_interpretation(memory_consumers, cpu_consumers),
        },
        'trend': {
            'metrics': (
                _metric('CPU Direction', _trend_direction(cpu_history), cpu['value'], _direction_tone(cpu_history)),
                _metric(
                    'Memory Direction',
                    _trend_direction(memory_history),
                    memory['value'],
                    _direction_tone(memory_history),
                ),
                _metric('Pod Direction', _trend_direction(pod_history), pods['value'], _direction_tone(pod_history)),
                _metric(
                    'Forecast Confidence',
                    forecast_confidence,
                    'Committed' if forecast_items else 'Not Available',
                    'normal' if forecast_items else 'muted',
                ),
            ),
            'chart_svg': trend_chart,
            'chart_available': any((cpu_history, memory_history, pod_history)),
            'rows': (
                _trend_row('T1', 'CPU', cpu['percent'], cpu_projection, cpu_history),
                _trend_row('T2', 'Memory', memory['percent'], memory_projection, memory_history),
                _trend_row('T3', 'Pods', pods['percent'], pod_projection, pod_history),
            ),
            'interpretation': _trend_interpretation(memory_projection, memory),
            'evidence': (
                'Forecast values use committed historical observations. Planned deployments, approved '
                'infrastructure expansion, workload migrations, and live state after the report cut-off '
                'are not modeled.'
                if forecast_items
                else (
                    'Historical utilization remains visible, but forecast evidence was not '
                    'available for this report run.'
                )
            ),
        },
        'recommendations': recommendations,
        'methodology': methodology,
        'storage_context': storage,
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


def _percent(value: float) -> str:
    return f'{max(0.0, min(100.0, value)):.1f}%'


def _optional_percent(value: float | None) -> str:
    return _percent(value) if value is not None else 'Not Available'


def _ratio_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(100.0, numerator / denominator * 100.0))


def _resource_metric(
    summary: Mapping[str, Any],
    risk: Mapping[str, Any],
    key: str,
    *,
    display_key: str | None = None,
) -> dict[str, Any]:
    risk_key = display_key or key
    risk_item = _mapping(risk.get(risk_key))
    raw = _float(summary.get(f'{key}_utilization'))
    status = sanitize_text(risk_item.get('status'), fallback=_status_for_percent(raw))
    tone = _tone_for_status(status, raw)
    return {
        'label': (display_key or key).title(),
        'percent': max(0.0, min(100.0, raw)),
        'value': _percent(raw),
        'headroom': max(0.0, 100.0 - raw),
        'status': status,
        'tone': tone,
        'reason': sanitize_text(risk_item.get('reason'), fallback=f'Utilization {_percent(raw)}'),
    }


def _status_for_percent(value: float) -> str:
    if value >= 85:
        return 'Critical'
    if value >= 70:
        return 'Review'
    return 'Normal'


def _tone_for_status(status: str, value: float = 0.0) -> str:
    normalized = status.strip().lower()
    if normalized in {'critical', 'failed', 'unavailable'} or value >= 85:
        return 'critical'
    if normalized in {'warning', 'review', 'attention', 'degraded'} or value >= 70:
        return 'warning'
    if normalized in {'normal', 'healthy', 'ready', 'current', 'clear'}:
        return 'normal'
    return 'muted'


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _consumer_rows(items: list[Any], *, resource: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        raw_value = max(0.0, _float(item.get('value')))
        result.append(
            {
                'name': sanitize_text(item.get('pod') or item.get('name'), fallback='Unknown Resource'),
                'namespace': sanitize_text(item.get('namespace'), fallback='-'),
                'resource': resource,
                'raw_value': raw_value,
                'value': f'{raw_value:.2f} cores' if resource == 'CPU' else f'{raw_value:.2f} GiB',
                'bar_percent': 0.0,
                'share_percent': 0.0,
            }
        )
    return result


def _normalize_consumer_bars(items: list[dict[str, Any]]) -> None:
    max_value = max((item['raw_value'] for item in items), default=0.0)
    total = sum(item['raw_value'] for item in items)
    for item in items:
        item['bar_percent'] = (item['raw_value'] / max_value * 100.0) if max_value else 0.0
        item['share_percent'] = (item['raw_value'] / total * 100.0) if total else 0.0


def _consumer_value(items: list[dict[str, Any]], index: int, *, unit: str) -> str:
    if len(items) <= index:
        return 'Not Available'
    return f"{items[index]['raw_value']:.2f}"


def _history_percent(item: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    for point in _sequence(item.get('historical_points')):
        if not isinstance(point, Mapping) or point.get('percent') is None:
            continue
        values.append(max(0.0, min(100.0, _float(point.get('percent')))))
    return values


def _forecast_points_percent(item: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    for point in _sequence(item.get('forecast_points')):
        if not isinstance(point, Mapping) or point.get('percent') is None:
            continue
        values.append(max(0.0, min(100.0, _float(point.get('percent')))))
    return values


def _forecast_percent(item: Mapping[str, Any]) -> float | None:
    value = item.get('projected_percent')
    if value is None:
        return None
    return max(0.0, min(100.0, _float(value)))


def _trend_values(value: Any) -> list[float]:
    result: list[float] = []
    for point in _sequence(value):
        if not isinstance(point, Mapping):
            continue
        raw = point.get('value')
        if raw is None:
            continue
        result.append(max(0.0, min(100.0, _float(raw))))
    return result


def _downsample(values: list[float], limit: int = 24) -> list[float]:
    if len(values) <= limit:
        return values
    step = (len(values) - 1) / (limit - 1)
    return [values[round(index * step)] for index in range(limit)]


def _single_resource_chart_svg(
    history: list[float],
    *,
    projection: list[float],
    color: str,
    current: float,
    projected: float | None,
    aria_label: str,
) -> str:
    history = _downsample(history)
    projection = _downsample(projection, limit=12)
    if not history:
        return _empty_chart_svg('Historical utilization evidence is not available.', aria_label)

    width, height = 720, 250
    left, right, top, bottom = 55, 18, 20, 42
    inner_w = width - left - right
    inner_h = height - top - bottom
    split_x = left + inner_w * (0.66 if projection else 1.0)

    def y(value: float) -> float:
        return top + (100.0 - value) / 100.0 * inner_h

    history_width = split_x - left
    history_points = []
    for index, value in enumerate(history):
        x = left + (index / max(1, len(history) - 1)) * history_width
        history_points.append((x, y(value)))

    projection_points: list[tuple[float, float]] = []
    if projection:
        projection_values = [history[-1], *projection]
        for index, value in enumerate(projection_values):
            x = split_x + (index / max(1, len(projection_values) - 1)) * (left + inner_w - split_x)
            projection_points.append((x, y(value)))

    history_polyline = ' '.join(f'{x:.1f},{yy:.1f}' for x, yy in history_points)
    projection_polyline = ' '.join(f'{x:.1f},{yy:.1f}' for x, yy in projection_points)
    current_x, current_y = history_points[-1]
    end_value = projected if projected is not None else current
    end_x, end_y = projection_points[-1] if projection_points else history_points[-1]

    grid = ''.join(
        f'<line x1="{left}" y1="{y(tick):.1f}" x2="{left + inner_w}" y2="{y(tick):.1f}" class="grid"/>'
        f'<text x="{left - 13}" y="{y(tick) + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>'
        for tick in (0, 50, 70, 85)
    )
    split = (
        f'<line x1="{split_x:.1f}" y1="{top}" x2="{split_x:.1f}" y2="{top + inner_h}" class="split"/>'
        if projection
        else ''
    )
    projection_svg = (
        f'<polyline points="{projection_polyline}" class="projection" style="stroke:{color}"/>'
        if projection_polyline
        else ''
    )
    horizon_label = '<text x="675" y="238" text-anchor="middle" class="axis">Horizon</text>' if projection else ''

    return f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(aria_label)}">
<style>
.grid{{stroke:#E2E8F0;stroke-width:1}}.axis{{font:12px Inter,sans-serif;fill:#64748B}}
.warning-line{{stroke:#D97706;stroke-width:1.2;stroke-dasharray:6 5}}
.critical-line{{stroke:#DC2626;stroke-width:1.2;stroke-dasharray:6 5}}
.history{{fill:none;stroke:{color};stroke-width:4;stroke-linejoin:round;stroke-linecap:round}}
.projection{{fill:none;stroke-width:4;stroke-dasharray:8 6;stroke-linejoin:round;stroke-linecap:round}}
.split{{stroke:#A78BFA;stroke-width:1.2;stroke-dasharray:4 4}}
.label{{font:13px Inter,sans-serif;font-weight:700;fill:#111827}}
</style>{grid}
<line x1="{left}" y1="{y(70):.1f}" x2="{left + inner_w}" y2="{y(70):.1f}" class="warning-line"/>
<line x1="{left}" y1="{y(85):.1f}" x2="{left + inner_w}" y2="{y(85):.1f}" class="critical-line"/>{split}
<polyline points="{history_polyline}" class="history"/>{projection_svg}
<circle cx="{current_x:.1f}" cy="{current_y:.1f}" r="4.5" fill="{color}"/>
<text x="{current_x - 8:.1f}" y="{current_y - 10:.1f}" text-anchor="end" class="label">{_percent(current)}</text>
<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" fill="{color}"/>
<text x="{end_x - 5:.1f}" y="{end_y - 10:.1f}" text-anchor="end" class="label">{_percent(end_value)}</text>
<text x="{left}" y="238" class="axis">Historical</text>
<text x="{split_x:.1f}" y="238" text-anchor="middle" class="axis">Cut-off</text>{horizon_label}
</svg>'''


def _combined_trend_chart_svg(resources: Mapping[str, Mapping[str, Any]]) -> str:
    available = [item for item in resources.values() if item.get('history')]
    if not available:
        return _empty_chart_svg('Committed historical trend evidence is not available.', 'Resource trend outlook')

    width, height = 760, 280
    left, right, top, bottom = 58, 20, 20, 45
    inner_w = width - left - right
    inner_h = height - top - bottom
    has_projection = any(item.get('projection') for item in available)
    split_x = left + inner_w * (0.68 if has_projection else 1.0)

    def y(value: float) -> float:
        return top + (100.0 - max(0.0, min(100.0, value))) / 100.0 * inner_h

    grid = ''.join(
        f'<line x1="{left}" y1="{y(tick):.1f}" x2="{left + inner_w}" y2="{y(tick):.1f}" class="grid"/>'
        f'<text x="{left - 14}" y="{y(tick) + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>'
        for tick in (0, 25, 50, 70, 85)
    )
    lines: list[str] = []
    labels: list[str] = []
    for key in ('memory', 'pods', 'cpu'):
        item = resources.get(key) or {}
        history = _downsample(list(item.get('history') or []))
        if not history:
            continue
        color = _RESOURCE_COLORS[key]
        history_points = []
        for index, value in enumerate(history):
            x = left + (index / max(1, len(history) - 1)) * (split_x - left)
            history_points.append((x, y(value)))
        lines.append(
            f'<polyline points="{" ".join(f"{x:.1f},{yy:.1f}" for x, yy in history_points)}" '
            f'fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        projection = _downsample(list(item.get('projection') or []), limit=12)
        end_x, end_y = history_points[-1]
        end_value = _float(item.get('current'))
        if projection:
            projection_values = [history[-1], *projection]
            projection_points = []
            for index, value in enumerate(projection_values):
                x = split_x + (index / max(1, len(projection_values) - 1)) * (left + inner_w - split_x)
                projection_points.append((x, y(value)))
            lines.append(
                f'<polyline points="{" ".join(f"{x:.1f},{yy:.1f}" for x, yy in projection_points)}" '
                f'fill="none" stroke="{color}" stroke-width="4" stroke-dasharray="8 6" '
                'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            end_x, end_y = projection_points[-1]
            end_value = _float(item.get('projected'), default=projection[-1])
        labels.append(
            f'<text x="{end_x - 4:.1f}" y="{end_y - 8:.1f}" text-anchor="end" '
            f'style="font:13px Inter,sans-serif;font-weight:700;fill:{color}">{_percent(end_value)}</text>'
        )

    split = (
        f'<line x1="{split_x:.1f}" y1="{top}" x2="{split_x:.1f}" '
        f'y2="{top + inner_h}" stroke="#A78BFA" stroke-width="1.2" '
        'stroke-dasharray="4 4"/>'
        if has_projection
        else ''
    )
    return f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="Resource trend outlook">
<style>.grid{{stroke:#E2E8F0;stroke-width:1}}.axis{{font:12px Inter,sans-serif;fill:#64748B}}</style>{grid}
<line x1="{left}" y1="{y(70):.1f}" x2="{left + inner_w}"
 y2="{y(70):.1f}" stroke="#D97706" stroke-width="1.2" stroke-dasharray="6 5"/>
<line x1="{left}" y1="{y(85):.1f}" x2="{left + inner_w}"
 y2="{y(85):.1f}" stroke="#DC2626" stroke-width="1.2" stroke-dasharray="6 5"/>{split}
{''.join(lines)}{''.join(labels)}
<text x="{left}" y="266" class="axis">Historical Start</text>
<text x="{split_x:.1f}" y="266" text-anchor="middle" class="axis">Cut-off</text>
<text x="{left + inner_w}" y="266" text-anchor="end" class="axis">{'Horizon' if has_projection else 'Latest'}</text>
</svg>'''


def _empty_chart_svg(message: str, aria_label: str) -> str:
    return f'''<svg viewBox="0 0 720 250" role="img" aria-label="{escape(aria_label)}">
<rect x="1" y="1" width="718" height="248" fill="#F8FAFC" stroke="#E2E8F0"/>
<text x="360" y="118" text-anchor="middle"
 style="font:700 15px Inter,sans-serif;fill:#475569">Trend Evidence Not Available</text>
<text x="360" y="143" text-anchor="middle" style="font:12px Inter,sans-serif;fill:#64748B">{escape(message)}</text>
</svg>'''


def _participation_donut_svg(percent: float, ready_nodes: int) -> str:
    value = max(0.0, min(_float(percent), 100.0))
    circumference = 2 * 3.141592653589793 * 52
    if value <= 0:
        progress = ''
    elif value >= 100:
        progress = '<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" stroke-width="20"/>'
    else:
        length = value / 100 * circumference
        progress = (
            f'<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" '
            f'stroke-width="20" stroke-linecap="butt" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            'transform="rotate(-90 78 78)"/>'
        )
    return f'''<svg viewBox="0 0 156 156" role="img" aria-label="Node participation {value:.0f} percent">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="20"/>{progress}
<text x="78" y="76" text-anchor="middle" font-family="Inter, sans-serif"
 font-size="28" font-weight="700" fill="#1E293B">{ready_nodes}</text>
<text x="78" y="96" text-anchor="middle" font-family="Inter, sans-serif"
 font-size="12" fill="#475569">Ready Nodes</text></svg>'''


def _donut_svg(items: list[dict[str, Any]]) -> str:
    total = sum(item['raw_value'] for item in items)
    if total <= 0:
        return _empty_donut_svg()
    colors = ('#7C3AED', '#9B7AF5', '#B8A8FF')
    circumference = 2 * 3.141592653589793 * 52
    offset = 0.0
    circles: list[str] = []
    for index, item in enumerate(items):
        length = item['raw_value'] / total * circumference
        circles.append(
            f'<circle cx="78" cy="78" r="52" fill="none" stroke="{colors[index % len(colors)]}" '
            f'stroke-width="20" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 78 78)"/>'
        )
        offset += length
    return f'''<svg viewBox="0 0 156 156" role="img" aria-label="Displayed memory concentration">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="20"/>{''.join(circles)}</svg>'''


def _empty_donut_svg() -> str:
    return '''<svg viewBox="0 0 156 156" role="img" aria-label="Displayed memory concentration unavailable">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="20"/>
<text x="78" y="82" text-anchor="middle" style="font:700 12px Inter,sans-serif;fill:#64748B">N/A</text></svg>'''


def _leading_interpretation(item: Mapping[str, Any]) -> str:
    value = _float(item.get('percent'))
    if value >= 85:
        return f"{item.get('label')} is in the critical operating band and requires immediate validation."
    if value >= 70:
        return f"{item.get('label')} is in the warning operating band and requires capacity review."
    return (
        f"{item.get('label')} remains below the warning band. Review direction and workload concentration "
        'before considering aggregate capacity expansion.'
    )


def _priority_findings(
    *,
    memory: Mapping[str, Any],
    cpu_consumers: list[dict[str, Any]],
    forecast_available: bool,
    source_rows: list[dict[str, str]],
) -> tuple[dict[str, str], ...]:
    memory_title = 'Memory Utilization Direction'
    memory_description = (
        'Review current memory utilization and committed projection evidence.'
        if forecast_available
        else 'Review current memory utilization; projection evidence was not available.'
    )
    cpu_description = (
        f"Validate whether {cpu_consumers[0]['name']} is expected for the selected reporting boundary."
        if cpu_consumers
        else 'No top CPU consumer evidence was returned.'
    )
    return (
        {
            'ref': 'F1',
            'priority': 'P2' if _float(memory.get('percent')) >= 50 else 'P3',
            'title': memory_title,
            'owner': 'Platform Operations',
            'status': 'Review',
            'tone': 'warning',
            'description': memory_description,
        },
        {
            'ref': 'F2',
            'priority': 'P3',
            'title': 'Top CPU Consumer Validation',
            'owner': 'Platform Operations',
            'status': 'Planned',
            'tone': 'info',
            'description': cpu_description,
        },
        {
            'ref': 'F3',
            'priority': 'P3',
            'title': 'Utilization Evidence Coverage',
            'owner': 'Observability Owner',
            'status': 'Current' if source_rows else 'Review',
            'tone': 'normal' if source_rows else 'warning',
            'description': 'Maintain committed metric coverage and investigate missing time-series gaps.',
        },
    )


def _cpu_assessment(cpu: Mapping[str, Any], consumers: list[dict[str, Any]]) -> str:
    if _float(cpu.get('percent')) >= 70:
        return (
            'The committed CPU signal is in or above the warning band. Confirm sustained demand, '
            'workload ownership, and available headroom.'
        )
    if consumers:
        return (
            'The committed P95 is below the warning threshold. Operational review should focus on whether '
            'the leading individual consumers are expected, not on aggregate expansion.'
        )
    return 'The committed P95 is below the warning threshold, but consumer-level evidence was not available.'


def _memory_assessment_title(memory: Mapping[str, Any], projection: float | None) -> str:
    current = _float(memory.get('percent'))
    if current >= 85:
        return 'Memory is currently in the critical operating band.'
    if current >= 70:
        return 'Memory requires immediate capacity review.'
    if projection is not None and projection >= 70:
        return 'Memory is normal now but is the primary planning signal.'
    return 'Memory remains within the normal operating band.'


def _memory_assessment_body(memory: Mapping[str, Any], projection: float | None) -> str:
    current = _float(memory.get('percent'))
    if projection is None:
        return (
            f'The current committed signal is {_percent(current)}. Forecast evidence was not available, '
            'so planning conclusions must remain limited to the committed cut-off.'
        )
    return (
        f'The current committed signal is {_percent(current)} and the available projection is {_percent(projection)}. '
        'Review threshold exposure before capacity pressure becomes operational.'
    )


def _forecast_eta(item: Mapping[str, Any]) -> str:
    eta = _mapping(item.get('warning_eta'))
    label = eta.get('display') or eta.get('label') or item.get('warning_eta_display')
    return sanitize_text(label, fallback='Planning Horizon' if item else 'Not Available')


def _forecast_confidence(items: Mapping[str, Mapping[str, Any]]) -> str:
    qualities = [sanitize_text(item.get('signal_quality'), fallback='') for item in items.values()]
    qualities = [quality for quality in qualities if quality]
    if not qualities:
        return 'Not Available'
    normalized = ' '.join(qualities).lower()
    if 'low' in normalized or 'poor' in normalized:
        return 'Review'
    if 'medium' in normalized:
        return 'Moderate'
    return 'High'


def _distribution_interpretation(
    memory_consumers: list[dict[str, Any]],
    cpu_consumers: list[dict[str, Any]],
) -> str:
    if memory_consumers and cpu_consumers:
        memory_namespace = memory_consumers[0]['namespace']
        namespaces = ', '.join(dict.fromkeys(item['namespace'] for item in cpu_consumers[:3]))
        return (
            f'The displayed memory signal is concentrated in {memory_namespace} resources, while the '
            f'displayed CPU signal is distributed across {namespaces}. These charts cover only '
            'the displayed top-consumer set.'
        )
    return 'Displayed consumer evidence was incomplete; concentration conclusions remain limited to available records.'


def _consumer_register(
    memory_consumers: list[dict[str, Any]],
    cpu_consumers: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for prefix, group in (('M', memory_consumers), ('C', cpu_consumers)):
        for index, item in enumerate(group, start=1):
            rows.append({'ref': f'{prefix}{index}', **item})
    return tuple(rows)


def _trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return 'Not Available'
    delta = values[-1] - values[0]
    if delta > 2:
        return 'Rising'
    if delta < -2:
        return 'Falling'
    return 'Stable'


def _direction_tone(values: list[float]) -> str:
    direction = _trend_direction(values)
    if direction == 'Rising':
        return 'warning'
    if direction == 'Not Available':
        return 'muted'
    return 'normal'


def _trend_row(
    ref: str,
    resource: str,
    current: float,
    projected: float | None,
    values: list[float],
) -> dict[str, str]:
    assessment = 'Review' if projected is not None and projected >= 70 else _trend_direction(values)
    tone = 'warning' if assessment in {'Review', 'Rising'} else 'normal' if assessment != 'Not Available' else 'muted'
    return {
        'ref': ref,
        'resource': resource,
        'current': _percent(current),
        'projection': _optional_percent(projected),
        'assessment': assessment,
        'tone': tone,
    }


def _trend_interpretation(memory_projection: float | None, memory: Mapping[str, Any]) -> str:
    if memory_projection is not None and memory_projection >= 70:
        return (
            'Memory is the only displayed resource projected to enter or remain in the warning '
            'band within the available planning horizon.'
        )
    if memory_projection is not None:
        return 'No displayed resource is projected to enter the warning band within the available planning horizon.'
    return (
        f"Memory is the highest current planning signal at {memory.get('value')}; "
        'projection evidence was not available.'
    )


def _recommendations(
    *,
    cpu: Mapping[str, Any],
    memory: Mapping[str, Any],
    pods: Mapping[str, Any],
    total_nodes: int,
    ready_nodes: int,
    cpu_consumers: list[dict[str, Any]],
    memory_projection: float | None,
    forecast_available: bool,
    prometheus_status: Mapping[str, Any],
) -> dict[str, Any]:
    items = [
        {
            'ref': 'R1',
            'priority': 'P2',
            'title': 'Validate Highest CPU Consumer',
            'owner': 'Platform Operations',
            'target': 'Next Week',
            'status': 'Open' if cpu_consumers else 'Evidence Required',
            'tone': 'warning',
            'description': (
                f"Confirm whether {cpu_consumers[0]['name']} is expected for the selected scope and reporting window."
                if cpu_consumers
                else 'Collect top CPU consumer evidence before closing utilization review.'
            ),
        },
        {
            'ref': 'R2',
            'priority': 'P2' if memory_projection is not None and memory_projection >= 70 else 'P3',
            'title': 'Review Memory Growth Direction',
            'owner': 'Platform Operations',
            'target': 'Next Week' if memory_projection is not None and memory_projection >= 70 else 'This Month',
            'status': 'Open' if memory_projection is not None and memory_projection >= 70 else 'Planned',
            'tone': 'warning' if memory_projection is not None and memory_projection >= 70 else 'info',
            'description': (
                f'Validate the projected memory position of {_percent(memory_projection)} and '
                'include the result in the next capacity gate.'
                if memory_projection is not None
                else 'Maintain current memory review; forecast evidence was not available for this run.'
            ),
        },
        {
            'ref': 'R3',
            'priority': 'P3',
            'title': 'Confirm Pod Scheduling Distribution',
            'owner': 'Platform Operations',
            'target': 'This Month',
            'status': 'Planned',
            'tone': 'info',
            'description': (
                f"Confirm that {_percent(_float(pods.get('headroom')))} schedulable headroom "
                'matches deployment expectations and scope definitions.'
            ),
        },
        {
            'ref': 'R4',
            'priority': 'P3',
            'title': 'Maintain Node Participation Evidence',
            'owner': 'Platform Operations',
            'target': 'This Month',
            'status': 'Current' if total_nodes and ready_nodes == total_nodes else 'Open',
            'tone': 'normal' if total_nodes and ready_nodes == total_nodes else 'warning',
            'description': (
                'Ensure not-ready nodes remain excluded from active capacity assumptions and '
                'visibly reported.'
            ),
        },
        {
            'ref': 'R5',
            'priority': 'P3',
            'title': 'Maintain Utilization Dataset Coverage',
            'owner': 'Observability Owner',
            'target': 'This Month',
            'status': 'Current' if _prometheus_ready(prometheus_status) else 'Open',
            'tone': 'normal' if _prometheus_ready(prometheus_status) else 'warning',
            'description': (
                'Maintain committed metric and forecast evidence coverage.'
                if forecast_available
                else 'Maintain committed metric coverage and investigate unavailable forecast evidence.'
            ),
        },
    ]
    p1 = sum(1 for item in items if item['priority'] == 'P1')
    p2 = sum(1 for item in items if item['priority'] == 'P2')
    p3 = sum(1 for item in items if item['priority'] == 'P3')
    return {
        'metrics': (
            _metric('P1 Actions', str(p1), 'None' if not p1 else 'Open', 'normal' if not p1 else 'critical'),
            _metric('P2 Actions', str(p2), 'Open' if p2 else 'None', 'warning' if p2 else 'normal'),
            _metric('P3 Actions', str(p3), 'Planned' if p3 else 'None', 'info' if p3 else 'normal'),
            _metric('Validation Gates', str(len(items)), 'Required', 'info'),
        ),
        'items': tuple(items),
        'primary_action': 'Review memory direction and validate the highest displayed CPU consumer.',
        'validation_criteria': (
            'Confirm live metrics, expected workload behavior, accountable ownership, and the '
            'approved capacity response before closure.'
        ),
        'assigned_owners': 'Platform Operations: 4 actions; Observability Owner: 1 action.',
        'change_control': 'No infrastructure or workload change is authorized by this report alone.',
    }


def _source_rows(
    payload: Mapping[str, Any],
    prometheus_status: Mapping[str, Any],
    forecast_payload: Mapping[str, Any],
    period_label: str,
) -> list[dict[str, str]]:
    provided = _sequence(payload.get('source_evidence'))
    rows: list[dict[str, str]] = []
    for item in provided:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'source': sanitize_text(item.get('source'), fallback='Unknown Source'),
                'freshness': sanitize_text(item.get('freshness'), fallback='Not Available'),
                'last_collected': _format_datetime(item.get('last_collected')),
            }
        )
    if rows:
        return rows[:4]

    rows.append(
        {
            'source': 'Prometheus Observation Cache',
            'freshness': _latency(prometheus_status.get('response_time_ms')),
            'last_collected': _format_datetime(prometheus_status.get('last_checked_at')),
        }
    )
    rows.append(
        {
            'source': 'Kubernetes Cluster Scope',
            'freshness': 'Committed',
            'last_collected': 'At report cut-off',
        }
    )
    rows.append(
        {
            'source': 'Utilization Trend Evidence',
            'freshness': period_label,
            'last_collected': 'At report cut-off',
        }
    )
    rows.append(
        {
            'source': 'Forecast Evidence',
            'freshness': sanitize_text(forecast_payload.get('forecast_horizon'), fallback='Not Available'),
            'last_collected': _format_datetime(forecast_payload.get('generated_at')),
        }
    )
    return rows


def _format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).strftime('%d %b %Y %H:%M UTC')
    text = sanitize_text(value, fallback='Not Available')
    return text


def _latency(value: Any) -> str:
    try:
        return f'{float(value):.0f} ms'
    except (TypeError, ValueError):
        return 'Not Available'


def _prometheus_ready(status: Mapping[str, Any]) -> bool:
    label = str(status.get('status') or status.get('status_label') or '').lower()
    return bool(status.get('connected')) or any(
        token in label for token in ('ready', 'connected', 'healthy', 'query ready')
    )
