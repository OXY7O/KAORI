from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.common.analytics.metrics.contracts import MetricPoint
from app.common.analytics.params import get_allowed_time_ranges, get_selected_time_range
from app.models.object_storage import ObjectStorageSystem
from app.storage.object_storage.analytics.alert_sources import (
    alertmanager_readiness,
    build_alert_posture,
    load_alert_stream,
    resolve_materialized_alert_stream,
    selected_alert_source,
)
from app.storage.object_storage.analytics.alert_table import build_alert_table_view
from app.storage.object_storage.analytics.analysis import (
    capacity_posture,
    derive_headroom,
    error_ratio,
    forecast_posture,
    metric_risk_signals,
    performance_posture,
)
from app.storage.object_storage.analytics.bucket_evidence import (
    add_bucket_usage_shares,
    build_bucket_forecast_summary,
    build_bucket_forecast_view,
    build_bucket_rows,
)
from app.storage.object_storage.analytics.bucket_table import (
    build_bucket_forecast_table_view,
    build_bucket_table_view,
)
from app.storage.object_storage.analytics.dependencies import (
    analytics_snapshot_blocker,
    inventory_required_blocker,
    system_required_blocker,
)
from app.storage.object_storage.analytics.materialization import (
    forecast_snapshot_state,
    get_forecast_snapshot,
    read_analytics_snapshot,
)
from app.storage.object_storage.analytics.presentation import (
    PerformanceEvidence,
    build_bucket_analysis,
    build_capacity_usage_view,
    build_comparison_view,
    build_performance_view,
    build_posture_view,
    build_signal_posture,
    build_trend_view,
    format_bytes,
    format_number,
    format_percent,
    format_rate,
    utilization_percent,
    utilization_tone,
)
from app.storage.object_storage.analytics.recommendations import (
    build_recommendation_context,
    empty_recommendation_context,
)
from app.storage.object_storage.analytics.runtime import (
    EvidenceReader,
    runtime_source_state,
    source_setup,
    waiting_metrics_readiness,
    waiting_metrics_source,
)


@dataclass(frozen=True)
class PageDefinition:
    title: str
    description: str
    icon: str
    eyebrow: str


PAGES: dict[str, PageDefinition] = {
    'overview': PageDefinition(
        'Analytics Overview',
        'Review consolidated capacity, request health, consumer concentration, forecast, and evidence posture.',
        'layout-dashboard',
        'Object Storage Analytics',
    ),
    'capacity': PageDefinition(
        'Object Storage Capacity & Usage',
        'Review usable capacity, consumption trends, bucket pressure, quota posture, and growth across the selected system.',
        'database',
        'Object Storage Analytics',
    ),
    'performance': PageDefinition(
        'Object Storage Performance',
        'Review S3 request activity, error pressure, queue depth, in-flight demand, and traffic across the selected system.',
        'activity',
        'Object Storage Analytics',
    ),
    'forecast': PageDefinition(
        'Forecast',
        'Project storage growth, future utilization, and capacity exhaustion from committed operational metric history.',
        'line-chart',
        'Object Storage Analytics',
    ),
    'top_consumers': PageDefinition(
        'Top Consumers',
        'Rank buckets by storage consumption, objects, request activity, error pressure, and concentration within the selected system.',
        'users',
        'Object Storage Analytics',
    ),
    'alerts': PageDefinition(
        'Alerts & Anomalies',
        'Review active alerts from Alertmanager or Metrics Source alongside metric-derived operating signals.',
        'triangle-alert',
        'Object Storage Analytics',
    ),
}


FORECAST_HISTORY_WINDOWS = (
    {'value': '7d', 'label': 'Last 7 Days'},
    {'value': '30d', 'label': 'Last 30 Days'},
    {'value': '90d', 'label': 'Last 90 Days'},
)


def _systems() -> list[ObjectStorageSystem]:
    return list(
        ObjectStorageSystem.query.options(
            selectinload(ObjectStorageSystem.buckets),
        ).order_by(ObjectStorageSystem.name.asc())
    )


def _selected_system(systems: list[ObjectStorageSystem], system_id: str) -> ObjectStorageSystem | None:
    if not systems:
        return None
    if system_id:
        return next((item for item in systems if str(item.id) == system_id), systems[0])
    return systems[0]


