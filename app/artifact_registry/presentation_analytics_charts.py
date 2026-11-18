"""Committed Registry analytics chart and insight projections, without provider reads."""

from __future__ import annotations

from math import isfinite
from typing import Any

from app.artifact_registry.presentation_common import _fmt_bytes


def _registry_usage_chart_rows(activity_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Qualified committed pull counters per project; zero is an observed value."""
    qualified: list[dict[str, Any]] = []
    for row in activity_rows:
        raw_count = row.get('pull_count')
        if (
            isinstance(raw_count, bool)
            or not isinstance(raw_count, (int, float))
            or not isfinite(raw_count)
            or raw_count < 0
        ):
            continue
        project = str(row.get('project_name') or '').strip()
        registry = str(row.get('registry_name') or '').strip()
        if not project or not registry:
            continue
        count = float(raw_count)
        qualified.append(
            {
                'project_name': project,
                'registry_name': registry,
                'pull_count': count,
                'pull_display': f'{count:,.0f}',
            }
        )
    return sorted(
        qualified,
        key=lambda row: (-row['pull_count'], row['project_name'].casefold(), row['registry_name'].casefold()),
    )[:5]


def _registry_capacity_project_rows(forecast_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Qualified, committed project quota ratios; never synthesize a forecast."""
    qualified: list[dict[str, Any]] = []
    for row in forecast_rows:
        usage, quota = row.get('usage_bytes'), row.get('quota_bytes')
        if (
            isinstance(usage, bool)
            or isinstance(quota, bool)
            or not isinstance(usage, (int, float))
            or not isinstance(quota, (int, float))
            or not isfinite(usage)
            or not isfinite(quota)
            or usage < 0
            or quota <= 0
        ):
            continue
        project = str(row.get('project_name') or '').strip()
        registry = str(row.get('registry_name') or '').strip()
        if not project or not registry:
            continue
        ratio = float(usage) / float(quota) * 100.0
        if not isfinite(ratio):
            continue
        qualified.append(
            {
                'project_name': project,
                'registry_name': registry,
                'utilization_percent': round(ratio, 3),
                'utilization_display': f'{ratio:.1f}%',
                'usage_bytes': float(usage),
                'quota_bytes': float(quota),
                'usage_display': row['usage_display'],
                'quota_display': row['quota_display'],
                'forecast_label': row.get('days_to_quota_display') or 'No forecast',
                'growth_display': row.get('growth_display') or 'Insufficient history',
            }
        )
    return sorted(
        qualified,
        key=lambda row: (-row['utilization_percent'], row['project_name'].casefold()),
    )


def _registry_capacity_chart_rows(forecast_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep Overview chart bounded while the detail table paginates."""
    return _registry_capacity_project_rows(forecast_rows)[:5]


def _analytics_summary_cards(
    aggregate: dict[str, Any],
    *,
    growth_rows: list[dict[str, Any]],
    growth: dict[str, Any],
    risk_candidate_count: int,
) -> list[dict[str, Any]]:
    return [
        {
            'icon': 'database',
            'label': 'Storage Footprint',
            'value': _fmt_bytes(int(aggregate['total_size_bytes'])),
            'detail': (
                f'{_fmt_bytes(round(growth["size_per_day"]))}/day materialized growth'
                if growth['size_per_day'] is not None
                else 'Historical storage-growth evidence is unavailable'
            ),
            'tone': 'brand',
        },
        {
            'icon': 'chart-no-axes-combined',
            'label': 'Artifact Growth',
            'value': f'{growth["artifacts_per_day"]:+.1f}/day' if growth['artifacts_per_day'] is not None else 'N/A',
            'detail': f'{aggregate["artifacts"]} committed artifacts',
            'tone': 'info' if growth['artifacts_per_day'] is not None else 'unknown',
        },
        {
            'icon': 'boxes',
            'label': 'Runtime-used',
            'value': str(aggregate['running_artifacts']),
            'detail': (
                f'{growth["runtime_usage_percent"]:.1f}% of committed artifact estate'
                if growth['runtime_usage_percent'] is not None
                else 'No committed artifact denominator'
            ),
            'tone': 'normal' if aggregate['running_artifacts'] else 'unknown',
        },
        {
            'icon': 'triangle-alert',
            'label': 'Risk Candidates',
            'value': str(risk_candidate_count),
            'detail': 'Cross-domain signals may overlap.',
            'tone': 'warning' if risk_candidate_count else 'normal',
        },
    ]


def _analytics_insights(
    aggregate: dict[str, Any],
    *,
    growth_rows: list[dict[str, Any]],
    growth: dict[str, Any],
) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    candidates = (
        (
            growth['artifacts_per_day'] is not None and growth['size_per_day'] is not None,
            {
                'icon': 'trending-up',
                'title': 'Registry growth is materialized',
                'detail': (
                    f'{float(growth["artifacts_per_day"] or 0):+.1f} artifacts/day and '
                    f'{_fmt_bytes(round(float(growth["size_per_day"] or 0)))}/day across current providers.'
                ),
                'tone': 'info',
            },
        ),
        (
            bool(aggregate['critical_runtime_artifacts']),
            {
                'icon': 'shield-alert',
                'title': 'Critical findings intersect runtime usage',
                'detail': (
                    f'{aggregate["critical_runtime_artifacts"]} running artifacts carry '
                    'critical security evidence and require Intelligence review.'
                ),
                'tone': 'critical',
            },
        ),
        (
            bool(aggregate['stale_candidates']),
            {
                'icon': 'archive',
                'title': 'Stale inventory candidates exist',
                'detail': (
                    f'{aggregate["stale_candidates"]} artifacts are review candidates only; '
                    'Analytics never performs automatic cleanup.'
                ),
                'tone': 'warning',
            },
        ),
        (
            bool(aggregate['runtime_scan_gaps']),
            {
                'icon': 'scan-search',
                'title': 'Runtime scan evidence is incomplete',
                'detail': (
                    f'{aggregate["runtime_scan_gaps"]} running artifacts have no normalized successful scan evidence.'
                ),
                'tone': 'warning',
            },
        ),
    )
    insights.extend(item for enabled, item in candidates if enabled)
    return insights or [
        {
            'icon': 'circle-check',
            'title': 'No derived review signal',
            'detail': 'Current committed analytics evidence has no derived review signal.',
            'tone': 'normal',
        }
    ]


def _decorate_analytics_rows(
    growth_rows: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
) -> None:
    for row in growth_rows:
        size_growth = row.get('size_growth_bytes_per_day')
        size_delta = row.get('size_delta_bytes')
        artifact_growth = row.get('artifact_growth_per_day')
        row['size_growth_display'] = (
            f'{_fmt_bytes(round(float(size_growth)))}/day' if isinstance(size_growth, (int, float)) else 'N/A'
        )
        row['size_delta_display'] = (
            _fmt_bytes(round(float(size_delta))) if isinstance(size_delta, (int, float)) else 'N/A'
        )
        row['artifact_growth_display'] = (
            f'{float(artifact_growth):+.1f}/day' if isinstance(artifact_growth, (int, float)) else 'N/A'
        )
    for row in forecast_rows:
        usage = row.get('usage_bytes')
        quota = row.get('quota_bytes')
        growth = row.get('growth_bytes_per_day')
        days = row.get('days_to_quota')
        utilization = row.get('utilization_percent')
        row['usage_display'] = _fmt_bytes(round(float(usage))) if isinstance(usage, (int, float)) else 'N/A'
        row['quota_display'] = _fmt_bytes(round(float(quota))) if isinstance(quota, (int, float)) else 'N/A'
        row['growth_display'] = (
            f'{_fmt_bytes(round(float(growth)))}/day' if isinstance(growth, (int, float)) else 'Insufficient history'
        )
        row['days_to_quota_display'] = f'{float(days):.1f} days' if isinstance(days, (int, float)) else 'No forecast'
        row['utilization_display'] = f'{float(utilization):.1f}%' if isinstance(utilization, (int, float)) else 'N/A'
