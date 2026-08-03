from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from html import escape
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_FORECAST_PAGE_TITLES = (
    'Cover',
    'Executive Forecast Brief',
    'Forecast Portfolio',
    'CPU Forecast',
    'Memory Forecast',
    'Pod and Storage Forecast',
    'Threshold Exposure and Confidence',
    'Recommendation Plan',
    'Methodology and Evidence Boundary',
)

_RESOURCE_ORDER = ('cpu', 'memory', 'pods', 'storage')
_RESOURCE_META = {
    'cpu': {'label': 'CPU', 'color': '#2563EB'},
    'memory': {'label': 'Memory', 'color': '#7C3AED'},
    'pods': {'label': 'Pods', 'color': '#15803D'},
    'storage': {'label': 'Storage', 'color': '#D97706'},
}
_WARNING_THRESHOLD = 70.0
_CRITICAL_THRESHOLD = 85.0


def build_forecast_analysis_presentation(
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
    forecast_payload = _mapping(payload.get('forecast_payload'))
    items = _resource_map(forecast_payload)
    resources = {
        key: _resource_presentation(key, _mapping(items.get(key)))
        for key in _RESOURCE_ORDER
    }
    available = [item for item in resources.values() if item['available']]
    highest = max(available, key=lambda item: item['projected_percent']) if available else None
    warning_count = sum(1 for item in available if item['projected_percent'] >= _WARNING_THRESHOLD)
    critical_count = sum(1 for item in available if item['projected_percent'] >= _CRITICAL_THRESHOLD)
    coverage_count = len(available)

    method = sanitize_text(
        forecast_payload.get('method_label')
        or forecast_payload.get('forecast_method_label')
        or forecast_payload.get('forecast_method'),
        fallback='Not Available',
    )
    history_window = sanitize_text(
        forecast_payload.get('history_window') or payload.get('history_window'),
        fallback='Not Available',
    )
    horizon = sanitize_text(
        forecast_payload.get('forecast_horizon') or payload.get('forecast_horizon'),
        fallback='Not Available',
    )
    horizon_days = _int(forecast_payload.get('horizon_days')) or _days_from_label(horizon)
    combined_chart = _combined_chart_svg(resources)

    recommendations = _recommendation_plan(
        forecast_payload=forecast_payload,
        resources=resources,
        warning_count=warning_count,
        critical_count=critical_count,
    )
    sources = _source_rows(payload, forecast_payload, history_window, horizon)

    highest_value = _percent(highest['projected_percent']) if highest else 'Not Available'
    highest_status = highest['label'] if highest else 'No Forecast Evidence'
    forecast_status = _executive_status(warning_count, critical_count, coverage_count)
    forecast_tone = _executive_tone(warning_count, critical_count, coverage_count)

    return {
        'presentation_version': 'v1.0-forecast-analysis-publication',
        'page_count': len(_FORECAST_PAGE_TITLES),
        'layout_contract': {
            'paper': 'A4 Portrait',
            'page_count': 9,
            'fixed_page_canvas': True,
            'status_style': 'plain-colored-text',
            'table_policy': 'single-line-technical-registers',
            'missing_evidence_policy': 'explicit-not-available',
            'forecast_policy': 'committed-materialized-evidence-only',
            'visual_style': 'kaori-forecast-analysis-v1.0',
        },
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Forecast Analysis',
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'page_titles': _FORECAST_PAGE_TITLES,
        'cover': {
            'environment': sanitize_text(cluster.get('environment'), fallback='Not Available'),
            'purpose': (
                'Support operational planning by separating current posture, committed projection, '
                'threshold timing, evidence confidence, and accountable forecast actions.'
            ),
            'context': (
                'Forecast values are read from committed materialized evidence. Missing resource forecasts '
                'remain explicit and are never converted to zero, stable, or healthy.'
            ),
        },
        'executive': {
            'metrics': (
                _metric('Highest Projection', highest_value, highest_status, 'warning' if highest else 'muted'),
                _metric(
                    'Warning Exposure',
                    str(warning_count),
                    _horizon_status(warning_count, horizon),
                    'warning' if warning_count else 'normal',
                ),
                _metric('Forecast Method', method, 'Committed' if available else 'Not Available', 'info' if available else 'muted'),
                _metric(
                    'Forecast Coverage',
                    f'{coverage_count} / {len(_RESOURCE_ORDER)}',
                    'Committed Resources',
                    'normal' if coverage_count == len(_RESOURCE_ORDER) else 'warning',
                ),
            ),
            'status': forecast_status,
            'tone': forecast_tone,
            'resources': tuple(resources[key] for key in _RESOURCE_ORDER),
            'interpretation_title': _executive_title(highest, warning_count, critical_count),
            'interpretation_body': _executive_body(highest, warning_count, critical_count, horizon),
            'interpretation_note': (
                'Threshold ETA beyond the configured horizon is a long-range planning signal, not an '
                'immediate breach. Planned deployments and live state are outside the model.'
            ),
            'decisions': tuple(recommendations['rows'][:4]),
        },
        'portfolio': {
            'metrics': tuple(
                _metric(
                    f"{item['label']} Projection",
                    item['projected_display'],
                    item['status'],
                    item['tone'],
                )
                for item in resources.values()
            ),
            'chart_svg': combined_chart,
            'rows': tuple(_portfolio_row(resources[key], idx + 1) for idx, key in enumerate(_RESOURCE_ORDER)),
            'interpretation': _portfolio_interpretation(resources, horizon),
        },
        'cpu': _resource_page(resources['cpu'], 'CPU'),
        'memory': _resource_page(resources['memory'], 'Memory'),
        'pod_storage': {
            'metrics': (
                _metric('Pod Current', resources['pods']['current_display'], resources['pods']['status'], resources['pods']['tone']),
                _metric('Pod Projection', resources['pods']['projected_display'], resources['pods']['status'], resources['pods']['tone']),
                _metric('Storage Current', resources['storage']['current_display'], resources['storage']['status'], resources['storage']['tone']),
                _metric('Storage Projection', resources['storage']['projected_display'], resources['storage']['status'], resources['storage']['tone']),
            ),
            'pods': _resource_page(resources['pods'], 'Pods'),
            'storage': _resource_page(resources['storage'], 'Storage'),
            'rows': (
                _resource_register_row(resources['pods'], 'S1'),
                _headroom_row(resources['pods'], 'S2'),
                _resource_register_row(resources['storage'], 'S3'),
                _threshold_row(resources['storage'], 'S4'),
            ),
        },
        'exposure': {
            'metrics': (
                _metric('Warning Exposures', str(warning_count), _horizon_status(warning_count, horizon), 'warning' if warning_count else 'normal'),
                _metric('Critical Exposures', str(critical_count), _horizon_status(critical_count, horizon), 'critical' if critical_count else 'normal'),
                _metric('Committed Forecasts', str(coverage_count), 'Available Resources', 'normal' if coverage_count else 'muted'),
                _metric('Evidence Gaps', str(len(_RESOURCE_ORDER) - coverage_count), 'Requires Review' if coverage_count < len(_RESOURCE_ORDER) else 'Clear', 'warning' if coverage_count < len(_RESOURCE_ORDER) else 'normal'),
            ),
            'rows': tuple(_exposure_row(resources[key], idx + 1) for idx, key in enumerate(_RESOURCE_ORDER)),
            'confidence_title': _confidence_title(resources),
            'confidence_body': _confidence_body(resources),
            'boundary_title': 'Committed observations define the forecast boundary.',
            'boundary_body': (
                'Planned deployments, approved infrastructure expansion, workload migrations, and live '
                'state after the report cut-off are not modeled.'
            ),
            'boundary_note': 'Missing observations remain visible as gaps and must not be converted to zero.',
        },
        'recommendations': recommendations,
        'methodology': {
            'metrics': (
                _metric('Data Sources', str(len(sources)), 'Committed' if sources else 'Not Available', 'normal' if sources else 'muted'),
                _metric('Forecast Horizon', _human_window(horizon), 'Configured', 'info'),
                _metric('Forecast Method', method, 'Committed' if available else 'Not Available', 'info' if available else 'muted'),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ),
            'sources': sources,
            'rules': (
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Threshold Bands', 'setting': '70% / 85%'},
                {'ref': 'M4', 'rule': 'Forecast Method', 'setting': method},
                {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ),
            'references': (
                _reference('M3', 'Threshold Bands', 'Normal below 70%, warning from 70% to 84.9%, and critical at 85% or above.'),
                _reference('M4', 'Forecast Method', f'{method} is used where committed historical evidence is available.'),
                _reference('M5', 'Missing Evidence', 'Unavailable forecast dimensions remain explicit and are never converted to zero.'),
            ),
            'included': (
                'Committed resource history and projected endpoints returned by the materialized forecast dataset.',
                'Configured threshold bands, horizon, model label, confidence, and threshold ETA when available.',
                'Committed actionable forecast recommendations and source-freshness evidence.',
            ),
            'excluded': (
                'Live cluster state after the report cut-off.',
                'Planned deployments, infrastructure expansion, or workload migrations not represented in committed evidence.',
                'Forecast values for resources without sufficient history or capacity evidence.',
            ),
            'limitations': (
                'Forecasts support planning and do not authorize autonomous remediation.',
                'Threshold ETA beyond the configured horizon is a long-range planning signal.',
                'Validate every recommendation against live state, ownership, and approved change controls.',
            ),
            'status_language': (
                _reference('S1', 'Not Available', 'No committed forecast exists for the requested dimension.'),
                _reference('S2', 'Not Collected', 'Collection was prevented by configuration or failure.'),
                _reference('S3', 'Partial Coverage', 'Evidence exists but does not cover the full requested scope.'),
                _reference('S4', 'Source Unavailable', 'The source was unreachable or not providing data at the cut-off.'),
            ),
            'history_window': history_window,
            'horizon': horizon,
            'horizon_days': horizon_days,
        },
    }


def _resource_map(forecast_payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in _sequence(forecast_payload.get('items')):
        if not isinstance(item, Mapping):
            continue
        key = _text(item.get('key'), '').lower()
        if key == 'pod':
            key = 'pods'
        if key in _RESOURCE_META:
            result[key] = item
    return result


def _resource_presentation(key: str, item: Mapping[str, Any]) -> dict[str, Any]:
    meta = _RESOURCE_META[key]
    capacity = _float(item.get('capacity'))
    current = _first_float(
        item.get('latest_daily_average_percent'),
        item.get('current_percent'),
        _ratio(item.get('latest_daily_average'), capacity),
        _ratio(item.get('current_value'), capacity),
    )
    projected = _first_float(
        item.get('projected_percent'),
        _ratio(item.get('projected_value'), capacity),
    )
    history = _point_percentages(item.get('historical_points'), capacity)
    projection = _point_percentages(item.get('forecast_points'), capacity)
    available = bool(item.get('has_data')) and projected is not None
    if projected is not None and (history or projection):
        available = True
    if current is None and history:
        current = history[-1]
    if projected is None and projection:
        projected = projection[-1]
    if current is None:
        current = 0.0
    if projected is None:
        projected = 0.0

    status = _status(projected) if available else 'Not Available'
    tone = _tone(projected) if available else 'warning'
    warning_eta = _eta(item.get('warning_eta')) if available else 'Not Available'
    critical_eta = _eta(item.get('critical_eta')) if available else 'Not Available'
    confidence = sanitize_text(
        item.get('signal_quality') or item.get('confidence'),
        fallback='Not Available' if not available else 'Review',
    )
    confidence_reason = sanitize_text(
        item.get('signal_quality_reason') or item.get('confidence_reason'),
        fallback='Committed forecast confidence metadata was not supplied.',
    )
    empty_reason = sanitize_text(
        item.get('empty_reason'),
        fallback='Committed forecast evidence is not available for this resource.',
    )
    chart_svg = _single_chart_svg(
        label=meta['label'],
        color=meta['color'],
        history=history,
        projection=projection,
        current=current if available else None,
        projected=projected if available else None,
        empty_reason=empty_reason,
    )
    headroom = max(0.0, 100.0 - projected) if available else None
    return {
        'key': key,
        'label': meta['label'],
        'color': meta['color'],
        'available': available,
        'current_percent': current,
        'projected_percent': projected,
        'current_display': _percent(current) if available else 'Not Available',
        'projected_display': _percent(projected) if available else 'Not Available',
        'headroom_percent': headroom,
        'headroom_display': _percent(headroom) if headroom is not None else 'Not Available',
        'status': status,
        'tone': tone,
        'warning_eta': warning_eta,
        'critical_eta': critical_eta,
        'confidence': confidence,
        'confidence_reason': confidence_reason,
        'history': history,
        'projection': projection,
        'chart_svg': chart_svg,
        'empty_reason': empty_reason,
        'scope_label': sanitize_text(item.get('scope_label'), fallback='Selected report boundary'),
        'method': sanitize_text(item.get('method_label') or item.get('forecast_method'), fallback='Not Available'),
    }


def _resource_page(resource: Mapping[str, Any], title: str) -> dict[str, Any]:
    projected = _float(resource.get('projected_percent'))
    available = bool(resource.get('available'))
    if not available:
        assessment_title = f'{title} forecast evidence is not available.'
        assessment_body = resource['empty_reason']
        assessment_note = 'The report does not convert missing evidence into zero usage, stable direction, or healthy capacity.'
    elif projected >= _CRITICAL_THRESHOLD:
        assessment_title = f'{title} is projected in the critical operating band.'
        assessment_body = 'Immediate ownership and live-state validation are required before capacity or workload changes.'
        assessment_note = 'Forecast conclusions remain subject to model confidence, source freshness, and approved change controls.'
    elif projected >= _WARNING_THRESHOLD:
        assessment_title = f'{title} is projected in the warning operating band.'
        assessment_body = 'Review growth assumptions, accountable ownership, and the available threshold ETA.'
        assessment_note = 'A forecast warning is a planning signal and does not authorize autonomous remediation.'
    else:
        assessment_title = f'{title} remains below the warning band in the configured horizon.'
        assessment_body = 'Maintain committed forecast coverage and validate whether known deployments could change the projected direction.'
        assessment_note = 'Live-state spikes and workload-specific concentration remain separate operational evidence.'
    return {
        'resource': resource,
        'metrics': (
            _metric('Current', resource['current_display'], resource['status'], resource['tone']),
            _metric('Projection', resource['projected_display'], resource['status'], resource['tone']),
            _metric('Projected Headroom', resource['headroom_display'], 'Available' if available else 'Not Available', 'normal' if available else 'warning'),
            _metric('Warning ETA', resource['warning_eta'], 'Threshold Timing', 'warning' if resource['warning_eta'] not in {'Not projected', 'Not Available'} else 'muted'),
        ),
        'assessment_title': assessment_title,
        'assessment_body': assessment_body,
        'assessment_note': assessment_note,
        'register': (
            {'ref': f"{resource['key'][:1].upper()}1", 'dimension': 'Current Signal', 'value': resource['current_display'], 'evidence': 'Committed' if available else 'Missing', 'status': resource['status'], 'tone': resource['tone']},
            {'ref': f"{resource['key'][:1].upper()}2", 'dimension': 'Projected Signal', 'value': resource['projected_display'], 'evidence': 'Committed' if available else 'Missing', 'status': resource['status'], 'tone': resource['tone']},
            {'ref': f"{resource['key'][:1].upper()}3", 'dimension': 'Projected Headroom', 'value': resource['headroom_display'], 'evidence': 'Derived' if available else 'Missing', 'status': 'Available' if available else 'Not Available', 'tone': 'normal' if available else 'warning'},
            {'ref': f"{resource['key'][:1].upper()}4", 'dimension': 'Warning ETA', 'value': resource['warning_eta'], 'evidence': resource['confidence'], 'status': 'Review' if available else 'Not Available', 'tone': 'warning' if available else 'muted'},
        ),
    }


def _portfolio_row(resource: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'P{index}',
        'resource': resource['label'],
        'current': resource['current_display'],
        'projection': resource['projected_display'],
        'warning_eta': resource['warning_eta'],
        'confidence': resource['confidence'],
        'assessment': resource['status'],
        'tone': resource['tone'],
    }


def _resource_register_row(resource: Mapping[str, Any], ref: str) -> dict[str, Any]:
    return {
        'ref': ref,
        'dimension': resource['label'],
        'current': resource['current_display'],
        'projection': resource['projected_display'],
        'evidence': 'Committed' if resource['available'] else 'Missing',
        'status': resource['status'],
        'tone': resource['tone'],
    }


def _headroom_row(resource: Mapping[str, Any], ref: str) -> dict[str, Any]:
    return {
        'ref': ref,
        'dimension': f"{resource['label']} Projected Headroom",
        'current': _percent(max(0.0, 100.0 - resource['current_percent'])) if resource['available'] else 'Not Available',
        'projection': resource['headroom_display'],
        'evidence': 'Derived' if resource['available'] else 'Missing',
        'status': 'Available' if resource['available'] else 'Not Available',
        'tone': 'normal' if resource['available'] else 'warning',
    }


def _threshold_row(resource: Mapping[str, Any], ref: str) -> dict[str, Any]:
    return {
        'ref': ref,
        'dimension': f"{resource['label']} Threshold ETA",
        'current': resource['warning_eta'],
        'projection': resource['critical_eta'],
        'evidence': resource['confidence'],
        'status': 'Review' if resource['available'] else 'Not Available',
        'tone': 'warning' if resource['available'] else 'muted',
    }


def _exposure_row(resource: Mapping[str, Any], index: int) -> dict[str, Any]:
    exposure = 'Not Assessable'
    if resource['available']:
        if resource['projected_percent'] >= _CRITICAL_THRESHOLD:
            exposure = 'Critical Exposure'
        elif resource['projected_percent'] >= _WARNING_THRESHOLD:
            exposure = 'Warning Exposure'
        else:
            exposure = 'No Exposure'
    return {
        'ref': f'T{index}',
        'resource': resource['label'],
        'projection': resource['projected_display'],
        'warning': '70%',
        'critical': '85%',
        'exposure': exposure,
        'confidence': resource['confidence'],
        'tone': resource['tone'],
    }


def _recommendation_plan(
    *,
    forecast_payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
    warning_count: int,
    critical_count: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    candidates = _sequence(
        forecast_payload.get('actionable_recommendations')
        or forecast_payload.get('recommendation_cards')
    )
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        title = sanitize_text(item.get('title') or item.get('label'), fallback='Review Forecast Evidence')
        description = sanitize_text(item.get('description') or item.get('message'), fallback='Validate committed forecast evidence and live state.')
        priority = _priority(item.get('priority') or item.get('severity'))
        rows.append(
            {
                'priority': priority,
                'title': title,
                'description': description,
                'owner': sanitize_text(item.get('owner'), fallback='Platform Operations'),
                'target': _target(priority),
                'status': 'Open' if priority in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if priority == 'P1' else 'warning' if priority == 'P2' else 'info',
            }
        )

    memory = resources['memory']
    storage = resources['storage']
    if memory['available'] and memory['warning_eta'] not in {'Not projected', 'Not Available'}:
        rows.append(
            {
                'priority': 'P2',
                'title': 'Review Memory Long-Range Direction',
                'description': f"Validate the projected memory position of {memory['projected_display']} and threshold ETA {memory['warning_eta']}.",
                'owner': 'Platform Operations',
                'target': 'Next Week',
                'status': 'Open',
                'tone': 'warning',
            }
        )
    if not storage['available']:
        rows.append(
            {
                'priority': 'P2',
                'title': 'Restore Storage Forecast Evidence',
                'description': 'Commit normalized storage history, projection, threshold ETA, confidence, and freshness evidence.',
                'owner': 'Platform Operations',
                'target': 'Next Week',
                'status': 'Open',
                'tone': 'warning',
            }
        )
    for key, title in (('cpu', 'Maintain CPU Forecast Coverage'), ('pods', 'Maintain Pod Forecast Coverage')):
        resource = resources[key]
        rows.append(
            {
                'priority': 'P3',
                'title': title,
                'description': (
                    f"Keep committed {resource['label']} history and projected endpoints available for the selected reporting boundary."
                    if resource['available']
                    else f"Restore committed {resource['label']} history and projected endpoint evidence."
                ),
                'owner': 'Observability Owner' if key == 'cpu' else 'Platform Operations',
                'target': 'This Month',
                'status': 'Current' if resource['available'] else 'Planned',
                'tone': 'normal' if resource['available'] else 'info',
            }
        )
    rows.append(
        {
            'priority': 'P3',
            'title': 'Validate Forecast Freshness',
            'description': 'Review materialization time, missing observations, model status, and source ownership before relying on forecast conclusions.',
            'owner': 'Observability Owner',
            'target': 'This Month',
            'status': 'Planned',
            'tone': 'info',
        }
    )

    rows = _dedupe_recommendations(rows)
    rows.sort(key=lambda item: ({'P1': 0, 'P2': 1, 'P3': 2}.get(item['priority'], 9), item['title']))
    rows = rows[:5]
    for idx, item in enumerate(rows, start=1):
        item['ref'] = f'R{idx}'

    p1 = sum(1 for item in rows if item['priority'] == 'P1')
    p2 = sum(1 for item in rows if item['priority'] == 'P2')
    p3 = sum(1 for item in rows if item['priority'] == 'P3')
    primary = rows[0]['title'] if rows else 'Maintain Forecast Monitoring'
    return {
        'metrics': (
            _metric('P1 Actions', str(p1), 'Open' if p1 else 'None', 'critical' if p1 else 'normal'),
            _metric('P2 Actions', str(p2), 'Open' if p2 else 'None', 'warning' if p2 else 'normal'),
            _metric('P3 Actions', str(p3), 'Planned' if p3 else 'None', 'info' if p3 else 'normal'),
            _metric('Validation Gates', str(len(rows)), 'Required', 'info'),
        ),
        'rows': tuple(rows),
        'primary_action': primary,
        'validation_criteria': (
            'Confirm source freshness, model status, scope, threshold policy, live metric, accountable '
            'ownership, and approved response before closure.'
        ),
        'assigned_owners': _owner_summary(rows),
        'change_control': 'No infrastructure or workload change is authorized by this report alone.',
        'risk_summary': f'{critical_count} critical and {warning_count} warning forecast exposure(s) are present.',
    }


def _dedupe_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = row['title'].strip().casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _source_rows(
    payload: Mapping[str, Any],
    forecast_payload: Mapping[str, Any],
    history_window: str,
    horizon: str,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in _sequence(payload.get('source_evidence')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'source': sanitize_text(item.get('source'), fallback='Forecast Evidence'),
                'freshness': sanitize_text(item.get('freshness'), fallback='Not Available'),
                'last_collected': _format_datetime(item.get('last_collected')),
            }
        )
    if not rows:
        rows.extend(
            [
                {'source': 'Forecast Materialized Snapshot', 'freshness': history_window, 'last_collected': _format_datetime(forecast_payload.get('generated_at'))},
                {'source': 'Forecast Projection Evidence', 'freshness': horizon, 'last_collected': _format_datetime(forecast_payload.get('generated_at'))},
            ]
        )
    return tuple(rows[:5])


def _combined_chart_svg(resources: Mapping[str, Mapping[str, Any]]) -> str:
    width, height = 760, 238
    left, top, chart_w, chart_h = 58.0, 24.0, 660.0, 160.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Forecast portfolio chart">',
        '<rect width="760" height="238" fill="#F8FAFC"/>',
    ]
    for value in (0, 25, 50, 70, 85):
        y = top + chart_h - chart_h * value / 100.0
        dash = ' stroke-dasharray="5 5"' if value in {70, 85} else ''
        color = '#D97706' if value == 70 else '#DC2626' if value == 85 else '#E2E8F0'
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+chart_w}" y2="{y:.1f}" stroke="{color}" stroke-width="1"{dash}/>' )
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#64748B">{value}%</text>')
    cutoff_x = left + chart_w * 0.68
    parts.append(f'<line x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{top+chart_h}" stroke="#A78BFA" stroke-dasharray="4 4"/>')
    for key in ('memory', 'pods', 'cpu', 'storage'):
        resource = resources[key]
        if not resource['available']:
            continue
        history = resource['history'] or [resource['current_percent']]
        projection = resource['projection'] or [resource['projected_percent']]
        hist_points = _series_points(history, left, cutoff_x, top, chart_h)
        proj_values = [resource['current_percent'], *projection]
        proj_points = _series_points(proj_values, cutoff_x, left + chart_w, top, chart_h)
        color = resource['color']
        if hist_points:
            parts.append(f'<polyline points="{hist_points}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
        if proj_points:
            parts.append(f'<polyline points="{proj_points}" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" stroke-linejoin="round"/>')
        end_y = top + chart_h - chart_h * resource['projected_percent'] / 100.0
        parts.append(f'<circle cx="{left+chart_w:.1f}" cy="{end_y:.1f}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{left+chart_w-6:.1f}" y="{end_y-8:.1f}" text-anchor="end" font-size="11" font-weight="700" fill="{color}">{escape(resource["projected_display"])}</text>')
    parts.extend(
        [
            f'<text x="{left}" y="{top+chart_h+24}" font-size="10" fill="#64748B">Historical Start</text>',
            f'<text x="{cutoff_x}" y="{top+chart_h+24}" text-anchor="middle" font-size="10" fill="#64748B">Cut-off</text>',
            f'<text x="{left+chart_w}" y="{top+chart_h+24}" text-anchor="end" font-size="10" fill="#64748B">Horizon</text>',
            '</svg>',
        ]
    )
    return ''.join(parts)


def _single_chart_svg(
    *,
    label: str,
    color: str,
    history: list[float],
    projection: list[float],
    current: float | None,
    projected: float | None,
    empty_reason: str,
) -> str:
    if current is None or projected is None:
        return _empty_chart_svg(f'{label} forecast unavailable', empty_reason)
    width, height = 620, 250
    left, top, chart_w, chart_h = 58.0, 28.0, 520.0, 160.0
    cutoff_x = left + chart_w * 0.68
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)} forecast chart">',
        '<rect width="620" height="250" fill="#F8FAFC"/>',
    ]
    for value in (0, 25, 50, 70, 85):
        y = top + chart_h - chart_h * value / 100.0
        dash = ' stroke-dasharray="5 5"' if value in {70, 85} else ''
        grid = '#D97706' if value == 70 else '#DC2626' if value == 85 else '#E2E8F0'
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+chart_w}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"{dash}/>' )
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#64748B">{value}%</text>')
    parts.append(f'<line x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{top+chart_h}" stroke="#A78BFA" stroke-dasharray="4 4"/>')
    hist_values = history or [current]
    proj_values = [current, *(projection or [projected])]
    parts.append(f'<polyline points="{_series_points(hist_values, left, cutoff_x, top, chart_h)}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<polyline points="{_series_points(proj_values, cutoff_x, left+chart_w, top, chart_h)}" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" stroke-linejoin="round"/>')
    current_y = top + chart_h - chart_h * current / 100.0
    projected_y = top + chart_h - chart_h * projected / 100.0
    parts.append(f'<circle cx="{cutoff_x:.1f}" cy="{current_y:.1f}" r="4" fill="{color}"/>')
    parts.append(f'<circle cx="{left+chart_w:.1f}" cy="{projected_y:.1f}" r="4" fill="{color}"/>')
    parts.append(f'<text x="{cutoff_x-8:.1f}" y="{current_y-8:.1f}" text-anchor="end" font-size="11" font-weight="700" fill="#0F172A">{current:.1f}%</text>')
    parts.append(f'<text x="{left+chart_w-6:.1f}" y="{projected_y-8:.1f}" text-anchor="end" font-size="11" font-weight="700" fill="{color}">{projected:.1f}%</text>')
    parts.extend(
        [
            f'<text x="{left}" y="{top+chart_h+24}" font-size="10" fill="#64748B">Historical</text>',
            f'<text x="{cutoff_x}" y="{top+chart_h+24}" text-anchor="middle" font-size="10" fill="#64748B">Cut-off</text>',
            f'<text x="{left+chart_w}" y="{top+chart_h+24}" text-anchor="end" font-size="10" fill="#64748B">Horizon</text>',
            '</svg>',
        ]
    )
    return ''.join(parts)