def _inventory_totals(system: ObjectStorageSystem) -> dict[str, float | int]:
    buckets = list(system.buckets or ())
    return {
        'size_bytes': sum(int(item.size_bytes or 0) for item in buckets),
        'object_count': sum(int(item.object_count or 0) for item in buckets),
        'bucket_count': len(buckets),
    }


def _build_core_metrics(reader: EvidenceReader, system: ObjectStorageSystem) -> dict[str, Any]:
    total = reader.scalar('object_storage.capacity.total_bytes')
    free_metric = reader.scalar('object_storage.capacity.free_bytes')
    used = reader.scalar('object_storage.usage.total_bytes')
    objects = reader.scalar('object_storage.usage.objects')
    buckets = reader.scalar('object_storage.usage.buckets')
    inventory = _inventory_totals(system)
    free, free_source = derive_headroom(total, free_metric, used)
    utilization = utilization_percent(used, total)
    headroom_percent = utilization_percent(free, total)
    return {
        'capacity_total': total,
        'capacity_total_display': format_bytes(total),
        'capacity_free': free,
        'capacity_free_display': format_bytes(free),
        'capacity_free_source': free_source,
        'usage_total': used,
        'usage_total_display': format_bytes(used),
        'object_count': objects,
        'object_count_display': format_number(objects),
        'bucket_count': buckets,
        'bucket_count_display': format_number(buckets),
        'utilization': utilization,
        'utilization_display': format_percent(utilization),
        'utilization_tone': utilization_tone(utilization),
        'headroom_percent': headroom_percent,
        'headroom_percent_display': format_percent(headroom_percent),
        'inventory_size_display': format_bytes(inventory['size_bytes']),
        'inventory_object_count_display': format_number(inventory['object_count']),
        'inventory_bucket_count_display': format_number(inventory['bucket_count']),
        'capacity_posture': build_posture_view(capacity_posture(utilization)),
        'reconciliation': [
            build_comparison_view('Used Capacity', used, inventory['size_bytes'], formatter=format_bytes),
            build_comparison_view('Objects', objects, inventory['object_count'], formatter=format_number),
            build_comparison_view('Buckets', buckets, inventory['bucket_count'], formatter=format_number),
        ],
    }


def _add_usage_trend(payload: dict[str, Any], reader: EvidenceReader, time_range: str) -> None:
    usage_trend = reader.trend('object_storage.usage.total_bytes', time_range)
    payload['usage_trend'] = usage_trend
    payload['usage_trend_summary'] = build_trend_view(usage_trend)


def _add_request_metrics(payload: dict[str, Any], reader: EvidenceReader) -> None:
    request_rate = reader.scalar('object_storage.requests.rate')
    request_error_rate = reader.scalar('object_storage.requests.error_rate')
    waiting = reader.scalar('object_storage.requests.waiting')
    offline_nodes = reader.scalar('object_storage.health.offline_nodes')
    request_error_ratio = error_ratio(request_error_rate, request_rate)
    signals = metric_risk_signals(
        utilization=payload.get('utilization'),
        error_ratio=request_error_ratio,
        waiting=waiting,
        offline_nodes=offline_nodes,
    )
    payload.update(
        {
            'request_rate': request_rate,
            'request_rate_display': format_rate(request_rate),
            'error_rate': request_error_rate,
            'error_rate_display': format_rate(request_error_rate),
            'error_ratio': request_error_ratio,
            'error_ratio_display': format_percent(request_error_ratio),
            'success_ratio': 100.0 - request_error_ratio if request_error_ratio is not None else None,
            'success_ratio_display': (
                format_percent(100.0 - request_error_ratio) if request_error_ratio is not None else 'N/A'
            ),
            'waiting': waiting,
            'waiting_display': format_number(waiting),
            'offline_nodes': offline_nodes,
            'offline_nodes_display': format_number(offline_nodes),
            'performance_posture': build_posture_view(
                performance_posture(
                    error_percent=request_error_ratio,
                    waiting=waiting,
                    offline_nodes=offline_nodes,
                )
            ),
            'signals': signals,
            'signal_posture': build_signal_posture(signals),
        }
    )


