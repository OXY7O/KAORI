from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from app.reports.export.html_pdf.chart_labels import resolve_vertical_labels

from .model import UtilizationState, float_value, forecast_points_percent, percent

_RESOURCE_COLORS = {
    'cpu': '#2563EB',
    'memory': '#7C3AED',
    'pods': '#15803D',
}


def build_utilization_charts(state: UtilizationState) -> dict[str, str]:
    return {
        'cpu': single_resource_chart_svg(
            state.cpu_history,
            projection=forecast_points_percent(state.cpu_forecast),
            color=_RESOURCE_COLORS['cpu'],
            current=state.cpu['percent'],
            projected=state.cpu_projection,
            aria_label='CPU utilization direction',
        ),
        'memory': single_resource_chart_svg(
            state.memory_history,
            projection=forecast_points_percent(state.memory_forecast),
            color=_RESOURCE_COLORS['memory'],
            current=state.memory['percent'],
            projected=state.memory_projection,
            aria_label='Memory utilization direction and projection',
        ),
        'trend': combined_trend_chart_svg(
            {
                'memory': {
                    'history': state.memory_history,
                    'projection': forecast_points_percent(state.memory_forecast),
                    'current': state.memory['percent'],
                    'projected': state.memory_projection,
                },
                'pods': {
                    'history': state.pod_history,
                    'projection': forecast_points_percent(state.pod_forecast),
                    'current': state.pods['percent'],
                    'projected': state.pod_projection,
                },
                'cpu': {
                    'history': state.cpu_history,
                    'projection': forecast_points_percent(state.cpu_forecast),
                    'current': state.cpu['percent'],
                    'projected': state.cpu_projection,
                },
            }
        ),
    }


def _downsample(values: list[float], limit: int = 24) -> list[float]:
    if len(values) <= limit:
        return values
    step = (len(values) - 1) / (limit - 1)
    return [values[round(index * step)] for index in range(limit)]


def single_resource_chart_svg(
    history: list[float],
    *,
    projection: list[float],
    color: str,
    current: float,
    projected: float | None,
    aria_label: str,
) -> str:
    history = _downsample(history)
    projection = _downsample(projection, limit=12)
    if not history:
        return empty_chart_svg('Historical utilization evidence is not available.', aria_label)

    width, height = 720, 250
    left, right, top, bottom = 55, 18, 20, 42
    inner_w = width - left - right
    inner_h = height - top - bottom
    split_x = left + inner_w * (0.66 if projection else 1.0)

    def y(value: float) -> float:
        return top + (100.0 - value) / 100.0 * inner_h

    history_width = split_x - left
    history_points = []
    for index, value in enumerate(history):
        x = left + (index / max(1, len(history) - 1)) * history_width
        history_points.append((x, y(value)))

    projection_points: list[tuple[float, float]] = []
    if projection:
        projection_values = [history[-1], *projection]
        for index, value in enumerate(projection_values):
            x = split_x + (index / max(1, len(projection_values) - 1)) * (left + inner_w - split_x)
            projection_points.append((x, y(value)))

    history_polyline = ' '.join(f'{x:.1f},{yy:.1f}' for x, yy in history_points)
    projection_polyline = ' '.join(f'{x:.1f},{yy:.1f}' for x, yy in projection_points)
    current_x, current_y = history_points[-1]
    end_value = projected if projected is not None else current
    end_x, end_y = projection_points[-1] if projection_points else history_points[-1]

    grid = ''.join(
        f'<line x1="{left}" y1="{y(tick):.1f}" x2="{left + inner_w}" y2="{y(tick):.1f}" class="grid"/>'
        f'<text x="{left - 13}" y="{y(tick) + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>'
        for tick in (0, 50, 70, 85)
    )
    split = (
        f'<line x1="{split_x:.1f}" y1="{top}" x2="{split_x:.1f}" y2="{top + inner_h}" class="split"/>'
        if projection
        else ''
    )
    projection_svg = (
        f'<polyline points="{projection_polyline}" class="projection" style="stroke:{color}"/>'
        if projection_polyline
        else ''
    )
    horizon_label = '<text x="675" y="238" text-anchor="middle" class="axis">Horizon</text>' if projection else ''

    return f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(aria_label)}">
