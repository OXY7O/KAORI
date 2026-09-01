from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any


def inventory_summary(
    payload: Mapping[str, Any],
    quota_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    workload_count = len(mapping_rows)
    pod_count = sum(max(integer(row.get('replicas')), 0) for row in mapping_rows)
    namespaces = {
        text(row.get('namespace'), '') for row in [*quota_rows, *mapping_rows] if text(row.get('namespace'), '')
    }
    namespace_options = payload.get('namespace_options')
    if not namespaces and isinstance(namespace_options, Sequence) and not isinstance(namespace_options, (str, bytes)):
        namespaces = {text(item, '') for item in namespace_options if text(item, '')}

    available = bool(mapping_rows or quota_rows)
    namespace_count = len(namespaces)
    coverage = 100.0 if mapping_rows else 0.0
    return {
        'available': available,
        'workload_count': workload_count,
        'pod_count': pod_count,
        'namespace_count': namespace_count,
        'cluster_count': 1 if mapping(payload.get('cluster')) else 0,
        'workload_display': str(workload_count) if mapping_rows else 'Not Available',
        'pod_display': str(pod_count) if mapping_rows else 'Not Available',
        'namespace_display': str(namespace_count) if namespace_count else 'Not Available',
        'coverage': coverage,
        'coverage_display': f'{coverage:.0f}%' if available else 'Not Available',
        'status': 'Current' if available else 'Not Available',
        'tone': 'normal' if available else 'warning',
    }


def quota_analysis(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = integer(summary.get('scope_total')) or len(rows)
    covered = integer(summary.get('scope_covered'))
    if not covered:
        covered = sum(1 for row in rows if label(row.get('quota_status')) in {'Complete', 'Partial'})
    complete = sum(1 for row in rows if label(row.get('quota_status')) == 'Complete')
    partial = sum(1 for row in rows if label(row.get('quota_status')) == 'Partial')
    missing = sum(1 for row in rows if label(row.get('quota_status')) == 'Missing')
    near_limit = integer(summary.get('scope_near_limit_count')) or sum(
        1 for row in rows if bool(row.get('quota_pressure_available')) and number(row.get('quota_usage_percent')) >= 75
    )
    over_quota = sum(
        1 for row in rows if bool(row.get('quota_pressure_available')) and number(row.get('quota_usage_percent')) >= 100
    )
    coverage = percent(covered, total) if total else None
    available = bool(rows)
    status = 'Current' if available and missing == 0 else 'Review' if available else 'Not Available'
    tone_value = 'normal' if available and missing == 0 and over_quota == 0 else 'warning'

    records = []
    for index, row in enumerate(rows[:5], start=1):
        namespace = text(row.get('namespace'), '-')
        status_label = label(row.get('quota_status'), 'Unknown')
        risk = label(row.get('risk'), 'Unknown')
        pressure = (
            percent_display(row.get('quota_usage_percent'))
            if bool(row.get('quota_pressure_available'))
            else 'Not Available'
        )
        records.append(
            {
                'ref': f'Q{index}',
                'namespace': namespace,
                'coverage': status_label,
                'pressure': pressure,
                'risk': risk,
                'tone': tone(risk),
            }
        )

    return {
        'available': available,
        'total': total,
        'covered': covered,
        'complete': complete,
        'partial': partial,
        'missing': missing,
        'near_limit': near_limit,
        'over_quota': over_quota,
        'coverage': coverage,
        'coverage_display': percent_display(coverage) if coverage is not None else 'Not Available',
        'status': status,
        'tone': tone_value,
        'metrics': (
            metric(
                'Namespaces',
                str(total) if total else 'Not Available',
                'Committed Scope' if total else 'Not Available',
                'normal' if total else 'warning',
            ),
            metric(
                'Quota Coverage',
                percent_display(coverage) if coverage is not None else 'Not Available',
                status,
                tone_value,
            ),
            metric(
                'Missing Quota',
                str(missing) if available else 'Not Available',
                'Review' if missing else 'Clear' if available else 'Not Available',
                'warning' if missing or not available else 'normal',
            ),
            metric(
                'Near / Over Limit',
                str(near_limit),
                'Review' if near_limit else 'Clear',
                'warning' if near_limit else 'normal',
            ),
        ),
        'records': records,
        'requirements': (
            {
                'ref': 'QE1',
                'evidence': 'ResourceQuota Inventory',
                'definition': 'Quota object and namespace scope',
                'status': 'Current' if available else 'Missing',
                'action': 'Monitor' if available else 'Required',
            },
            {
                'ref': 'QE2',
                'evidence': 'Quota Used / Hard',
                'definition': 'Used and hard values by resource',
                'status': 'Current' if available else 'Missing',
                'action': 'Review' if near_limit else 'Monitor' if available else 'Required',
            },
            {
                'ref': 'QE3',
                'evidence': 'LimitRange Inventory',
                'definition': 'Default and min/max controls',
                'status': 'Not Collected',
                'action': 'Required',
            },
            {
                'ref': 'QE4',
                'evidence': 'Enforcement Result',
                'definition': 'Quota rejection or policy evidence',
                'status': 'Not Collected',
                'action': 'Validate',
            },
        ),
        'decision': (
            'Review namespaces with missing or partial quota definitions before approving additional workload growth.'
            if available
            else 'Restore ResourceQuota evidence before assigning tenant governance status.'
        ),
    }


def mapping_analysis(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    namespace_count = len({text(row.get('namespace'), '') for row in rows if text(row.get('namespace'), '')})
    complete_requests = sum(1 for row in rows if label(row.get('request_coverage')) == 'Complete')
    complete_limits = sum(1 for row in rows if label(row.get('limit_coverage')) == 'Complete')
    complete_metrics = sum(1 for row in rows if label(row.get('metrics_coverage')) == 'Complete')
    high_risk = sum(1 for row in rows if label(row.get('risk')) in {'High', 'Critical'})
    available = bool(rows)

    records = []
    for index, row in enumerate(rows[:5], start=1):
        records.append(
            {
                'ref': f'M{index}',
                'workload': text(row.get('workload'), '-'),
                'type': text(row.get('type'), '-'),
                'namespace': text(row.get('namespace'), '-'),
                'mapping': f'{integer(row.get("replicas"))} pod(s)'
                if row.get('replicas') is not None
                else 'Inventory row',
                'status': label(row.get('risk'), 'Unknown'),
                'tone': tone(label(row.get('risk'), 'Unknown')),
            }
        )

    return {
        'available': available,
        'metrics': (
            metric(
                'Workloads',
                str(total) if available else 'Not Available',
                'Inventory Available' if available else 'Not Available',
                'normal' if available else 'warning',
            ),
            metric(
                'Namespaces',
                str(namespace_count) if namespace_count else 'Not Available',
                'Committed Scope' if namespace_count else 'Not Available',
                'normal' if namespace_count else 'warning',
            ),
            metric(
                'Resource Mapping',
                percent_display(percent(complete_metrics, total)) if total else 'Not Available',
                'Complete Metrics' if total else 'Not Available',
                'normal' if total and complete_metrics == total else 'warning',
            ),
            metric('Owner Mapping', 'Not Available', 'Not Committed', 'warning'),
        ),
        'records': records,
        'identities': tuple(
            {
                'ref': item['ref'],
                'title': item['workload'],
                'metadata': f'Namespace: {item["namespace"]} · Type: {item["type"]}',
            }
            for item in records
        ),
        'coverage': (
            {
                'label': 'Inventory to Namespace',
                'value': 100.0 if available else 0.0,
                'display': 'Available' if available else 'Not Available',
                'available': available,
            },
            {
                'label': 'Requests Coverage',
                'value': percent(complete_requests, total) or 0.0,
                'display': percent_display(percent(complete_requests, total)) if total else 'Not Available',
                'available': available,
            },
            {
                'label': 'Limits Coverage',
                'value': percent(complete_limits, total) or 0.0,
                'display': percent_display(percent(complete_limits, total)) if total else 'Not Available',
                'available': available,
            },
            {'label': 'Application Owner', 'value': 0.0, 'display': 'Not Available', 'available': False},
        ),
        'interpretation_title': (
            'Mapping supports workload triage, but ownership remains incomplete.'
            if available
            else 'Workload mapping evidence is not available.'
        ),
        'interpretation_body': (
            f'{total} workload row(s) cover {namespace_count} namespace(s). '
            f'{high_risk} high-risk workload row(s) require review. Application-owner identity is not committed.'
            if available
            else 'Restore committed workload-to-pod and namespace mapping before deriving configuration posture.'
        ),
        'decision': (
            'Confirm controller, application owner, deployment intent, maintenance window, and rollback readiness before changing resources or replicas.'
        ),
    }


def configuration_analysis(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    request_complete = sum(1 for row in rows if label(row.get('request_coverage')) == 'Complete')
    limit_complete = sum(1 for row in rows if label(row.get('limit_coverage')) == 'Complete')
    metrics_complete = sum(1 for row in rows if label(row.get('metrics_coverage')) == 'Complete')
    best_effort = sum(1 for row in rows if label(row.get('qos')) == 'BestEffort')
    missing_requests = sum(1 for row in rows if label(row.get('request_coverage')) in {'Missing', 'Partial'})
    limit_review = sum(1 for row in rows if label(row.get('limit_coverage')) != 'Complete')
    right_size = sum(
        1
        for row in rows
        if any(token in text(row.get('recommendation'), '').lower() for token in ('reduce', 'increase', 'right-size'))
    )
    available = bool(rows)

    records = []
    for index, row in enumerate(rows[:5], start=1):
        records.append(
            {
                'ref': f'C{index}',
                'workload': text(row.get('workload'), '-'),
                'namespace': text(row.get('namespace'), '-'),
                'requests': label(row.get('request_coverage'), 'Unknown'),
                'limits': label(row.get('limit_coverage'), 'Unknown'),
                'qos': label(row.get('qos'), 'Unknown'),
                'risk': label(row.get('risk'), 'Unknown'),
                'tone': tone(label(row.get('risk'), 'Unknown')),
            }
        )

    return {
        'available': available,
        'total': total,
        'request_complete': request_complete,
        'limit_complete': limit_complete,
        'metrics_complete': metrics_complete,
        'best_effort': best_effort,
        'missing_requests': missing_requests,
        'limit_review': limit_review,
        'right_size': right_size,
        'request_coverage': percent(request_complete, total),
        'limit_coverage': percent(limit_complete, total),
        'metrics_coverage': percent(metrics_complete, total),
        'metrics': (
            metric(
                'CPU / Memory Requests',
                percent_display(percent(request_complete, total)) if total else 'Not Available',
                'Complete Rows' if total else 'Not Available',
                'normal' if total and request_complete == total else 'warning',
            ),
            metric(
                'Limits Coverage',
                percent_display(percent(limit_complete, total)) if total else 'Not Available',
                'Complete Rows' if total else 'Not Available',
                'normal' if total and limit_complete == total else 'warning',
            ),
            metric(
                'BestEffort',
                str(best_effort) if available else 'Not Available',
                'Review' if best_effort else 'Clear' if available else 'Not Available',
                'warning' if best_effort or not available else 'normal',
            ),
            metric(
                'Metrics Coverage',
                percent_display(percent(metrics_complete, total)) if total else 'Not Available',
                'Complete Rows' if total else 'Not Available',
                'normal' if total and metrics_complete == total else 'warning',
            ),
        ),
        'coverage_rows': (
            {
                'label': 'Requests Complete',
                'value': percent(request_complete, total) or 0.0,
                'display': percent_display(percent(request_complete, total)) if total else 'Not Available',
                'available': available,
            },
            {
                'label': 'Limits Complete',
                'value': percent(limit_complete, total) or 0.0,
                'display': percent_display(percent(limit_complete, total)) if total else 'Not Available',
                'available': available,
            },
            {
                'label': 'Metrics Complete',
                'value': percent(metrics_complete, total) or 0.0,
                'display': percent_display(percent(metrics_complete, total)) if total else 'Not Available',
                'available': available,
            },
        ),
        'records': records,
        'identities': tuple(
            {
                'ref': item['ref'],
                'title': item['workload'],
                'metadata': f'Namespace: {item["namespace"]}',
            }
            for item in records
        ),
        'decision': (
            'Prioritize incomplete requests, memory-limit review, BestEffort workloads, and incomplete metrics evidence before right-sizing.'
            if available
            else 'Restore workload request, limit, QoS, and metrics evidence before assigning configuration status.'
        ),
    }


def metric(label_value: str, value: str, status: str, tone_value: str) -> dict[str, str]:
    return {'label': label_value, 'value': value, 'status': status, 'tone': tone_value}


def reference(ref: str, title: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'title': title, 'description': description}


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def text(value: Any, fallback: str = '-') -> str:
    if value is None:
        return fallback
    text_value = str(value).strip()
    return text_value or fallback


def label(value: Any, fallback: str = '') -> str:
    if isinstance(value, Mapping):
        return text(value.get('label'), fallback)
    return text(value, fallback)


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def integer(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def percent(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) * 100.0 / float(denominator), 1)


def percent_display(value: Any) -> str:
    if value is None:
        return 'Not Available'
    return f'{number(value):.1f}%'


def tone(value: str) -> str:
    normalized = value.lower()
    if normalized in {'critical', 'high', 'missing'}:
        return 'critical'
    if normalized in {'warning', 'watch', 'review', 'medium', 'partial', 'unknown'}:
        return 'warning'
    if normalized in {'info', 'planned'}:
        return 'info'
    return 'normal'


def priority_from_severity(value: str) -> str:
    normalized = value.lower()
    if normalized in {'critical', 'high'}:
        return 'P1'
    if normalized in {'warning', 'medium'}:
        return 'P2'
    return 'P3'


def priority(value: str) -> str:
    normalized = value.lower()
    if normalized in {'critical', 'p1', 'high'}:
        return 'P1'
    if normalized in {'warning', 'p2', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def target(priority_value: str) -> str:
    return 'This Week' if priority_value == 'P1' else 'Next Week' if priority_value == 'P2' else 'This Month'


def is_actionable(item: Mapping[str, Any]) -> bool:
    value = item.get('is_actionable')
    if isinstance(value, bool):
        return value
    return text(value, '').lower() in {'yes', 'true', '1'} or priority(text(item.get('priority'), 'Info')) in {
        'P1',
        'P2',
    }


def date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    return text(value, 'At report cut-off')