def _add_performance_metrics(payload: dict[str, Any], reader: EvidenceReader, time_range: str) -> None:
    inflight = reader.scalar('object_storage.requests.inflight')
    received_bps = reader.scalar('object_storage.traffic.received_bps')
    sent_bps = reader.scalar('object_storage.traffic.sent_bps')
    request_trend = reader.trend('object_storage.requests.rate', time_range)
    error_trend = reader.trend('object_storage.requests.error_rate', time_range)
    total_traffic = received_bps + sent_bps if received_bps is not None and sent_bps is not None else None
    payload.update(
        {
            'inflight': inflight,
            'inflight_display': format_number(inflight),
            'received_bps': received_bps,
            'received_bps_display': format_bytes(received_bps) + '/s' if received_bps is not None else 'N/A',
            'sent_bps': sent_bps,
            'sent_bps_display': format_bytes(sent_bps) + '/s' if sent_bps is not None else 'N/A',
            'traffic_total_bps': total_traffic,
            'traffic_total_bps_display': format_bytes(total_traffic) + '/s' if total_traffic is not None else 'N/A',
            'request_trend': request_trend,
            'request_trend_summary': build_trend_view(request_trend, formatter=format_rate),
            'error_trend': error_trend,
            'error_trend_summary': build_trend_view(error_trend, formatter=format_rate),
        }
    )


def _add_performance_view(payload: dict[str, Any]) -> None:
    payload['performance'] = build_performance_view(
        PerformanceEvidence(
            request_rate=payload.get('request_rate'),
            error_rate=payload.get('error_rate'),
            error_ratio=payload.get('error_ratio'),
            success_ratio=payload.get('success_ratio'),
            waiting=payload.get('waiting'),
            inflight=payload.get('inflight'),
            offline_nodes=payload.get('offline_nodes'),
            received_bps=payload.get('received_bps'),
            sent_bps=payload.get('sent_bps'),
            request_trend_summary=payload.get('request_trend_summary') or {},
            error_trend_summary=payload.get('error_trend_summary') or {},
            bucket_analysis=payload.get('bucket_analysis') or {},
        )
    )


def _add_bucket_metrics(
    payload: dict[str, Any],
    system: ObjectStorageSystem,
    reader: EvidenceReader,
    *,
    include_activity: bool,
    include_capacity_detail: bool = True,
    sort_by: str = 'usage_bytes',
) -> None:
    rows = build_bucket_rows(
        system,
        reader,
        include_activity=include_activity,
        include_capacity_detail=include_capacity_detail,
    )
    add_bucket_usage_shares(rows, payload.get('usage_total'))
    rows.sort(key=lambda item: float(item.get(sort_by) or 0), reverse=True)
    payload['bucket_rows'] = rows
    payload['bucket_analysis'] = build_bucket_analysis(rows, payload.get('usage_total'))


def _forecast_projection_points(
    points: list[MetricPoint],
    forecast: dict[str, float | None],
) -> list[MetricPoint]:
    if not points:
        return []
    last = points[-1]
    projected: list[MetricPoint] = [{'timestamp': float(last['timestamp']), 'value': float(last['value'])}]
    projected_7d = forecast.get('projected_7d')
    projected_30d = forecast.get('projected_30d')
    if projected_7d is not None:
        projected.append({'timestamp': float(last['timestamp']) + (7 * 86400.0), 'value': float(projected_7d)})
    if projected_30d is not None:
        projected.append({'timestamp': float(last['timestamp']) + (30 * 86400.0), 'value': float(projected_30d)})
    return projected


def _apply_forecast_result(
    payload: dict[str, Any],
    *,
    points: list[MetricPoint],
    forecast: dict[str, float | None],
) -> None:
    payload['forecast'] = forecast
    payload['forecast_display'] = {
        'growth_per_day': (
            format_bytes(forecast['growth_per_day']) + '/day' if forecast['growth_per_day'] is not None else 'N/A'
        ),
        'projected_7d': format_bytes(forecast['projected_7d']),
        'projected_30d': format_bytes(forecast['projected_30d']),
        'days_to_capacity': (
            f'{forecast["days_to_capacity"]:.1f} days' if forecast['days_to_capacity'] is not None else 'N/A'
        ),
    }
    payload['forecast_posture'] = build_posture_view(
        forecast_posture(forecast['growth_per_day'], forecast['days_to_capacity'])
    )
    payload['forecast_history'] = points
    payload['forecast_projection'] = _forecast_projection_points(points, forecast)
    payload['forecast_history_summary'] = build_trend_view(points)


