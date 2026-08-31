from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import integer, number, sequence, text, tone


def alerts(alert_detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(sequence(alert_detail.get('alerts'))[:10], start=1):
        if not isinstance(item, Mapping):
            continue
        severity = text(item.get('severity') or item.get('severity_label'), 'Info')
        resource = text(
            item.get('affected_resource') or item.get('resource_name') or item.get('resource') or item.get('instance'),
            'Not Available',
        )
        rows.append(
            {
                'rank': index,
                'severity': severity,
                'tone': tone(severity),
                'name': text(item.get('alertname') or item.get('name') or item.get('title'), 'Unnamed Alert'),
                'resource': resource,
                'namespace': text(item.get('namespace'), 'Cluster Scoped'),
                'since': text(
                    item.get('duration') or item.get('active_for') or item.get('starts_at'),
                    'Not Available',
                ),
                'status': text(item.get('status'), 'Active'),
            }
        )
    return rows


def anomalies(alert_detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(sequence(alert_detail.get('anomalies'))[:8], start=1):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'rank': index,
                'name': text(
                    item.get('name') or item.get('title') or item.get('anomaly_type'),
                    'Unnamed Anomaly',
                ),
                'namespace': text(item.get('namespace'), 'Cluster Scoped'),
                'detected_at': text(
                    item.get('detected_at') or item.get('starts_at') or item.get('timestamp'),
                    'Not Available',
                ),
                'tone': tone(item.get('severity') or item.get('status')),
            }
        )
    return rows


def alert_metrics(
    alerts_snapshot: Mapping[str, Any],
    alert_detail: Mapping[str, Any],
) -> list[dict[str, Any]]:
    summary = alert_detail.get('summary') if isinstance(alert_detail.get('summary'), Mapping) else {}
    critical = integer(
        summary.get('critical') or summary.get('critical_alerts') or alerts_snapshot.get('critical_alerts')
    )
    warning = integer(summary.get('warning') or summary.get('warning_alerts') or alerts_snapshot.get('warning_alerts'))
    info = integer(summary.get('info') or summary.get('info_alerts'))
    anomaly_count = integer(summary.get('anomalies') or alerts_snapshot.get('recent_anomalies'))
    return [
        {
            'label': 'Critical Alerts',
            'value': str(critical),
            'status': 'Requires Immediate Action' if critical else 'Clear',
            'tone': 'critical' if critical else 'normal',
        },
        {
            'label': 'Warning Alerts',
            'value': str(warning),
            'status': 'Requires Attention' if warning else 'Clear',
            'tone': 'warning' if warning else 'normal',
        },
        {'label': 'Info Alerts', 'value': str(info), 'status': 'Informational', 'tone': 'info'},
        {
            'label': 'Anomalies Detected',
            'value': str(anomaly_count),
            'status': 'Unusual Patterns' if anomaly_count else 'None Detected',
            'tone': 'info' if anomaly_count else 'normal',
        },
    ]


def alert_severity_svg(alerts_snapshot: Mapping[str, Any], alert_detail: Mapping[str, Any]) -> str:
    metrics = alert_metrics(alerts_snapshot, alert_detail)
    labels = ('Critical', 'Warning', 'Info')
    colors = ('#DC2626', '#D97706', '#2563EB')
    values = [max(0.0, number(metric['value'])) for metric in metrics[:3]]
    total = sum(values)
    radius = 46.0
    circumference = 2 * 3.141592653589793 * radius
    segments = _severity_segments(values, colors, total, circumference)
    legend = _severity_legend(labels, values, colors)
    centre_caption = 'Active Alerts' if total else 'No Active Alerts'
    return (
        '<svg class="ao-chart-svg ao-alert-donut" viewBox="0 0 350 155" role="img" '
        'aria-label="Alert severity distribution">'
        '<circle cx="108" cy="76" r="46" fill="none" stroke="#E5E7EB" stroke-width="18"/>'
        + ''.join(segments)
        + f'<text x="108" y="74" text-anchor="middle" class="donut-total">{int(total)}</text>'
        + f'<text x="108" y="146" text-anchor="middle" class="donut-caption donut-caption-below">{centre_caption}</text>'
        + ''.join(legend)
        + '</svg>'
    )


def _severity_segments(
    values: Sequence[float],
    colors: Sequence[str],
    total: float,
    circumference: float,
) -> list[str]:
    if total <= 0:
        return []
    cumulative = 0.0
    segments: list[str] = []
    for value, color in zip(values, colors, strict=False):
        if value <= 0:
            continue
        length = circumference * (value / total)
        offset = -circumference * (cumulative / total)
        segments.append(
            '<circle cx="108" cy="76" r="46" fill="none" '
            f'stroke="{color}" stroke-width="18" stroke-linecap="butt" '
            f'stroke-dasharray="{length:.3f} {circumference - length:.3f}" '
            f'stroke-dashoffset="{offset:.3f}" transform="rotate(-90 108 76)"/>'
        )
        cumulative += value
    return segments


def _severity_legend(
    labels: Sequence[str],
    values: Sequence[float],
    colors: Sequence[str],
) -> list[str]:
    legend: list[str] = []
    for index, (label, value, color) in enumerate(zip(labels, values, colors, strict=False)):
        y = 43 + index * 29
        legend.append(
            f'<rect x="204" y="{y - 5}" width="10" height="10" rx="2" fill="{color}"/>'
            f'<text x="224" y="{y}" class="donut-legend-label">{label}</text>'
            f'<text x="330" y="{y}" text-anchor="end" class="donut-legend-value">{int(value)}</text>'
        )
    return legend


def alert_category_mix(alert_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in alert_rows:
        category = _alert_category(text(item.get('name'), '').lower())
        counts[category] = counts.get(category, 0) + 1
    if not counts:
        counts = {'No Active Alert Detail': 0}
    total = sum(counts.values()) or 1
    return [
        {'label': label, 'value': value, 'percent': (value / total) * 100}
        for label, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _alert_category(name: str) -> str:
    if any(token in name for token in ('memory', 'cpu', 'storage', 'pvc', 'disk')):
        return 'Capacity'
    if any(token in name for token in ('ready', 'down', 'unavailable')):
        return 'Availability'
    if any(token in name for token in ('config', 'secret', 'certificate')):
        return 'Configuration'
    return 'Resource'


def alert_intelligence_summary(
    alerts_snapshot: Mapping[str, Any],
    alert_rows: Sequence[Mapping[str, Any]],
) -> str:
    critical = integer(alerts_snapshot.get('critical_alerts'))
    warning = integer(alerts_snapshot.get('warning_alerts'))
    if critical or warning:
        return f'{critical} critical and {warning} warning alert(s) require operational ownership and response validation.'
    if alert_rows:
        return 'Active alert details are available, but no critical or warning total was reported.'
    return 'No active alert detail was returned for the selected reporting boundary.'


def alert_next_steps(
    recommendations: Sequence[Mapping[str, Any]],
    alert_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    related = [item for item in recommendations if 'alert' in text(item.get('source'), '').lower()]
    items: Sequence[Mapping[str, Any]] = related[:4]
    if not items and alert_rows:
        items = [
            {
                'title': f'Review {text(item.get("name"))}',
                'description': f'Confirm owner and response status for {text(item.get("resource"))}.',
                'tone': tone(item.get('tone')),
            }
            for item in alert_rows[:4]
        ]
    return [
        {
            'title': text(item.get('title')),
            'description': text(item.get('description'), ''),
            'tone': tone(item.get('tone')),
        }
        for item in items
    ]
