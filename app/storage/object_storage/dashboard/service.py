from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.common.pagination import paginate_sequence
from app.intelligence.alert_intelligence.dashboard_cases import active_recommendation_alert_cases
from app.intelligence.dashboard_recommendations import get_dashboard_recommendation_findings
from app.models import Report, ReportSchedule, ReportTemplate
from app.models.object_storage import ObjectStorageSystem
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
from app.storage.object_storage.analytics.presentation import format_bytes, format_number
from app.storage.object_storage.dashboard.presentation import build_forecast_view, build_top_consumers_view

_DASHBOARD_TIME_RANGE = '24h'
_DASHBOARD_FORECAST_WINDOW = '30d'


def _systems() -> list[ObjectStorageSystem]:
    return list(
        ObjectStorageSystem.query.options(selectinload(ObjectStorageSystem.buckets)).order_by(
            ObjectStorageSystem.name.asc()
        )
    )


def _selected_system(systems: list[ObjectStorageSystem], selected_system_id: str | None) -> ObjectStorageSystem | None:
    if not selected_system_id:
        return None
    return next((system for system in systems if str(system.id) == str(selected_system_id)), None)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _inventory_observation_times(systems: list[ObjectStorageSystem]) -> list[datetime]:
    observed: list[datetime] = []
    for system in systems:
        resolved = _aware(system.inventory_observed_at)
        if resolved is not None:
            observed.append(resolved)
    return observed


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


def _kaori_alert_posture(system: ObjectStorageSystem | None) -> dict[str, Any]:
    cases = (
        active_recommendation_alert_cases(domain='object_storage', asset_key=str(system.id))
        if system is not None
        else []
    )
    return {
        'cases': cases,
        'critical': sum(case.severity == 'critical' for case in cases),
        'warning': sum(case.severity == 'warning' for case in cases),
        'info': sum(case.severity not in {'critical', 'warning'} for case in cases),
        'total': len(cases),
    }


def _inventory_summary(systems: list[ObjectStorageSystem]) -> dict[str, Any]:
    buckets = [bucket for system in systems for bucket in (system.buckets or ())]
    observed_systems = [system for system in systems if system.inventory_observed_at is not None]
    empty_observed_systems = [system for system in observed_systems if not (system.buckets or ())]
    size_values = [int(bucket.size_bytes) for bucket in buckets if bucket.size_bytes is not None]
    object_values = [int(bucket.object_count) for bucket in buckets if bucket.object_count is not None]
    quota_configured = [
        bucket for bucket in buckets if bucket.quota_state == 'configured' and bucket.quota_bytes is not None
    ]
    usage_collected = [
        bucket for bucket in buckets if bucket.size_bytes is not None and bucket.object_count is not None
    ]
    return {
        'systems': len(systems),
        'buckets': len(buckets),
        'stored_bytes': sum(size_values),
        'stored_display': format_bytes(sum(size_values)) if size_values else 'Not Collected',
        'objects': sum(object_values),
        'objects_display': format_number(sum(object_values)) if object_values else 'Not Collected',
        'quota_configured': len(quota_configured),
        'usage_collected': len(usage_collected),
        'observed_systems': len(observed_systems),
        'empty_observed_systems': len(empty_observed_systems),
    }