def _apply_unavailable_forecast(payload: dict[str, Any], state: dict[str, Any]) -> None:
    payload['forecast'] = {
        'growth_per_day': None,
        'projected_7d': None,
        'projected_30d': None,
        'days_to_capacity': None,
    }
    payload['forecast_display'] = {
        'growth_per_day': 'N/A',
        'projected_7d': 'N/A',
        'projected_30d': 'N/A',
        'days_to_capacity': 'N/A',
    }
    payload['forecast_posture'] = {
        'status': state['label'],
        'tone': state['tone'],
        'headline': 'Forecast worker evidence is not current.',
        'detail': 'Refresh the Object Storage forecast materialization before using projected capacity values.',
    }
    payload['forecast_history'] = []
    payload['forecast_projection'] = []
    payload['bucket_forecasts'] = []
    payload['bucket_forecast_summary'] = build_bucket_forecast_summary([])
    payload['forecast_history_summary'] = build_trend_view([])


def _attach_forecast_materialization(
    context: dict[str, Any],
    *,
    system: ObjectStorageSystem,
    history_window: str,
) -> None:
    snapshot = get_forecast_snapshot(system_id=system.id, history_window=history_window)
    state = forecast_snapshot_state(snapshot)
    state['history_window'] = history_window
    state['method'] = 'Linear Baseline'
    context['forecast_materialization'] = state
    payload = snapshot.payload_json if snapshot is not None and isinstance(snapshot.payload_json, dict) else None
    if state['usable'] and payload is not None:
        points: list[MetricPoint] = []
        for point in payload.get('points') or []:
            if not isinstance(point, dict):
                continue
            timestamp = point.get('timestamp')
            value = point.get('value')
            if not isinstance(timestamp, (int, float)) or not isinstance(value, (int, float)):
                continue
            points.append({'timestamp': float(timestamp), 'value': float(value)})
        raw_forecast = payload.get('forecast')
        forecast: dict[str, Any] = dict(raw_forecast) if isinstance(raw_forecast, dict) else {}
        _apply_forecast_result(
            context['metrics'],
            points=points,
            forecast={
                'growth_per_day': forecast.get('growth_per_day'),
                'projected_7d': forecast.get('projected_7d'),
                'projected_30d': forecast.get('projected_30d'),
                'days_to_capacity': forecast.get('days_to_capacity'),
            },
        )
        bucket_forecasts = build_bucket_forecast_view(payload.get('bucket_forecasts'))
        context['metrics']['bucket_forecasts'] = bucket_forecasts
        context['metrics']['bucket_forecast_summary'] = build_bucket_forecast_summary(bucket_forecasts)
        return
    _apply_unavailable_forecast(context['metrics'], state)


def _add_overview_posture(payload: dict[str, Any]) -> None:
    tones = (
        payload['capacity_posture']['tone'],
        payload['performance_posture']['tone'],
        payload['bucket_analysis']['concentration_tone'],
    )
    tone_order = {'critical': 3, 'warning': 2, 'unknown': 1, 'normal': 0}
    overall_tone = max(tones, key=lambda tone: tone_order.get(tone, 1))
    overall_labels = {
        'critical': ('Critical', 'Immediate operational triage is required.'),
        'warning': ('Attention', 'One or more operational domains require planned review.'),
        'unknown': ('Unknown', 'Operational posture is incomplete because metric evidence is missing.'),
        'normal': ('Healthy', 'No immediate capacity or request-path pressure is indicated.'),
    }
    overall_status, overall_detail = overall_labels[overall_tone]
    payload['operational_posture'] = {
        'status': overall_status,
        'tone': overall_tone,
        'detail': overall_detail,
    }


