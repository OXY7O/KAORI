from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from app.reports.export.html_pdf.chart_labels import resolve_vertical_labels

from .forecast import forecast_points_percent, history_percent
from .model import mapping, number_float

RESOURCE_COLORS = {
    'cpu': '#2563EB',
    'memory': '#7C3AED',
    'pods': '#15803D',
}


def build_capacity_forecast_chart_svg(
    *,
    resources: Mapping[str, Mapping[str, Any]],
    forecast_items: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, float | None],
) -> str:
    if not any(value is not None for value in projections.values()):
        return empty_chart_svg(
            'Committed forecast evidence was not available at the report cut-off.',
            'Capacity forecast unavailable',
        )

    width, height = 760, 250
    left, right, top, bottom = 58, 165, 22, 40
    inner_w = width - left - right
    inner_h = height - top - bottom
    split_x = left + inner_w * 0.68

    def point(value: float, x: float) -> tuple[float, float]:
        return x, top + inner_h * (1 - min(max(value, 0.0), 100.0) / 100.0)

    svg: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Capacity projection outlook">',
        '<style>.axis{font:11px Inter,sans-serif;fill:#64748B}</style>',
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" fill="#FFFFFF" stroke="#E2E8F0"/>',
    ]
    for tick in (0, 25, 50, 70, 85):
        y = point(tick, left)[1]
        svg.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + inner_w}" y2="{y:.1f}" stroke="#E2E8F0"/>'
        )
        svg.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>'
        )
    for threshold, color in ((70, '#D97706'), (85, '#DC2626')):
        y = point(threshold, left)[1]
        svg.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + inner_w}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-dasharray="5 5"/>'
        )
    svg.append(
        f'<line x1="{split_x:.1f}" y1="{top}" x2="{split_x:.1f}" y2="{top + inner_h}" '
        'stroke="#A78BFA" stroke-dasharray="4 4"/>'
    )

    endpoint_labels: list[tuple[str, float]] = []
    endpoint_meta: dict[str, tuple[float, str, float]] = {}
    for key in ('memory', 'pods', 'cpu'):
        item = mapping(forecast_items.get(key))
        history = history_percent(item)
        projection_points = forecast_points_percent(item)
        current = number_float(resources[key].get('used_percent'))
        projected = projections[key]
        if not history:
            history = [current, current]
        history = history[-12:]
        history_xs = [
            left + (split_x - left) * index / max(len(history) - 1, 1)
            for index in range(len(history))
        ]
        history_points = [point(value, x) for x, value in zip(history_xs, history)]
        color = RESOURCE_COLORS[key]
        svg.append(
            f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in history_points)}" '
            f'fill="none" stroke="{color}" stroke-width="3"/>'
        )
        if projected is not None:
            future_values = projection_points or [projected]
            future_values = future_values[-8:]
            future_xs = [
                split_x + (left + inner_w - split_x) * (index + 1) / len(future_values)
                for index in range(len(future_values))
            ]
            future_points = [point(value, x) for x, value in zip(future_xs, future_values)]
            start_point = point(current, split_x)
            svg.append(
                f'<polyline points="{start_point[0]:.1f},{start_point[1]:.1f} '
                f'{" ".join(f"{x:.1f},{y:.1f}" for x, y in future_points)}" '
                f'fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="8 6"/>'
            )
            end_x, end_y = future_points[-1]
            svg.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="{color}"/>')
            endpoint_labels.append((key, end_y))
            endpoint_meta[key] = (end_x, color, projected)

    resolved_labels = resolve_vertical_labels(
        endpoint_labels,
        min_y=top + 7,
        max_y=top + inner_h - 5,
        min_gap=17,
    )
    point_y = dict(endpoint_labels)
    label_line_x = width - 166
    label_x = width - 18
    for key, label_y in resolved_labels.items():
        end_x, color, projected = endpoint_meta[key]
        svg.append(
            f'<path d="M {end_x + 3:.1f} {point_y[key]:.1f} L {label_line_x:.1f} {label_y:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1" opacity=".75"/>'
        )
        svg.append(
            f'<text x="{label_x:.1f}" y="{label_y + 4:.1f}" text-anchor="end" '
            f'style="font:11px Inter,sans-serif;font-weight:700;fill:{color}">'
            f'{key.title()} {projected:.1f}%</text>'
        )

    svg.extend(
        [
            f'<text x="{left}" y="{height - 15}" class="axis">Historical Start</text>',
            f'<text x="{split_x:.1f}" y="{height - 15}" text-anchor="middle" class="axis">Cut-off</text>',
            f'<text x="{left + inner_w}" y="{height - 15}" text-anchor="end" class="axis">Horizon</text>',
            '</svg>',
        ]
    )
    return ''.join(svg)


def empty_chart_svg(message: str, aria_label: str) -> str:
    return f'''<svg viewBox="0 0 720 250" role="img" aria-label="{escape(aria_label)}">
<rect x="1" y="1" width="718" height="248" fill="#F8FAFC" stroke="#E2E8F0"/>
<text x="360" y="118" text-anchor="middle" style="font:700 15px Inter,sans-serif;fill:#475569">Forecast Evidence Not Available</text>
<text x="360" y="143" text-anchor="middle" style="font:12px Inter,sans-serif;fill:#64748B">{escape(message)}</text>
</svg>'''


def build_participation_donut_svg(percent: float, ready_nodes: int, total_nodes: int) -> str:
    value = max(0.0, min(percent, 100.0))
    circumference = 2 * 3.141592653589793 * 52
    if value <= 0:
        progress = ''
    elif value >= 100:
        progress = '<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" stroke-width="18"/>'
    else:
        length = value / 100 * circumference
        progress = (
            f'<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" '
            f'stroke-width="18" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            'transform="rotate(-90 78 78)"/>'
        )
    label = f'{ready_nodes} / {total_nodes}' if total_nodes else 'N/A'
    return f'''<svg viewBox="0 0 156 156" role="img" aria-label="Node participation {value:.0f} percent">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="18"/>{progress}
<text x="78" y="75" text-anchor="middle" font-family="Inter, sans-serif" font-size="22" font-weight="700" fill="#1E293B">{escape(label)}</text>
<text x="78" y="94" text-anchor="middle" font-family="Inter, sans-serif" font-size="10" fill="#475569">Ready Nodes</text></svg>'''
