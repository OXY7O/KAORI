from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import selectinload

from app.common.analytics.metrics.contracts import MetricPoint
from app.common.analytics.params import get_allowed_time_ranges, get_selected_time_range
from app.models.object_storage import ObjectStorageSystem
from app.storage.object_storage.analytics.alert_sources import (
    alertmanager_readiness,
    build_alert_posture,
    load_alert_stream,
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
from app.storage.object_storage.analytics.bucket_table import build_bucket_table_view
from app.storage.object_storage.analytics.dependencies import (
    inventory_required_blocker,
    system_required_blocker,
)
from app.storage.object_storage.analytics.materialization import forecast_snapshot_state, get_forecast_snapshot
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


def _metric_evidence_label(state: str, *, bucket_scoped: bool = False) -> str:
    labels = {
        'unsupported': 'Metric Not Scraped',
        'blocked': 'Metric Contract Blocked',
        'not_validated': 'Validation Required',
        'failed': 'Runtime Query Failed',
        'skipped': 'Runtime Query Skipped',
        'no_data': 'No Current Samples',
    }
    if state == 'ready' and bucket_scoped:
        return 'No Bucket Series'
    return labels.get(state, 'Unavailable')


def _add_bucket_usage_shares(rows: list[dict[str, Any]], usage_total: float | None) -> None:
    for row in rows:
        row['usage_share'] = utilization_percent(row.get('usage_bytes'), usage_total)
        row['usage_share_display'] = format_percent(row['usage_share'])


def _bucket_rows(
    system: ObjectStorageSystem,
    reader: EvidenceReader,
    *,
    include_activity: bool,
    include_capacity_detail: bool = True,
) -> list[dict[str, Any]]:
    usage = reader.vector('object_storage.bucket.usage')
    objects = reader.vector('object_storage.bucket.objects') if include_capacity_detail else {}
    quota = reader.vector('object_storage.bucket.quota') if include_capacity_detail else {}
    request_rate = reader.vector('object_storage.bucket.request_rate') if include_activity else {}
    error_rate = reader.vector('object_storage.bucket.error_rate') if include_activity else {}

    usage_state = reader.evidence_state('object_storage.bucket.usage')
    objects_state = reader.evidence_state('object_storage.bucket.objects') if include_capacity_detail else 'not_requested'
    quota_metric_state = reader.evidence_state('object_storage.bucket.quota') if include_capacity_detail else 'not_requested'
    request_state = reader.evidence_state('object_storage.bucket.request_rate') if include_activity else 'not_requested'
    error_state = reader.evidence_state('object_storage.bucket.error_rate') if include_activity else 'not_requested'

    inventory = {bucket.name: bucket for bucket in system.buckets or ()}
    names = set(inventory) | set(usage) | set(objects) | set(quota) | set(request_rate) | set(error_rate)
    rows: list[dict[str, Any]] = []
    for name in names:
        bucket = inventory.get(name)
        size = usage.get(name)
        usage_source = reader.source_label if size is not None else _metric_evidence_label(usage_state, bucket_scoped=True)
        if size is None and bucket is not None and bucket.size_bytes is not None:
            size = float(bucket.size_bytes)
            usage_source = 'Committed Snapshot'

        object_count = objects.get(name)
        objects_source = (
            reader.source_label
            if object_count is not None
            else _metric_evidence_label(objects_state, bucket_scoped=True)
        )
        if object_count is None and bucket is not None and bucket.object_count is not None:
            object_count = float(bucket.object_count)
            objects_source = 'Committed Snapshot'

        quota_bytes = quota.get(name)
        quota_state = 'configured' if quota_bytes is not None else 'unknown'
        quota_evidence_code = 'metrics_source' if quota_bytes is not None else None
        quota_source = (
            reader.source_label
            if quota_bytes is not None
            else _metric_evidence_label(quota_metric_state, bucket_scoped=True)
        )
        if bucket is not None:
            inventory_quota_state = str(bucket.quota_state or 'not_collected').strip().lower().replace('-', '_')
            if quota_bytes is None and bucket.quota_bytes is not None:
                quota_bytes = float(bucket.quota_bytes)
                quota_state = 'configured'
                quota_source = 'Committed Snapshot'
                quota_evidence_code = bucket.quota_evidence_code
            elif quota_bytes is None and inventory_quota_state == 'not_configured':
                quota_state = 'not_configured'
                quota_source = 'Committed Snapshot'
                quota_evidence_code = bucket.quota_evidence_code
            elif quota_bytes is None and inventory_quota_state in {'not_collected', 'not_supported'}:
                quota_state = inventory_quota_state
                quota_source = 'Inventory Quota Not Collected' if inventory_quota_state == 'not_collected' else 'Inventory Quota Unsupported'
                quota_evidence_code = bucket.quota_evidence_code
            elif quota_bytes is None and inventory_quota_state == 'configured':
                quota_state = 'inconsistent'
                quota_source = 'Inventory Evidence Incomplete'
                quota_evidence_code = bucket.quota_evidence_code

        bucket_request_rate = request_rate.get(name)
        request_source = (
            reader.source_label
            if bucket_request_rate is not None
            else _metric_evidence_label(request_state, bucket_scoped=True)
        )
        bucket_error_rate = error_rate.get(name)
        error_source = (
            reader.source_label
            if bucket_error_rate is not None
            else _metric_evidence_label(error_state, bucket_scoped=True)
        )
        bucket_error_ratio = error_ratio(bucket_error_rate, bucket_request_rate)
        quota_utilization = utilization_percent(size, quota_bytes)
        quota_tone = utilization_tone(quota_utilization) if quota_bytes is not None else 'unknown'
        if quota_state == 'not_configured':
            quota_display = 'Not Configured'
            quota_utilization_display = 'Not Applicable'
            quota_status_label = 'No Quota Configured'
            quota_status_tone = 'info'
        elif quota_state == 'inconsistent':
            quota_display = 'Evidence Incomplete'
            quota_utilization_display = 'Unknown'
            quota_status_label = 'Review Inventory Evidence'
            quota_status_tone = 'warning'
        elif quota_state == 'not_collected':
            quota_display = 'N/A'
            quota_utilization_display = 'Unknown'
            quota_status_label = 'Quota Not Collected'
            quota_status_tone = 'warning'
        elif quota_state == 'not_supported':
            quota_display = 'N/A'
            quota_utilization_display = 'Not Available'
            quota_status_label = 'Quota Collection Unsupported'
            quota_status_tone = 'unknown'
        elif quota_bytes is None:
            quota_display = 'N/A'
            quota_utilization_display = 'N/A'
            quota_status_label = _metric_evidence_label(quota_metric_state, bucket_scoped=True)
            quota_status_tone = 'unknown'
        elif quota_utilization is not None and quota_utilization >= 95:
            quota_display = format_bytes(quota_bytes)
            quota_utilization_display = format_percent(quota_utilization)
            quota_status_label = 'Critical'
            quota_status_tone = 'critical'
        elif quota_utilization is not None and quota_utilization >= 85:
            quota_display = format_bytes(quota_bytes)
            quota_utilization_display = format_percent(quota_utilization)
            quota_status_label = 'Pressure'
            quota_status_tone = 'warning'
        else:
            quota_display = format_bytes(quota_bytes)
            quota_utilization_display = format_percent(quota_utilization)
            quota_status_label = 'Within Quota'
            quota_status_tone = 'normal'

        rows.append(
            {
                'name': name,
                'usage_bytes': size,
                'usage_display': format_bytes(size),
                'usage_source': usage_source,
                'usage_evidence_state': usage_state,
                'objects': object_count,
                'objects_display': format_number(object_count),
                'objects_source': objects_source,
                'objects_evidence_state': objects_state,
                'quota_bytes': quota_bytes,
                'quota_display': quota_display,
                'quota_source': quota_source,
                'quota_state': quota_state,
                'quota_evidence_code': quota_evidence_code,
                'quota_utilization': quota_utilization,
                'quota_utilization_display': quota_utilization_display,
                'quota_tone': quota_tone,
                'quota_status_label': quota_status_label,
                'quota_status_tone': quota_status_tone,
                'request_rate': bucket_request_rate,
                'request_rate_display': format_rate(bucket_request_rate),
                'request_source': request_source,
                'request_evidence_state': request_state,
                'error_rate': bucket_error_rate,
                'error_rate_display': format_rate(bucket_error_rate),
                'error_source': error_source,
                'error_evidence_state': error_state,
                'error_ratio': bucket_error_ratio,
                'error_ratio_display': format_percent(bucket_error_ratio),
                'source': usage_source,
            }
        )
    rows.sort(key=lambda item: float(item['usage_bytes'] or 0), reverse=True)
    return rows


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
    rows = _bucket_rows(
        system,
        reader,
        include_activity=include_activity,
        include_capacity_detail=include_capacity_detail,
    )
    _add_bucket_usage_shares(rows, payload.get('usage_total'))
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


def _bucket_forecast_view(raw_rows: object) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_rows if isinstance(raw_rows, list) else []:
        if not isinstance(raw, dict):
            continue
        forecast = raw.get('forecast') if isinstance(raw.get('forecast'), dict) else {}
        history_state = str(raw.get('history_state') or ('ready' if int(raw.get('sample_count') or 0) >= 2 else 'no_data'))
        current = raw.get('current_bytes')
        inventory_usage = raw.get('inventory_usage_bytes')
        quota = raw.get('quota_bytes')
        projected_30d = forecast.get('projected_30d')
        days_to_quota = forecast.get('days_to_capacity')
        quota_utilization = utilization_percent(current, quota)
        projected_quota_utilization = utilization_percent(projected_30d, quota)
        growth_per_day = forecast.get('growth_per_day')
        if history_state != 'ready':
            watch_label, watch_tone = 'Insufficient History', 'unknown'
        elif days_to_quota is not None and days_to_quota <= 30:
            watch_label, watch_tone = 'Critical · Quota ≤ 30d', 'critical'
        elif days_to_quota is not None and days_to_quota <= 90:
            watch_label, watch_tone = 'Warning · Quota ≤ 90d', 'warning'
        elif projected_quota_utilization is not None and projected_quota_utilization >= 95:
            watch_label, watch_tone = 'Critical · Projected ≥ 95%', 'critical'
        elif projected_quota_utilization is not None and projected_quota_utilization >= 85:
            watch_label, watch_tone = 'Warning · Projected ≥ 85%', 'warning'
        elif growth_per_day is not None and growth_per_day > 0:
            watch_label, watch_tone = 'Growth Watch', 'info'
        elif growth_per_day is not None:
            watch_label, watch_tone = 'Stable / Decreasing', 'normal'
        else:
            watch_label, watch_tone = 'Insufficient History', 'unknown'
        rows.append(
            {
                'name': str(raw.get('name') or 'Unknown Bucket'),
                'sample_count': int(raw.get('sample_count') or 0),
                'history_state': history_state,
                'history_label': (
                    'Forecast Ready'
                    if history_state == 'ready'
                    else ('One Range Sample' if history_state == 'partial' else 'No Range Series')
                ),
                'history_tone': 'normal' if history_state == 'ready' else 'unknown',
                'current_bytes': current,
                'current_display': format_bytes(current),
                'inventory_usage_bytes': inventory_usage,
                'inventory_usage_display': format_bytes(inventory_usage),
                'growth_per_day': growth_per_day,
                'growth_per_day_display': format_bytes(growth_per_day) + '/day' if growth_per_day is not None else 'N/A',
                'projected_30d': projected_30d,
                'projected_30d_display': format_bytes(projected_30d),
                'quota_bytes': quota,
                'quota_display': format_bytes(quota) if quota is not None else 'Not Configured',
                'quota_utilization': quota_utilization,
                'quota_utilization_display': format_percent(quota_utilization),
                'projected_quota_utilization': projected_quota_utilization,
                'projected_quota_utilization_display': format_percent(projected_quota_utilization),
                'days_to_quota': days_to_quota,
                'days_to_quota_display': f'{days_to_quota:.1f} days' if days_to_quota is not None else 'No ETA',
                'watch_label': watch_label,
                'watch_tone': watch_tone,
            }
        )
    tone_order = {'critical': 4, 'warning': 3, 'info': 2, 'unknown': 1, 'normal': 0}
    rows.sort(
        key=lambda row: (
            tone_order.get(str(row['watch_tone']), 1),
            float(row.get('projected_30d') or row.get('current_bytes') or row.get('inventory_usage_bytes') or 0),
        ),
        reverse=True,
    )
    return rows


def _bucket_forecast_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'tracked_count': len(rows),
        'ready_count': sum(row.get('history_state') == 'ready' for row in rows),
        'attention_count': sum(row.get('watch_tone') in {'critical', 'warning'} for row in rows),
        'critical_count': sum(row.get('watch_tone') == 'critical' for row in rows),
        'warning_count': sum(row.get('watch_tone') == 'warning' for row in rows),
        'quota_bounded_count': sum(row.get('quota_bytes') is not None for row in rows),
        'history_gap_count': sum(row.get('history_state') != 'ready' for row in rows),
    }


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
    payload['bucket_forecast_summary'] = _bucket_forecast_summary([])
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
        bucket_forecasts = _bucket_forecast_view(payload.get('bucket_forecasts'))
        context['metrics']['bucket_forecasts'] = bucket_forecasts
        context['metrics']['bucket_forecast_summary'] = _bucket_forecast_summary(bucket_forecasts)
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
        'alertmanager': (
            alertmanager_readiness(system)
            if system is not None
            else {
                'configured': False,
                'connected': False,
                'label': 'Not Configured',
                'tone': 'unknown',
                'description': 'Select an Object Storage system.',
                'instance_name': None,
                'profile': 'object-storage-alerts-v1',
            }
        ),
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
        'metrics': {},
        'bucket_table': None,
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


