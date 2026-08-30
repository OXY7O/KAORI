from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .forecast import CapacityForecastState
from .model import RESOURCE_LABELS, CapacityState, mapping, percent, sequence


@dataclass(frozen=True)
class CapacityActionState:
    risks: tuple[dict[str, str], ...]
    recommendations: tuple[dict[str, str], ...]
    source_rows: tuple[dict[str, str], ...]
    executive_findings: tuple[dict[str, str], ...]
    evidence_gap_count: int
    p1_count: int
    p2_count: int
    p3_count: int


def compute_register_row(
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


def executive_interpretation(
    leading: Mapping[str, Any] | None,
    evidence_gap_count: int,
) -> str:
    if leading is None:
        return 'Committed capacity evidence was not available for the selected reporting boundary.'
    text = (
        f'{leading["label"]} is the highest available utilization signal at '
        f'{leading["used_display"]} with {leading["headroom_display"]} remaining headroom.'
    )
    if evidence_gap_count:
        text += f' {evidence_gap_count} resource domain(s) remain unavailable and must not be interpreted as healthy.'
    return text


def executive_findings(
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
            'description': (
                'Retain current memory headroom and committed projection evidence in the next capacity gate.'
            ),
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


def risk_rows(
    *,
    payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
    allocations: Mapping[str, Mapping[str, Any]],
    total_nodes: int,
    ready_nodes: int,
    projections: Mapping[str, float | None],
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in sequence(payload.get('risk_summary')):
        if not isinstance(item, Mapping):
            continue
        key = str(item.get('resource') or '').lower()
        if key not in resources:
            continue
        resource = resources[key]
        status = mapping(item.get('status'))
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
                'title': f'{RESOURCE_LABELS[key]} Allocation Pressure',
                'priority': 'P1' if allocation['tone'] == 'critical' else 'P2',
                'impact': 'High' if allocation['tone'] == 'critical' else 'Medium',
                'owner': 'Platform Operations',
                'status': allocation['status'],
                'tone': allocation['tone'],
                'description': (
                    f'Allocation status is {allocation["status"]}; validate requests, limits, actual use, and peak use.'
                ),
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
                'description': (
                    f'{total_nodes - ready_nodes} node(s) are not ready and excluded from active capacity assumptions.'
                ),
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
                'description': (
                    f'Memory projects to {percent(projections["memory"])} within the committed planning horizon.'
                ),
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


def recommendation_rows(
    *,
    payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, float | None],
    total_nodes: int,
    ready_nodes: int,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for card in sequence(payload.get('recommendation_cards')):
        if not isinstance(card, Mapping):
            continue
        title = sanitize_text(card.get('title'), fallback='Review Capacity Evidence')
        description = sanitize_text(
            card.get('description'),
            fallback='Validate the committed capacity evidence.',
        )
        priority = priority_code(card.get('priority'))
        owner = (
            'Observability Owner'
            if 'coverage' in title.lower() or 'metrics_source' in title.lower()
            else 'Platform Operations'
        )
        rows.append(
            {
                'ref': f'A{len(rows) + 1}',
                'priority': priority,
                'title': title,
                'owner': owner,
                'target': ('This Week' if priority == 'P1' else 'Next Week' if priority == 'P2' else 'This Month'),
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
                'description': ('Restore or formally exclude not-ready nodes before relying on schedulable capacity.'),
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


def priority_code(value: Any) -> str:
    normalized = sanitize_text(value, fallback='Info').lower()
    if normalized in {'p1', 'critical', 'urgent', 'high'}:
        return 'P1'
    if normalized in {'p2', 'warning', 'review', 'medium'}:
        return 'P2'
    return 'P3'


def owner_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        owner = sanitize_text(row.get('owner'), fallback='Unassigned')
        counts[owner] = counts.get(owner, 0) + 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No action owner assigned.'


def source_rows(
    *,
    payload: Mapping[str, Any],
    metrics_source_status: Mapping[str, Any],
    forecast_payload: Mapping[str, Any],
    period_label: str,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in sequence(payload.get('source_evidence')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'source': sanitize_text(item.get('source'), fallback='Capacity Evidence'),
                'freshness': sanitize_text(item.get('freshness'), fallback='Not Available'),
                'last_collected': format_datetime(item.get('last_collected')),
            }
        )
    if not rows:
        rows = [
            {
                'source': 'Metrics Source Observation Cache',
                'freshness': latency(metrics_source_status.get('response_time_ms')),
                'last_collected': format_datetime(metrics_source_status.get('last_checked_at')),
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
                'last_collected': format_datetime(forecast_payload.get('generated_at')),
            },
        ]
    return tuple(rows[:4])


def format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.strftime('%d %b %Y %H:%M UTC')
    return sanitize_text(value, fallback='Not Available')


def latency(value: Any) -> str:
    try:
        return f'{float(value):.0f} ms'
    except (TypeError, ValueError):
        return 'Not Available'


def risk_interpretation(
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


def build_capacity_action_state(
    payload: Mapping[str, Any],
    state: CapacityState,
    forecast: CapacityForecastState,
    *,
    period_label: str,
) -> CapacityActionState:
    risks = risk_rows(
        payload=payload,
        resources=state.resources,
        allocations=state.allocations,
        total_nodes=state.total_nodes,
        ready_nodes=state.ready_nodes,
        projections=forecast.projections,
    )
    recommendations = recommendation_rows(
        payload=payload,
        resources=state.resources,
        projections=forecast.projections,
        total_nodes=state.total_nodes,
        ready_nodes=state.ready_nodes,
    )
    sources = source_rows(
        payload=payload,
        metrics_source_status=state.metrics_source_status,
        forecast_payload=state.forecast_payload,
        period_label=period_label,
    )
    findings = executive_findings(
        resources=state.resources,
        projections=forecast.projections,
        total_nodes=state.total_nodes,
        ready_nodes=state.ready_nodes,
    )
    evidence_gap_count = sum(1 for item in state.resources.values() if not item['evidence_available'])
    return CapacityActionState(
        risks=risks,
        recommendations=recommendations,
        source_rows=sources,
        executive_findings=findings,
        evidence_gap_count=evidence_gap_count,
        p1_count=sum(1 for item in recommendations if item['priority'] == 'P1'),
        p2_count=sum(1 for item in recommendations if item['priority'] == 'P2'),
        p3_count=sum(1 for item in recommendations if item['priority'] == 'P3'),
    )
