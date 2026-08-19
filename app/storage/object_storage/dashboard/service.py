from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.models import Report, ReportSchedule, ReportTemplate
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
from app.storage.object_storage.analytics.alert_sources import (
    build_alert_posture,
    resolve_materialized_alert_stream,
)
from app.storage.object_storage.analytics.materialization import (
    analytics_snapshot_state,
    forecast_snapshot_state,
    get_analytics_snapshot,
    get_forecast_snapshot,
    read_analytics_snapshot,
)
from app.storage.object_storage.analytics.presentation import format_bytes, format_number, format_percent

_DASHBOARD_TIME_RANGE = '24h'
_DASHBOARD_FORECAST_WINDOW = '30d'


def _systems() -> list[ObjectStorageSystem]:
    return list(
        ObjectStorageSystem.query.options(selectinload(ObjectStorageSystem.buckets)).order_by(
            ObjectStorageSystem.name.asc()
        )
    )


def _selected_system(
    systems: list[ObjectStorageSystem], selected_system_id: str | None
) -> ObjectStorageSystem | None:
    if not selected_system_id:
        return None
    return next((system for system in systems if str(system.id) == str(selected_system_id)), None)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _human_time(value: datetime | None) -> str:
    resolved = _aware(value)
    if resolved is None:
        return 'Not Collected'
    seconds = max(int((datetime.now(UTC) - resolved).total_seconds()), 0)
    if seconds < 60:
        return 'Just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours}h ago'
    days = hours // 24
    return f'{days}d ago'


def _snapshot_payload(system: ObjectStorageSystem) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return read_analytics_snapshot(system_id=str(system.id), time_range=_DASHBOARD_TIME_RANGE)


def _forecast_payload(system: ObjectStorageSystem) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    snapshot = get_forecast_snapshot(system_id=str(system.id), history_window=_DASHBOARD_FORECAST_WINDOW)
    state = forecast_snapshot_state(snapshot)
    payload = snapshot.payload_json if snapshot is not None and isinstance(snapshot.payload_json, dict) else None
    if not state.get('usable'):
        payload = None
    return payload, state


