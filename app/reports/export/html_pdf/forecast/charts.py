from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from app.reports.export.html_pdf.chart_labels import resolve_vertical_labels


def combined_chart_svg(resources: Mapping[str, Mapping[str, Any]]) -> str:
    width, height = 800, 238
    left, top, chart_w, chart_h = 58.0, 24.0, 520.0, 160.0
    label_line_x = 626.0
    label_x = width - 18.0
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-label="Forecast portfolio chart">'
        ),
        '<rect width="800" height="238" fill="#F8FAFC"/>',
    ]
    for value in (0, 25, 50, 75, 90):
        y = top + chart_h - chart_h * value / 100.0
        dash = ' stroke-dasharray="5 5"' if value in {75, 90} else ''
        color = '#D97706' if value == 75 else '#DC2626' if value == 90 else '#E2E8F0'
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_w}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="1"{dash}/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="10" '
            f'fill="#64748B">{value}%</text>'
        )
    cutoff_x = left + chart_w * 0.68
    parts.append(
        f'<line x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{top + chart_h}" '
        'stroke="#A78BFA" stroke-dasharray="4 4"/>'
    )

    endpoint_labels: list[tuple[str, float]] = []
    endpoint_meta: dict[str, tuple[float, str, str]] = {}
    for key in ('memory', 'pods', 'cpu', 'storage'):
        resource = resources[key]
        if not resource['available']:
            continue
        history = resource['history'] or [resource['current_percent']]
        projection = resource['projection'] or [resource['projected_percent']]
        hist_points = series_points(history, left, cutoff_x, top, chart_h)
        proj_values = [resource['current_percent'], *projection]
        proj_points = series_points(proj_values, cutoff_x, left + chart_w, top, chart_h)
        color = resource['color']
        if hist_points:
            parts.append(
                f'<polyline points="{hist_points}" fill="none" stroke="{color}" stroke-width="3" '
                'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        if proj_points:
            parts.append(
                f'<polyline points="{proj_points}" fill="none" stroke="{color}" stroke-width="3" '
                'stroke-dasharray="8 6" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        end_y = top + chart_h - chart_h * resource['projected_percent'] / 100.0
        end_x = left + chart_w
        parts.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="{color}"/>')
        endpoint_labels.append((key, end_y))
        endpoint_meta[key] = (end_x, color, f'{resource["label"]} {resource["projected_display"]}')

    resolved = resolve_vertical_labels(
        endpoint_labels,
        min_y=top + 7,
        max_y=top + chart_h - 4,
        min_gap=17,
    )
    data_y_by_key = dict(endpoint_labels)
    for key, label_y in resolved.items():
        end_x, color, text = endpoint_meta[key]
        data_y = data_y_by_key[key]
        parts.append(
            f'<path d="M {end_x + 3:.1f} {data_y:.1f} L {label_line_x:.1f} {label_y:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1" opacity=".75"/>'
        )
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y + 4:.1f}" text-anchor="end" font-size="10.5" '
            f'font-weight="700" fill="{color}">{escape(text)}</text>'
        )

    parts.extend(
        [
            f'<text x="{left}" y="{top + chart_h + 24}" font-size="10" fill="#64748B">Historical Start</text>',
            (
                f'<text x="{cutoff_x}" y="{top + chart_h + 24}" text-anchor="middle" font-size="10" '
                'fill="#64748B">Cut-off</text>'
            ),
            (
                f'<text x="{left + chart_w}" y="{top + chart_h + 24}" text-anchor="end" '
                'font-size="10" fill="#64748B">Horizon</text>'
            ),
            '</svg>',
        ]
    )
    return ''.join(parts)


def single_chart_svg(
    *,
    label: str,
    color: str,
    history: list[float],
    projection: list[float],
    current: float | None,
    projected: float | None,
    empty_reason: str,
) -> str:
    if current is None or projected is None:
        return empty_chart_svg(f'{label} forecast unavailable', empty_reason)
    width, height = 620, 250
    left, top, chart_w, chart_h = 58.0, 28.0, 520.0, 160.0
    cutoff_x = left + chart_w * 0.68
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{escape(label)} forecast chart">'
        ),
        '<rect width="620" height="250" fill="#F8FAFC"/>',
    ]
    for value in (0, 25, 50, 75, 90):
        y = top + chart_h - chart_h * value / 100.0
        dash = ' stroke-dasharray="5 5"' if value in {75, 90} else ''
        grid = '#D97706' if value == 75 else '#DC2626' if value == 90 else '#E2E8F0'
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_w}" y2="{y:.1f}" '
            f'stroke="{grid}" stroke-width="1"{dash}/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="10" '
            f'fill="#64748B">{value}%</text>'
        )
    parts.append(
        f'<line x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{top + chart_h}" '
        'stroke="#A78BFA" stroke-dasharray="4 4"/>'
    )
    hist_values = history or [current]
    proj_values = [current, *(projection or [projected])]
    parts.append(
        f'<polyline points="{series_points(hist_values, left, cutoff_x, top, chart_h)}" '
        f'fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    parts.append(
        f'<polyline points="{series_points(proj_values, cutoff_x, left + chart_w, top, chart_h)}" '
        f'fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="8 6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    current_y = top + chart_h - chart_h * current / 100.0
    projected_y = top + chart_h - chart_h * projected / 100.0
    parts.append(f'<circle cx="{cutoff_x:.1f}" cy="{current_y:.1f}" r="4" fill="{color}"/>')
    parts.append(f'<circle cx="{left + chart_w:.1f}" cy="{projected_y:.1f}" r="4" fill="{color}"/>')
    parts.append(
        f'<text x="{cutoff_x - 8:.1f}" y="{current_y - 8:.1f}" text-anchor="end" font-size="11" '
        f'font-weight="700" fill="#0F172A">{current:.1f}%</text>'
    )
    parts.append(
        f'<text x="{left + chart_w - 6:.1f}" y="{projected_y - 8:.1f}" text-anchor="end" '
        f'font-size="11" font-weight="700" fill="{color}">{projected:.1f}%</text>'
    )
    parts.extend(
        [
            f'<text x="{left}" y="{top + chart_h + 24}" font-size="10" fill="#64748B">Historical</text>',
            (
                f'<text x="{cutoff_x}" y="{top + chart_h + 24}" text-anchor="middle" font-size="10" '
                'fill="#64748B">Cut-off</text>'
            ),
            (
                f'<text x="{left + chart_w}" y="{top + chart_h + 24}" text-anchor="end" '
                'font-size="10" fill="#64748B">Horizon</text>'
            ),
            '</svg>',
        ]
    )
    return ''.join(parts)


def empty_chart_svg(title: str, message: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 250" role="img" '
        f'aria-label="{escape(title)}">'
        '<rect width="620" height="250" fill="#F8FAFC"/>'
        f'<text x="310" y="112" text-anchor="middle" font-size="17" font-weight="700" '
        f'fill="#0F172A">{escape(title)}</text>'
        f'<text x="310" y="140" text-anchor="middle" font-size="11" '
        f'fill="#64748B">{escape(message[:100])}</text>'
        '</svg>'
    )


def series_points(values: list[float], start_x: float, end_x: float, top: float, chart_h: float) -> str:
    if not values:
        return ''
    if len(values) == 1:
        values = [values[0], values[0]]
    step = (end_x - start_x) / max(len(values) - 1, 1)
    return ' '.join(
        (
            f'{start_x + index * step:.1f},'
            f'{top + chart_h - chart_h * max(0.0, min(100.0, value)) / 100.0:.1f}'
        )
        for index, value in enumerate(values)
    )