def _health_rows(systems: list[ObjectStorageSystem]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for system in systems:
        payload, snapshot_state = _snapshot_payload(system)
        overview = _page_metrics(payload, 'overview')
        posture = _kaori_alert_posture(system)
        buckets = list(system.buckets or ())
        inventory_usage_values = [float(bucket.size_bytes) for bucket in buckets if bucket.size_bytes is not None]
        snapshot_usage = overview.get('usage_total')
        stored_bytes = (
            snapshot_usage
            if snapshot_usage is not None
            else (sum(inventory_usage_values) if inventory_usage_values else None)
        )
        usage_source = (
            'Snapshot' if snapshot_usage is not None else ('Inventory' if inventory_usage_values else 'Not Collected')
        )
        provider_status = str(system.status or 'unknown').replace('_', ' ').title()
        analytics_usable = bool(snapshot_state.get('usable'))
        critical_alerts = int(posture.get('critical') or 0)
        warning_alerts = int(posture.get('warning') or 0)

        if provider_status.lower() not in {'connected', 'ready'}:
            overall_status = 'Critical'
            overall_tone = 'critical'
            status_reason = f'Provider state is {provider_status}.'
        elif critical_alerts > 0:
            overall_status = 'Critical'
            overall_tone = 'critical'
            status_reason = f'{critical_alerts} active critical alert signal(s).'
        elif not analytics_usable:
            overall_status = 'Warning'
            overall_tone = 'warning'
            status_reason = f'Analytics snapshot is {snapshot_state.get("label") or "not ready"}.'
        elif warning_alerts > 0:
            overall_status = 'Warning'
            overall_tone = 'warning'
            status_reason = f'{warning_alerts} active warning alert signal(s).'
        else:
            overall_status = 'Healthy'
            overall_tone = 'normal'
            status_reason = 'Inventory & analytics ready.'

        rows.append(
            {
                'id': str(system.id),
                'name': system.name,
                'environment': system.environment,
                'provider_status': provider_status,
                'inventory_updated': _human_time(system.inventory_observed_at),
                'inventory_ready': system.inventory_observed_at is not None,
                'bucket_count': len(buckets),
                'stored_display': format_bytes(stored_bytes),
                'usage_source': usage_source,
                'snapshot_label': str(snapshot_state.get('label') or 'Worker Data Required'),
                'snapshot_tone': str(snapshot_state.get('tone') or 'unknown'),
                'snapshot_ready': analytics_usable,
                'utilization_display': str(overview.get('utilization_display') or 'N/A'),
                'utilization_tone': str(overview.get('utilization_tone') or 'unknown'),
                'active_alerts': int(posture.get('total') or 0),
                'alert_cases_available': True,
                'overall_status': overall_status,
                'overall_tone': overall_tone,
                'status_reason': status_reason,
            }
        )
    return rows


def _dashboard_kpis(systems: list[ObjectStorageSystem], selected: ObjectStorageSystem | None) -> list[dict[str, str]]:
    scoped = [selected] if selected is not None else systems
    inventory = _inventory_summary(scoped)
    active_alerts = 0
    analytics_ready = 0
    operational_usage: float | None = None
    selected_utilization: str | None = None
    for system in scoped:
        payload, state = _snapshot_payload(system)
        analytics_ready += int(bool(state.get('usable')))
        overview = _page_metrics(payload, 'overview')
        active_alerts += int(_kaori_alert_posture(system).get('total') or 0)
        if selected is not None:
            operational_usage = overview.get('usage_total')
            selected_utilization = str(overview.get('utilization_display') or 'N/A')

    if selected is not None:
        usage_display = (
            format_bytes(operational_usage) if operational_usage is not None else inventory['stored_display']
        )
        return [
            {
                'label': 'Buckets',
                'value': str(inventory['buckets']),
                'description': 'Committed inventory assets',
                'icon': 'database',
            },
            {
                'label': 'Used Capacity',
                'value': usage_display,
                'description': 'Worker metrics with inventory fallback context',
                'icon': 'hard-drive',
            },
            {
                'label': 'Utilization',
                'value': selected_utilization or 'N/A',
                'description': 'Committed 24h analytics snapshot',
                'icon': 'gauge',
            },
            {
                'label': 'Active Alerts',
                'value': str(active_alerts),
                'description': 'KAORI Alert Intelligence cases',
                'icon': 'bell-ring',
            },
        ]

    return [
        {
            'label': 'Systems',
            'value': str(inventory['systems']),
            'description': 'Registered Object Storage systems',
            'icon': 'server',
        },
        {
            'label': 'Buckets',
            'value': str(inventory['buckets']),
            'description': 'Committed inventory assets',
            'icon': 'database',
        },
        {
            'label': 'Inventory Usage',
            'value': str(inventory['stored_display']),
            'description': 'Committed bucket usage evidence',
            'icon': 'hard-drive',
        },
        {
            'label': 'Analytics Ready',
            'value': f'{analytics_ready} / {len(scoped)}' if scoped else '0 / 0',
            'description': 'Usable 24h worker snapshots',
            'icon': 'database-zap',
        },
    ]


def _freshness(selected: ObjectStorageSystem | None, systems: list[ObjectStorageSystem]) -> list[dict[str, str]]:
    if selected is None:
        observed = _inventory_observation_times(systems)
        analytics_states = [
            analytics_snapshot_state(get_analytics_snapshot(system_id=str(system.id), time_range=_DASHBOARD_TIME_RANGE))
            for system in systems
        ]
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


def _alerts(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    if selected is None:
        return {
            'available': False,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'total': 0,
            'source_label': 'Alert Intelligence',
            'source_detail': 'Recommendation-origin durable alert cases',
            'rows': [],
        }
    posture = _kaori_alert_posture(selected)
    rows = [
        {
            'name': case.alert_name,
            'severity': case.severity,
            'summary': case.summary or case.target or 'KAORI recommendation alert case.',
            'state': (
                'Source Unknown'
                if case.source_state == 'unknown'
                else case.workflow_state.replace('_', ' ').title()
            ),
            'case_id': case.public_id,
        }
        for case in posture['cases'][:3]
    ]
    return {
        'available': True,
        'critical': int(posture['critical']),
        'warning': int(posture['warning']),
        'info': int(posture['info']),
        'total': int(posture['total']),
        'source_label': 'Alert Intelligence',
        'source_detail': 'Recommendation-origin durable alert cases',
        'rows': rows,
    }


def _recommended_actions(selected: ObjectStorageSystem | None) -> list[dict[str, str]]:
    if selected is None:
        return []
    findings = get_dashboard_recommendation_findings(
        domain='object_storage',
        asset_key=str(selected.id),
    )
    return [
        {
            'title': str(item.get('title') or 'Review recommendation'),
            'description': str(item.get('recommended_action') or item.get('summary') or ''),
            'category': str(item.get('category_label') or item.get('category') or 'Operations'),
            'severity': str(item.get('severity') or 'info'),
            'priority': str(item.get('priority') or 'P3'),
            'source': str(item.get('signal_source_label') or item.get('signal_source') or 'Intelligence'),
            'rule_key': str(item.get('rule_key') or ''),
            'icon': 'sparkles',
        }
        for item in findings
    ]


def _forecast(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    if selected is None:
        return build_forecast_view(None, {})
    payload, state = _forecast_payload(selected)
    return build_forecast_view(payload, state)


def _top_consumers(selected: ObjectStorageSystem | None) -> dict[str, Any]:
    if selected is None:
        return build_top_consumers_view({}, {})
    payload, state = _snapshot_payload(selected)
    metrics = _page_metrics(payload, 'top_consumers')
    return build_top_consumers_view(metrics, state)


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
        'source_status': 'Available',
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
    *,
    selected_system_id: str | None = None,
    system_health_page: str | int | None = 1,
    system_health_per_page: int = 5,
    active_tab: str = 'overview',
) -> dict[str, Any]:
    systems = _systems()
    selected = _selected_system(systems, selected_system_id)
    inventory = _inventory_summary([selected] if selected is not None else systems)
    health_scope = [selected] if selected is not None else systems
    _visible_systems, health_pagination = paginate_sequence(
        health_scope,
        page=system_health_page,
        per_page=system_health_per_page,
    )
    return {
        'systems': [{'id': str(system.id), 'name': system.name} for system in systems],
        'selected_system_id': str(selected.id) if selected is not None else None,
        'selected_system': selected,
        'active_tab': active_tab,
        'last_updated': _human_time(
            selected.inventory_observed_at
            if selected is not None
            else max(_inventory_observation_times(systems), default=None)
        ),
        'inventory': inventory,
        'system_health_pagination': health_pagination,
    }


def get_dashboard_section(
    section: str,
    *,
    selected_system_id: str | None = None,
    system_health_page: str | int | None = 1,
    system_health_per_page: int = 5,
) -> dict[str, Any]:
    systems = _systems()
    selected = _selected_system(systems, selected_system_id)
    dashboard = get_dashboard_overview(
        selected_system_id=selected_system_id,
        system_health_page=system_health_page,
        system_health_per_page=system_health_per_page,
    )
    if section in {'overview', 'system_health'}:
        health_scope = [selected] if selected is not None else systems
        visible_systems, pagination = paginate_sequence(
            health_scope,
            page=system_health_page,
            per_page=system_health_per_page,
        )
        dashboard['health_rows'] = _health_rows(visible_systems)
        dashboard['system_health_pagination'] = pagination
        if section == 'system_health':
            return dashboard
        dashboard['inventory'] = _inventory_summary([selected] if selected is not None else systems)
        dashboard['freshness'] = _freshness(selected, systems)
    elif section == 'kpi_cards':
        dashboard['kpis'] = _dashboard_kpis(systems, selected)
    elif section == 'capacity':
        dashboard['capacity'] = _capacity(selected)
        dashboard['forecast'] = _forecast(selected)
        dashboard['top_consumers'] = _top_consumers(selected)
    elif section == 'signals':
        dashboard['alerts'] = _alerts(selected)
        dashboard['forecast'] = _forecast(selected)
        dashboard['capacity'] = _capacity(selected)
        dashboard['top_consumers'] = _top_consumers(selected)
        dashboard['recommended_actions'] = _recommended_actions(selected)
    elif section == 'reporting':
        dashboard['reporting'] = _reporting(selected)
        dashboard['freshness'] = _freshness(selected, systems)
    return dashboard
