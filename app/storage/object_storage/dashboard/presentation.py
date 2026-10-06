from __future__ import annotations

from typing import Any

from app.storage.object_storage.analytics.presentation import format_bytes, format_percent

_DASHBOARD_FORECAST_WINDOW = '30d'


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _clamp_percent(value: float) -> float:
    return max(0.0, min(float(value), 100.0))


def _sample(values: list[float], *, limit: int) -> list[float]:
    if len(values) <= limit:
        return values
    if limit <= 1:
        return [values[-1]]
    last_index = len(values) - 1
    indexes = [round(index * last_index / (limit - 1)) for index in range(limit)]
    return [values[index] for index in indexes]


def _polyline_points(values: list[float], *, start_x: float, end_x: float) -> str:
    if not values:
        return ''
    denominator = max(len(values) - 1, 1)
    points: list[str] = []
    for index, value in enumerate(values):
        x_value = start_x + ((end_x - start_x) * index / denominator)
        y_value = max(2.0, min(98.0, 100.0 - _clamp_percent(value)))
        points.append(f'{x_value:.2f},{y_value:.2f}')
    return ' '.join(points)


def _forecast_posture(*, days: float | None, projected_percent: float | None, growth: float | None) -> dict[str, str]:
    if days is not None and days <= 30:
        return {'label': 'Critical', 'tone': 'critical'}
    if days is not None and days <= 90:
        return {'label': 'Warning', 'tone': 'warning'}
    if projected_percent is not None and projected_percent >= 90:
        return {'label': 'Critical', 'tone': 'critical'}
    if projected_percent is not None and projected_percent >= 75:
        return {'label': 'Warning', 'tone': 'warning'}
    if growth is None:
        return {'label': 'Insufficient History', 'tone': 'unknown'}
    if growth > 0:
        return {'label': 'Growth Watch', 'tone': 'info'}
    return {'label': 'Stable', 'tone': 'normal'}


def _forecast_chart_item(
    *,
    payload: dict[str, Any],
    forecast: dict[str, Any],
    posture: dict[str, str],
) -> dict[str, Any] | None:
    capacity = _optional_float(payload.get('capacity_bytes'))
    points = [point for point in payload.get('points') or [] if isinstance(point, dict)]
    if capacity is None or capacity <= 0 or not points:
        return None
    historical_values = [
        _clamp_percent(float(point['value']) / capacity * 100)
        for point in points
        if _optional_float(point.get('value')) is not None
    ]
    if not historical_values:
        return None
    projected = _optional_float(forecast.get('projected_30d'))
    projected_percent = _clamp_percent(projected / capacity * 100) if projected is not None else None
    current_percent = historical_values[-1]
    history = _sample(historical_values, limit=8)
    forecast_values = [current_percent, projected_percent if projected_percent is not None else current_percent]
    growth = _optional_float(forecast.get('growth_per_day'))
    trend = (
        'Increasing'
        if growth is not None and growth > 0
        else ('Decreasing' if growth is not None and growth < 0 else 'Stable')
    )
    return {
        'key': 'storage',
        'label': 'Storage Usage',
        'risk': posture['label'],
        'latest_daily_average_percent': current_percent,
        'projected_percent': projected_percent,
        'trend': trend,
        'historical_points': _polyline_points(history, start_x=2, end_x=56),
        'forecast_points': _polyline_points(forecast_values, start_x=56, end_x=98),
    }


