from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from typing import Any

from .common import display_percent, integer, mapping, number, sequence, status, text, tone


def publication_timestamp(value: Any) -> str:
    rendered = text(value, 'Not Available')
    if rendered == 'Not Available':
        return rendered
    parsed = _parse_timestamp(rendered)
    if parsed is None:
        return rendered
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.strftime('%d %b %Y %H:%M UTC')


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        pass
    for pattern in ('%Y-%m-%d %H:%M UTC', '%d/%m/%Y %H:%M UTC', '%d %b %Y %H:%M UTC'):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def source_short_label(item: Mapping[str, Any]) -> str:
    label = text(item.get('label'), '').lower()
    source = text(item.get('source'), 'Unknown Source')
    if label == 'metrics' or 'metrics source' in source.lower():
        return 'Metrics Cache'
    if label == 'inventory' or 'kubernetes committed inventory' in source.lower():
        return 'Kubernetes Inventory'
    if label == 'analytics' or 'analytics materialized' in source.lower():
        return 'Analytics Snapshots'
    if label == 'alerts' or 'alertmanager' in source.lower():
        return 'Alert Cache'
    return source


def source_freshness_short(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {'at report cut-off', 'at report cutoff'}:
        return 'At cut-off'
    if normalized == 'current generation':
        return 'Current'
    return value


def source_status_short(value: str) -> str:
    normalized = value.strip().lower()
    if 'partial' in normalized:
        return 'Partial'
    if 'connected' in normalized:
        return 'Connected'
    if 'query ready' in normalized:
        return 'Query Ready'
    if normalized == 'current':
        return 'Current'
    return value


def source_rows(
    *,
    payload: Mapping[str, Any],
    inventory: Mapping[str, Any],
    freshness: Mapping[str, Any],
    alert_detail: Mapping[str, Any],
) -> list[dict[str, Any]]:
    explicit = sequence(freshness.get('sources'))
    if explicit:
        return [_explicit_source_row(mapping(item)) for item in explicit]
    return _default_source_rows(payload, inventory, alert_detail)


def _explicit_source_row(item: Mapping[str, Any]) -> dict[str, Any]:
    freshness_value = text(item.get('freshness'), 'Not Available')
    status_value = text(item.get('status'), 'Unknown')
    return {
        'label': text(item.get('label'), 'Data Source'),
        'source': text(item.get('source'), 'Unknown Source'),
        'source_short': source_short_label(item),
        'type': text(item.get('type'), 'Evidence'),
        'last_successful': publication_timestamp(item.get('last_successful')),
        'freshness': freshness_value,
        'freshness_short': source_freshness_short(freshness_value),
        'status': status_value,
        'status_short': source_status_short(status_value),
        'tone': tone(item.get('tone') or item.get('status')),
    }


def _default_source_rows(
    payload: Mapping[str, Any],
    inventory: Mapping[str, Any],
    alert_detail: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metrics_source = mapping(payload.get('metrics_source'))
    snapshot = mapping(payload.get('snapshot_summary'))
    health = mapping(alert_detail.get('source_status'))
    inventory_clusters = sequence(inventory.get('clusters'))
    inventory_last = next(
        (text(item.get('collected_at')) for item in inventory_clusters if isinstance(item, Mapping)),
        'Not Available',
    )
    metrics_status = text(metrics_source.get('status_label') or metrics_source.get('status'), 'Unknown')
    snapshot_status = text(snapshot.get('status'), 'Unknown')
    return [
        {
            'label': 'Metrics',
            'source': 'Metrics Source Observation Cache',
            'source_short': 'Metrics Cache',
            'type': 'Metrics',
            'last_successful': publication_timestamp(metrics_source.get('last_checked_at')),
            'freshness': text(metrics_source.get('response_time_ms'), 'Not Available'),
            'freshness_short': text(metrics_source.get('response_time_ms'), 'Not Available'),
            'status': metrics_status,
            'status_short': source_status_short(metrics_status),
            'tone': tone(metrics_source.get('status_tone') or metrics_source.get('status')),
        },
        {
            'label': 'Inventory',
            'source': 'Kubernetes Committed Inventory',
            'source_short': 'Kubernetes Inventory',
            'type': 'Snapshot',
            'last_successful': publication_timestamp(inventory_last),
            'freshness': 'Current',
            'freshness_short': 'Current',
            'status': 'Current' if inventory_clusters else 'Not Available',
            'status_short': 'Current' if inventory_clusters else 'Not Available',
            'tone': 'normal' if inventory_clusters else 'neutral',
        },
        {
            'label': 'Analytics',
            'source': 'Analytics Materialized Snapshots',
            'source_short': 'Analytics Snapshots',
            'type': 'Analytics',
            'last_successful': publication_timestamp(snapshot.get('latest_generated_at')),
            'freshness': text(snapshot.get('analysis_window'), 'Not Available'),
            'freshness_short': source_freshness_short(text(snapshot.get('analysis_window'), 'Not Available')),
            'status': snapshot_status,
            'status_short': source_status_short(snapshot_status),
            'tone': tone(snapshot.get('tone')),
        },
        {
            'label': 'Alerts',
            'source': 'Alertmanager Observation Cache',
            'source_short': 'Alert Cache',
            'type': 'Alertmanager',
            'last_successful': publication_timestamp(alert_detail.get('generated_at')),
            'freshness': 'At cut-off',
            'freshness_short': 'At cut-off',
            'status': status(health, 'Unknown'),
            'status_short': source_status_short(status(health, 'Unknown')),
            'tone': tone(health.get('tone') or health.get('status')),
        },
    ]


def freshness_page(
    source_rows_value: Sequence[Mapping[str, Any]],
    snapshot_summary: Mapping[str, Any],
    freshness: Mapping[str, Any],
) -> dict[str, Any]:
    scores = [_source_score(row) for row in source_rows_value]
    overall = sum(scores) / len(scores) if scores else 0
    expected = integer(snapshot_summary.get('expected_dataset_count'))
    current = integer(snapshot_summary.get('current_dataset_count'))
    completeness = (current / expected * 100.0) if expected else overall
    failed = integer(snapshot_summary.get('failed_dataset_count'))
    issues = sequence(freshness.get('issues')) or [_default_quality_issue(expected, current)]
    quality_score = (overall + completeness) / 2
    return {
        'metrics': _freshness_metrics(overall, completeness, failed, len(source_rows_value), quality_score),
        'sources': list(source_rows_value),
        'freshness_svg': freshness_svg(freshness),
        'reliability': _reliability_rows(overall, completeness, freshness),
        'recency': recency_distribution(source_rows_value),
        'issues': [normalize_quality_issue(item) for item in issues[:8]],
        'meaning': (
            'Data pipelines are evaluated from committed snapshots and their latest successful collection evidence.',
            'Missing or stale sources remain visible and are not silently interpreted as zero values.',
        ),
        'actions': (
            'Investigate sources marked Attention or Unavailable.',
            'Refresh failed analytics datasets before relying on affected conclusions.',
            'Maintain source ownership and retention controls.',
        ),
    }


def _source_score(row: Mapping[str, Any]) -> int:
    row_tone = tone(row.get('tone'))
    if row_tone == 'normal':
        return 100
    if row_tone in {'info', 'warning'}:
        return 75
    if row_tone == 'critical':
        return 40
    return 0


def _default_quality_issue(expected: int, current: int) -> dict[str, Any]:
    return {
        'issue_type': 'Unavailable Dataset',
        'source': 'Analytics Materialization',
        'count': max(0, expected - current),
        'impact': 'Medium' if current < expected else 'None',
        'status': 'Open' if current < expected else 'Clear',
    }


def _freshness_metrics(
    overall: float,
    completeness: float,
    failed: int,
    source_count: int,
    quality_score: float,
) -> list[dict[str, Any]]:
    return [
        {
            'label': 'Overall Freshness',
            'value': display_percent(overall),
            'status': 'Good' if overall >= 85 else 'Attention',
            'tone': 'normal' if overall >= 85 else 'warning',
        },
        {'label': 'Data Sources', 'value': str(source_count), 'status': 'Active', 'tone': 'info'},
        {
            'label': 'Dataset Completeness',
            'value': display_percent(completeness),
            'status': 'Healthy' if completeness >= 90 else 'Attention',
            'tone': 'normal' if completeness >= 90 else 'warning',
        },
        {
            'label': 'Failed Datasets',
            'value': str(failed),
            'status': 'Attention' if failed else 'Healthy',
            'tone': 'critical' if failed else 'normal',
        },
        {
            'label': 'Data Quality Score',
            'value': display_percent(quality_score),
            'status': 'Good' if quality_score >= 85 else 'Attention',
            'tone': 'normal' if quality_score >= 85 else 'warning',
        },
    ]


def _reliability_rows(
    overall: float,
    completeness: float,
    freshness: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            'label': 'Completeness',
            'value': display_percent(completeness),
            'tone': 'normal' if completeness >= 90 else 'warning',
        },
        {
            'label': 'Consistency',
            'value': display_percent(overall),
            'tone': 'normal' if overall >= 85 else 'warning',
        },
        {'label': 'Accuracy', 'value': 'Committed Evidence', 'tone': 'info'},
        {'label': 'Latency', 'value': text(freshness.get('average_latency'), 'Not Available'), 'tone': 'neutral'},
        {
            'label': 'Retention Coverage',
            'value': text(freshness.get('retention_coverage'), 'Policy Managed'),
            'tone': 'info',
        },
    ]


def freshness_svg(freshness: Mapping[str, Any]) -> str:
    raw_history = (
        sequence(freshness.get('history'))
        or sequence(freshness.get('freshness_history'))
        or sequence(freshness.get('trend'))
    )
    values, labels = _freshness_history(raw_history)
    if len(values) < 2:
        return _empty_freshness_svg()
    points = _freshness_points(values)
    point_text = ' '.join(f'{x:.2f},{y:.2f}' for x, y in points)
    first_label = escape(labels[0])
    last_label = escape(labels[-1])
    return (
        '<svg class="ao-chart-svg" viewBox="0 0 640 150" preserveAspectRatio="none" role="img" aria-label="Freshness over time">'
        '<rect x="0" y="0" width="640" height="150" fill="#ffffff"/>'
        '<g stroke="#e5e7eb" stroke-width="1">'
        '<line x1="42" y1="18" x2="606" y2="18"/><line x1="42" y1="67" x2="606" y2="67"/><line x1="42" y1="116" x2="606" y2="116"/>'
        '</g>'
        '<g fill="#64748b" font-size="9" font-family="Inter, Arial"><text x="12" y="21">100%</text><text x="18" y="70">50%</text><text x="24" y="119">0%</text></g>'
        f'<polyline points="{point_text}" fill="none" stroke="#7c3aed" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="4" fill="#7c3aed"/>'
        f'<g fill="#64748b" font-size="9" font-family="Inter, Arial"><text x="42" y="140">{first_label}</text><text x="606" y="140" text-anchor="end">{last_label}</text></g>'
        '</svg>'
    )


def _freshness_history(raw_history: Sequence[Any]) -> tuple[list[float], list[str]]:
    values: list[float] = []
    labels: list[str] = []
    for index, item in enumerate(raw_history[:12]):
        row = mapping(item)
        raw_value = row.get('percent') or row.get('value') or row.get('freshness')
        if raw_value is None:
            continue
        values.append(max(0.0, min(number(raw_value), 100.0)))
        labels.append(text(row.get('label') or row.get('timestamp') or row.get('date'), f'T{index + 1}'))
    return values, labels


def _freshness_points(values: Sequence[float]) -> list[tuple[float, float]]:
    left, right, top, bottom = 42.0, 606.0, 18.0, 116.0
    step = (right - left) / (len(values) - 1)
    return [(left + index * step, bottom - (value / 100.0) * (bottom - top)) for index, value in enumerate(values)]


def _empty_freshness_svg() -> str:
    return (
        '<svg class="ao-chart-svg freshness-empty" viewBox="0 0 640 150" preserveAspectRatio="none" '
        'role="img" aria-label="Freshness history not available">'
        '<rect x="0" y="0" width="640" height="150" fill="#f8fafc"/>'
        '<line x1="36" y1="112" x2="604" y2="112" stroke="#cbd5e1" stroke-width="1"/>'
        '<text x="320" y="68" text-anchor="middle" font-size="13" font-family="Inter, Arial" fill="#475569">Historical freshness trend is not available</text>'
        '<text x="320" y="91" text-anchor="middle" font-size="10" font-family="Inter, Arial" fill="#64748b">Current source freshness remains available in the table below.</text>'
        '</svg>'
    )


def recency_distribution(source_rows_value: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = {'Current': 0, 'Attention': 0, 'Unavailable': 0}
    for row in source_rows_value:
        row_tone = tone(row.get('tone'))
        if row_tone == 'normal':
            counts['Current'] += 1
        elif row_tone in {'warning', 'info'}:
            counts['Attention'] += 1
        else:
            counts['Unavailable'] += 1
    total = sum(counts.values()) or 1
    return [
        {'label': label, 'value': value, 'percent': value / total * 100, 'tone': row_tone}
        for (label, value), row_tone in zip(
            counts.items(),
            ('normal', 'warning', 'critical'),
            strict=False,
        )
    ]


def normalize_quality_issue(item: Any) -> dict[str, Any]:
    row = mapping(item)
    impact = text(row.get('impact'), 'Low')
    issue_status = text(row.get('status'), 'Open')
    return {
        'issue_type': text(row.get('issue_type') or row.get('type'), 'Data Quality Issue'),
        'source': text(row.get('source') or row.get('affected_source'), 'Unknown Source'),
        'count': integer(row.get('count')),
        'impact': impact,
        'impact_tone': tone(impact),
        'status': issue_status,
        'status_tone': tone(issue_status),
    }