<style>
.grid{{stroke:#E2E8F0;stroke-width:1}}.axis{{font:12px Inter,sans-serif;fill:#64748B}}
.warning-line{{stroke:#D97706;stroke-width:1.2;stroke-dasharray:6 5}}
.critical-line{{stroke:#DC2626;stroke-width:1.2;stroke-dasharray:6 5}}
.history{{fill:none;stroke:{color};stroke-width:4;stroke-linejoin:round;stroke-linecap:round}}
.projection{{fill:none;stroke-width:4;stroke-dasharray:8 6;stroke-linejoin:round;stroke-linecap:round}}
.split{{stroke:#A78BFA;stroke-width:1.2;stroke-dasharray:4 4}}
.label{{font:13px Inter,sans-serif;font-weight:700;fill:#111827}}
</style>{grid}
<line x1="{left}" y1="{y(70):.1f}" x2="{left + inner_w}" y2="{y(70):.1f}" class="warning-line"/>
<line x1="{left}" y1="{y(85):.1f}" x2="{left + inner_w}" y2="{y(85):.1f}" class="critical-line"/>{split}
<polyline points="{history_polyline}" class="history"/>{projection_svg}
<circle cx="{current_x:.1f}" cy="{current_y:.1f}" r="4.5" fill="{color}"/>
<text x="{current_x - 8:.1f}" y="{current_y - 10:.1f}" text-anchor="end" class="label">{percent(current)}</text>
<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" fill="{color}"/>
<text x="{end_x - 5:.1f}" y="{end_y - 10:.1f}" text-anchor="end" class="label">{percent(end_value)}</text>
<text x="{left}" y="238" class="axis">Historical</text>
<text x="{split_x:.1f}" y="238" text-anchor="middle" class="axis">Cut-off</text>{horizon_label}
</svg>'''


def combined_trend_chart_svg(resources: Mapping[str, Mapping[str, Any]]) -> str:
    available = [item for item in resources.values() if item.get('history')]
    if not available:
        return empty_chart_svg('Committed historical trend evidence is not available.', 'Resource trend outlook')

    width, height = 800, 280
    left, right, top, bottom = 58, 92, 20, 45
    inner_w = width - left - right
    inner_h = height - top - bottom
    has_projection = any(item.get('projection') for item in available)
    split_x = left + inner_w * (0.68 if has_projection else 1.0)

    def y(value: float) -> float:
        return top + (100.0 - max(0.0, min(100.0, value))) / 100.0 * inner_h

    grid = ''.join(
        f'<line x1="{left}" y1="{y(tick):.1f}" x2="{left + inner_w}" y2="{y(tick):.1f}" class="grid"/>'
        f'<text x="{left - 14}" y="{y(tick) + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>'
        for tick in (0, 25, 50, 70, 85)
    )
    lines: list[str] = []
    endpoint_labels: list[tuple[str, float]] = []
    endpoint_meta: dict[str, tuple[float, str, float]] = {}
    for key in ('memory', 'pods', 'cpu'):
        item = resources.get(key) or {}
        history = _downsample(list(item.get('history') or []))
        if not history:
            continue
        color = _RESOURCE_COLORS[key]
        history_points = []
        for index, value in enumerate(history):
            x = left + (index / max(1, len(history) - 1)) * (split_x - left)
            history_points.append((x, y(value)))
        lines.append(
            f'<polyline points="{" ".join(f"{x:.1f},{yy:.1f}" for x, yy in history_points)}" '
            f'fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        projection = _downsample(list(item.get('projection') or []), limit=12)
        end_x, end_y = history_points[-1]
        end_value = float_value(item.get('current'))
        if projection:
            projection_values = [history[-1], *projection]
            projection_points = []
            for index, value in enumerate(projection_values):
                x = split_x + (index / max(1, len(projection_values) - 1)) * (left + inner_w - split_x)
                projection_points.append((x, y(value)))
            lines.append(
                f'<polyline points="{" ".join(f"{x:.1f},{yy:.1f}" for x, yy in projection_points)}" '
                f'fill="none" stroke="{color}" stroke-width="4" stroke-dasharray="8 6" '
                'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            end_x, end_y = projection_points[-1]
            end_value = float_value(item.get('projected'), default=projection[-1])
        endpoint_labels.append((key, end_y))
        endpoint_meta[key] = (end_x, color, end_value)

    resolved_labels = resolve_vertical_labels(
        endpoint_labels,
        min_y=top + 7,
        max_y=top + inner_h - 5,
        min_gap=17,
    )
    point_y = dict(endpoint_labels)
    label_parts: list[str] = []
    label_x = width - 70
    for key, label_y in resolved_labels.items():
        end_x, color, end_value = endpoint_meta[key]
        label_parts.append(
            f'<path d="M {end_x + 3:.1f} {point_y[key]:.1f} L {label_x - 7:.1f} {label_y:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1" opacity=".75"/>'
        )
        label_parts.append(
            f'<text x="{label_x:.1f}" y="{label_y + 4:.1f}" '
            f'style="font:12px Inter,sans-serif;font-weight:700;fill:{color}">{key.title()} {percent(end_value)}</text>'
        )
    label_svg = ''.join(label_parts)

    split = (
        f'<line x1="{split_x:.1f}" y1="{top}" x2="{split_x:.1f}" '
        f'y2="{top + inner_h}" stroke="#A78BFA" stroke-width="1.2" '
        'stroke-dasharray="4 4"/>'
        if has_projection
        else ''
    )
    return f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="Resource trend outlook">
<style>.grid{{stroke:#E2E8F0;stroke-width:1}}.axis{{font:12px Inter,sans-serif;fill:#64748B}}</style>{grid}
<line x1="{left}" y1="{y(70):.1f}" x2="{left + inner_w}"
 y2="{y(70):.1f}" stroke="#D97706" stroke-width="1.2" stroke-dasharray="6 5"/>
<line x1="{left}" y1="{y(85):.1f}" x2="{left + inner_w}"
 y2="{y(85):.1f}" stroke="#DC2626" stroke-width="1.2" stroke-dasharray="6 5"/>{split}
{''.join(lines)}{label_svg}
<text x="{left}" y="266" class="axis">Historical Start</text>
<text x="{split_x:.1f}" y="266" text-anchor="middle" class="axis">Cut-off</text>
<text x="{left + inner_w}" y="266" text-anchor="end" class="axis">{'Horizon' if has_projection else 'Latest'}</text>
</svg>'''


def empty_chart_svg(message: str, aria_label: str) -> str:
    return f'''<svg viewBox="0 0 720 250" role="img" aria-label="{escape(aria_label)}">
<rect x="1" y="1" width="718" height="248" fill="#F8FAFC" stroke="#E2E8F0"/>
<text x="360" y="118" text-anchor="middle"
 style="font:700 15px Inter,sans-serif;fill:#475569">Trend Evidence Not Available</text>
<text x="360" y="143" text-anchor="middle" style="font:12px Inter,sans-serif;fill:#64748B">{escape(message)}</text>
</svg>'''


def participation_donut_svg(value: float, ready_nodes: int) -> str:
    value = max(0.0, min(float_value(value), 100.0))
    circumference = 2 * 3.141592653589793 * 52
    if value <= 0:
        progress = ''
    elif value >= 100:
        progress = '<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" stroke-width="20"/>'
    else:
        length = value / 100 * circumference
        progress = (
            f'<circle cx="78" cy="78" r="52" fill="none" stroke="#15803D" '
            f'stroke-width="20" stroke-linecap="butt" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            'transform="rotate(-90 78 78)"/>'
        )
    return f"""<svg viewBox="0 0 156 156" role="img" aria-label="Node participation {value:.0f} percent">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="20"/>{progress}
<text x="78" y="76" text-anchor="middle" font-family="Inter, sans-serif"
 font-size="28" font-weight="700" fill="#1E293B">{ready_nodes}</text>
<text x="78" y="96" text-anchor="middle" font-family="Inter, sans-serif"
 font-size="12" fill="#475569">Ready Nodes</text></svg>"""


def donut_svg(items: list[dict[str, Any]]) -> str:
    total = sum(item['raw_value'] for item in items)
    if total <= 0:
        return _empty_donut_svg()
    colors = ('#7C3AED', '#9B7AF5', '#B8A8FF')
    circumference = 2 * 3.141592653589793 * 52
    offset = 0.0
    circles: list[str] = []
    for index, item in enumerate(items):
        length = item['raw_value'] / total * circumference
        circles.append(
            f'<circle cx="78" cy="78" r="52" fill="none" stroke="{colors[index % len(colors)]}" '
            f'stroke-width="20" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 78 78)"/>'
        )
        offset += length
    return f"""<svg viewBox="0 0 156 156" role="img" aria-label="Displayed memory concentration">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="20"/>{''.join(circles)}<text x="78" y="78" text-anchor="middle" font-family="Inter, sans-serif" font-size="22" font-weight="700" fill="#1E293B">{total:.2f}</text><text x="78" y="96" text-anchor="middle" font-family="Inter, sans-serif" font-size="10" fill="#475569">GiB displayed</text></svg>"""


def _empty_donut_svg() -> str:
    return """<svg viewBox="0 0 156 156" role="img" aria-label="Displayed memory concentration unavailable">
<circle cx="78" cy="78" r="52" fill="none" stroke="#E2E8F0" stroke-width="20"/>
<text x="78" y="82" text-anchor="middle" style="font:700 12px Inter,sans-serif;fill:#64748B">N/A</text></svg>"""