def _page_metrics(payload: dict[str, Any] | None, page_key: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    pages = payload.get('page_metrics')
    if not isinstance(pages, dict):
        return {}
    metrics = pages.get(page_key)
    return dict(metrics) if isinstance(metrics, dict) else {}


def _alert_view(payload: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    streams = payload.get('alert_streams') if isinstance(payload, dict) else None
    stream = resolve_materialized_alert_stream(
        streams if isinstance(streams, dict) else {},
        selected_source='auto',
    )
    return stream, build_alert_posture(stream)


def _inventory_summary(systems: list[ObjectStorageSystem]) -> dict[str, Any]:
    buckets = [bucket for system in systems for bucket in (system.buckets or ())]
    size_values = [int(bucket.size_bytes) for bucket in buckets if bucket.size_bytes is not None]
    object_values = [int(bucket.object_count) for bucket in buckets if bucket.object_count is not None]
    quota_configured = [bucket for bucket in buckets if bucket.quota_state == 'configured' and bucket.quota_bytes is not None]
    usage_collected = [bucket for bucket in buckets if bucket.size_bytes is not None and bucket.object_count is not None]
    return {
        'systems': len(systems),
        'buckets': len(buckets),
        'stored_bytes': sum(size_values),
        'stored_display': format_bytes(sum(size_values)) if size_values else 'Not Collected',
        'objects': sum(object_values),
        'objects_display': format_number(sum(object_values)) if object_values else 'Not Collected',
        'quota_configured': len(quota_configured),
        'usage_collected': len(usage_collected),
    }


def _health_rows(systems: list[ObjectStorageSystem]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for system in systems:
        payload, snapshot_state = _snapshot_payload(system)
        overview = _page_metrics(payload, 'overview')
        stream, posture = _alert_view(payload)
        rows.append(
            {
                'id': str(system.id),
                'name': system.name,
                'environment': system.environment,
                'provider_status': str(system.status or 'unknown').replace('_', ' ').title(),
                'inventory_updated': _human_time(system.inventory_observed_at),
                'snapshot_label': str(snapshot_state.get('label') or 'Worker Data Required'),
                'snapshot_tone': str(snapshot_state.get('tone') or 'unknown'),
                'utilization_display': str(overview.get('utilization_display') or 'N/A'),
                'utilization_tone': str(overview.get('utilization_tone') or 'unknown'),
                'active_alerts': int(posture.get('total') or 0) if stream.get('connected') else None,
                'alerts_connected': bool(stream.get('connected')),
            }
        )
    return rows


def _dashboard_kpis(
    systems: list[ObjectStorageSystem], selected: ObjectStorageSystem | None
) -> list[dict[str, str]]:
    scoped = [selected] if selected is not None else systems
    inventory = _inventory_summary(scoped)
    active_alerts = 0
    alert_sources_ready = 0
    analytics_ready = 0
    operational_usage: float | None = None
    selected_utilization: str | None = None
    for system in scoped:
        payload, state = _snapshot_payload(system)
        analytics_ready += int(bool(state.get('usable')))
        overview = _page_metrics(payload, 'overview')
        stream, posture = _alert_view(payload)
        if stream.get('connected'):
            alert_sources_ready += 1
            active_alerts += int(posture.get('total') or 0)
        if selected is not None:
            operational_usage = overview.get('usage_total')
            selected_utilization = str(overview.get('utilization_display') or 'N/A')

    if selected is not None:
        usage_display = format_bytes(operational_usage) if operational_usage is not None else inventory['stored_display']
        return [
            {'label': 'Buckets', 'value': str(inventory['buckets']), 'description': 'Committed inventory assets', 'icon': 'database'},
            {'label': 'Used Capacity', 'value': usage_display, 'description': 'Worker metrics with inventory fallback context', 'icon': 'hard-drive'},
            {'label': 'Utilization', 'value': selected_utilization or 'N/A', 'description': 'Committed 24h analytics snapshot', 'icon': 'gauge'},
            {'label': 'Active Alerts', 'value': str(active_alerts) if alert_sources_ready else 'N/A', 'description': 'Committed alert evidence', 'icon': 'bell-ring'},
        ]

    return [
        {'label': 'Systems', 'value': str(inventory['systems']), 'description': 'Registered Object Storage systems', 'icon': 'server'},
        {'label': 'Buckets', 'value': str(inventory['buckets']), 'description': 'Committed inventory assets', 'icon': 'database'},
        {'label': 'Inventory Usage', 'value': str(inventory['stored_display']), 'description': 'Committed bucket usage evidence', 'icon': 'hard-drive'},
        {
            'label': 'Analytics Ready',
            'value': f'{analytics_ready} / {len(scoped)}' if scoped else '0 / 0',
            'description': 'Usable 24h worker snapshots',
            'icon': 'database-zap',
        },
    ]


def _freshness(selected: ObjectStorageSystem | None, systems: list[ObjectStorageSystem]) -> list[dict[str, str]]:
    if selected is None:
        observed = [_aware(system.inventory_observed_at) for system in systems if system.inventory_observed_at is not None]
        analytics_states = [analytics_snapshot_state(get_analytics_snapshot(system_id=str(system.id), time_range=_DASHBOARD_TIME_RANGE)) for system in systems]
        ready = sum(bool(state.get('usable')) for state in analytics_states)
        return [
            {
                'label': 'Inventory Fleet',
                'status': 'Available' if observed else 'Not Collected',
                'tone': 'normal' if observed else 'warning',
                'value': _human_time(max(observed)) if observed else 'No committed inventory',
                'description': 'Most recent Object Storage Inventory observation across registered systems.',
                'icon': 'database',
            },
            {
                'label': 'Analytics Fleet',
                'status': 'Ready' if ready == len(systems) and systems else ('Partial' if ready else 'Required'),
                'tone': 'normal' if ready == len(systems) and systems else ('warning' if ready else 'unknown'),
                'value': f'{ready} / {len(systems)} systems',
                'description': 'Usable 24h Object Storage Analytics worker snapshots.',
                'icon': 'database-zap',
            },
        ]

    analytics_snapshot = get_analytics_snapshot(system_id=str(selected.id), time_range=_DASHBOARD_TIME_RANGE)
    analytics_state = analytics_snapshot_state(analytics_snapshot)
    forecast_snapshot = get_forecast_snapshot(system_id=str(selected.id), history_window=_DASHBOARD_FORECAST_WINDOW)
    forecast_state = forecast_snapshot_state(forecast_snapshot)
    payload, _state = _snapshot_payload(selected)
    stream, _posture = _alert_view(payload)
    return [
        {
            'label': 'Inventory Snapshot',
            'status': 'Available' if selected.inventory_observed_at else 'Required',
            'tone': 'normal' if selected.inventory_observed_at else 'warning',
            'value': _human_time(selected.inventory_observed_at),
            'description': 'Committed bucket identity, usage fallback, quota, and provider state.',
            'icon': 'database',
        },
        {
            'label': 'Analytics Snapshot',
            'status': str(analytics_state.get('label') or 'Required'),
            'tone': str(analytics_state.get('tone') or 'unknown'),
            'value': _human_time(analytics_state.get('generated_at')),
            'description': 'Committed capacity, performance, consumer, and alert evidence collected by the worker.',
            'icon': 'database-zap',
        },
        {
            'label': 'Forecast Snapshot',
            'status': str(forecast_state.get('label') or 'Required'),
            'tone': str(forecast_state.get('tone') or 'unknown'),
            'value': _human_time(forecast_state.get('generated_at')),
            'description': 'Committed 30d system and bucket forecast evidence.',
            'icon': 'trending-up',
        },
        {
            'label': 'Alert Evidence',
            'status': 'Available' if stream.get('connected') else 'Unavailable',
            'tone': 'normal' if stream.get('connected') else 'warning',
            'value': str(stream.get('resolved_label') or stream.get('label') or 'Unavailable'),
            'description': 'Alertmanager preferred with Metrics Source fallback, resolved from the analytics snapshot.',
            'icon': 'bell-ring',
        },
    ]


def _capacity(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    if selected is None:
        return {'available': False}
    payload, state = _snapshot_payload(selected)
    metrics = _page_metrics(payload, 'capacity')
    return {
        'available': bool(metrics),
        'snapshot': state,
        'used_display': str(metrics.get('usage_total_display') or 'N/A'),
        'free_display': str(metrics.get('capacity_free_display') or 'N/A'),
        'total_display': str(metrics.get('capacity_total_display') or 'N/A'),
        'utilization': metrics.get('utilization'),
        'utilization_display': str(metrics.get('utilization_display') or 'N/A'),
        'utilization_tone': str(metrics.get('utilization_tone') or 'unknown'),
        'headroom_display': str(metrics.get('headroom_percent_display') or 'N/A'),
        'posture': dict(metrics.get('capacity_posture') or {}),
        'reconciliation': list(metrics.get('reconciliation') or []),
    }


def _forecast(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    if selected is None:
        return {'available': False}
    payload, state = _forecast_payload(selected)
    forecast = payload.get('forecast') if isinstance(payload, dict) and isinstance(payload.get('forecast'), dict) else {}
    bucket_rows = payload.get('bucket_forecasts') if isinstance(payload, dict) and isinstance(payload.get('bucket_forecasts'), list) else []
    projected = forecast.get('projected_30d')
    days = forecast.get('days_to_capacity')
    growth = forecast.get('growth_per_day')
    if days is not None and float(days) <= 30:
        posture = {'label': 'Critical', 'tone': 'critical'}
    elif days is not None and float(days) <= 90:
        posture = {'label': 'Warning', 'tone': 'warning'}
    elif growth is not None:
        posture = {'label': 'Growth Watch' if float(growth) > 0 else 'Stable', 'tone': 'info' if float(growth) > 0 else 'normal'}
    else:
        posture = {'label': 'Insufficient History', 'tone': 'unknown'}
    return {
        'available': bool(payload),
        'snapshot': state,
        'projected_30d_display': format_bytes(projected),
        'growth_per_day_display': f'{format_bytes(growth)}/day' if growth is not None else 'N/A',
        'days_to_capacity_display': f'{float(days):.1f} days' if days is not None else 'No ETA',
        'posture': posture,
        'bucket_count': len(bucket_rows),
        'attention_count': sum(
            1
            for row in bucket_rows
            if isinstance(row, dict)
            and isinstance(row.get('forecast'), dict)
            and row['forecast'].get('days_to_capacity') is not None
            and float(row['forecast']['days_to_capacity']) <= 90
        ),
    }


def _top_consumers(selected: ObjectStorageSystem | None) -> list[dict[str, str]]:
    if selected is None:
        return []
    payload, _state = _snapshot_payload(selected)
    metrics = _page_metrics(payload, 'top_consumers')
    rows = [row for row in metrics.get('bucket_rows') or [] if isinstance(row, dict)]
    rows.sort(key=lambda row: float(row.get('usage_bytes') or 0), reverse=True)
    result: list[dict[str, str]] = []
    for row in rows[:5]:
        result.append(
            {
                'name': str(row.get('name') or 'Unknown Bucket'),
                'usage': str(row.get('usage_display') or format_bytes(row.get('usage_bytes'))),
                'share': str(row.get('usage_share_display') or format_percent(row.get('usage_share'))),
                'objects': str(row.get('objects_display') or format_number(row.get('objects'))),
                'request_rate': str(row.get('request_rate_display') or 'N/A'),
            }
        )
    return result


def _alerts(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    if selected is None:
        return {'available': False, 'critical': 0, 'warning': 0, 'info': 0, 'rows': []}
    payload, state = _snapshot_payload(selected)
    stream, posture = _alert_view(payload)
    rows = [row for row in stream.get('rows') or [] if isinstance(row, dict)]
    return {
        'available': bool(stream.get('connected')),
        'snapshot': state,
        'critical': int(posture.get('critical') or 0),
        'warning': int(posture.get('warning') or 0),
        'info': int(posture.get('info') or 0),
        'total': int(posture.get('total') or 0),
        'source_label': str(stream.get('resolved_label') or stream.get('label') or 'Unavailable'),
        'rows': rows[:3],
    }


def _reporting(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    reports_query = Report.query.filter(Report.report_domain == 'object_storage')
    schedules_query = ReportSchedule.query.filter(ReportSchedule.report_domain == 'object_storage')
    if selected is not None:
        scope_filter = or_(Report.scope_asset_id == str(selected.id), Report.scope_asset_id.is_(None))
        reports_query = reports_query.filter(scope_filter)
        schedule_scope_filter = or_(
            ReportSchedule.scope_asset_id == str(selected.id), ReportSchedule.scope_asset_id.is_(None)
        )
        schedules_query = schedules_query.filter(schedule_scope_filter)
    recent = reports_query.order_by(Report.created_at.desc()).limit(3).all()
    return {
        'generated_reports': reports_query.count(),
        'templates': ReportTemplate.query.filter(ReportTemplate.report_domain == 'object_storage').count(),
        'schedules': schedules_query.count(),
        'latest_reports': [
            {
                'title': report.name,
                'status': str(report.status or 'unknown').replace('_', ' ').title(),
                'generated_at': _human_time(report.created_at),
            }
            for report in recent
        ],
    }


def get_dashboard_overview(
    *, selected_system_id: str | None = None, active_tab: str = 'overview'
) -> dict[str, Any]:
    systems = _systems()
    selected = _selected_system(systems, selected_system_id)
    inventory = _inventory_summary([selected] if selected is not None else systems)
    return {
        'systems': [{'id': str(system.id), 'name': system.name} for system in systems],
        'selected_system_id': str(selected.id) if selected is not None else None,
        'selected_system': selected,
        'active_tab': active_tab,
        'last_updated': _human_time(selected.inventory_observed_at if selected is not None else max(
            (_aware(system.inventory_observed_at) for system in systems if system.inventory_observed_at is not None),
            default=None,
        )),
        'inventory': inventory,
    }


def get_dashboard_section(section: str, *, selected_system_id: str | None = None) -> dict[str, Any]:
    systems = _systems()
    selected = _selected_system(systems, selected_system_id)
    dashboard = get_dashboard_overview(selected_system_id=selected_system_id)
    if section == 'kpi_cards':
        dashboard['kpis'] = _dashboard_kpis(systems, selected)
    elif section == 'overview':
        dashboard['health_rows'] = _health_rows(systems)
        dashboard['inventory'] = _inventory_summary([selected] if selected is not None else systems)
        dashboard['freshness'] = _freshness(selected, systems)
    elif section == 'capacity':
        dashboard['capacity'] = _capacity(selected)
        dashboard['forecast'] = _forecast(selected)
        dashboard['top_consumers'] = _top_consumers(selected)
    elif section == 'signals':
        dashboard['alerts'] = _alerts(selected)
        dashboard['forecast'] = _forecast(selected)
        dashboard['capacity'] = _capacity(selected)
    elif section == 'reporting':
        dashboard['reporting'] = _reporting(selected)
        dashboard['freshness'] = _freshness(selected, systems)
    return dashboard
