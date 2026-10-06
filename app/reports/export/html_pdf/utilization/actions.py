from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .model import (
    UtilizationState,
    float_value,
    mapping,
    metric,
    optional_percent,
    percent,
    sequence,
)


def forecast_confidence(state: UtilizationState) -> str:
    qualities = [sanitize_text(item.get('signal_quality'), fallback='') for item in state.forecast_items.values()]
    qualities = [quality for quality in qualities if quality]
    if not qualities:
        return 'Not Available'
    normalized = ' '.join(qualities).lower()
    if 'low' in normalized or 'poor' in normalized:
        return 'Review'
    if 'medium' in normalized:
        return 'Moderate'
    return 'High'


def leading_interpretation(item: dict[str, Any]) -> str:
    value = float_value(item.get('percent'))
    if value >= 85:
        return f'{item.get("label")} is in the critical operating band and requires immediate validation.'
    if value >= 70:
        return f'{item.get("label")} is in the warning operating band and requires capacity review.'
    return (
        f'{item.get("label")} remains below the warning band. Review direction and workload concentration '
        'before considering aggregate capacity expansion.'
    )


def priority_findings(
    state: UtilizationState,
    source_rows: list[dict[str, str]],
) -> tuple[dict[str, str], ...]:
    memory_description = (
        'Review current memory utilization and committed projection evidence.'
        if state.forecast_items
        else 'Review current memory utilization; projection evidence was not available.'
    )
    cpu_description = (
        f'Validate whether {state.cpu_consumers[0]["name"]} is expected for the selected reporting boundary.'
        if state.cpu_consumers
        else 'No top CPU consumer evidence was returned.'
    )
    return (
        {
            'ref': 'F1',
            'priority': 'P2' if float_value(state.memory.get('percent')) >= 50 else 'P3',
            'title': 'Memory Utilization Direction',
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


def cpu_assessment(state: UtilizationState) -> str:
    if float_value(state.cpu.get('percent')) >= 70:
        return (
            'The committed CPU signal is in or above the warning band. Confirm sustained demand, '
            'workload ownership, and available headroom.'
        )
    if state.cpu_consumers:
        return (
            'The committed P95 is below the warning threshold. Operational review should focus on whether '
            'the leading individual consumers are expected, not on aggregate expansion.'
        )
    return 'The committed P95 is below the warning threshold, but consumer-level evidence was not available.'


def memory_assessment_title(state: UtilizationState) -> str:
    current = float_value(state.memory.get('percent'))
    if current >= 85:
        return 'Memory is currently in the critical operating band.'
    if current >= 70:
        return 'Memory requires immediate capacity review.'
    if state.memory_projection is not None and state.memory_projection >= 70:
        return 'Memory is normal now but is the primary planning signal.'
    return 'Memory remains within the normal operating band.'


def memory_assessment_body(state: UtilizationState) -> str:
    current = float_value(state.memory.get('percent'))
    if state.memory_projection is None:
        return (
            f'The current committed signal is {percent(current)}. Forecast evidence was not available, '
            'so planning conclusions must remain limited to the committed cut-off.'
        )
    return (
        f'The current committed signal is {percent(current)} and the available projection is '
        f'{percent(state.memory_projection)}. Review threshold exposure before capacity pressure becomes operational.'
    )


def forecast_eta(state: UtilizationState) -> str:
    eta = mapping(state.memory_forecast.get('warning_eta'))
    label = eta.get('display') or eta.get('label') or state.memory_forecast.get('warning_eta_display')
    return sanitize_text(label, fallback='Planning Horizon' if state.memory_forecast else 'Not Available')


def distribution_interpretation(state: UtilizationState) -> str:
    if state.memory_consumers and state.cpu_consumers:
        memory_namespace = state.memory_consumers[0]['namespace']
        namespaces = ', '.join(dict.fromkeys(item['namespace'] for item in state.cpu_consumers[:3]))
        return (
            f'The displayed memory signal is concentrated in {memory_namespace} resources, while the '
            f'displayed CPU signal is distributed across {namespaces}. These charts cover only '
            'the displayed top-consumer set.'
        )
    return 'Displayed consumer evidence was incomplete; concentration conclusions remain limited to available records.'


def consumer_register(state: UtilizationState) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for prefix, group in (('M', state.memory_consumers[:3]), ('C', state.cpu_consumers[:3])):
        for index, item in enumerate(group, start=1):
            rows.append({'ref': f'{prefix}{index}', **item})
    return tuple(rows)


def trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return 'Not Available'
    delta = values[-1] - values[0]
    if delta > 2:
        return 'Rising'
    if delta < -2:
        return 'Falling'
    return 'Stable'


def direction_tone(values: list[float]) -> str:
    direction = trend_direction(values)
    if direction == 'Rising':
        return 'warning'
    if direction == 'Not Available':
        return 'muted'
    return 'normal'


def trend_row(
    ref: str,
    resource: str,
    current: float,
    projected: float | None,
    values: list[float],
) -> dict[str, str]:
    assessment = 'Review' if projected is not None and projected >= 70 else trend_direction(values)
    tone = 'warning' if assessment in {'Review', 'Rising'} else 'normal' if assessment != 'Not Available' else 'muted'
    return {
        'ref': ref,
        'resource': resource,
        'current': percent(current),
        'projection': optional_percent(projected),
        'assessment': assessment,
        'tone': tone,
    }


def trend_interpretation(state: UtilizationState) -> str:
    if state.memory_projection is not None and state.memory_projection >= 70:
        return (
            'Memory is the only displayed resource projected to enter or remain in the warning '
            'band within the available planning horizon.'
        )
    if state.memory_projection is not None:
        return 'No displayed resource is projected to enter the warning band within the available planning horizon.'
    return (
        f'Memory is the highest current planning signal at {state.memory.get("value")}; '
        'projection evidence was not available.'
    )


def build_recommendations(state: UtilizationState) -> dict[str, Any]:
    items = _recommendation_items(state)
    p1 = sum(1 for item in items if item['priority'] == 'P1')
    p2 = sum(1 for item in items if item['priority'] == 'P2')
    p3 = sum(1 for item in items if item['priority'] == 'P3')
    return {
        'metrics': (
            metric('P1 Actions', str(p1), 'None' if not p1 else 'Open', 'normal' if not p1 else 'critical'),
            metric('P2 Actions', str(p2), 'Open' if p2 else 'None', 'warning' if p2 else 'normal'),
            metric('P3 Actions', str(p3), 'Planned' if p3 else 'None', 'info' if p3 else 'normal'),
            metric('Validation Gates', str(len(items)), 'Required', 'info'),
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


def _recommendation_items(state: UtilizationState) -> list[dict[str, str]]:
    memory_requires_review = state.memory_projection is not None and state.memory_projection >= 70
    source_ready = metrics_source_ready(state.metrics_source_status)
    return [
        {
            'ref': 'R1',
            'priority': 'P2',
            'title': 'Validate Highest CPU Consumer',
            'owner': 'Platform Operations',
            'target': 'Next Week',
            'status': 'Open' if state.cpu_consumers else 'Evidence Required',
            'tone': 'warning',
            'description': (
                f'Confirm whether {state.cpu_consumers[0]["name"]} is expected for the selected scope and reporting window.'
                if state.cpu_consumers
                else 'Collect top CPU consumer evidence before closing utilization review.'
            ),
        },
        {
            'ref': 'R2',
            'priority': 'P2' if memory_requires_review else 'P3',
            'title': 'Review Memory Growth Direction',
            'owner': 'Platform Operations',
            'target': 'Next Week' if memory_requires_review else 'This Month',
            'status': 'Open' if memory_requires_review else 'Planned',
            'tone': 'warning' if memory_requires_review else 'info',
            'description': (
                f'Validate the projected memory position of {percent(state.memory_projection)} and '
                'include the result in the next capacity gate.'
                if state.memory_projection is not None
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
                f'Confirm that {percent(float_value(state.pods.get("headroom")))} schedulable headroom '
                'matches deployment expectations and scope definitions.'
            ),
        },
        {
            'ref': 'R4',
            'priority': 'P3',
            'title': 'Maintain Node Participation Evidence',
            'owner': 'Platform Operations',
            'target': 'This Month',
            'status': 'Current' if state.total_nodes and state.ready_nodes == state.total_nodes else 'Open',
            'tone': 'normal' if state.total_nodes and state.ready_nodes == state.total_nodes else 'warning',
            'description': 'Ensure not-ready nodes remain excluded from active capacity assumptions and visibly reported.',
        },
        {
            'ref': 'R5',
            'priority': 'P3',
            'title': 'Maintain Utilization Dataset Coverage',
            'owner': 'Observability Owner',
            'target': 'This Month',
            'status': 'Current' if source_ready else 'Open',
            'tone': 'normal' if source_ready else 'warning',
            'description': (
                'Maintain committed metric and forecast evidence coverage.'
                if state.forecast_items
                else 'Maintain committed metric coverage and investigate unavailable forecast evidence.'
            ),
        },
    ]


def build_source_rows(state: UtilizationState, period_label: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in sequence(state.payload.get('source_evidence')):
        if not isinstance(item, dict):
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
    return [
        {
            'source': 'Metrics Source Observation Cache',
            'freshness': _latency(state.metrics_source_status.get('response_time_ms')),
            'last_collected': _format_datetime(state.metrics_source_status.get('last_checked_at')),
        },
        {
            'source': 'Kubernetes Cluster Scope',
            'freshness': 'Committed',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Utilization Trend Evidence',
            'freshness': period_label,
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Forecast Evidence',
            'freshness': sanitize_text(state.forecast_payload.get('forecast_horizon'), fallback='Not Available'),
            'last_collected': _format_datetime(state.forecast_payload.get('generated_at')),
        },
    ]


def metrics_source_ready(status: dict[str, Any] | Any) -> bool:
    normalized = mapping(status)
    label = str(normalized.get('status') or normalized.get('status_label') or '').lower()
    return bool(normalized.get('connected')) or any(
        token in label for token in ('ready', 'connected', 'healthy', 'query ready')
    )


def _format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).strftime('%d %b %Y %H:%M UTC')
    return sanitize_text(value, fallback='Not Available')


def _latency(value: Any) -> str:
    try:
        return f'{float(value):.0f} ms'
    except (TypeError, ValueError):
        return 'Not Available'
