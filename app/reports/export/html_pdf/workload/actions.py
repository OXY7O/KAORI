from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.publication_copy import compact_governance_signal

from .model import (
    date_text,
    is_actionable,
    mapping,
    metric,
    number,
    percent_display,
    priority,
    priority_from_severity,
    target,
    text,
    tone,
)


def governance_analysis(
    findings: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    quota_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = []
    for index, item in enumerate(findings[:6], start=1):
        severity = text(item.get('severity'), 'warning').lower()
        title = text(item.get('label'), 'Review workload governance finding')
        normalized.append(
            {
                'ref': f'G{index}',
                'title': title,
                'priority': priority_from_severity(severity),
                'impact': 'High'
                if severity in {'critical', 'high'}
                else 'Medium'
                if severity in {'warning', 'medium'}
                else 'Low',
                'owner': 'Application Owner',
                'status': 'Open' if severity in {'critical', 'warning'} else 'Current',
                'tone': tone(severity),
                'description': (
                    'Review the related workload, namespace, or policy condition. '
                    f'Filter context: {text(item.get("filter"), "-")}.'
                ),
            }
        )

    if not normalized:
        normalized.append(
            {
                'ref': 'G1',
                'title': 'No Critical Governance Findings Detected',
                'priority': 'P3',
                'impact': 'Low',
                'owner': 'Application Owner',
                'status': 'Current',
                'tone': 'normal',
                'description': 'Continue monitoring quota, requests, limits, QoS, and metrics coverage.',
            }
        )

    actionable_count = sum(1 for item in normalized if item['status'] in {'Open', 'Review'})
    critical_count = sum(1 for item in normalized if item['priority'] == 'P1')
    review_count = sum(1 for item in normalized if item['status'] in {'Open', 'Review'})
    signals = [
        {
            'ref': item['ref'],
            'signal': compact_governance_signal(item['title']),
            'namespace': 'Selected Scope',
            'state': item['status'],
            'tone': item['tone'],
        }
        for item in normalized
    ]
    return {
        'items': normalized,
        'signals': signals,
        'actionable_count': actionable_count,
        'critical_count': critical_count,
        'review_count': review_count,
        'metrics': (
            metric(
                'Critical Findings',
                str(critical_count),
                'Open' if critical_count else 'Clear',
                'critical' if critical_count else 'normal',
            ),
            metric(
                'Review Findings',
                str(review_count),
                'Requires Ownership' if review_count else 'Clear',
                'warning' if review_count else 'normal',
            ),
            metric(
                'Quota Rows',
                str(len(quota_rows)) if quota_rows else 'Not Available',
                'Committed' if quota_rows else 'Not Available',
                'normal' if quota_rows else 'warning',
            ),
            metric(
                'Workload Rows',
                str(len(mapping_rows)) if mapping_rows else 'Not Available',
                'Committed' if mapping_rows else 'Not Available',
                'normal' if mapping_rows else 'warning',
            ),
        ),
        'interpretation': (
            'Workload governance risk is derived from committed quota, configuration, QoS, metrics, and '
            'recommendation evidence. Confirm owner and live state before remediation.'
        ),
    }


def recommendation_plan(
    recommendations: list[dict[str, Any]],
    governance: Mapping[str, Any],
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    items = []
    for item in recommendations:
        actionable = is_actionable(item)
        if not actionable:
            continue
        item_priority = priority(text(item.get('priority'), 'Info'))
        items.append(
            {
                'priority': item_priority,
                'title': text(item.get('title') or item.get('label'), 'Review Workload Governance Finding'),
                'description': text(item.get('description'), 'Review the related workload analysis evidence.'),
                'owner': 'Application Owner',
                'target': target(item_priority),
                'status': 'Open' if item_priority in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if item_priority == 'P1' else 'warning' if item_priority == 'P2' else 'info',
            }
        )

    if not items:
        for finding in governance.get('items', ()):
            if finding.get('status') not in {'Open', 'Review'}:
                continue
            items.append(
                {
                    'priority': finding['priority'],
                    'title': finding['title'],
                    'description': finding['description'],
                    'owner': finding['owner'],
                    'target': target(finding['priority']),
                    'status': 'Open' if finding['priority'] in {'P1', 'P2'} else 'Planned',
                    'tone': finding['tone'],
                }
            )

    if not items:
        items.append(
            {
                'priority': 'P3',
                'title': 'Continue Workload Governance Monitoring',
                'description': (
                    'No actionable finding was generated. Continue committed quota, requests, limits, QoS, '
                    'and metrics monitoring.'
                ),
                'owner': 'Application Owner',
                'target': 'This Month',
                'status': 'Current',
                'tone': 'normal',
            }
        )

    rank = {'P1': 1, 'P2': 2, 'P3': 3}
    items.sort(key=lambda item: (rank.get(item['priority'], 9), item['title']))
    items = items[:5]
    for index, item in enumerate(items, start=1):
        item['ref'] = f'R{index}'

    p1 = sum(1 for item in items if item['priority'] == 'P1')
    p2 = sum(1 for item in items if item['priority'] == 'P2')
    p3 = sum(1 for item in items if item['priority'] == 'P3')
    return {
        'metrics': (
            metric('P1 Actions', str(p1), 'Open' if p1 else 'None', 'critical' if p1 else 'normal'),
            metric('P2 Actions', str(p2), 'Open' if p2 else 'None', 'warning' if p2 else 'normal'),
            metric('P3 Actions', str(p3), 'Planned' if p3 else 'None', 'info' if p3 else 'normal'),
            metric('Validation Gates', str(len(items)), 'Required', 'info'),
        ),
        'items': items,
        'governance': (
            {'field': 'Primary Action', 'requirement': items[0]['title']},
            {
                'field': 'Validation Criteria',
                'requirement': (
                    'Confirm live state, owner, service objective, rollout window, and rollback readiness before closure.'
                ),
            },
            {'field': 'Assigned Owners', 'requirement': f'Application Owner: {len(items)} action(s).'},
            {
                'field': 'Change Control',
                'requirement': (
                    'No request, limit, quota, replica, or autoscaling change is authorized by this report alone.'
                ),
            },
        ),
    }


def executive_findings(
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    candidates = []
    if quota.get('missing'):
        candidates.append(
            (
                'P1',
                'Restore Missing ResourceQuota Coverage',
                f'{quota["missing"]} namespace(s) have missing quota coverage.',
                'Open',
                'critical',
            )
        )
    if configuration.get('missing_requests'):
        candidates.append(
            (
                'P1',
                'Validate Incomplete Resource Requests',
                f'{configuration["missing_requests"]} workload(s) have incomplete requests.',
                'Open',
                'critical',
            )
        )
    if configuration.get('limit_review'):
        candidates.append(
            (
                'P2',
                'Review Workload Limits',
                f'{configuration["limit_review"]} workload(s) require limit review.',
                'Review',
                'warning',
            )
        )
    if configuration.get('best_effort'):
        candidates.append(
            (
                'P1',
                'Review BestEffort Workloads',
                f'{configuration["best_effort"]} BestEffort workload(s) were detected.',
                'Open',
                'critical',
            )
        )
    if not candidates:
        candidates.append(
            (
                'P3',
                'Maintain Workload Governance Evidence',
                'No critical configuration gap was derived from the committed rows.',
                'Current',
                'normal',
            )
        )

    findings = []
    for index, (item_priority, title, description, status, tone_value) in enumerate(candidates[:4], start=1):
        findings.append(
            {
                'ref': f'F{index}',
                'priority': item_priority,
                'title': title,
                'description': description,
                'owner': 'Application Owner',
                'status': status,
                'tone': tone_value,
            }
        )
    return tuple(findings)


def inventory_register(
    inventory: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    return (
        {
            'ref': 'I1',
            'dimension': 'Workload Inventory',
            'scope': inventory['workload_display'],
            'evidence': 'Workload mapping rows',
            'status': inventory['status'],
            'tone': inventory['tone'],
        },
        {
            'ref': 'I2',
            'dimension': 'Pod Participation',
            'scope': inventory['pod_display'],
            'evidence': 'Replica totals',
            'status': inventory['status'],
            'tone': inventory['tone'],
        },
        {
            'ref': 'I3',
            'dimension': 'Namespace Scope',
            'scope': inventory['namespace_display'],
            'evidence': 'Quota and mapping rows',
            'status': inventory['status'],
            'tone': inventory['tone'],
        },
        {
            'ref': 'I4',
            'dimension': 'Governance Signals',
            'scope': str(governance['review_count']),
            'evidence': 'Committed findings',
            'status': 'Review' if governance['review_count'] else 'Current',
            'tone': 'warning' if governance['review_count'] else 'normal',
        },
    )


def source_rows(
    payload: Mapping[str, Any],
    quota: Mapping[str, Any],
    mapping_state: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    supplied = payload.get('source_evidence')
    rows = []
    if isinstance(supplied, Sequence) and not isinstance(supplied, (str, bytes)):
        for item in supplied:
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    'source': text(item.get('source'), 'Workload Evidence'),
                    'freshness': text(item.get('freshness'), 'Committed'),
                    'last_collected': date_text(item.get('last_collected')),
                }
            )
    if rows:
        return tuple(rows[:4])

    status = mapping(payload.get('metrics_source_status'))
    response = status.get('response_time_ms') or status.get('response_time')
    freshness = f'{number(response):.0f} ms' if response is not None and number(response) > 0 else 'Committed'
    return (
        {'source': 'Metrics Source Workload Evidence', 'freshness': freshness, 'last_collected': 'At report cut-off'},
        {
            'source': 'Tenant Quota Analysis',
            'freshness': 'Committed' if quota['available'] else 'Not Available',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Workload Resource Mapping',
            'freshness': 'Committed' if mapping_state['available'] else 'Not Available',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Governance Recommendation Evidence',
            'freshness': 'Committed',
            'last_collected': 'At report cut-off',
        },
    )


def executive_title(
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> str:
    if governance.get('critical_count'):
        return 'Critical workload governance findings require ownership.'
    if quota.get('missing') or configuration.get('missing_requests') or configuration.get('best_effort'):
        return 'Workload governance requires application-owner review.'
    return 'Committed workload posture is available for review.'


def executive_body(
    inventory: Mapping[str, Any],
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> str:
    if not inventory.get('available'):
        return 'Committed workload rows are not available. No governance conclusion should be assigned.'
    return (
        f'The committed scope contains {inventory["workload_display"]} workload(s), '
        f'{inventory["pod_display"]} pod(s), and {inventory["namespace_display"]} namespace(s). '
        f'Quota coverage is {quota["coverage_display"]}; request coverage is '
        f'{percent_display(configuration.get("request_coverage"))}. '
        f'{governance["actionable_count"]} finding(s) require ownership and validation.'
    )
