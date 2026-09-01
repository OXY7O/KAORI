from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class _QuotaStats:
    total: int
    covered: int
    complete: int
    partial: int
    missing: int
    near_limit: int
    over_quota: int
    coverage: float | None
    available: bool
    status: str
    tone: str


@dataclass(frozen=True, slots=True)
class _MappingStats:
    total: int
    namespace_count: int
    complete_requests: int
    complete_limits: int
    complete_metrics: int
    high_risk: int
    available: bool


@dataclass(frozen=True, slots=True)
class _ConfigurationStats:
    total: int
    request_complete: int
    limit_complete: int
    metrics_complete: int
    best_effort: int
    missing_requests: int
    limit_review: int
    right_size: int
    available: bool


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


def _quota_stats(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> _QuotaStats:
    total = integer(summary.get('scope_total')) or len(rows)
    covered = integer(summary.get('scope_covered')) or sum(
        1 for row in rows if label(row.get('quota_status')) in {'Complete', 'Partial'}
    )
    complete = sum(1 for row in rows if label(row.get('quota_status')) == 'Complete')
    partial = sum(1 for row in rows if label(row.get('quota_status')) == 'Partial')
    missing = sum(1 for row in rows if label(row.get('quota_status')) == 'Missing')
    near_limit = integer(summary.get('scope_near_limit_count')) or sum(
        1 for row in rows if bool(row.get('quota_pressure_available')) and number(row.get('quota_usage_percent')) >= 75
    )
    over_quota = sum(
        1 for row in rows if bool(row.get('quota_pressure_available')) and number(row.get('quota_usage_percent')) >= 100
    )
    available = bool(rows)
    coverage = percent(covered, total) if total else None
    status = 'Current' if available and missing == 0 else 'Review' if available else 'Not Available'
    tone_value = 'normal' if available and missing == 0 and over_quota == 0 else 'warning'
    return _QuotaStats(
        total=total,
        covered=covered,
        complete=complete,
        partial=partial,
        missing=missing,
        near_limit=near_limit,
        over_quota=over_quota,
        coverage=coverage,
        available=available,
        status=status,
        tone=tone_value,
    )


def _quota_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:5], start=1):
        risk = label(row.get('risk'), 'Unknown')
        pressure = (
            percent_display(row.get('quota_usage_percent'))
            if bool(row.get('quota_pressure_available'))
            else 'Not Available'
        )
        records.append(
            {
                'ref': f'Q{index}',
                'namespace': text(row.get('namespace'), '-'),
                'coverage': label(row.get('quota_status'), 'Unknown'),
                'pressure': pressure,
                'risk': risk,
                'tone': tone(risk),
            }
        )
    return records


def _quota_metrics(stats: _QuotaStats) -> tuple[dict[str, str], ...]:
    return (
        metric(
            'Namespaces',
            str(stats.total) if stats.total else 'Not Available',
            'Committed Scope' if stats.total else 'Not Available',
            'normal' if stats.total else 'warning',
        ),
        metric(
            'Quota Coverage',
            percent_display(stats.coverage) if stats.coverage is not None else 'Not Available',
            stats.status,
            stats.tone,
        ),
        metric(
            'Missing Quota',
            str(stats.missing) if stats.available else 'Not Available',
            'Review' if stats.missing else 'Clear' if stats.available else 'Not Available',
            'warning' if stats.missing or not stats.available else 'normal',
        ),
        metric(
            'Near / Over Limit',
            str(stats.near_limit),
            'Review' if stats.near_limit else 'Clear',
            'warning' if stats.near_limit else 'normal',
        ),
    )


