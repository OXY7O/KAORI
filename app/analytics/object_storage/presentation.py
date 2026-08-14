from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.analytics.object_storage.analysis import (
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
            f"{formatter(summary.growth_per_day)} per day" if summary.growth_per_day is not None else 'N/A'
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
    denominator = total_usage if total_usage is not None and total_usage > 0 else sum(
        float(row['usage_bytes'] or 0) for row in rows
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
    quota_coverage_percent = (
        quota_known_count / bucket_count * 100.0 if bucket_count > 0 else None
    )
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
