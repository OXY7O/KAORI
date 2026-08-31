from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .model import (
    CRITICAL_THRESHOLD,
    RESOURCE_META,
    WARNING_THRESHOLD,
    ForecastState,
    float_value,
    human_window,
    metric,
    percent,
    reference,
)


def build_cover(state: ForecastState) -> dict[str, str]:
    return {
        'environment': str(state.cluster.get('environment') or 'Not Available'),
        'purpose': (
            'Support operational planning by separating current posture, committed projection, '
            'threshold timing, evidence confidence, and accountable forecast actions.'
        ),
        'context': (
            'Forecast values are read from committed materialized evidence. Missing resource forecasts '
            'remain explicit and are never converted to zero, stable, or healthy.'
        ),
    }


def build_executive(
    state: ForecastState,
    recommendations: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        'metrics': (
            metric(
                'Highest Projection',
                state.highest_value,
                state.highest_status,
                'warning' if state.highest else 'muted',
            ),
            metric(
                'Warning Exposure',
                str(state.warning_count),
                horizon_status(state.warning_count, state.horizon),
                'warning' if state.warning_count else 'normal',
            ),
            metric(
                'Forecast Method',
                state.method,
                'Committed' if state.available else 'Not Available',
                'info' if state.available else 'muted',
            ),
            metric(
                'Forecast Coverage',
                f'{state.coverage_count} / {len(RESOURCE_META)}',
                'Committed Resources',
                'normal' if state.coverage_count == len(RESOURCE_META) else 'warning',
            ),
        ),
        'status': state.forecast_status,
        'tone': state.forecast_tone,
        'resources': tuple(state.resources[key] for key in RESOURCE_META),
        'interpretation_title': executive_title(
            state.highest,
            state.warning_count,
            state.critical_count,
        ),
        'interpretation_body': executive_body(
            state.highest,
            state.warning_count,
            state.critical_count,
            state.horizon,
        ),
        'interpretation_note': (
            'Threshold ETA beyond the configured horizon is a long-range planning signal, not an '
            'immediate breach. Planned deployments and live state are outside the model.'
        ),
        'decisions': tuple(recommendations['rows'][:4]),
    }


def build_portfolio(state: ForecastState) -> dict[str, Any]:
    return {
        'metrics': tuple(
            metric(
                f'{item["label"]} Projection',
                item['projected_display'],
                item['status'],
                item['tone'],
            )
            for item in state.resources.values()
        ),
        'chart_svg': state.combined_chart,
        'rows': tuple(portfolio_row(state.resources[key], index + 1) for index, key in enumerate(RESOURCE_META)),
        'interpretation': portfolio_interpretation(state.resources, state.horizon),
    }


def build_resource_page(resource: Mapping[str, Any], title: str) -> dict[str, Any]:
    projected = float_value(resource.get('peak_projected_percent'))
    available = bool(resource.get('available')) and projected is not None
    assessment_title, assessment_body, assessment_note = resource_assessment(
        resource,
        title,
        projected,
        available,
    )
    return {
        'resource': resource,
        'metrics': (
            metric('Current', resource['current_display'], resource['status'], resource['tone']),
            metric(
                'Peak Projection',
                resource['peak_projected_display'],
                resource['status'],
                resource['tone'],
            ),
            metric(
                'Projected Headroom',
                resource['headroom_display'],
                'Available' if available else 'Not Available',
                'normal' if available else 'warning',
            ),
            metric(
                'Warning ETA',
                resource['warning_eta'],
                'Threshold Timing',
                'warning' if resource['warning_eta'] not in {'Not projected', 'Not Available'} else 'muted',
            ),
        ),
        'assessment_title': assessment_title,
        'assessment_body': assessment_body,
        'assessment_note': assessment_note,
        'register': resource_register(resource, available),
    }


