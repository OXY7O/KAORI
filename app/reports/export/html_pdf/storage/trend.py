from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.storage.model import mapping, percent, rows, safe_float, status_from_percent, text


def storage_trend(payload: Mapping[str, Any], *, current: float) -> dict[str, Any]:
    forecast = mapping(payload.get('forecast_payload'))
    items = rows(forecast.get('items'))
    storage_item = next((item for item in items if text(item.get('key'), '').lower() == 'storage'), {})
    historical = _point_values(storage_item.get('historical_points'))
    projected = _point_values(storage_item.get('forecast_points'))
    projected_percent = safe_float(storage_item.get('projected_percent'))
    if projected_percent is None and projected:
        projected_percent = projected[-1]
    historical_available = bool(historical)
    available = bool(historical or projected or projected_percent is not None)
    assessment_status, assessment_tone = status_from_percent(
        projected_percent if projected_percent is not None else current if available else None
    )
    assessment = (
        'Stable'
        if projected_percent is not None and projected_percent < 70
        else assessment_status
        if available
        else 'Review'
    )
    return {
        'available': available,
        'historical_available': historical_available,
        'projection_percent': projected_percent,
        'projection_display': percent(projected_percent),
        'status': 'Committed' if available else 'Not Available',
        'tone': assessment_tone if available else 'warning',
        'assessment': assessment,
        'method': text(forecast.get('method_label') or forecast.get('forecast_method'), 'Not Available'),
        'horizon': text(forecast.get('forecast_horizon'), 'Not Available'),
        'chart_svg': _trend_svg(historical, projected, current=current, projection=projected_percent) if available else '',
    }


def trend_interpretation(capacity: Mapping[str, Any], trend: Mapping[str, Any]) -> str:
    if not capacity.get('evidence_available'):
        return 'No aggregate trend conclusion can be made without committed current capacity evidence.'
    if not trend.get('available'):
        return 'Current aggregate capacity is available, but committed historical and forecast evidence are not available. Continue collection before using this report for expansion planning.'
    projection = safe_float(trend.get('projection_percent'))
    if projection is not None and projection >= 70:
        return f'Storage is projected to reach {projection:.1f}%, which requires planning review before the warning-band exposure becomes operational.'
    return 'Current and projected aggregate storage remain below the warning band within the available committed horizon.'


def _point_values(value: Any) -> list[float]:
    result: list[float] = []
    for item in rows(value):
        number = safe_float(item.get('percent', item.get('value')))
        if number is not None:
            result.append(max(0.0, min(100.0, number)))
    return result


def _trend_svg(historical: list[float], projected: list[float], *, current: float, projection: float | None) -> str:
    width, height = 760, 250
    left, right, top, bottom = 58, 22, 18, 42
    chart_w = width - left - right
    chart_h = height - top - bottom
    history_values = historical[:] or [current]
    if history_values[-1] != current:
        history_values.append(current)
    forecast_values = projected[:]
    if projection is not None and (not forecast_values or forecast_values[-1] != projection):
        forecast_values.append(projection)
    all_count = max(2, len(history_values) + len(forecast_values))
    cutoff_index = len(history_values) - 1

    def x(index: int) -> float:
        return left + chart_w * index / max(1, all_count - 1)

    def y(value: float) -> float:
        return top + chart_h * (1 - max(0.0, min(100.0, value)) / 100)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Storage utilization trend">']
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>')
    for tick in (0, 25, 50, 70, 85, 100):
        yy = y(float(tick))
        color = '#D97706' if tick == 70 else '#DC2626' if tick == 85 else '#E2E8F0'
        dash = ' stroke-dasharray="5 5"' if tick in {70, 85} else ''
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width - right}" y2="{yy:.1f}" stroke="{color}" stroke-width="1"{dash}/>')
        parts.append(f'<text x="{left - 12}" y="{yy + 3:.1f}" text-anchor="end" font-size="9" fill="#64748B">{tick}%</text>')
    cutoff_x = x(cutoff_index)
    parts.append(f'<line x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{height - bottom}" stroke="#A78BFA" stroke-width="1" stroke-dasharray="4 4"/>')
    history_points = ' '.join(f'{x(index):.1f},{y(value):.1f}' for index, value in enumerate(history_values))
    parts.append(f'<polyline points="{history_points}" fill="none" stroke="#7C3AED" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
    if forecast_values:
        forecast_series = [history_values[-1], *forecast_values]
        forecast_points = ' '.join(f'{x(cutoff_index + index):.1f},{y(value):.1f}' for index, value in enumerate(forecast_series))
        parts.append(f'<polyline points="{forecast_points}" fill="none" stroke="#7C3AED" stroke-width="4" stroke-dasharray="8 6" stroke-linejoin="round" stroke-linecap="round"/>')
    end_value = forecast_values[-1] if forecast_values else history_values[-1]
    end_x = x(cutoff_index + len(forecast_values))
    end_y = y(end_value)
    parts.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="5" fill="#7C3AED"/>')
    parts.append(f'<text x="{end_x - 6:.1f}" y="{end_y - 10:.1f}" text-anchor="end" font-size="12" font-weight="700" fill="#7C3AED">{end_value:.1f}%</text>')
    if cutoff_x - left >= 70:
        parts.append(f'<text x="{left}" y="{height - 14}" font-size="10" fill="#64748B">Historical Start</text>')
    parts.append(f'<text x="{cutoff_x:.1f}" y="{height - 14}" text-anchor="middle" font-size="10" fill="#64748B">Cut-off</text>')
    parts.append(f'<text x="{width - right}" y="{height - 14}" text-anchor="end" font-size="10" fill="#64748B">Horizon</text>')
    parts.append('</svg>')
    return ''.join(parts)