def _build_metrics(
    page_key: str,
    reader: EvidenceReader,
    system: ObjectStorageSystem,
    time_range: str,
) -> dict[str, Any]:
    payload = _build_core_metrics(reader, system)
    if page_key in {'overview', 'capacity'}:
        _add_usage_trend(payload, reader, time_range)
    if page_key in {'overview', 'performance', 'alerts'}:
        _add_request_metrics(payload, reader)
    if page_key == 'performance':
        _add_performance_metrics(payload, reader, time_range)
    if page_key in {'overview', 'capacity', 'performance', 'top_consumers'}:
        _add_bucket_metrics(
            payload,
            system,
            reader,
            include_activity=page_key in {'performance', 'top_consumers'},
            include_capacity_detail=page_key != 'performance',
            sort_by='request_rate' if page_key == 'performance' else 'usage_bytes',
        )
    if page_key == 'performance':
        _add_performance_view(payload)
    if page_key == 'capacity':
        payload['capacity_usage'] = build_capacity_usage_view(
            capacity_total=payload.get('capacity_total'),
            usage_total=payload.get('usage_total'),
            capacity_free=payload.get('capacity_free'),
            capacity_free_source=str(payload.get('capacity_free_source') or 'Unavailable'),
            utilization=payload.get('utilization'),
            trend_summary=payload.get('usage_trend_summary') or {},
            bucket_analysis=payload.get('bucket_analysis') or {},
        )
    if page_key == 'overview':
        _add_overview_posture(payload)
    return payload


def build_analytics_snapshot_payload(
    *,
    system: ObjectStorageSystem,
    time_range: str,
) -> dict[str, Any]:
    """Collect one reusable operational snapshot on the analytics worker.

    This is the only Object Storage Analytics path that performs operational
    Metrics Source and alert-source reads. UI requests consume the committed
    payload through ``read_analytics_snapshot``.
    """

    source, source_view, readiness, blocker = source_setup(system, execution_mode='background')
    if source is None or blocker is not None:
        detail = blocker.get('diagnostic_detail') if blocker else None
        raise RuntimeError(
            str(
                detail
                or (blocker.get('description') if blocker else '')
                or 'Object Storage Metrics Source is not eligible.'
            )
        )

    reader = EvidenceReader(source)
    page_metrics = {
        page_key: _build_metrics(page_key, reader, system, time_range)
        for page_key in ('overview', 'capacity', 'performance', 'top_consumers', 'alerts', 'forecast')
    }
    runtime_blocker = runtime_source_state(system, source_view, reader)
    if runtime_blocker is not None:
        raise RuntimeError(
            str(
                runtime_blocker.get('diagnostic_detail')
                or runtime_blocker.get('description')
                or 'Operational metrics query failed.'
            )
        )

    alertmanager_stream = load_alert_stream(system, selected_source='alertmanager')
    metrics_alert_stream = load_alert_stream(system, selected_source='metrics_source')
    return {
        'time_range': time_range,
        'inventory_observed_at': system.inventory_observed_at,
        'metrics_source': source_view,
        'metrics_readiness': readiness,
        'query_diagnostics': list(dict.fromkeys(item for item in reader.diagnostics if item)),
        'query_states': dict(reader.query_states),
        'page_metrics': page_metrics,
        'alert_streams': {
            'alertmanager': alertmanager_stream,
            'metrics_source': metrics_alert_stream,
        },
        'alertmanager': alertmanager_readiness(system, runtime_stream=alertmanager_stream),
    }