def _get_alerts_context(
    context: dict[str, Any],
    system: ObjectStorageSystem,
    query_args: Any,
    time_range: str,
) -> dict[str, Any]:
    alert_stream = load_alert_stream(system, selected_source=context['selected_alert_source'])
    context['alert_source'] = alert_stream
    context['alertmanager'] = alertmanager_readiness(system, runtime_stream=alert_stream)
    context['alert_posture'] = build_alert_posture(alert_stream)
    context['alert_table'] = build_alert_table_view(
        alert_stream.get('rows') or [],
        query_args,
        system=system,
        selected_source=context['selected_alert_source'],
    )

    source, source_view, readiness, blocker = source_setup(system)
    context['metrics_source'] = source_view
    context['metrics_readiness'] = readiness
    metrics_operational = False
    if source is not None and blocker is None:
        reader = EvidenceReader(source)
        context['metrics'] = _build_metrics('alerts', reader, system, time_range)
        context['query_diagnostics'] = list(dict.fromkeys(item for item in reader.diagnostics if item))
        runtime_blocker = runtime_source_state(system, context['metrics_source'], reader)
        metrics_operational = runtime_blocker is None
        if not metrics_operational:
            context['metrics'] = _unavailable_alert_metrics()
    else:
        context['metrics'] = _unavailable_alert_metrics()

    context['alerts_evidence_available'] = bool(alert_stream.get('connected')) or metrics_operational
    context['alerts_degraded'] = not (bool(alert_stream.get('connected')) and metrics_operational)
    return context


