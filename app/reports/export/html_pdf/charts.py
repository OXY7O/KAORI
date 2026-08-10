from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_SERIES_COLORS = ('#7C3AED', '#2563EB', '#15803D', '#B45309', '#B91C1C', '#64748B')


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def build_forecast_chart(payload: Mapping[str, Any]) -> str:
    forecast_payload = payload.get('forecast_payload')
    if not isinstance(forecast_payload, Mapping):
        return ''

    items = forecast_payload.get('items')
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        return ''

    series: list[tuple[str, float, float]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        current = _safe_float(item.get('current_percent'))
        projected = _safe_float(item.get('projected_percent'))
        if current is None or projected is None:
            continue
        series.append((sanitize_text(item.get('label') or item.get('key')), current, projected))

    if not series:
        return ''

    width = 680
    height = 260
    left = 58
    right = 28
    top = 30
    bottom = 42
    chart_width = width - left - right
    chart_height = height - top - bottom
    current_x = left + chart_width * 0.22
    projected_x = left + chart_width * 0.78

    max_value = max(100.0, max(max(current, projected) for _, current, projected in series))
    max_value = math.ceil(max_value / 10.0) * 10.0

    def y(value: float) -> float:
        bounded = max(0.0, min(value, max_value))
        return top + chart_height - (bounded / max_value) * chart_height

    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="report-chart" role="img" '
        'aria-label="Current and projected resource utilization">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
    ]

    for tick in range(0, int(max_value) + 1, 20):
        tick_y = y(float(tick))
        parts.append(
            f'<line x1="{left}" y1="{tick_y:.1f}" x2="{width - right}" y2="{tick_y:.1f}" '
            'stroke="#E7E2EE" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 9}" y="{tick_y + 4:.1f}" text-anchor="end" font-size="10" fill="#6B7280">{tick}%</text>'
        )

    for threshold, color, label in ((75, '#B45309', 'Warning'), (90, '#B91C1C', 'Critical')):
        if threshold <= max_value:
            threshold_y = y(float(threshold))
            parts.append(
                f'<line x1="{left}" y1="{threshold_y:.1f}" x2="{width - right}" y2="{threshold_y:.1f}" '
                f'stroke="{color}" stroke-width="1.4" stroke-dasharray="5 5"/>'
            )
            parts.append(
                f'<text x="{width - right}" y="{threshold_y - 5:.1f}" text-anchor="end" font-size="9" '
                f'fill="{color}">{label} {threshold}%</text>'
            )

    for index, (label, current, projected) in enumerate(series[:6]):
        color = _SERIES_COLORS[index % len(_SERIES_COLORS)]
        current_y = y(current)
        projected_y = y(projected)
        parts.extend(
            [
                f'<line x1="{current_x:.1f}" y1="{current_y:.1f}" x2="{projected_x:.1f}" '
                f'y2="{projected_y:.1f}" stroke="{color}" stroke-width="3" stroke-linecap="round"/>',
                f'<circle cx="{current_x:.1f}" cy="{current_y:.1f}" r="4" fill="#FFFFFF" '
                f'stroke="{color}" stroke-width="3"/>',
                f'<circle cx="{projected_x:.1f}" cy="{projected_y:.1f}" r="4" fill="{color}"/>',
                f'<text x="{projected_x + 9:.1f}" y="{projected_y + 4:.1f}" font-size="10" fill="{color}">'
                f'{html.escape(label)} {projected:.1f}%</text>',
            ]
        )

    parts.extend(
        [
            f'<text x="{current_x:.1f}" y="{height - 16}" text-anchor="middle" font-size="11" '
            'font-weight="700" fill="#1F2937">Current</text>',
            f'<text x="{projected_x:.1f}" y="{height - 16}" text-anchor="middle" font-size="11" '
            'font-weight="700" fill="#1F2937">Projected</text>',
            '</svg>',
        ]
    )
    return ''.join(parts)


def build_alert_severity_chart(payload: Mapping[str, Any]) -> str:
    alerts = payload.get('alerts')
    if not isinstance(alerts, Sequence) or isinstance(alerts, (str, bytes, bytearray)):
        return ''

    counts = {'Critical': 0, 'Warning': 0, 'Info': 0, 'Unknown': 0}
    for item in alerts:
        if not isinstance(item, Mapping):
            continue
        severity = sanitize_text(item.get('severity'), fallback='Unknown').lower()
        if severity in {'critical', 'error', 'high'}:
            counts['Critical'] += 1
        elif severity in {'warning', 'warn', 'medium'}:
            counts['Warning'] += 1
        elif severity in {'info', 'information', 'low'}:
            counts['Info'] += 1
        else:
            counts['Unknown'] += 1

    total = sum(counts.values())
    if total == 0:
        return ''

    width = 560
    height = 220
    center_x = 122
    center_y = 108
    radius = 70
    circumference = 2 * math.pi * radius
    palette = {'Critical': '#B91C1C', 'Warning': '#B45309', 'Info': '#2563EB', 'Unknown': '#64748B'}

    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="report-chart" role="img" '
        'aria-label="Alert severity distribution">',
        f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="none" stroke="#EEEAF3" stroke-width="24"/>',
    ]
    offset = 0.0
    for label in ('Critical', 'Warning', 'Info', 'Unknown'):
        count = counts[label]
        if count <= 0:
            continue
        length = circumference * count / total
        parts.append(
            f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="none" '
            f'stroke="{palette[label]}" stroke-width="24" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {center_x} {center_y})"/>'
        )
        offset += length

    parts.extend(
        [
            f'<text x="{center_x}" y="{center_y - 3}" text-anchor="middle" font-size="11" fill="#6B7280">Alerts</text>',
            f'<text x="{center_x}" y="{center_y + 25}" text-anchor="middle" font-size="27" '
            f'font-weight="700" fill="#1F2937">{total}</text>',
        ]
    )

    legend_x = 275
    legend_y = 48
    for index, label in enumerate(('Critical', 'Warning', 'Info', 'Unknown')):
        y = legend_y + index * 35
        parts.append(f'<circle cx="{legend_x}" cy="{y}" r="5" fill="{palette[label]}"/>')
        parts.append(
            f'<text x="{legend_x + 14}" y="{y + 4}" font-size="11" fill="#1F2937">{label}: {counts[label]}</text>'
        )

    parts.append('</svg>')
    return ''.join(parts)