def _base_context(page_key: str, query_args: Any) -> tuple[dict[str, Any], ObjectStorageSystem | None, str]:
    page = PAGES.get(page_key, PAGES['overview'])
    systems = _systems()
    system_id = str(query_args.get('system_id') or '').strip()
    system = _selected_system(systems, system_id)
    time_range = get_selected_time_range(query_args=query_args, default='24h')
    history_window = str(query_args.get('history_window') or '30d').strip()
    if history_window not in {item['value'] for item in FORECAST_HISTORY_WINDOWS}:
        history_window = '30d'
    context: dict[str, Any] = {
        'page_key': page_key,
        'page': page,
        'systems': systems,
        'system': system,
        'selected_time_range': time_range,
        'allowed_time_ranges': get_allowed_time_ranges(),
        'selected_forecast_history_window': history_window,
        'forecast_history_windows': FORECAST_HISTORY_WINDOWS,
        'analytics_materialization': {
            'state': 'missing',
            'label': 'Worker Data Required',
            'tone': 'warning',
            'usable': False,
            'stale': False,
            'time_range': time_range,
            'generated_at': None,
            'last_attempt_at': None,
            'last_error': None,
            'dispatch_error': None,
        },
        'forecast_materialization': {
            'state': 'missing',
            'label': 'Worker Data Required',
            'tone': 'warning',
            'usable': False,
            'history_window': history_window,
            'method': 'Linear Baseline',
            'generated_at': None,
            'last_attempt_at': None,
            'last_error': None,
        },
        'dependency_blocker': None,
        'metrics_source': waiting_metrics_source(),
        'metrics_readiness': waiting_metrics_readiness(),
        'selected_alert_source': selected_alert_source(query_args),
        'alert_source': {
            'selected_source': selected_alert_source(query_args),
            'resolved_source': 'none',
            'resolved_label': 'Unavailable',
            'configured': False,
            'connected': False,
            'label': 'Waiting for System',
            'tone': 'unknown',
            'detail': 'Select an Object Storage system.',
            'rows': [],
            'instance_name': None,
            'fallback_used': False,
            'fallback_reason': None,
            'checked_at': None,
        },
        'alertmanager': {
            'configured': False,
            'connected': False,
            'label': 'Waiting for Analytics Snapshot' if system is not None else 'Not Configured',
            'tone': 'unknown',
            'description': (
                'Alertmanager readiness is read from the committed analytics snapshot.'
                if system is not None
                else 'Select an Object Storage system.'
            ),
            'instance_name': None,
            'profile': 'object-storage-alerts-v1',
        },
        'alert_posture': {
            'total': 0,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'firing': 0,
            'pending': 0,
            'silenced': 0,
            'inhibited': 0,
            'status': 'Unknown',
            'tone': 'unknown',
            'detail': 'Select an Object Storage system.',
        },
        'alert_table': None,
        **empty_recommendation_context(),
        'metrics': {},
        'bucket_table': None,
        'bucket_forecast_table': None,
        'query_diagnostics': [],
        'inventory_observed_at': system.inventory_observed_at if system is not None else None,
    }
    return context, system, time_range


def _unavailable_alert_metrics() -> dict[str, Any]:
    signals = metric_risk_signals(
        utilization=None,
        error_ratio=None,
        waiting=None,
        offline_nodes=None,
    )
    return {
        'signals': signals,
        'signal_posture': build_signal_posture(signals),
    }