def _forecast_attention_count(bucket_rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in bucket_rows:
        forecast = row.get('forecast') if isinstance(row, dict) else None
        days = _optional_float(forecast.get('days_to_capacity')) if isinstance(forecast, dict) else None
        count += int(days is not None and days <= 90)
    return count


def build_forecast_view(payload: dict[str, Any] | None, state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {'available': False, 'snapshot': state, 'chart_items': []}
    raw_forecast = payload.get('forecast')
    forecast = raw_forecast if isinstance(raw_forecast, dict) else {}
    raw_bucket_rows = payload.get('bucket_forecasts')
    bucket_rows = [row for row in raw_bucket_rows if isinstance(row, dict)] if isinstance(raw_bucket_rows, list) else []
    points = [point for point in payload.get('points') or [] if isinstance(point, dict)]
    projected = _optional_float(forecast.get('projected_30d'))
    days = _optional_float(forecast.get('days_to_capacity'))
    growth = _optional_float(forecast.get('growth_per_day'))
    capacity = _optional_float(payload.get('capacity_bytes'))
    current = _optional_float(points[-1].get('value')) if points else None
    current_percent = (current / capacity * 100) if current is not None and capacity and capacity > 0 else None
    projected_percent = (projected / capacity * 100) if projected is not None and capacity and capacity > 0 else None
    posture = _forecast_posture(days=days, projected_percent=projected_percent, growth=growth)
    chart_item = _forecast_chart_item(payload=payload, forecast=forecast, posture=posture)
    attention_count = _forecast_attention_count(bucket_rows)
    return {
        'available': True,
        'snapshot': state,
        'history_window': str(payload.get('history_window') or _DASHBOARD_FORECAST_WINDOW),
        'horizon_days': 30,
        'sample_count': len(points),
        'current_display': format_bytes(current),
        'current_percent': current_percent,
        'current_percent_display': format_percent(current_percent),
        'projected_30d_display': format_bytes(projected),
        'projected_percent': projected_percent,
        'projected_percent_display': format_percent(projected_percent),
        'growth_per_day_display': f'{format_bytes(growth)}/day' if growth is not None else 'N/A',
        'days_to_capacity_display': f'{days:.1f} days' if days is not None else 'No ETA',
        'posture': posture,
        'bucket_count': len(bucket_rows),
        'attention_count': attention_count,
        'chart_items': [chart_item] if chart_item else [],
        'has_historical_series': bool(chart_item and chart_item.get('historical_points')),
        'insight': (
            f'{attention_count} bucket forecast(s) are inside the 90-day attention boundary.'
            if attention_count
            else 'No bucket forecast is currently inside the 90-day attention boundary.'
        ),
    }


def _consumer_signal_state(percent: float | None) -> str:
    if percent is None:
        return 'unknown'
    if percent >= 50:
        return 'critical'
    if percent >= 25:
        return 'warning'
    return 'normal'


def _usage_items(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(
        (row for row in rows if _optional_float(row.get('usage_bytes')) is not None),
        key=lambda row: float(row.get('usage_bytes') or 0),
        reverse=True,
    )
    items: list[dict[str, Any]] = []
    for rank, row in enumerate(ordered[:3], start=1):
        share = _optional_float(row.get('usage_share'))
        items.append(
            {
                'rank': rank,
                'name': str(row.get('name') or 'Unknown Bucket'),
                'context': str(row.get('usage_source') or 'Committed Evidence'),
                'value': str(row.get('usage_display') or format_bytes(row.get('usage_bytes'))),
                'percent': share,
                'signal_label': str(row.get('usage_share_display') or format_percent(share)),
                'signal_state': _consumer_signal_state(share),
            }
        )
    return items, ordered


def _request_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        (row for row in rows if _optional_float(row.get('request_rate')) is not None),
        key=lambda row: float(row.get('request_rate') or 0),
        reverse=True,
    )
    max_request = max((_optional_float(row.get('request_rate')) or 0.0 for row in ordered), default=0.0)
    items: list[dict[str, Any]] = []
    for rank, row in enumerate(ordered[:3], start=1):
        request_rate = _optional_float(row.get('request_rate'))
        relative_percent = (request_rate / max_request * 100) if request_rate is not None and max_request > 0 else None
        error_ratio = _optional_float(row.get('error_ratio'))
        signal_state = 'unknown'
        if request_rate is not None:
            signal_state = (
                'critical' if (error_ratio or 0) >= 5 else ('warning' if (error_ratio or 0) >= 1 else 'normal')
            )
        items.append(
            {
                'rank': rank,
                'name': str(row.get('name') or 'Unknown Bucket'),
                'context': str(row.get('request_source') or 'Committed Evidence'),
                'value': str(row.get('request_rate_display') or 'N/A'),
                'percent': relative_percent,
                'signal_label': str(row.get('error_ratio_display') or 'Error N/A'),
                'signal_state': signal_state,
            }
        )
    return items


def _consumer_insight(
    *,
    ordered_usage: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    state: dict[str, Any],
) -> tuple[str, str, list[str], int, int]:
    missing_activity_count = sum(_optional_float(row.get('request_rate')) is None for row in rows)
    high_usage_count = sum((_optional_float(row.get('usage_share')) or 0) >= 25 for row in rows)
    top_share = _optional_float(ordered_usage[0].get('usage_share')) if ordered_usage else None
    if top_share is not None and top_share >= 50:
        title = 'Usage Concentration Requires Review'
        description = (
            f'The leading bucket accounts for {format_percent(top_share)} of committed storage usage, '
            'showing how much usage is concentrated in the largest consumer.'
        )
    elif missing_activity_count:
        title = 'Request Activity Evidence Incomplete'
        description = f'{missing_activity_count} bucket(s) do not have committed request-rate evidence.'
    else:
        title = 'Bucket Demand Is Distributed'
        description = (
            'No dominant usage concentration or request-path evidence gap is present in the committed snapshot.'
        )
    items: list[str] = []
    if top_share is not None:
        items.append(f'Top usage share {format_percent(top_share)}')
    if missing_activity_count:
        items.append(f'{missing_activity_count} activity gaps')
    if state.get('label'):
        items.append(str(state['label']))
    return title, description, items, missing_activity_count, high_usage_count


def build_top_consumers_view(metrics: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in metrics.get('bucket_rows') or [] if isinstance(row, dict)]
    usage_items, ordered_usage = _usage_items(rows)
    request_items = _request_items(rows)
    title, description, insight_items, missing_activity_count, high_usage_count = _consumer_insight(
        ordered_usage=ordered_usage,
        rows=rows,
        state=state,
    )
    return {
        'usage': usage_items,
        'requests': request_items,
        'source_status': 'Available' if rows else 'Unavailable',
        'message': (
            'Committed bucket consumer data is not available yet.'
            if not rows
            else 'Committed bucket consumer data loaded.'
        ),
        'insight_title': title,
        'insight_description': description,
        'insight_items': insight_items,
        'missing_activity_count': missing_activity_count,
        'high_usage_count': high_usage_count,
    }


def _action(
    *,
    priority: str,
    category: str,
    title: str,
    description: str,
    icon: str,
    severity: str,
    source: str,
    endpoint: str,
) -> dict[str, str]:
    return {
        'priority': priority,
        'category': category,
        'title': title,
        'description': description,
        'icon': icon,
        'severity': severity,
        'source': source,
        'endpoint': endpoint,
    }


def build_recommended_actions(
    *,
    alerts: dict[str, Any],
    capacity: dict[str, Any],
    forecast: dict[str, Any],
    top_consumers: dict[str, Any],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if int(alerts.get('critical') or 0) > 0:
        actions.append(
            _action(
                priority='P1',
                category='Incident',
                title='Triage Critical Object Storage Alerts',
                description='Validate active critical signals, affected buckets or systems, routing ownership, and the approved response runbook.',
                icon='siren',
                severity='critical',
                source='KAORI Alert Intelligence',
                endpoint='alert_intelligence.index',
            )
        )
    utilization = _optional_float(capacity.get('utilization'))
    if utilization is not None and utilization >= 85:
        actions.append(
            _action(
                priority='P2',
                category='Capacity',
                title='Review Capacity Pressure',
                description='Capacity utilization is inside the warning boundary. Review headroom, top bucket consumers, and forecast trajectory before additional growth.',
                icon='gauge',
                severity='warning',
                source='Committed Analytics Snapshot',
                endpoint='analytics.object_storage_capacity',
            )
        )
    if int(forecast.get('attention_count') or 0) > 0:
        actions.append(
            _action(
                priority='P2',
                category='Forecast',
                title='Review Bucket Forecast Watch',
                description='One or more bucket forecasts are inside the 90-day attention boundary. Validate growth ownership, quota policy, and projected capacity timing.',
                icon='chart-spline',
                severity='warning',
                source='Committed Forecast Snapshot',
                endpoint='analytics.object_storage_forecast',
            )
        )
    missing_activity = int(top_consumers.get('missing_activity_count') or 0)
    if missing_activity > 0:
        actions.append(
            _action(
                priority='P3',
                category='Evidence',
                title='Close Bucket Request Evidence Gaps',
                description=f'{missing_activity} bucket(s) do not have committed request-rate evidence. Validate bucket metric scraping and the shared Object Storage binding selector.',
                icon='scan-search',
                severity='info',
                source='Committed Consumer Evidence',
                endpoint='analytics.object_storage_top_consumers',
            )
        )
    if int(alerts.get('warning') or 0) > 0 and not any(action['category'] == 'Incident' for action in actions):
        actions.append(
            _action(
                priority='P3',
                category='Alert',
                title='Review Warning Alert Signals',
                description='Warning signals are active. Confirm recurrence, ownership, and supporting metrics before they become operational incidents.',
                icon='triangle-alert',
                severity='info',
                source='KAORI Alert Intelligence',
                endpoint='alert_intelligence.index',
            )
        )
    return actions[:5]