def get_object_storage_analytics_context(page_key: str, query_args: Any) -> dict[str, Any]:
    context, system, time_range = _base_context(page_key, query_args)
    if system is None:
        context['dependency_blocker'] = system_required_blocker()
        return context
    if system.inventory_observed_at is None:
        context['dependency_blocker'] = inventory_required_blocker(system)
        return context

    if page_key == 'alerts':
        return _get_alerts_context(context, system, query_args, time_range)

    source, source_view, readiness, blocker = source_setup(system)
    context['metrics_source'] = source_view
    context['metrics_readiness'] = readiness
    if source is None or blocker is not None:
        context['dependency_blocker'] = blocker
        return context

    reader = EvidenceReader(source)
    context['metrics'] = _build_metrics(page_key, reader, system, time_range)
    context['query_diagnostics'] = list(dict.fromkeys(item for item in reader.diagnostics if item))
    runtime_blocker = runtime_source_state(system, context['metrics_source'], reader)
    if runtime_blocker is not None:
        context['dependency_blocker'] = runtime_blocker
        return context

    if page_key in {'overview', 'forecast'}:
        history_window = '30d' if page_key == 'overview' else context['selected_forecast_history_window']
        _attach_forecast_materialization(context, system=system, history_window=history_window)

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
    context, system, _ = _base_context('alerts', query_args)
    if system is None:
        context['dependency_blocker'] = system_required_blocker()
        return context
    if system.inventory_observed_at is None:
        context['dependency_blocker'] = inventory_required_blocker(system)
        return context
    alert_stream = load_alert_stream(system, selected_source=context['selected_alert_source'])
    context['alert_source'] = alert_stream
    context['alertmanager'] = alertmanager_readiness(system, runtime_stream=alert_stream)
    context['alert_posture'] = build_alert_posture(alert_stream)
    context['alert_table'] = build_alert_table_view(
        alert_stream.get('rows') or [],
        query_args,
        system=system,
        selected_source=context['selected_alert_source'],
    )
    return context