def _empty_chart_svg(title: str, message: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 250" role="img" '
        f'aria-label="{escape(title)}">'
        '<rect width="620" height="250" fill="#F8FAFC"/>'
        f'<text x="310" y="112" text-anchor="middle" font-size="17" font-weight="700" fill="#0F172A">{escape(title)}</text>'
        f'<text x="310" y="140" text-anchor="middle" font-size="11" fill="#64748B">{escape(message[:100])}</text>'
        '</svg>'
    )


def _series_points(values: list[float], start_x: float, end_x: float, top: float, chart_h: float) -> str:
    if not values:
        return ''
    if len(values) == 1:
        values = [values[0], values[0]]
    step = (end_x - start_x) / max(len(values) - 1, 1)
    return ' '.join(
        f'{start_x + index * step:.1f},{top + chart_h - chart_h * max(0.0, min(100.0, value)) / 100.0:.1f}'
        for index, value in enumerate(values)
    )


def _point_percentages(value: Any, capacity: float | None) -> list[float]:
    result: list[float] = []
    for item in _sequence(value):
        if not isinstance(item, Mapping):
            continue
        percent = _float(item.get('percent'))
        if percent is None and capacity:
            raw = _float(item.get('value'))
            if raw is not None:
                percent = raw / capacity * 100.0
        if percent is not None:
            result.append(max(0.0, min(100.0, percent)))
    return result