def resource_assessment(
    resource: Mapping[str, Any],
    title: str,
    projected: float | None,
    available: bool,
) -> tuple[str, str, str]:
    if not available:
        return (
            f'{title} forecast evidence is not available.',
            str(resource['empty_reason']),
            'The report does not convert missing evidence into zero usage, stable direction, or healthy capacity.',
        )
    if projected is not None and projected >= CRITICAL_THRESHOLD:
        return (
            f'{title} is projected in the critical operating band.',
            'Immediate ownership and live-state validation are required before capacity or workload changes.',
            'Forecast conclusions remain subject to model confidence, source freshness, and approved change controls.',
        )
    if projected is not None and projected >= WARNING_THRESHOLD:
        return (
            f'{title} is projected in the warning operating band.',
            'Review growth assumptions, accountable ownership, and the available threshold ETA.',
            'A forecast warning is a planning signal and does not authorize autonomous remediation.',
        )
    return (
        f'{title} remains below the warning band in the configured horizon.',
        (
            'Maintain committed forecast coverage and validate whether known deployments could change '
            'the projected direction.'
        ),
        'Live-state spikes and workload-specific concentration remain separate operational evidence.',
    )


def resource_register(resource: Mapping[str, Any], available: bool) -> tuple[dict[str, Any], ...]:
    prefix = str(resource['key'])[:1].upper()
    return (
        {
            'ref': f'{prefix}1',
            'dimension': 'Current Signal',
            'value': resource['current_display'],
            'evidence': 'Committed' if available else 'Missing',
            'status': resource['status'],
            'tone': resource['tone'],
        },
        {
            'ref': f'{prefix}2',
            'dimension': 'Peak Projected Signal',
            'value': resource['peak_projected_display'],
            'evidence': 'Committed' if available else 'Missing',
            'status': resource['status'],
            'tone': resource['tone'],
        },
        {
            'ref': f'{prefix}3',
            'dimension': 'Projected Headroom',
            'value': resource['headroom_display'],
            'evidence': 'Derived' if available else 'Missing',
            'status': 'Available' if available else 'Not Available',
            'tone': 'normal' if available else 'warning',
        },
        {
            'ref': f'{prefix}4',
            'dimension': 'Warning ETA',
            'value': resource['warning_eta'],
            'evidence': resource['confidence'],
            'status': 'Review' if available else 'Not Available',
            'tone': 'warning' if available else 'muted',
        },
    )


def build_pod_storage(state: ForecastState) -> dict[str, Any]:
    pods = state.resources['pods']
    storage = state.resources['storage']
    return {
        'metrics': (
            metric('Pod Current', pods['current_display'], pods['status'], pods['tone']),
            metric('Pod Projection', pods['projected_display'], pods['status'], pods['tone']),
            metric(
                'Storage Current',
                storage['current_display'],
                storage['status'],
                storage['tone'],
            ),
            metric(
                'Storage Projection',
                storage['projected_display'],
                storage['status'],
                storage['tone'],
            ),
        ),
        'pods': build_resource_page(pods, 'Pods'),
        'storage': build_resource_page(storage, 'Storage'),
        'rows': (
            resource_register_row(pods, 'S1'),
            headroom_row(pods, 'S2'),
            resource_register_row(storage, 'S3'),
            threshold_row(storage, 'S4'),
        ),
    }


def build_exposure(state: ForecastState) -> dict[str, Any]:
    return {
        'metrics': (
            metric(
                'Warning Exposures',
                str(state.warning_count),
                horizon_status(state.warning_count, state.horizon),
                'warning' if state.warning_count else 'normal',
            ),
            metric(
                'Critical Exposures',
                str(state.critical_count),
                horizon_status(state.critical_count, state.horizon),
                'critical' if state.critical_count else 'normal',
            ),
            metric(
                'Committed Forecasts',
                str(state.coverage_count),
                'Available Resources',
                'normal' if state.coverage_count else 'muted',
            ),
            metric(
                'Evidence Gaps',
                str(len(RESOURCE_META) - state.coverage_count),
                'Requires Review' if state.coverage_count < len(RESOURCE_META) else 'Clear',
                'warning' if state.coverage_count < len(RESOURCE_META) else 'normal',
            ),
        ),
        'rows': tuple(exposure_row(state.resources[key], index + 1) for index, key in enumerate(RESOURCE_META)),
        'confidence_title': confidence_title(state.resources),
        'confidence_body': confidence_body(state.resources),
        'boundary_title': 'Committed observations define the forecast boundary.',
        'boundary_body': (
            'Planned deployments, approved infrastructure expansion, workload migrations, and live '
            'state after the report cut-off are not modeled.'
        ),
        'boundary_note': 'Missing observations remain visible as gaps and must not be converted to zero.',
    }