def get_object_storage_bucket_table_context(page_key: str, query_args: Any) -> dict[str, Any]:
    if page_key not in {'capacity', 'performance', 'top_consumers'}:
        page_key = 'top_consumers'
    context, system, time_range = _base_context(page_key, query_args)
    if system is None:
        context['dependency_blocker'] = system_required_blocker()
        return context
    if system.inventory_observed_at is None:
        context['dependency_blocker'] = inventory_required_blocker(system)
        return context

    source, source_view, readiness, blocker = source_setup(system)
    context['metrics_source'] = source_view
    context['metrics_readiness'] = readiness
    if source is None or blocker is not None:
        context['dependency_blocker'] = blocker
        return context

    reader = EvidenceReader(source)
    core = _build_core_metrics(reader, system)
    rows = _bucket_rows(
        system,
        reader,
        include_activity=page_key in {'performance', 'top_consumers'},
        include_capacity_detail=page_key != 'performance',
    )
    if page_key == 'performance':
        rows.sort(key=lambda item: float(item.get('request_rate') or 0), reverse=True)
    _add_bucket_usage_shares(rows, core.get('usage_total'))
    context['metrics'] = {'bucket_rows': rows}
    context['query_diagnostics'] = list(dict.fromkeys(item for item in reader.diagnostics if item))
    runtime_blocker = runtime_source_state(system, context['metrics_source'], reader)
    if runtime_blocker is not None:
        context['dependency_blocker'] = runtime_blocker
        return context
    context['bucket_table'] = build_bucket_table_view(
        rows,
        query_args,
        page_key=page_key,
        system=system,
        time_range=time_range,
    )
    return context