def _confidence_title(resources: Mapping[str, Mapping[str, Any]]) -> str:
    unavailable = [item['label'] for item in resources.values() if not item['available']]
    if unavailable:
        return 'Forecast coverage is incomplete and requires explicit review.'
    qualities = {str(item['confidence']).lower() for item in resources.values()}
    if 'low' in qualities:
        return 'At least one resource has low forecast confidence.'
    return 'Committed forecast confidence is available for all resources.'


def _confidence_body(resources: Mapping[str, Mapping[str, Any]]) -> str:
    parts = [f"{item['label']}: {item['confidence']}" for item in resources.values()]
    return '; '.join(parts) + '. Confidence must be reviewed with history completeness and source freshness.'


def _executive_status(warning_count: int, critical_count: int, coverage_count: int) -> str:
    if critical_count:
        return 'Critical Review'
    if warning_count or coverage_count < len(_RESOURCE_ORDER):
        return 'Review Required'
    if coverage_count:
        return 'Normal'
    return 'Not Available'


def _executive_tone(warning_count: int, critical_count: int, coverage_count: int) -> str:
    if critical_count:
        return 'critical'
    if warning_count or coverage_count < len(_RESOURCE_ORDER):
        return 'warning'
    return 'normal' if coverage_count else 'muted'