def build_methodology(
    state: ForecastState,
    *,
    sources: tuple[dict[str, str], ...],
    period_label: str,
    data_cutoff: str,
) -> dict[str, Any]:
    return {
        'metrics': (
            metric(
                'Data Sources',
                str(len(sources)),
                'Committed' if sources else 'Not Available',
                'normal' if sources else 'muted',
            ),
            metric('Forecast Horizon', human_window(state.horizon), 'Configured', 'info'),
            metric(
                'Forecast Method',
                state.method,
                'Committed' if state.available else 'Not Available',
                'info' if state.available else 'muted',
            ),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ),
        'sources': sources,
        'rules': (
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
            {'ref': 'M3', 'rule': 'Threshold Bands', 'setting': '75% / 90%'},
            {'ref': 'M4', 'rule': 'Forecast Method', 'setting': state.method},
            {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
        ),
        'references': (
            reference(
                'M3',
                'Threshold Bands',
                'Normal below 75%, warning from 75% to 89.9%, and critical at 90% or above.',
            ),
            reference(
                'M4',
                'Forecast Method',
                f'{state.method} is used where committed historical evidence is available.',
            ),
            reference(
                'M5',
                'Missing Evidence',
                'Unavailable forecast dimensions remain explicit and are never converted to zero.',
            ),
        ),
        'included': (
            'Committed resource history and projected endpoints returned by the materialized forecast dataset.',
            'Configured threshold bands, horizon, model label, confidence, and threshold ETA when available.',
            'Committed actionable forecast recommendations and source-freshness evidence.',
        ),
        'excluded': (
            'Live cluster state after the report cut-off.',
            (
                'Planned deployments, infrastructure expansion, or workload migrations not represented '
                'in committed evidence.'
            ),
            'Forecast values for resources without sufficient history or capacity evidence.',
        ),
        'limitations': (
            'Forecasts support planning and do not authorize autonomous remediation.',
            'Threshold ETA beyond the configured horizon is a long-range planning signal.',
            'Validate every recommendation against live state, ownership, and approved change controls.',
        ),
        'status_language': (
            reference('S1', 'Not Available', 'No committed forecast exists for the requested dimension.'),
            reference('S2', 'Not Collected', 'Collection was prevented by configuration or failure.'),
            reference('S3', 'Partial Coverage', 'Evidence exists but does not cover the full requested scope.'),
            reference(
                'S4',
                'Source Unavailable',
                'The source was unreachable or not providing data at the cut-off.',
            ),
        ),
        'history_window': state.history_window,
        'horizon': state.horizon,
        'horizon_days': state.horizon_days,
    }


def portfolio_row(resource: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        'ref': f'P{index}',
        'resource': resource['label'],
        'current': resource['current_display'],
        'projection': resource['peak_projected_display'],
        'warning_eta': resource['warning_eta'],
        'confidence': resource['confidence'],
        'assessment': resource['status'],
        'tone': resource['tone'],
    }


def resource_register_row(resource: Mapping[str, Any], ref: str) -> dict[str, Any]:
    return {
        'ref': ref,
        'dimension': resource['label'],
        'current': resource['current_display'],
        'projection': resource['peak_projected_display'],
        'evidence': 'Committed' if resource['available'] else 'Missing',
        'status': resource['status'],
        'tone': resource['tone'],
    }


def headroom_row(resource: Mapping[str, Any], ref: str) -> dict[str, Any]:
    return {
        'ref': ref,
        'dimension': f'{resource["label"]} Projected Headroom',
        'current': (percent(max(0.0, 100.0 - resource['current_percent'])) if resource['available'] else 'Not Available'),
        'projection': resource['headroom_display'],
        'evidence': 'Derived' if resource['available'] else 'Missing',
        'status': 'Available' if resource['available'] else 'Not Available',
        'tone': 'normal' if resource['available'] else 'warning',
    }


def threshold_row(resource: Mapping[str, Any], ref: str) -> dict[str, Any]:
    return {
        'ref': ref,
        'dimension': f'{resource["label"]} Threshold ETA',
        'current': resource['warning_eta'],
        'projection': resource['critical_eta'],
        'evidence': resource['confidence'],
        'status': 'Review' if resource['available'] else 'Not Available',
        'tone': 'warning' if resource['available'] else 'muted',
    }


def exposure_row(resource: Mapping[str, Any], index: int) -> dict[str, Any]:
    exposure = 'Not Assessable'
    if resource['available']:
        if resource['peak_projected_percent'] >= CRITICAL_THRESHOLD:
            exposure = 'Critical Exposure'
        elif resource['peak_projected_percent'] >= WARNING_THRESHOLD:
            exposure = 'Warning Exposure'
        else:
            exposure = 'No Exposure'
    return {
        'ref': f'T{index}',
        'resource': resource['label'],
        'projection': resource['peak_projected_display'],
        'warning': '75%',
        'critical': '90%',
        'exposure': exposure,
        'confidence': resource['confidence'],
        'tone': resource['tone'],
    }


def confidence_title(resources: Mapping[str, Mapping[str, Any]]) -> str:
    unavailable = [item['label'] for item in resources.values() if not item['available']]
    if unavailable:
        return 'Forecast coverage is incomplete and requires explicit review.'
    qualities = {str(item['confidence']).lower() for item in resources.values()}
    if 'low' in qualities:
        return 'At least one resource has low forecast confidence.'
    return 'Committed forecast confidence is available for all resources.'


def confidence_body(resources: Mapping[str, Mapping[str, Any]]) -> str:
    parts = [f'{item["label"]}: {item["confidence"]}' for item in resources.values()]
    return '; '.join(parts) + '. Confidence must be reviewed with history completeness and source freshness.'


def executive_title(
    highest: Mapping[str, Any] | None,
    warning_count: int,
    critical_count: int,
) -> str:
    if critical_count:
        return 'Critical forecast exposure requires accountable ownership.'
    if warning_count:
        return 'Forecast warning exposure requires planning review.'
    if highest:
        return f'{highest["label"]} is the leading projected resource signal.'
    return 'Committed forecast evidence is not available.'


def executive_body(
    highest: Mapping[str, Any] | None,
    warning_count: int,
    critical_count: int,
    horizon: str,
) -> str:
    if not highest:
        return 'No committed resource projection can be assigned for the selected reporting boundary.'
    return (
        f'The highest peak projected signal is {highest["label"]} at {highest["peak_projected_display"]}. '
        f'The configured horizon is {human_window(horizon)} with {warning_count} warning and '
        f'{critical_count} critical exposure(s).'
    )


def portfolio_interpretation(resources: Mapping[str, Mapping[str, Any]], horizon: str) -> str:
    available = [item for item in resources.values() if item['available']]
    missing = [item['label'] for item in resources.values() if not item['available']]
    if not available:
        return 'Committed forecast evidence was not available for any resource.'
    highest = max(available, key=lambda item: item['peak_projected_percent'])
    message = (
        f'{highest["label"]} is the highest peak projected resource at '
        f'{highest["peak_projected_display"]} within {human_window(horizon)}.'
    )
    if missing:
        message += f' Missing forecast evidence remains explicit for {", ".join(missing)}.'
    return message


def horizon_status(count: int, horizon: str) -> str:
    return f'Within {human_window(horizon)}' if count else f'None within {human_window(horizon)}'
