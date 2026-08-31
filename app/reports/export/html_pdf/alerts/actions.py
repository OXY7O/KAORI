from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .model import AlertsState, mapping, metric, sequence


def severity_category_register(state: AlertsState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(state.severity_rows, start=1):
        rows.append(
            {
                'ref': f'S{index}',
                'dimension': item['label'],
                'count': str(item['count']),
                'evidence': 'Committed Severity',
                'status': 'Review' if item['count'] else 'Clear',
                'tone': item['tone'] if item['count'] else 'normal',
            }
        )
    for index, item in enumerate(state.category_rows, start=1):
        rows.append(
            {
                'ref': f'C{index}',
                'dimension': item['label'],
                'count': str(item['count']),
                'evidence': 'Displayed Category',
                'status': 'Review',
                'tone': 'warning',
            }
        )
    return rows


def alert_references(alerts: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            'ref': f'A{index}',
            'title': item['name'],
            'description': (
                f'Validate {item["namespace"]} live state, expected behavior, and accountable ownership. '
                f'{item["summary"]}'
            ),
        }
        for index, item in enumerate(alerts, start=1)
    ]


def ownership_rows(state: AlertsState) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index = 1
    for item in state.alerts[:5]:
        owner = item['owner'] if item['owner'] != 'Not Available' else owner_domain(item['namespace'])
        result.append(
            {
                'ref': f'O{index}',
                'scope': item['namespace'],
                'owner': owner,
                'focus': item['name'],
                'coverage': metadata_coverage(item),
                'status': 'Review',
            }
        )
        index += 1
    for item in state.anomalies[:2]:
        if len(result) >= 6:
            break
        result.append(
            {
                'ref': f'O{index}',
                'scope': item['namespace'],
                'owner': owner_domain(item['namespace']),
                'focus': item['name'],
                'coverage': 'Partial',
                'status': 'Review',
            }
        )
        index += 1
    return result


def correlation_rows(state: AlertsState) -> list[dict[str, Any]]:
    alerts_by_namespace: dict[str, list[str]] = defaultdict(list)
    anomalies_by_namespace: dict[str, list[str]] = defaultdict(list)
    for item in state.alerts:
        alerts_by_namespace[item['namespace']].append(item['name'])
    for item in state.anomalies:
        anomalies_by_namespace[item['namespace']].append(item['name'])

    rows = common_namespace_correlations(alerts_by_namespace, anomalies_by_namespace)
    append_related_alert_rows(rows, alerts_by_namespace)
    rows.append(
        {
            'ref': f'C{len(rows) + 1}',
            'scope': 'Category Coverage',
            'signal_a': f'{state.active_count} active alerts',
            'signal_b': f'{state.categorized_count} categorized',
            'relationship': 'Partial' if state.categorized_count < state.active_count else 'Complete',
            'status': 'Reconcile' if state.categorized_count < state.active_count else 'Current',
        }
    )
    return rows[:5]