def _executive_title(highest: Mapping[str, Any] | None, warning_count: int, critical_count: int) -> str:
    if critical_count:
        return 'Critical forecast exposure requires accountable ownership.'
    if warning_count:
        return 'Forecast warning exposure requires planning review.'
    if highest:
        return f"{highest['label']} is the leading projected resource signal."
    return 'Committed forecast evidence is not available.'


def _executive_body(highest: Mapping[str, Any] | None, warning_count: int, critical_count: int, horizon: str) -> str:
    if not highest:
        return 'No committed resource projection can be assigned for the selected reporting boundary.'
    return (
        f"The highest projected signal is {highest['label']} at {highest['projected_display']}. "
        f"The configured horizon is {_human_window(horizon)} with {warning_count} warning and "
        f"{critical_count} critical exposure(s)."
    )


def _portfolio_interpretation(resources: Mapping[str, Mapping[str, Any]], horizon: str) -> str:
    available = [item for item in resources.values() if item['available']]
    missing = [item['label'] for item in resources.values() if not item['available']]
    if not available:
        return 'Committed forecast evidence was not available for any resource.'
    highest = max(available, key=lambda item: item['projected_percent'])
    message = f"{highest['label']} is the highest projected resource at {highest['projected_display']} within {_human_window(horizon)}."
    if missing:
        message += f" Missing forecast evidence remains explicit for {', '.join(missing)}."
    return message