def _quota_requirements(stats: _QuotaStats) -> tuple[dict[str, str], ...]:
    return (
        {
            'ref': 'QE1',
            'evidence': 'ResourceQuota Inventory',
            'definition': 'Quota object and namespace scope',
            'status': 'Current' if stats.available else 'Missing',
            'action': 'Monitor' if stats.available else 'Required',
        },
        {
            'ref': 'QE2',
            'evidence': 'Quota Used / Hard',
            'definition': 'Used and hard values by resource',
            'status': 'Current' if stats.available else 'Missing',
            'action': 'Review' if stats.near_limit else 'Monitor' if stats.available else 'Required',
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
    )


def quota_analysis(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = _quota_stats(summary, rows)
    return {
        'available': stats.available,
        'total': stats.total,
        'covered': stats.covered,
        'complete': stats.complete,
        'partial': stats.partial,
        'missing': stats.missing,
        'near_limit': stats.near_limit,
        'over_quota': stats.over_quota,
        'coverage': stats.coverage,
        'coverage_display': percent_display(stats.coverage) if stats.coverage is not None else 'Not Available',
        'status': stats.status,
        'tone': stats.tone,
        'metrics': _quota_metrics(stats),
        'records': _quota_records(rows),
        'requirements': _quota_requirements(stats),
        'decision': (
            'Review namespaces with missing or partial quota definitions before approving additional workload growth.'
            if stats.available
            else 'Restore ResourceQuota evidence before assigning tenant governance status.'
        ),
    }


def _mapping_stats(rows: list[dict[str, Any]]) -> _MappingStats:
    return _MappingStats(
        total=len(rows),
        namespace_count=len({text(row.get('namespace'), '') for row in rows if text(row.get('namespace'), '')}),
        complete_requests=sum(1 for row in rows if label(row.get('request_coverage')) == 'Complete'),
        complete_limits=sum(1 for row in rows if label(row.get('limit_coverage')) == 'Complete'),
        complete_metrics=sum(1 for row in rows if label(row.get('metrics_coverage')) == 'Complete'),
        high_risk=sum(1 for row in rows if label(row.get('risk')) in {'High', 'Critical'}),
        available=bool(rows),
    )


def _mapping_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:5], start=1):
        risk = label(row.get('risk'), 'Unknown')
        records.append(
            {
                'ref': f'M{index}',
                'workload': text(row.get('workload'), '-'),
                'type': text(row.get('type'), '-'),
                'namespace': text(row.get('namespace'), '-'),
                'mapping': f'{integer(row.get("replicas"))} pod(s)'
                if row.get('replicas') is not None
                else 'Inventory row',
                'status': risk,
                'tone': tone(risk),
            }
        )
    return records


def _mapping_metrics(stats: _MappingStats) -> tuple[dict[str, str], ...]:
    return (
        metric(
            'Workloads',
            str(stats.total) if stats.available else 'Not Available',
            'Inventory Available' if stats.available else 'Not Available',
            'normal' if stats.available else 'warning',
        ),
        metric(
            'Namespaces',
            str(stats.namespace_count) if stats.namespace_count else 'Not Available',
            'Committed Scope' if stats.namespace_count else 'Not Available',
            'normal' if stats.namespace_count else 'warning',
        ),
        metric(
            'Resource Mapping',
            percent_display(percent(stats.complete_metrics, stats.total)) if stats.total else 'Not Available',
            'Complete Metrics' if stats.total else 'Not Available',
            'normal' if stats.total and stats.complete_metrics == stats.total else 'warning',
        ),
        metric('Owner Mapping', 'Not Available', 'Not Committed', 'warning'),
    )


def _mapping_coverage(stats: _MappingStats) -> tuple[dict[str, Any], ...]:
    requests = percent(stats.complete_requests, stats.total)
    limits = percent(stats.complete_limits, stats.total)
    return (
        {
            'label': 'Inventory to Namespace',
            'value': 100.0 if stats.available else 0.0,
            'display': 'Available' if stats.available else 'Not Available',
            'available': stats.available,
        },
        {
            'label': 'Requests Coverage',
            'value': requests or 0.0,
            'display': percent_display(requests) if stats.total else 'Not Available',
            'available': stats.available,
        },
        {
            'label': 'Limits Coverage',
            'value': limits or 0.0,
            'display': percent_display(limits) if stats.total else 'Not Available',
            'available': stats.available,
        },
        {'label': 'Application Owner', 'value': 0.0, 'display': 'Not Available', 'available': False},
    )


def mapping_analysis(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = _mapping_stats(rows)
    records = _mapping_records(rows)
    return {
        'available': stats.available,
        'metrics': _mapping_metrics(stats),
        'records': records,
        'identities': tuple(
            {
                'ref': item['ref'],
                'title': item['workload'],
                'metadata': f'Namespace: {item["namespace"]} · Type: {item["type"]}',
            }
            for item in records
        ),
        'coverage': _mapping_coverage(stats),
        'interpretation_title': (
            'Mapping supports workload triage, but ownership remains incomplete.'
            if stats.available
            else 'Workload mapping evidence is not available.'
        ),
        'interpretation_body': (
            f'{stats.total} workload row(s) cover {stats.namespace_count} namespace(s). '
            f'{stats.high_risk} high-risk workload row(s) require review. Application-owner identity is not committed.'
            if stats.available
            else 'Restore committed workload-to-pod and namespace mapping before deriving configuration posture.'
        ),
        'decision': (
            'Confirm controller, application owner, deployment intent, maintenance window, and rollback readiness before changing resources or replicas.'
        ),
    }


def _configuration_stats(rows: list[dict[str, Any]]) -> _ConfigurationStats:
    return _ConfigurationStats(
        total=len(rows),
        request_complete=sum(1 for row in rows if label(row.get('request_coverage')) == 'Complete'),
        limit_complete=sum(1 for row in rows if label(row.get('limit_coverage')) == 'Complete'),
        metrics_complete=sum(1 for row in rows if label(row.get('metrics_coverage')) == 'Complete'),
        best_effort=sum(1 for row in rows if label(row.get('qos')) == 'BestEffort'),
        missing_requests=sum(1 for row in rows if label(row.get('request_coverage')) in {'Missing', 'Partial'}),
        limit_review=sum(1 for row in rows if label(row.get('limit_coverage')) != 'Complete'),
        right_size=sum(
            1
            for row in rows
            if any(
                token in text(row.get('recommendation'), '').lower()
                for token in ('reduce', 'increase', 'right-size')
            )
        ),
        available=bool(rows),
    )


def _configuration_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:5], start=1):
        risk = label(row.get('risk'), 'Unknown')
        records.append(
            {
                'ref': f'C{index}',
                'workload': text(row.get('workload'), '-'),
                'namespace': text(row.get('namespace'), '-'),
                'requests': label(row.get('request_coverage'), 'Unknown'),
                'limits': label(row.get('limit_coverage'), 'Unknown'),
                'qos': label(row.get('qos'), 'Unknown'),
                'risk': risk,
                'tone': tone(risk),
            }
        )
    return records


def _configuration_metrics(stats: _ConfigurationStats) -> tuple[dict[str, str], ...]:
    request_coverage = percent(stats.request_complete, stats.total)
    limit_coverage = percent(stats.limit_complete, stats.total)
    metrics_coverage = percent(stats.metrics_complete, stats.total)
    return (
        metric(
            'CPU / Memory Requests',
            percent_display(request_coverage) if stats.total else 'Not Available',
            'Complete Rows' if stats.total else 'Not Available',
            'normal' if stats.total and stats.request_complete == stats.total else 'warning',
        ),
        metric(
            'Limits Coverage',
            percent_display(limit_coverage) if stats.total else 'Not Available',
            'Complete Rows' if stats.total else 'Not Available',
            'normal' if stats.total and stats.limit_complete == stats.total else 'warning',
        ),
        metric(
            'BestEffort',
            str(stats.best_effort) if stats.available else 'Not Available',
            'Review' if stats.best_effort else 'Clear' if stats.available else 'Not Available',
            'warning' if stats.best_effort or not stats.available else 'normal',
        ),
        metric(
            'Metrics Coverage',
            percent_display(metrics_coverage) if stats.total else 'Not Available',
            'Complete Rows' if stats.total else 'Not Available',
            'normal' if stats.total and stats.metrics_complete == stats.total else 'warning',
        ),
    )


def _configuration_coverage(stats: _ConfigurationStats) -> tuple[dict[str, Any], ...]:
    request_coverage = percent(stats.request_complete, stats.total)
    limit_coverage = percent(stats.limit_complete, stats.total)
    metrics_coverage = percent(stats.metrics_complete, stats.total)
    return (
        {
            'label': 'Requests Complete',
            'value': request_coverage or 0.0,
            'display': percent_display(request_coverage) if stats.total else 'Not Available',
            'available': stats.available,
        },
        {
            'label': 'Limits Complete',
            'value': limit_coverage or 0.0,
            'display': percent_display(limit_coverage) if stats.total else 'Not Available',
            'available': stats.available,
        },
        {
            'label': 'Metrics Complete',
            'value': metrics_coverage or 0.0,
            'display': percent_display(metrics_coverage) if stats.total else 'Not Available',
            'available': stats.available,
        },
    )


def configuration_analysis(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = _configuration_stats(rows)
    records = _configuration_records(rows)
    return {
        'available': stats.available,
        'total': stats.total,
        'request_complete': stats.request_complete,
        'limit_complete': stats.limit_complete,
        'metrics_complete': stats.metrics_complete,
        'best_effort': stats.best_effort,
        'missing_requests': stats.missing_requests,
        'limit_review': stats.limit_review,
        'right_size': stats.right_size,
        'request_coverage': percent(stats.request_complete, stats.total),
        'limit_coverage': percent(stats.limit_complete, stats.total),
        'metrics_coverage': percent(stats.metrics_complete, stats.total),
        'metrics': _configuration_metrics(stats),
        'coverage_rows': _configuration_coverage(stats),
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
            if stats.available
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