def common_namespace_correlations(
    alerts_by_namespace: Mapping[str, list[str]],
    anomalies_by_namespace: Mapping[str, list[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for namespace in sorted(set(alerts_by_namespace) & set(anomalies_by_namespace)):
        rows.append(
            {
                'ref': f'C{len(rows) + 1}',
                'scope': namespace,
                'signal_a': alerts_by_namespace[namespace][0],
                'signal_b': anomalies_by_namespace[namespace][0],
                'relationship': 'Unconfirmed',
                'status': 'Review',
            }
        )
    return rows


def append_related_alert_rows(rows: list[dict[str, Any]], alerts_by_namespace: Mapping[str, list[str]]) -> None:
    if len(rows) >= 5:
        return
    for namespace, names in alerts_by_namespace.items():
        if len(names) < 2 or len(rows) >= 4:
            continue
        rows.append(
            {
                'ref': f'C{len(rows) + 1}',
                'scope': namespace,
                'signal_a': names[0],
                'signal_b': names[1],
                'relationship': 'Related alerts',
                'status': 'Review',
            }
        )


def build_recommendations(state: AlertsState) -> list[dict[str, Any]]:
    items = provided_recommendations(state.payload)
    append_default_recommendations(items, state)
    items.sort(key=lambda item: (int(item['priority'][1]), item['ref']))
    for index, item in enumerate(items, start=1):
        item['ref'] = f'R{index}'
    return items


def provided_recommendations(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = sequence(payload.get('actionable_recommendations') or payload.get('recommendations'))
    items: list[dict[str, Any]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            continue
        level = priority(value.get('priority') or value.get('severity'))
        items.append(
            {
                'ref': f'R{len(items) + 1}',
                'priority': level,
                'title': sanitize_text(value.get('title'), fallback='Review Alert and Anomaly Evidence'),
                'description': sanitize_text(
                    value.get('description'),
                    fallback='Validate the signal against live state and expected workload behavior.',
                ),
                'owner': sanitize_text(value.get('owner'), fallback='Platform Operations'),
                'target': 'This Week' if level == 'P1' else ('Next Week' if level == 'P2' else 'This Month'),
                'status': 'Open' if level in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if level == 'P1' else ('warning' if level == 'P2' else 'info'),
            }
        )
        if len(items) >= 5:
            break
    return items


def append_default_recommendations(items: list[dict[str, Any]], state: AlertsState) -> None:
    defaults: list[tuple[str, str, str, str]] = []
    for alert in state.alerts[:3]:
        defaults.append(
            (
                'P2',
                f'Validate {alert["name"]}',
                f'Confirm live state, expected behavior, and ownership for {alert["namespace"]}.',
                owner_domain(alert['namespace']),
            )
        )
    if state.anomalies and not all(item['evidence_available'] for item in state.anomalies):
        defaults.append(
            (
                'P2',
                'Restore Anomaly Evidence',
                'Commit observation window, metric deviation, entity identity, and related event evidence.',
                'Observability Owner',
            )
        )
    if state.uncategorized_count:
        defaults.append(
            (
                'P3',
                'Reconcile Alert Categories',
                f'Reconcile {state.uncategorized_count} active alert(s) outside the displayed category summary.',
                'Observability Owner',
            )
        )
    append_unique_defaults(items, defaults)


def append_unique_defaults(items: list[dict[str, Any]], defaults: list[tuple[str, str, str, str]]) -> None:
    existing = {item['title'] for item in items}
    for level, title, description, owner in defaults:
        if title in existing or len(items) >= 5:
            continue
        items.append(
            {
                'ref': f'R{len(items) + 1}',
                'priority': level,
                'title': title,
                'description': description,
                'owner': owner,
                'target': 'Next Week' if level == 'P2' else 'This Month',
                'status': 'Open' if level == 'P2' else 'Planned',
                'tone': 'warning' if level == 'P2' else 'info',
            }
        )
        existing.add(title)


def source_rows(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    source_status = mapping(payload.get('source_status'))
    anomaly_status = mapping(payload.get('anomaly_source_status'))
    return [
        {
            'source': sanitize_text(
                source_status.get('label') or source_status.get('resolved_source'), fallback='Alert Source'
            ),
            'freshness': response_time(source_status),
            'last_collected': 'At report cut-off',
        },
        {
            'source': sanitize_text(anomaly_status.get('label'), fallback='Analytics Anomaly Evidence'),
            'freshness': response_time(anomaly_status),
            'last_collected': 'At report cut-off',
        },
    ]


def recommendation_metrics(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    p1_count = sum(1 for item in items if item['priority'] == 'P1')
    return [
        metric('P1 Actions', str(p1_count), 'Immediate', 'critical' if p1_count else 'normal'),
        metric('P2 Actions', str(sum(1 for item in items if item['priority'] == 'P2')), 'Open', 'warning'),
        metric('P3 Actions', str(sum(1 for item in items if item['priority'] == 'P3')), 'Planned', 'info'),
        metric('Validation Gates', str(len(items)), 'Required', 'info'),
    ]


def priority(value: Any) -> str:
    normalized = sanitize_text(value, fallback='P3').lower()
    if normalized in {'p1', 'critical', 'high'}:
        return 'P1'
    if normalized in {'p2', 'warning', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def owner_domain(namespace: str) -> str:
    if namespace.lower() in {'monitoring', 'logging', 'kube-system', 'openebs'}:
        return 'Platform Operations'
    return 'Application Owner'


def metadata_coverage(item: Mapping[str, Any]) -> str:
    available = sum(1 for key in ('owner', 'runbook', 'contact') if item.get(key) not in {None, '', 'Not Available'})
    if available == 3:
        return 'Complete'
    if available:
        return 'Partial'
    return 'Missing'


def oldest_label(alerts: list[dict[str, Any]]) -> str:
    values = [item['starts_at_display'] for item in alerts if item['starts_at_display'] != 'Not Available']
    return values[0] if values else 'Not Available'


def response_time(value: Mapping[str, Any]) -> str:
    response = value.get('response_time_ms')
    try:
        if response is not None:
            return f'{int(response)} ms'
        return 'Partial' if value.get('partial') else 'At report cut-off'
    except (TypeError, ValueError):
        return 'At report cut-off'


def owner_summary(items: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item['owner']] += 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No assigned action.'