def _status(value: float) -> str:
    if value >= _CRITICAL_THRESHOLD:
        return 'Critical'
    if value >= _WARNING_THRESHOLD:
        return 'Warning'
    return 'Stable'


def _tone(value: float) -> str:
    if value >= _CRITICAL_THRESHOLD:
        return 'critical'
    if value >= _WARNING_THRESHOLD:
        return 'warning'
    return 'normal'


def _eta(value: Any) -> str:
    if isinstance(value, Mapping):
        return sanitize_text(value.get('label'), fallback='Not projected')
    return sanitize_text(value, fallback='Not projected')


def _priority(value: Any) -> str:
    label = _text(value, '').lower()
    if label in {'p1', 'critical', 'high'}:
        return 'P1'
    if label in {'p2', 'warning', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def _target(priority: str) -> str:
    return {'P1': 'This Week', 'P2': 'Next Week', 'P3': 'This Month'}.get(priority, 'This Month')


def _owner_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in rows:
        owner = sanitize_text(item.get('owner'), fallback='Platform Operations')
        counts[owner] = counts.get(owner, 0) + 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No owner assignment available.'


def _horizon_status(count: int, horizon: str) -> str:
    return f"Within {_human_window(horizon)}" if count else f"None within {_human_window(horizon)}"


def _human_window(value: str) -> str:
    text = sanitize_text(value, fallback='Not Available')
    lower = text.lower()
    if lower.endswith('d') and lower[:-1].isdigit():
        return f'{int(lower[:-1])} Days'
    return text


def _days_from_label(value: str) -> int | None:
    text = value.strip().lower()
    if text.endswith('d') and text[:-1].isdigit():
        return int(text[:-1])
    return None


def _ratio(value: Any, denominator: float | None) -> float | None:
    numerator = _float(value)
    if numerator is None or not denominator:
        return None
    return numerator / denominator * 100.0


def _first_float(*values: Any) -> float | None:
    for value in values:
        parsed = _float(value)
        if parsed is not None:
            return parsed
    return None


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _reference(ref: str, title: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'title': title, 'description': description}


def _percent(value: float | None) -> str:
    return 'Not Available' if value is None else f'{value:.1f}%'


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _int(value: Any) -> int | None:
    parsed = _float(value)
    return int(parsed) if parsed is not None else None


def _text(value: Any, fallback: str = '') -> str:
    return sanitize_text(value, fallback=fallback)


def _format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    text = sanitize_text(value, fallback='Not Available')
    try:
        normalized = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return text
    normalized = normalized.astimezone(UTC) if normalized.tzinfo else normalized.replace(tzinfo=UTC)
    return normalized.strftime('%d %b %Y %H:%M UTC')