def _queue_analytics_snapshot_refresh(
    *,
    system: ObjectStorageSystem,
    time_range: str,
) -> tuple[bool, str | None]:
    """Queue a missing/stale snapshot without performing source reads in the web request."""

    try:
        from app.platform_operations.jobs.dispatcher import dispatch_registered_job

        outcome = dispatch_registered_job(
            job_key='object_storage.analytics.materialize',
            trigger_type='on_demand',
            requested_by_user_id=None,
            parameters={'system_id': str(system.id), 'time_range': time_range},
        )
        return bool(outcome.accepted), None if outcome.accepted else str(outcome.message or '') or None
    except (CeleryError, KombuOperationalError, LookupError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        return False, f'Analytics refresh could not be queued: {exc}'


def _attach_committed_analytics_snapshot(
    context: dict[str, Any],
    *,
    system: ObjectStorageSystem,
    time_range: str,
) -> dict[str, Any] | None:
    payload, state = read_analytics_snapshot(system_id=system.id, time_range=time_range)
    state = {**state, 'dispatch_error': None, 'refresh_dispatched': False}
    if payload is None or state.get('stale'):
        dispatched, dispatch_error = _queue_analytics_snapshot_refresh(system=system, time_range=time_range)
        state['refresh_dispatched'] = dispatched
        state['dispatch_error'] = dispatch_error
    context['analytics_materialization'] = state
    if payload is None:
        context['dependency_blocker'] = analytics_snapshot_blocker(
            system,
            time_range=time_range,
            label=str(state.get('label') or 'Worker Data Required'),
            detail=str(state.get('last_error') or state.get('dispatch_error') or '').strip() or None,
        )
        return None

    context['metrics_source'] = dict(payload.get('metrics_source') or waiting_metrics_source())
    context['metrics_readiness'] = dict(payload.get('metrics_readiness') or waiting_metrics_readiness())
    context['query_diagnostics'] = list(payload.get('query_diagnostics') or [])
    context['inventory_observed_at'] = payload.get('inventory_observed_at') or context.get('inventory_observed_at')
    return payload


def _apply_alert_snapshot_context(
    context: dict[str, Any],
    *,
    payload: dict[str, Any],
    system: ObjectStorageSystem,
    query_args: Any,
) -> None:
    streams_value = payload.get('alert_streams')
    streams = cast(dict[str, Any], streams_value) if isinstance(streams_value, dict) else {}
    alert_stream = resolve_materialized_alert_stream(
        streams,
        selected_source=context['selected_alert_source'],
    )
    context['alert_source'] = alert_stream
    context['alertmanager'] = dict(payload.get('alertmanager') or context['alertmanager'])
    context['alert_posture'] = build_alert_posture(alert_stream)
    context['alert_table'] = build_alert_table_view(
        alert_stream.get('rows') or [],
        query_args,
        system=system,
        selected_source=context['selected_alert_source'],
    )
    page_metrics_value = payload.get('page_metrics')
    page_metrics = cast(dict[str, Any], page_metrics_value) if isinstance(page_metrics_value, dict) else {}
    context['metrics'] = dict(page_metrics.get('alerts') or _unavailable_alert_metrics())
    metrics_runtime_state = str(context['metrics_source'].get('runtime_state') or '')
    metrics_operational = metrics_runtime_state in {'operational', 'degraded'}
    context['alerts_evidence_available'] = bool(alert_stream.get('connected')) or metrics_operational
    context['alerts_degraded'] = not (bool(alert_stream.get('connected')) and metrics_operational)


def get_object_storage_analytics_context(page_key: str, query_args: Any) -> dict[str, Any]:
    context, system, time_range = _base_context(page_key, query_args)
    if system is None:
        context['dependency_blocker'] = system_required_blocker()
        return context
    if system.inventory_observed_at is None:
        context['dependency_blocker'] = inventory_required_blocker(system)
        return context

    context.update(build_recommendation_context(system, page_key=page_key))

    payload = _attach_committed_analytics_snapshot(context, system=system, time_range=time_range)
    if payload is None:
        return context

    if page_key == 'alerts':
        _apply_alert_snapshot_context(context, payload=payload, system=system, query_args=query_args)
        return context

    page_metrics_value = payload.get('page_metrics')
    page_metrics = cast(dict[str, Any], page_metrics_value) if isinstance(page_metrics_value, dict) else {}
    metrics = page_metrics.get(page_key)
    if not isinstance(metrics, dict):
        context['dependency_blocker'] = analytics_snapshot_blocker(
            system,
            time_range=time_range,
            label='Snapshot Contract Invalid',
            detail=f'Committed analytics snapshot does not contain the {page_key} dataset.',
        )
        return context
    context['metrics'] = metrics

    if page_key in {'overview', 'forecast'}:
        history_window = '30d' if page_key == 'overview' else context['selected_forecast_history_window']
        _attach_forecast_materialization(context, system=system, history_window=history_window)

    if page_key == 'forecast':
        context['bucket_forecast_table'] = build_bucket_forecast_table_view(
            context['metrics'].get('bucket_forecasts') or [],
            query_args,
            system=system,
            history_window=context['selected_forecast_history_window'],
        )

    if page_key in {'capacity', 'performance', 'top_consumers'}:
        context['bucket_table'] = build_bucket_table_view(
            context['metrics'].get('bucket_rows') or [],
            query_args,
            page_key=page_key,
            system=system,
            time_range=time_range,
        )
    return context


def get_object_storage_alert_table_context(query_args: Any) -> dict[str, Any]:
    return get_object_storage_analytics_context('alerts', query_args)


def get_object_storage_bucket_table_context(page_key: str, query_args: Any) -> dict[str, Any]:
    if page_key not in {'capacity', 'performance', 'top_consumers'}:
        page_key = 'top_consumers'
    return get_object_storage_analytics_context(page_key, query_args)


def get_object_storage_bucket_forecast_table_context(query_args: Any) -> dict[str, Any]:
    return get_object_storage_analytics_context('forecast', query_args)
