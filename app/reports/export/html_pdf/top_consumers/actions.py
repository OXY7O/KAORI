from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .model import integer, metric, sequence, tone_from_risk


def build_risk_rows(
    rows: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    risky = [row for row in rows if row['risk_key'] in {'critical', 'warning'}]
    for index, row in enumerate(risky[:3], start=1):
        priority = 'P1' if row['risk_key'] == 'critical' else 'P2'
        result.append(
            {
                'ref': f'R{index}',
                'risk': f'{row["resource_label"]} Consumer: {row["identity"]}',
                'priority': priority,
                'impact': 'High' if priority == 'P1' else 'Medium',
                'owner': 'Platform Operations',
                'status': 'Open',
                'tone': tone_from_risk(row['risk_key']),
            }
        )
    defaults = [
        ('Displayed Denominator Limit', 'P2', 'Medium', 'Observability Owner', 'Review'),
        ('Consumer Trend Evidence', 'P3', 'Low', 'Observability Owner', 'Missing'),
        ('Application Owner Mapping', 'P3', 'Low', 'Application Owner', 'Missing'),
    ]
    for title, priority, impact, owner, status in defaults:
        if len(result) >= 5:
            break
        result.append(
            {
                'ref': f'R{len(result) + 1}',
                'risk': title,
                'priority': priority,
                'impact': impact,
                'owner': owner,
                'status': status,
                'tone': 'warning' if priority == 'P2' else 'muted',
            }
        )
    return result


def build_recommendations(
    payload: Mapping[str, Any],
    cpu_rows: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw = sequence(payload.get('actionable_recommendations'))
    items: list[dict[str, Any]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            continue
        title = sanitize_text(value.get('title'), fallback='Review Top Consumer Evidence')
        description = sanitize_text(
            value.get('description'),
            fallback='Validate the displayed record against live state and expected workload behavior.',
        )
        priority = priority_for(value.get('priority') or value.get('severity'))
        items.append(
            {
                'ref': f'A{len(items) + 1}',
                'priority': priority,
                'title': title,
                'description': description,
                'owner': sanitize_text(value.get('owner'), fallback='Platform Operations'),
                'target': 'This Week' if priority == 'P1' else ('Next Week' if priority == 'P2' else 'This Month'),
                'status': 'Open' if priority in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if priority == 'P1' else ('warning' if priority == 'P2' else 'info'),
            }
        )
        if len(items) >= 5:
            break
    add_default_recommendations(items, cpu_rows, memory_rows)
    items.sort(key=lambda item: (int(item['priority'][1]), item['ref']))
    for index, item in enumerate(items, start=1):
        item['ref'] = f'A{index}'
    return items


def add_default_recommendations(
    items: list[dict[str, Any]],
    cpu_rows: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
) -> None:
    defaults: list[tuple[str, str, str, str]] = []
    if cpu_rows:
        defaults.append(
            (
                'P2',
                'Validate Highest CPU Consumer',
                f'Confirm whether {cpu_rows[0]["identity"]} is expected for the selected scope and reporting window.',
                'Platform Operations',
            )
        )
    if memory_rows:
        defaults.append(
            (
                'P2',
                'Validate Memory Concentration',
                f'Confirm whether the displayed {memory_rows[0]["namespace"]} memory concentration is expected.',
                'Platform Operations',
            )
        )
    defaults.extend(
        [
            (
                'P2',
                'Confirm Displayed Denominator',
                'Document whether the published ranking set represents complete or partial resource evidence.',
                'Observability Owner',
            ),
            (
                'P3',
                'Restore Consumer Trend Evidence',
                'Commit consumer-level historical direction before concluding sustained growth or decline.',
                'Observability Owner',
            ),
            (
                'P3',
                'Map Application Ownership',
                'Resolve committed application ownership before assigning workload changes.',
                'Application Owner',
            ),
        ]
    )
    existing = {item['title'] for item in items}
    for priority, title, description, owner in defaults:
        if title in existing or len(items) >= 5:
            continue
        items.append(
            {
                'ref': f'A{len(items) + 1}',
                'priority': priority,
                'title': title,
                'description': description,
                'owner': owner,
                'target': 'Next Week' if priority == 'P2' else 'This Month',
                'status': 'Open' if priority == 'P2' else 'Planned',
                'tone': 'warning' if priority == 'P2' else 'info',
            }
        )


def recommendation_metrics(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        metric(
            'P1 Actions',
            str(sum(1 for item in items if item['priority'] == 'P1')),
            'Immediate',
            'critical' if any(item['priority'] == 'P1' for item in items) else 'normal',
        ),
        metric('P2 Actions', str(sum(1 for item in items if item['priority'] == 'P2')), 'Open', 'warning'),
        metric('P3 Actions', str(sum(1 for item in items if item['priority'] == 'P3')), 'Planned', 'info'),
        metric('Validation Gates', str(len(items)), 'Required', 'info'),
    ]


def primary_interpretation(cpu_rows: list[dict[str, Any]], memory_rows: list[dict[str, Any]]) -> dict[str, str]:
    if memory_rows and len({row['namespace'] for row in memory_rows}) == 1:
        namespace = memory_rows[0]['namespace']
        return {
            'title': f'Displayed memory concentration is localized in {namespace}.',
            'body': (
                f'All {len(memory_rows)} displayed memory records belong to {namespace}. '
                f'Displayed CPU contribution spans {len({row["namespace"] for row in cpu_rows})} namespace(s).'
            ),
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


def build_source_evidence(
    payload: Mapping[str, Any],
    metrics_source: Mapping[str, Any],
) -> list[dict[str, str]]:
    raw = sequence(payload.get('source_evidence'))
    result = []
    for value in raw:
        if isinstance(value, Mapping):
            result.append(
                {
                    'source': sanitize_text(value.get('source'), fallback='Consumer Evidence'),
                    'freshness': sanitize_text(value.get('freshness'), fallback='At report cut-off'),
                    'last_collected': sanitize_text(value.get('last_collected'), fallback='At report cut-off'),
                }
            )
    if not result:
        result = [
            {
                'source': 'Metrics Source Consumer Evidence',
                'freshness': response_time(metrics_source),
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Committed Top Consumer Records',
                'freshness': 'Displayed resource rows',
                'last_collected': 'At report cut-off',
            },
        ]
    return result[:4]


def priority_for(value: Any) -> str:
    normalized = sanitize_text(value, fallback='P3').lower()
    if normalized in {'p1', 'critical', 'high'}:
        return 'P1'
    if normalized in {'p2', 'warning', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def owner_summary(items: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item['owner']] += 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No assigned action.'


def response_time(value: Mapping[str, Any]) -> str:
    response = value.get('response_time_ms')
    return f'{integer(response)} ms' if response is not None else 'At report cut-off'
