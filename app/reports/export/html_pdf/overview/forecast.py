from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from .common import display_percent, mapping, number, sequence, text


def forecast_series(forecast_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_series = sequence(forecast_snapshot.get('series'))
    if not raw_series:
        return []

    if any(isinstance(item, Mapping) and item.get('key') for item in raw_series):
        result: list[dict[str, Any]] = []
        for item in raw_series:
            if not isinstance(item, Mapping):
                continue
            result.append(
                {
                    'key': text(item.get('key'), '').lower(),
                    'label': text(item.get('label'), 'Resource'),
                    'historical_points': text(item.get('historical_points'), ''),
                    'forecast_points': text(item.get('forecast_points'), ''),
                    'latest_percent': number(item.get('latest_percent')),
                    'projected_percent': number(item.get('projected_percent')),
                    'confidence': text(item.get('confidence'), 'Not Available'),
                    'trend': text(item.get('trend'), 'Unknown'),
                }
            )
        return result

    points = [item for item in raw_series if isinstance(item, Mapping)]
    if not points:
        return []
    historical_values = [
        number(item.get('value'))
        for item in points
        if str(item.get('kind') or '').lower() == 'historical'
    ]
    forecast_values = [
        number(item.get('value'))
        for item in points
        if str(item.get('kind') or '').lower() == 'forecast'
    ]
    all_values = historical_values + forecast_values
    if not all_values:
        return []

    historical_points = _chart_points(historical_values, 0.0, 54.0)
    forecast_points = _chart_points(forecast_values, 54.0, 100.0)
    latest = historical_values[-1] if historical_values else all_values[0]
    projected = forecast_values[-1] if forecast_values else latest
    return [
        {
            'key': 'memory',
            'label': 'Memory',
            'historical_points': historical_points,
            'forecast_points': forecast_points,
            'latest_percent': latest,
            'projected_percent': projected,
            'confidence': 'Not Available',
            'trend': 'Increasing' if projected > latest else 'Stable',
        }
    ]


def _chart_points(values: Sequence[float], start: float, end: float) -> str:
    if not values:
        return ''
    if len(values) == 1:
        xs = [start]
    else:
        step = (end - start) / (len(values) - 1)
        xs = [start + index * step for index in range(len(values))]
    return ' '.join(
        f'{x:.2f},{100.0 - max(0.0, min(value, 100.0)):.2f}'
        for x, value in zip(xs, values, strict=False)
    )


def forecast_headline(forecast_snapshot: Mapping[str, Any]) -> str:
    resource = text(forecast_snapshot.get('highest_projected_resource'), 'No resource')
    value = forecast_snapshot.get('highest_projected_percent')
    nearest = mapping(forecast_snapshot.get('nearest_critical')) or mapping(
        forecast_snapshot.get('nearest_warning')
    )
    eta = text(nearest.get('label'), '')
    if value is None:
        return 'No forecast threshold breach is currently projected.'
    suffix = f' within {eta}' if eta and eta.lower() != 'not projected' else ''
    return f'{resource} is the highest projected resource at {display_percent(number(value))}{suffix}.'


def forecast_svg(series: Sequence[Mapping[str, Any]]) -> str:
    selected = next((item for item in series if str(item.get('key')) == 'memory'), None)
    if selected is None and series:
        selected = series[0]
    if selected is None:
        return _empty_chart_svg('Forecast series is not available')

    label = escape(text(selected.get('label'), 'Resource'))
    historical = _scaled_chart_points(text(selected.get('historical_points'), ''))
    forecast = _scaled_chart_points(text(selected.get('forecast_points'), ''))
    projected = max(0.0, min(number(selected.get('projected_percent')), 100.0))
    latest = max(0.0, min(number(selected.get('latest_percent')), 100.0))
    forecast_start_x = _forecast_start_x(forecast)
    historical_line = _polyline(
        historical,
        color='#7c3aed',
        dash='',
    )
    forecast_line = _polyline(
        forecast,
        color='#8b5cf6',
        dash=' stroke-dasharray="8 6"',
    )
    projected_y = _chart_y(projected)
    latest_y = _chart_y(latest)
    projected_label_y = _projected_label_y(projected, projected_y)
    threshold_label_x = min(610.0, forecast_start_x + 165.0)

    return f'''<svg class="ao-chart-svg chart" viewBox="0 0 800 230" role="img" aria-label="{label} demand forecast">
        <rect x="{forecast_start_x:.1f}" y="18" width="{748 - forecast_start_x:.1f}" height="164" fill="#faf7ff"/>
        <text x="{forecast_start_x + 12:.1f}" y="32" fill="#6d28d9" font-size="10" font-weight="700">FORECAST</text>
        <g stroke="#e5e7eb" stroke-width="1">
            <line x1="68" x2="748" y1="182" y2="182"/><line x1="68" x2="748" y1="143" y2="143"/>
            <line x1="68" x2="748" y1="104" y2="104"/><line x1="68" x2="748" y1="65" y2="65"/>
            <line x1="68" x2="748" y1="39" y2="39"/>
        </g>
        <line x1="68" x2="748" y1="65" y2="65" stroke="#d97706" stroke-width="1.3" stroke-dasharray="6 5"/>
        <line x1="68" x2="748" y1="39" y2="39" stroke="#dc2626" stroke-width="1.3" stroke-dasharray="6 5"/>
        <line x1="{forecast_start_x:.1f}" x2="{forecast_start_x:.1f}" y1="18" y2="182" stroke="#a78bfa" stroke-width="1.1" stroke-dasharray="4 4"/>
        <g fill="#64748b" font-size="10"><text x="24" y="186">0%</text><text x="24" y="147">25%</text>
            <text x="24" y="108">50%</text><text x="24" y="69">70%</text><text x="24" y="43">85%</text></g>
        <text x="{threshold_label_x:.1f}" y="60" text-anchor="start" fill="#b45309" font-size="9.5">Warning 70%</text>
        <text x="{threshold_label_x:.1f}" y="34" text-anchor="start" fill="#b91c1c" font-size="9.5">Critical 85%</text>
        {historical_line}{forecast_line}
        <circle cx="{forecast_start_x:.1f}" cy="{latest_y:.1f}" r="3.4" fill="#7c3aed"/>
        <circle cx="742" cy="{projected_y:.1f}" r="3.6" fill="#8b5cf6"/>
        <text x="730" y="{projected_label_y:.1f}" text-anchor="end" fill="#5b21b6" font-size="10.5" font-weight="700">{projected:.1f}%</text>
        <g fill="#64748b" font-size="9.2" text-anchor="middle"><text x="68" y="207">Start</text>
            <text x="284" y="207">Historical</text><text x="536" y="207">Near-term</text><text x="742" y="207">Horizon</text></g>
        <line x1="80" x2="108" y1="223" y2="223" stroke="#7c3aed" stroke-width="2.5"/>
        <text x="114" y="227" fill="#64748b" font-size="8.8">Historical P95</text>
        <line x1="238" x2="266" y1="223" y2="223" stroke="#8b5cf6" stroke-width="2.5" stroke-dasharray="7 5"/>
        <text x="272" y="227" fill="#64748b" font-size="8.8">Projected demand</text>
        <line x1="420" x2="448" y1="223" y2="223" stroke="#d97706" stroke-width="1.4" stroke-dasharray="6 5"/>
        <text x="454" y="227" fill="#64748b" font-size="8.8">Threshold</text>
    </svg>'''


def _forecast_start_x(forecast: str) -> float:
    if not forecast:
        return 430.0
    try:
        return float(forecast.split()[0].split(',')[0])
    except (IndexError, TypeError, ValueError):
        return 430.0


def _polyline(points: str, *, color: str, dash: str) -> str:
    if not points:
        return ''
    return (
        f'<polyline points="{escape(points)}" fill="none" stroke="{color}" '
        f'stroke-width="3"{dash} stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _projected_label_y(projected: float, projected_y: float) -> float:
    if 66.0 <= projected <= 74.0 or 81.0 <= projected <= 89.0:
        return min(178.0, projected_y + 16.0)
    return max(14.0, projected_y - 9.0)


def _scaled_chart_points(points: str) -> str:
    if not points:
        return ''
    scaled: list[str] = []
    for token in points.split():
        try:
            raw_x, raw_y = token.split(',', 1)
            x = 68.0 + (float(raw_x) / 100.0) * 674.0
            y = 18.0 + (float(raw_y) / 100.0) * 164.0
        except (TypeError, ValueError):
            continue
        scaled.append(f'{x:.2f},{y:.2f}')
    return ' '.join(scaled)


def _chart_y(value: float) -> float:
    return 182.0 - (max(0.0, min(value, 100.0)) / 100.0) * 164.0


def _empty_chart_svg(message: str) -> str:
    return (
        '<svg class="ao-chart-svg" viewBox="0 0 100 100" role="img" aria-label="No chart data">'
        '<rect width="100" height="100" rx="4" fill="#f8fafc"/>'
        f'<text x="50" y="50" text-anchor="middle" font-size="4" fill="#64748b">{escape(message)}</text>'
        '</svg>'
    )


def forecast_rows(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    forecast_snapshot: Mapping[str, Any],
    series: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    item_map = {str(item.get('key')): item for item in series}
    nearest_warning = mapping(forecast_snapshot.get('nearest_warning'))
    nearest_critical = mapping(forecast_snapshot.get('nearest_critical'))
    nearest_resource = str(nearest_critical.get('resource') or nearest_warning.get('resource') or '').lower()
    nearest_label = text(nearest_critical.get('label') or nearest_warning.get('label'), 'Not projected')
    rows: list[dict[str, Any]] = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('storage', 'PVC Storage'), ('pods', 'Pods')):
        metric = mapping(resource_metrics.get(key))
        item = mapping(item_map.get(key))
        current = _current_percent(item, metric)
        projected = number(item.get('projected_percent'), current or 0.0) if item else None
        trend = text(item.get('trend'), text(forecast_snapshot.get(f'{key}_trend'), 'Unknown'))
        eta = nearest_label if key == nearest_resource else 'Not projected'
        confidence = text(item.get('confidence'), 'Not Available') if item else 'Not Available'
        row_tone = _forecast_tone(projected)
        rows.append(
            {
                'resource': label,
                'growth': trend,
                'current': display_percent(current),
                'projected': display_percent(projected),
                'eta': eta,
                'confidence': confidence,
                'tone': row_tone,
                'assessment': _forecast_assessment(projected, row_tone),
            }
        )
    return rows


def _current_percent(item: Mapping[str, Any], metric: Mapping[str, Any]) -> float | None:
    if item and item.get('latest_percent') is not None:
        return number(item.get('latest_percent'))
    if metric.get('available'):
        value = metric.get('percent')
        return float(value) if isinstance(value, (int, float)) else number(value)
    return None


def _forecast_tone(projected: float | None) -> str:
    if projected is None:
        return 'neutral'
    if projected >= 85:
        return 'critical'
    if projected >= 70:
        return 'warning'
    return 'normal'


def _forecast_assessment(projected: float | None, row_tone: str) -> str:
    if projected is None:
        return 'Not available from the committed forecast evidence.'
    if row_tone == 'critical':
        return 'Projected to enter the critical band.'
    if row_tone == 'warning':
        return 'Projected to enter or remain in the warning band.'
    return 'Stable within the current operating window.'


def forecast_interpretation(forecast_snapshot: Mapping[str, Any]) -> str:
    return text(
        forecast_snapshot.get('risk_note'),
        'Forecast evidence is unavailable or does not currently indicate a threshold breach.',
    )
