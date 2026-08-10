from __future__ import annotations

from collections import Counter, defaultdict
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


def build_alerts_anomalies_presentation(
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
    overview = _mapping(payload.get('selected_cluster_signal_overview'))
    alerts = [_alert_row(item) for item in _sequence(payload.get('alerts')) if isinstance(item, Mapping)]
    anomalies = [_anomaly_row(item) for item in _sequence(payload.get('anomalies')) if isinstance(item, Mapping)]

    active_count = _first_int(summary, overview, keys=('active_alerts',))
    critical_count = _first_int(summary, overview, keys=('critical_alerts',))
    warning_count = _first_int(summary, overview, keys=('warning_alerts',))
    info_count = _first_int(summary, overview, keys=('info_alerts',))
    anomaly_count = _first_int(summary, overview, keys=('detected_anomalies', 'anomalies'))

    if not active_count:
        active_count = sum(1 for item in alerts if item['status_key'] in {'active', 'firing', 'pending'})
    if not critical_count:
        critical_count = sum(1 for item in alerts if item['severity_key'] == 'critical')
    if not warning_count:
        warning_count = sum(1 for item in alerts if item['severity_key'] == 'warning')
    if not info_count:
        info_count = sum(1 for item in alerts if item['severity_key'] == 'info')
    if not anomaly_count:
        anomaly_count = len(anomalies)

    severity_rows = [
        {
            'label': 'Critical',
            'count': critical_count,
            'tone': 'critical',
            'bar': _bar(critical_count, max(critical_count, warning_count, info_count, 1)),
        },
        {
            'label': 'Warning',
            'count': warning_count,
            'tone': 'warning',
            'bar': _bar(warning_count, max(critical_count, warning_count, info_count, 1)),
        },
        {
            'label': 'Info',
            'count': info_count,
            'tone': 'info',
            'bar': _bar(info_count, max(critical_count, warning_count, info_count, 1)),
        },
    ]

    category_rows = _category_rows(alerts)
    categorized_count = sum(item['count'] for item in category_rows)
    uncategorized_count = max(active_count - categorized_count, 0)
    category_coverage = (categorized_count / active_count * 100.0) if active_count else None

    recommendations = _recommendations(payload, alerts, anomalies, uncategorized_count)
    ownership_rows = _ownership_rows(alerts, anomalies)
    correlation_rows = _correlation_rows(alerts, anomalies, active_count, categorized_count)
    source_rows = _source_rows(payload)

    cluster = _mapping(payload.get('cluster'))
    environment = sanitize_text(cluster.get('environment'), fallback='Not Available')
    executive_tone = 'critical' if critical_count else ('warning' if warning_count or anomaly_count else 'normal')
    executive_title = (
        'Critical alerts require immediate operational ownership.'
        if critical_count
        else (
            'Warning alerts require operational ownership and response validation.'
            if warning_count
            else (
                'Anomaly evidence requires review.'
                if anomaly_count
                else 'No active alert or anomaly signal is committed.'
            )
        )
    )
    executive_body = (
        f'{active_count} active alert(s) and {anomaly_count} anomaly candidate(s) are committed at the report cut-off. '
        f'{categorized_count} active alert(s) are represented by displayed categories; {uncategorized_count} remain outside the category summary.'
    )

    return {
        'presentation_version': 'v3.0-alerts-anomalies-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': _PAGE_COUNT,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            correlation_policy='review-lead-not-causality',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Alerts and Anomalies',
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'cover': {
            'environment': environment,
            'purpose': 'Support operational review of alert severity, sustained conditions, anomaly evidence, ownership, and response validation.',
            'context': 'Alert state, anomaly labels, and potential correlations remain separate evidence domains. Missing anomaly support is not interpreted as no anomaly.',
        },
        'executive': {
            'metrics': [
                _metric(
                    'Critical Alerts',
                    str(critical_count),
                    'Immediate' if critical_count else 'Clear',
                    'critical' if critical_count else 'normal',
                ),
                _metric(
                    'Warning Alerts',
                    str(warning_count),
                    'Requires Attention' if warning_count else 'Clear',
                    'warning' if warning_count else 'normal',
                ),
                _metric('Info Alerts', str(info_count), 'Informational', 'info'),
                _metric(
                    'Anomalies',
                    str(anomaly_count),
                    'Unusual Patterns' if anomaly_count else 'None',
                    'warning' if anomaly_count else 'normal',
                ),
            ],
            'severity_rows': severity_rows,
            'category_rows': category_rows,
            'interpretation_title': executive_title,
            'interpretation_body': executive_body,
            'interpretation_note': 'Anomaly evidence and alert category coverage must be validated independently from severity.',
            'tone': executive_tone,
            'decisions': recommendations[:4],
        },
        'severity_category': {
            'metrics': [
                _metric('Active Alerts', str(active_count), 'At cut-off', 'warning' if active_count else 'normal'),
                _metric('Categorized Alerts', str(categorized_count), 'Displayed', 'info'),
                _metric(
                    'Uncategorized',
                    str(uncategorized_count),
                    'Requires Review' if uncategorized_count else 'Clear',
                    'warning' if uncategorized_count else 'normal',
                ),
                _metric(
                    'Category Coverage',
                    _percent(category_coverage),
                    'Partial' if uncategorized_count else 'Complete',
                    'warning' if uncategorized_count else 'normal',
                ),
            ],
            'severity_rows': severity_rows,
            'category_rows': category_rows,
            'register': _severity_category_register(severity_rows, category_rows),
        },
        'active_alerts': {
            'metrics': [
                _metric('Displayed Alerts', str(min(len(alerts), 8)), 'Top active', 'info'),
                _metric(
                    'Namespaces',
                    str(len({item['namespace'] for item in alerts if item['namespace'] != 'Not Available'})),
                    'Displayed',
                    'normal',
                ),
                _metric(
                    'Firing State',
                    str(sum(1 for item in alerts if item['status_key'] == 'firing')),
                    'Active',
                    'warning',
                ),
                _metric(
                    'Oldest Since',
                    _oldest_label(alerts),
                    'Sustained' if alerts else 'Not Available',
                    'warning' if alerts else 'muted',
                ),
            ],
            'rows': [_with_ref(item, f'A{index}') for index, item in enumerate(alerts[:8], start=1)],
            'references': _alert_references(alerts[:5]),
        },
        'anomalies': {
            'metrics': [
                _metric(
                    'Detected Anomalies',
                    str(anomaly_count),
                    'Committed count',
                    'warning' if anomaly_count else 'normal',
                ),
                _metric('Displayed Records', str(min(len(anomalies), 8)), 'Recent', 'info'),
                _metric(
                    'Evidence Available',
                    str(sum(1 for item in anomalies if item['evidence_available'])),
                    'Committed support',
                    'normal' if anomalies and all(item['evidence_available'] for item in anomalies) else 'warning',
                ),
                _metric(
                    'Namespaces',
                    str(len({item['namespace'] for item in anomalies if item['namespace'] != 'Not Available'})),
                    'Displayed',
                    'normal',
                ),
            ],
            'rows': [_with_ref(item, f'N{index}') for index, item in enumerate(anomalies[:8], start=1)],
            'requirements': [
                {
                    'ref': 'E1',
                    'evidence': 'Observation Window',
                    'definition': 'Start, end, and comparison baseline',
                    'status': 'Missing',
                    'action': 'Required',
                },
                {
                    'ref': 'E2',
                    'evidence': 'Signal Evidence',
                    'definition': 'Metric, expected band, and deviation',
                    'status': 'Missing',
                    'action': 'Required',
                },
                {
                    'ref': 'E3',
                    'evidence': 'Entity Identity',
                    'definition': 'Pod, workload, namespace, and owner',
                    'status': 'Partial',
                    'action': 'Required',
                },
                {
                    'ref': 'E4',
                    'evidence': 'Correlation Evidence',
                    'definition': 'Related alerts, events, and changes',
                    'status': 'Missing',
                    'action': 'Required',
                },
            ],
        },
        'ownership': {
            'metrics': [
                _metric(
                    'Sustained Alerts',
                    str(sum(1 for item in alerts if item['starts_at_display'] != 'Not Available')),
                    'Displayed',
                    'warning',
                ),
                _metric(
                    'Owner Coverage',
                    str(sum(1 for item in alerts if item['owner'] != 'Not Available')),
                    'Committed',
                    'normal' if alerts and all(item['owner'] != 'Not Available' for item in alerts) else 'warning',
                ),
                _metric(
                    'Runbook Coverage',
                    str(sum(1 for item in alerts if item['runbook'] != 'Not Available')),
                    'Committed',
                    'normal' if alerts and all(item['runbook'] != 'Not Available' for item in alerts) else 'warning',
                ),
                _metric('Response Validation', 'Required', 'All displayed', 'info'),
            ],
            'rows': ownership_rows,
        },
        'correlation': {
            'metrics': [
                _metric('Alert Records', str(active_count), 'Active count', 'warning' if active_count else 'normal'),
                _metric(
                    'Anomaly Records', str(anomaly_count), 'Detected count', 'warning' if anomaly_count else 'normal'
                ),
                _metric('Direct Correlations', '0', 'Not committed', 'warning'),
                _metric('Evidence Quality', 'Partial', 'Review', 'warning'),
            ],
            'rows': correlation_rows,
        },
        'recommendations': {
            'metrics': _recommendation_metrics(recommendations),
            'rows': recommendations,
            'governance': [
                {
                    'field': 'Primary Action',
                    'requirement': recommendations[0]['title']
                    if recommendations
                    else 'Continue alert and anomaly monitoring.',
                },
                {
                    'field': 'Validation Criteria',
                    'requirement': 'Confirm live alert state, expected workload behavior, events, metrics, accountable owner, and approved response before closure.',
                },
                {'field': 'Assigned Owners', 'requirement': _owner_summary(recommendations)},
                {
                    'field': 'Change Control',
                    'requirement': 'No workload or infrastructure change is authorized by this report alone.',
                },
            ],
        },
        'methodology': {
            'metrics': [
                _metric('Data Sources', str(len(source_rows)), 'Committed', 'normal'),
                _metric('Active Alerts', str(active_count), 'At cut-off', 'warning' if active_count else 'normal'),
                _metric('Anomalies', str(anomaly_count), 'Committed count', 'warning' if anomaly_count else 'normal'),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ],
            'sources': source_rows,
            'rules': [
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Severity', 'setting': 'Committed labels'},
                {'ref': 'M4', 'rule': 'Category Coverage', 'setting': 'Displayed categories'},
                {'ref': 'M5', 'rule': 'Anomaly Evidence', 'setting': 'Explicit Not Available'},
            ],
            'included': [
                'Committed alert severity, namespace, start time, ownership metadata, and firing state.',
                'Displayed alert-category counts and committed source health when available.',
                'Committed anomaly count and recent anomaly labels.',
            ],
            'excluded': [
                'Live alert state after the report cut-off.',
                'Uncommitted root cause, causal correlation, and business impact.',
                'Missing anomaly metric, event, and comparison evidence.',
            ],
            'limitations': [
                'Alert severity does not establish business impact.',
                'Category coverage and anomaly support may be partial.',
                'Validate all actions against live state before remediation.',
            ],
            'status_language': [
                {'ref': 'S1', 'title': 'Not Available', 'description': 'No supporting evidence exists.'},
                {
                    'ref': 'S2',
                    'title': 'Partial Coverage',
                    'description': 'Only part of the active set is categorized or evidenced.',
                },
                {'ref': 'S3', 'title': 'Firing', 'description': 'The alert was active at the committed cut-off.'},
                {'ref': 'S4', 'title': 'Unconfirmed', 'description': 'A relationship is a review lead, not causality.'},
            ],
        },
    }


def _alert_row(value: Mapping[str, Any]) -> dict[str, Any]:
    labels = _mapping(value.get('labels'))
    annotations = _mapping(value.get('annotations'))
    severity = sanitize_text(value.get('severity') or labels.get('severity'), fallback='none').lower()
    status = sanitize_text(value.get('status'), fallback='active').lower()
    category = sanitize_text(
        value.get('category') or labels.get('category') or labels.get('domain') or labels.get('alert_category'),
        fallback='Uncategorized',
    )
    return {
        'name': sanitize_text(value.get('name') or labels.get('alertname'), fallback='Unknown Alert'),
        'severity': severity.title() if severity != 'none' else 'None',
        'severity_key': severity,
        'status': status.title(),
        'status_key': status,
        'namespace': sanitize_text(value.get('namespace') or labels.get('namespace'), fallback='Not Available'),
        'target': sanitize_text(
            value.get('target') or labels.get('pod') or labels.get('instance'), fallback='Not Available'
        ),
        'source': sanitize_text(value.get('source'), fallback='Not Available'),
        'summary': sanitize_text(
            value.get('summary')
            or annotations.get('summary')
            or value.get('description')
            or annotations.get('description'),
            fallback='No committed description.',
        ),
        'starts_at_display': sanitize_text(
            value.get('starts_at_display') or value.get('starts_at'), fallback='Not Available'
        ),
        'owner': sanitize_text(value.get('owner'), fallback='Not Available'),
        'runbook': sanitize_text(value.get('runbook_url'), fallback='Not Available'),
        'contact': sanitize_text(value.get('contact'), fallback='Not Available'),
        'category': category,
        'tone': 'critical'
        if severity == 'critical'
        else ('warning' if severity == 'warning' else ('info' if severity == 'info' else 'muted')),
    }


def _anomaly_row(value: Mapping[str, Any]) -> dict[str, Any]:
    evidence = value.get('evidence') or value.get('metric') or value.get('value')
    evidence_available = evidence not in {None, '', '-', 'Not Available'}
    return {
        'name': sanitize_text(value.get('name') or value.get('title'), fallback='Unknown Anomaly'),
        'namespace': sanitize_text(value.get('namespace'), fallback='Not Available'),
        'severity': sanitize_text(value.get('severity'), fallback='warning').title(),
        'status': sanitize_text(value.get('status'), fallback='Review').title(),
        'summary': sanitize_text(
            value.get('description') or value.get('summary'), fallback='No committed anomaly description.'
        ),
        'evidence': sanitize_text(evidence, fallback='Not Available'),
        'evidence_available': evidence_available,
        'starts_at_display': sanitize_text(
            value.get('starts_at_display') or value.get('timestamp') or value.get('observed_at'),
            fallback='Not Available',
        ),
        'tone': 'warning',
    }


def _category_rows(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(item['category'] for item in alerts if item['category'] != 'Uncategorized')
    if not counts:
        return []
    max_count = max(counts.values())
    return [{'label': label, 'count': count, 'bar': _bar(count, max_count)} for label, count in counts.most_common(6)]


def _severity_category_register(
    severity_rows: list[dict[str, Any]], category_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(severity_rows, start=1):
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
    for index, item in enumerate(category_rows, start=1):
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


def _alert_references(alerts: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            'ref': f'A{index}',
            'title': item['name'],
            'description': f'Validate {item["namespace"]} live state, expected behavior, and accountable ownership. {item["summary"]}',
        }
        for index, item in enumerate(alerts, start=1)
    ]


def _ownership_rows(alerts: list[dict[str, Any]], anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index = 1
    for item in alerts[:5]:
        owner_domain = item['owner'] if item['owner'] != 'Not Available' else _owner_domain(item['namespace'])
        result.append(
            {
                'ref': f'O{index}',
                'scope': item['namespace'],
                'owner': owner_domain,
                'focus': item['name'],
                'coverage': _metadata_coverage(item),
                'status': 'Review',
            }
        )
        index += 1
    for item in anomalies[:2]:
        if len(result) >= 6:
            break
        result.append(
            {
                'ref': f'O{index}',
                'scope': item['namespace'],
                'owner': _owner_domain(item['namespace']),
                'focus': item['name'],
                'coverage': 'Partial',
                'status': 'Review',
            }
        )
        index += 1
    return result


def _correlation_rows(
    alerts: list[dict[str, Any]], anomalies: list[dict[str, Any]], active_count: int, categorized_count: int
) -> list[dict[str, Any]]:
    alerts_by_namespace: dict[str, list[str]] = defaultdict(list)
    anomalies_by_namespace: dict[str, list[str]] = defaultdict(list)
    for item in alerts:
        alerts_by_namespace[item['namespace']].append(item['name'])
    for item in anomalies:
        anomalies_by_namespace[item['namespace']].append(item['name'])
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
    if len(rows) < 5:
        for namespace, names in alerts_by_namespace.items():
            if len(names) >= 2 and len(rows) < 4:
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
    rows.append(
        {
            'ref': f'C{len(rows) + 1}',
            'scope': 'Category Coverage',
            'signal_a': f'{active_count} active alerts',
            'signal_b': f'{categorized_count} categorized',
            'relationship': 'Partial' if categorized_count < active_count else 'Complete',
            'status': 'Reconcile' if categorized_count < active_count else 'Current',
        }
    )
    return rows[:5]


def _recommendations(
    payload: Mapping[str, Any], alerts: list[dict[str, Any]], anomalies: list[dict[str, Any]], uncategorized_count: int
) -> list[dict[str, Any]]:
    raw = _sequence(payload.get('actionable_recommendations') or payload.get('recommendations'))
    items: list[dict[str, Any]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            continue
        priority = _priority(value.get('priority') or value.get('severity'))
        items.append(
            {
                'ref': f'R{len(items) + 1}',
                'priority': priority,
                'title': sanitize_text(value.get('title'), fallback='Review Alert and Anomaly Evidence'),
                'description': sanitize_text(
                    value.get('description'),
                    fallback='Validate the signal against live state and expected workload behavior.',
                ),
                'owner': sanitize_text(value.get('owner'), fallback='Platform Operations'),
                'target': 'This Week' if priority == 'P1' else ('Next Week' if priority == 'P2' else 'This Month'),
                'status': 'Open' if priority in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if priority == 'P1' else ('warning' if priority == 'P2' else 'info'),
            }
        )
        if len(items) >= 5:
            break
    defaults: list[tuple[str, str, str, str]] = []
    for alert in alerts[:3]:
        defaults.append(
            (
                'P2',
                f'Validate {alert["name"]}',
                f'Confirm live state, expected behavior, and ownership for {alert["namespace"]}.',
                _owner_domain(alert['namespace']),
            )
        )
    if anomalies and not all(item['evidence_available'] for item in anomalies):
        defaults.append(
            (
                'P2',
                'Restore Anomaly Evidence',
                'Commit observation window, metric deviation, entity identity, and related event evidence.',
                'Observability Owner',
            )
        )
    if uncategorized_count:
        defaults.append(
            (
                'P3',
                'Reconcile Alert Categories',
                f'Reconcile {uncategorized_count} active alert(s) outside the displayed category summary.',
                'Observability Owner',
            )
        )
    existing = {item['title'] for item in items}
    for priority, title, description, owner in defaults:
        if title in existing or len(items) >= 5:
            continue
        items.append(
            {
                'ref': f'R{len(items) + 1}',
                'priority': priority,
                'title': title,
                'description': description,
                'owner': owner,
                'target': 'Next Week' if priority == 'P2' else 'This Month',
                'status': 'Open' if priority == 'P2' else 'Planned',
                'tone': 'warning' if priority == 'P2' else 'info',
            }
        )
    items.sort(key=lambda item: (int(item['priority'][1]), item['ref']))
    for index, item in enumerate(items, start=1):
        item['ref'] = f'R{index}'
    return items


def _source_rows(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    source_status = _mapping(payload.get('source_status'))
    anomaly_status = _mapping(payload.get('anomaly_source_status'))
    rows = [
        {
            'source': sanitize_text(
                source_status.get('label') or source_status.get('resolved_source'), fallback='Alert Source'
            ),
            'freshness': _response_time(source_status),
            'last_collected': 'At report cut-off',
        },
        {
            'source': sanitize_text(anomaly_status.get('label'), fallback='Analytics Anomaly Evidence'),
            'freshness': _response_time(anomaly_status),
            'last_collected': 'At report cut-off',
        },
    ]
    return rows


def _recommendation_metrics(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        _metric(
            'P1 Actions',
            str(sum(1 for item in items if item['priority'] == 'P1')),
            'Immediate',
            'critical' if any(item['priority'] == 'P1' for item in items) else 'normal',
        ),
        _metric('P2 Actions', str(sum(1 for item in items if item['priority'] == 'P2')), 'Open', 'warning'),
        _metric('P3 Actions', str(sum(1 for item in items if item['priority'] == 'P3')), 'Planned', 'info'),
        _metric('Validation Gates', str(len(items)), 'Required', 'info'),
    ]


def _with_ref(item: dict[str, Any], ref: str) -> dict[str, Any]:
    row = dict(item)
    row['ref'] = ref
    return row


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _bar(value: int, maximum: int) -> float:
    return min(max(value / max(maximum, 1) * 100.0, 0.0), 100.0)


def _percent(value: float | None) -> str:
    return f'{value:.1f}%' if value is not None else 'Not Available'


def _priority(value: Any) -> str:
    normalized = sanitize_text(value, fallback='P3').lower()
    if normalized in {'p1', 'critical', 'high'}:
        return 'P1'
    if normalized in {'p2', 'warning', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def _owner_domain(namespace: str) -> str:
    normalized = namespace.lower()
    if normalized in {'monitoring', 'logging', 'kube-system', 'openebs'}:
        return 'Platform Operations'
    return 'Application Owner'


def _metadata_coverage(item: Mapping[str, Any]) -> str:
    available = sum(1 for key in ('owner', 'runbook', 'contact') if item.get(key) not in {None, '', 'Not Available'})
    return 'Complete' if available == 3 else ('Partial' if available else 'Missing')


def _oldest_label(alerts: list[dict[str, Any]]) -> str:
    values = [item['starts_at_display'] for item in alerts if item['starts_at_display'] != 'Not Available']
    return values[0] if values else 'Not Available'


def _response_time(value: Mapping[str, Any]) -> str:
    response = value.get('response_time_ms')
    try:
        return (
            f'{int(response)} ms'
            if response is not None
            else ('Partial' if value.get('partial') else 'At report cut-off')
        )
    except (TypeError, ValueError):
        return 'At report cut-off'


def _owner_summary(items: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item['owner']] += 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No assigned action.'


def _first_int(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for mapping in mappings:
        for key in keys:
            if key in mapping:
                try:
                    return int(mapping.get(key) or 0)
                except (TypeError, ValueError):
                    continue
    return 0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []
