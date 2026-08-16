from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.analytics.object_storage.analysis import (
    ERROR_CRITICAL_PERCENT,
    ERROR_WARNING_PERCENT,
    OperationalPosture,
    compare_evidence,
    summarize_trend,
)


def format_bytes(value: float | int | None) -> str:
    if value is None:
        return 'N/A'
    size = float(value)
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            return f'{size:,.1f} {unit}' if unit != 'B' else f'{size:,.0f} {unit}'
        size /= 1024
    return 'N/A'


def format_number(value: float | int | None) -> str:
    return 'N/A' if value is None else f'{value:,.0f}'


def format_rate(value: float | int | None) -> str:
    return 'N/A' if value is None else f'{value:,.2f}/s'


def format_percent(value: float | int | None) -> str:
    return 'N/A' if value is None else f'{value:,.1f}%'


def utilization_percent(used: float | None, capacity: float | None) -> float | None:
    if used is None or capacity is None or capacity <= 0:
        return None
    return max(0.0, min(100.0, used / capacity * 100.0))


def utilization_tone(value: float | None) -> str:
    if value is None:
        return 'unknown'
    if value >= 95:
        return 'critical'
    if value >= 85:
        return 'warning'
    return 'normal'


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return 'Not Collected'
    return value.strftime('%Y-%m-%d %H:%M UTC')


def build_trend_view(
    points: list[dict[str, float]],
    *,
    formatter: Callable[[float | int | None], str] = format_bytes,
) -> dict[str, Any]:
    summary = summarize_trend(points)
    direction_labels = {
        'increasing': ('Increasing', 'warning', 'trending-up'),
        'decreasing': ('Decreasing', 'normal', 'trending-down'),
        'stable': ('Stable', 'normal', 'minus'),
        'unknown': ('Unknown', 'unknown', 'circle-help'),
    }
    label, tone, icon = direction_labels[summary.direction]
    return {
        'sample_count': summary.sample_count,
        'first_value': summary.first_value,
        'current_value': summary.current_value,
        'delta': summary.delta,
        'delta_display': formatter(summary.delta) if summary.delta is not None else 'N/A',
        'delta_percent': summary.delta_percent,
        'delta_percent_display': format_percent(summary.delta_percent),
        'growth_per_day': summary.growth_per_day,
        'growth_per_day_display': (
            f'{formatter(summary.growth_per_day)} per day' if summary.growth_per_day is not None else 'N/A'
        ),
        'direction': summary.direction,
        'direction_label': label,
        'tone': tone,
        'icon': icon,
    }


def build_comparison_view(
    label: str,
    operational: float | None,
    inventory: float | int | None,
    *,
    formatter: Callable[[float | int | None], str],
) -> dict[str, Any]:
    comparison = compare_evidence(operational, inventory)
    delta_prefix = '+' if comparison.delta is not None and comparison.delta > 0 else ''
    delta_display = formatter(comparison.delta) if comparison.delta is not None else 'N/A'
    return {
        'label': label,
        'operational_display': formatter(comparison.operational_value),
        'inventory_display': formatter(comparison.inventory_value),
        'delta_display': f'{delta_prefix}{delta_display}' if comparison.delta is not None else 'N/A',
        'delta_percent_display': format_percent(comparison.delta_percent),
        'status': comparison.status,
        'tone': comparison.tone,
    }


def build_bucket_analysis(rows: list[dict[str, Any]], total_usage: float | None) -> dict[str, Any]:
    denominator = (
        total_usage
        if total_usage is not None and total_usage > 0
        else sum(float(row['usage_bytes'] or 0) for row in rows)
    )
    for row in rows:
        row['usage_share'] = (
            float(row['usage_bytes'] or 0) / denominator * 100.0
            if denominator and row['usage_bytes'] is not None
            else None
        )
        row['usage_share_display'] = format_percent(row['usage_share'])

    def leader(key: str) -> dict[str, Any] | None:
        values = [row for row in rows if row.get(key) is not None]
        return max(values, key=lambda item: float(item[key] or 0)) if values else None

    quota_known = [row for row in rows if row['quota_bytes'] is not None]
    request_evidence_count = sum(row.get('request_rate') is not None for row in rows)
    error_evidence_count = sum(row.get('error_ratio') is not None for row in rows)
    quota_pressure = [
        row for row in quota_known if row['quota_utilization'] is not None and row['quota_utilization'] >= 85
    ]
    top_usage = leader('usage_bytes')
    top_usage_share = top_usage.get('usage_share') if top_usage else None
    if top_usage_share is None:
        concentration = {'label': 'Unknown', 'tone': 'unknown'}
    elif top_usage_share >= 70:
        concentration = {'label': 'Highly Concentrated', 'tone': 'warning'}
    elif top_usage_share >= 50:
        concentration = {'label': 'Concentrated', 'tone': 'warning'}
    else:
        concentration = {'label': 'Distributed', 'tone': 'normal'}
    return {
        'bucket_count': len(rows),
        'quota_known_count': len(quota_known),
        'quota_unknown_count': len(rows) - len(quota_known),
        'quota_pressure_count': len(quota_pressure),
        'critical_quota_count': sum(
            row['quota_utilization'] is not None and row['quota_utilization'] >= 95 for row in quota_known
        ),
        'top_usage': top_usage,
        'top_objects': leader('objects'),
        'top_request_rate': leader('request_rate'),
        'top_error_rate': leader('error_rate'),
        'top_error_ratio': leader('error_ratio'),
        'request_evidence_count': request_evidence_count,
        'error_evidence_count': error_evidence_count,
        'request_evidence_coverage_display': format_percent(
            request_evidence_count / len(rows) * 100.0 if rows else None
        ),
        'error_evidence_coverage_display': format_percent(error_evidence_count / len(rows) * 100.0 if rows else None),
        'quota_evidence_coverage_display': format_percent(len(quota_known) / len(rows) * 100.0 if rows else None),
        'top_usage_share': top_usage_share,
        'top_usage_share_display': format_percent(top_usage_share),
        'concentration_label': concentration['label'],
        'concentration_tone': concentration['tone'],
    }


def build_capacity_usage_view(
    *,
    capacity_total: float | None,
    usage_total: float | None,
    capacity_free: float | None,
    capacity_free_source: str,
    utilization: float | None,
    trend_summary: dict[str, Any],
    bucket_analysis: dict[str, Any],
) -> dict[str, Any]:
    bucket_count = int(bucket_analysis.get('bucket_count') or 0)
    quota_known_count = int(bucket_analysis.get('quota_known_count') or 0)
    quota_pressure_count = int(bucket_analysis.get('quota_pressure_count') or 0)
    critical_quota_count = int(bucket_analysis.get('critical_quota_count') or 0)
    warning_quota_count = max(0, quota_pressure_count - critical_quota_count)
    within_quota_count = max(0, quota_known_count - quota_pressure_count)
    quota_coverage_percent = quota_known_count / bucket_count * 100.0 if bucket_count > 0 else None
    if quota_known_count == 0:
        quota_status = 'No Quota Evidence'
        quota_tone = 'unknown'
    elif critical_quota_count:
        quota_status = 'Critical Quota Pressure'
        quota_tone = 'critical'
    elif quota_pressure_count:
        quota_status = 'Quota Pressure'
        quota_tone = 'warning'
    else:
        quota_status = 'Within Known Quotas'
        quota_tone = 'normal'

    capacity_evidence_available = capacity_total is not None and usage_total is not None
    trend_sample_count = int(trend_summary.get('sample_count') or 0)
    trend_evidence_available = trend_sample_count >= 2
    growth_per_day = trend_summary.get('growth_per_day')
    growth_capacity_percent = (
        float(growth_per_day) / capacity_total * 100.0
        if growth_per_day is not None and capacity_total is not None and capacity_total > 0
        else None
    )
    return {
        'capacity_evidence_available': capacity_evidence_available,
        'headroom_source': capacity_free_source,
        'utilization': utilization,
        'utilization_display': format_percent(utilization),
        'utilization_tone': utilization_tone(utilization),
        'trend_evidence_available': trend_evidence_available,
        'trend_sample_count': trend_sample_count,
        'growth_per_day_display': trend_summary.get('growth_per_day_display') or 'N/A',
        'growth_capacity_percent': growth_capacity_percent,
        'growth_capacity_percent_display': format_percent(growth_capacity_percent),
        'trend_direction_label': trend_summary.get('direction_label') or 'Unknown',
        'trend_tone': trend_summary.get('tone') or 'unknown',
        'window_delta_display': trend_summary.get('delta_display') or 'N/A',
        'window_delta_percent_display': trend_summary.get('delta_percent_display') or 'N/A',
        'quota_coverage_display': format_percent(quota_coverage_percent),
        'quota_known_count': quota_known_count,
        'quota_unknown_count': int(bucket_analysis.get('quota_unknown_count') or 0),
        'quota_within_count': within_quota_count,
        'quota_warning_count': warning_quota_count,
        'quota_critical_count': critical_quota_count,
        'quota_status': quota_status,
        'quota_tone': quota_tone,
        'top_usage_share_display': bucket_analysis.get('top_usage_share_display') or 'N/A',
        'concentration_label': bucket_analysis.get('concentration_label') or 'Unknown',
        'concentration_tone': bucket_analysis.get('concentration_tone') or 'unknown',
    }


@dataclass(frozen=True, slots=True)
class PerformanceEvidence:
    request_rate: float | None
    error_rate: float | None
    error_ratio: float | None
    success_ratio: float | None
    waiting: float | None
    inflight: float | None
    offline_nodes: float | None
    received_bps: float | None
    sent_bps: float | None
    request_trend_summary: dict[str, Any]
    error_trend_summary: dict[str, Any]
    bucket_analysis: dict[str, Any]


def _reliability_state(error_ratio: float | None) -> tuple[str, str]:
    if error_ratio is None:
        return 'Error Evidence Unavailable', 'unknown'
    if error_ratio >= ERROR_CRITICAL_PERCENT:
        return 'Critical Error Pressure', 'critical'
    if error_ratio >= ERROR_WARNING_PERCENT:
        return 'Elevated Error Pressure', 'warning'
    return 'Within Error Baseline', 'normal'


def _queue_state(waiting: float | None) -> tuple[str, str]:
    if waiting is None:
        return 'Queue Evidence Unavailable', 'unknown'
    if waiting > 0:
        return 'Requests Waiting', 'warning'
    return 'No Waiting Requests', 'normal'


def _node_state(offline_nodes: float | None) -> tuple[str, str]:
    if offline_nodes is None:
        return 'Node Evidence Unavailable', 'unknown'
    if offline_nodes > 0:
        return 'Offline Storage Nodes', 'critical'
    return 'No Offline Nodes', 'normal'


def _request_trend_state(direction: str) -> tuple[str, str]:
    return {
        'increasing': ('Increasing Demand', 'info'),
        'decreasing': ('Decreasing Demand', 'info'),
        'stable': ('Stable Demand', 'normal'),
    }.get(direction, ('Demand Trend Unknown', 'unknown'))


def _error_trend_state(direction: str) -> tuple[str, str]:
    return {
        'increasing': ('Errors Increasing', 'warning'),
        'decreasing': ('Errors Decreasing', 'normal'),
        'stable': ('Errors Stable', 'normal'),
    }.get(direction, ('Error Trend Unknown', 'unknown'))


def _traffic_shares(
    received_bps: float | None,
    sent_bps: float | None,
) -> tuple[float | None, float | None, float | None]:
    if received_bps is None or sent_bps is None:
        return None, None, None
    total = received_bps + sent_bps
    if total <= 0:
        return total, None, None
    return total, received_bps / total * 100.0, sent_bps / total * 100.0


def _bucket_activity_coverage(bucket_analysis: dict[str, Any]) -> tuple[int, int, int, float | None, float | None]:
    bucket_count = int(bucket_analysis.get('bucket_count') or 0)
    request_count = int(bucket_analysis.get('request_evidence_count') or 0)
    error_count = int(bucket_analysis.get('error_evidence_count') or 0)
    request_coverage = request_count / bucket_count * 100.0 if bucket_count else None
    error_coverage = error_count / bucket_count * 100.0 if bucket_count else None
    return bucket_count, request_count, error_count, request_coverage, error_coverage


def build_performance_view(evidence: PerformanceEvidence) -> dict[str, Any]:
    reliability_status, reliability_tone = _reliability_state(evidence.error_ratio)
    queue_status, queue_tone = _queue_state(evidence.waiting)
    node_status, node_tone = _node_state(evidence.offline_nodes)
    request_trend_status, request_trend_tone = _request_trend_state(
        str(evidence.request_trend_summary.get('direction') or 'unknown')
    )
    error_trend_status, error_trend_tone = _error_trend_state(
        str(evidence.error_trend_summary.get('direction') or 'unknown')
    )
    total_traffic, received_share, sent_share = _traffic_shares(evidence.received_bps, evidence.sent_bps)
    bucket_count, request_count, error_count, request_coverage, error_coverage = _bucket_activity_coverage(
        evidence.bucket_analysis
    )
    evidence_values = (
        evidence.request_rate,
        evidence.error_rate,
        evidence.error_ratio,
        evidence.waiting,
        evidence.inflight,
        evidence.offline_nodes,
        evidence.received_bps,
        evidence.sent_bps,
    )
    evidence_available = sum(value is not None for value in evidence_values)
    evidence_total = len(evidence_values)
    evidence_coverage = evidence_available / evidence_total * 100.0
    top_request_bucket = evidence.bucket_analysis.get('top_request_rate')
    top_error_bucket = evidence.bucket_analysis.get('top_error_ratio')

    return {
        'request_rate_display': format_rate(evidence.request_rate),
        'error_rate_display': format_rate(evidence.error_rate),
        'error_ratio_display': format_percent(evidence.error_ratio),
        'success_ratio_display': format_percent(evidence.success_ratio),
        'waiting_display': format_number(evidence.waiting),
        'inflight_display': format_number(evidence.inflight),
        'offline_nodes_display': format_number(evidence.offline_nodes),
        'received_bps_display': (
            format_bytes(evidence.received_bps) + '/s' if evidence.received_bps is not None else 'N/A'
        ),
        'sent_bps_display': format_bytes(evidence.sent_bps) + '/s' if evidence.sent_bps is not None else 'N/A',
        'total_traffic_display': format_bytes(total_traffic) + '/s' if total_traffic is not None else 'N/A',
        'received_share_display': format_percent(received_share),
        'sent_share_display': format_percent(sent_share),
        'reliability_status': reliability_status,
        'reliability_tone': reliability_tone,
        'queue_status': queue_status,
        'queue_tone': queue_tone,
        'node_status': node_status,
        'node_tone': node_tone,
        'request_trend_status': request_trend_status,
        'request_trend_tone': request_trend_tone,
        'request_trend_samples': int(evidence.request_trend_summary.get('sample_count') or 0),
        'request_window_delta_display': evidence.request_trend_summary.get('delta_display') or 'N/A',
        'request_window_delta_percent_display': evidence.request_trend_summary.get('delta_percent_display') or 'N/A',
        'error_trend_status': error_trend_status,
        'error_trend_tone': error_trend_tone,
        'error_trend_samples': int(evidence.error_trend_summary.get('sample_count') or 0),
        'error_window_delta_display': evidence.error_trend_summary.get('delta_display') or 'N/A',
        'error_window_delta_percent_display': evidence.error_trend_summary.get('delta_percent_display') or 'N/A',
        'bucket_request_coverage_display': format_percent(request_coverage),
        'bucket_error_coverage_display': format_percent(error_coverage),
        'bucket_request_evidence_count': request_count,
        'bucket_error_evidence_count': error_count,
        'bucket_count': bucket_count,
        'top_request_bucket_name': str(top_request_bucket.get('name') or 'N/A') if top_request_bucket else 'N/A',
        'top_request_bucket_value': top_request_bucket.get('request_rate_display') if top_request_bucket else 'N/A',
        'top_error_bucket_name': str(top_error_bucket.get('name') or 'N/A') if top_error_bucket else 'N/A',
        'top_error_bucket_value': top_error_bucket.get('error_ratio_display') if top_error_bucket else 'N/A',
        'evidence_coverage_display': format_percent(evidence_coverage),
        'evidence_available_count': evidence_available,
        'evidence_total_count': evidence_total,
    }


def build_posture_view(posture: OperationalPosture) -> dict[str, str]:
    return {
        'status': posture.status,
        'tone': posture.tone,
        'headline': posture.headline,
        'detail': posture.detail,
    }


def build_signal_posture(signals: list[dict[str, str]]) -> dict[str, Any]:
    counts = {severity: 0 for severity in ('critical', 'warning', 'normal', 'unknown')}
    for signal in signals:
        severity = str(signal.get('severity') or 'unknown')
        counts[severity if severity in counts else 'unknown'] += 1

    if counts['critical']:
        status, tone = 'Critical', 'critical'
        detail = 'One or more metric-derived signals require immediate operational triage.'
    elif counts['warning']:
        status, tone = 'Attention', 'warning'
        detail = 'Metric-derived evidence indicates conditions that require planned operational review.'
    elif counts['unknown']:
        status, tone = 'Unknown', 'unknown'
        detail = 'Operational signal evaluation is incomplete because required metric evidence is unavailable.'
    else:
        status, tone = 'Baseline', 'normal'
        detail = 'Current metric-derived signals remain inside the baseline operating boundaries.'
    return {
        'status': status,
        'tone': tone,
        'detail': detail,
        'critical_count': counts['critical'],
        'warning_count': counts['warning'],
        'normal_count': counts['normal'],
        'unknown_count': counts['unknown'],
    }
