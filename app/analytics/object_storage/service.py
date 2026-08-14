from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import selectinload

from app.analytics.object_storage.analysis import (
    capacity_posture,
    derive_headroom,
    error_ratio,
    forecast_posture,
    metric_risk_signals,
    performance_posture,
)
from app.analytics.object_storage.bucket_table import build_bucket_table_view
from app.analytics.object_storage.dependencies import system_required_blocker
from app.analytics.object_storage.forecasting import linear_forecast
from app.analytics.object_storage.presentation import (
    build_bucket_analysis,
    build_comparison_view,
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
from app.analytics.object_storage.runtime import (
    EvidenceReader,
    runtime_source_state,
    source_setup,
    waiting_metrics_readiness,
    waiting_metrics_source,
)
from app.analytics.shared.params import get_allowed_time_ranges, get_selected_time_range
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem


@dataclass(frozen=True)
class PageDefinition:
    title: str
    description: str
    icon: str
    eyebrow: str


PAGES: dict[str, PageDefinition] = {
    'overview': PageDefinition(
        'Overview',
        'Review capacity, request health, demand concentration, growth, and operational readiness at a glance.',
        'layout-dashboard',
        'Object Storage Analytics',
    ),
    'capacity': PageDefinition(
        'Capacity & Usage',
        'Review usable capacity, consumption, bucket pressure, and growth.',
        'database',
        'Object Storage Analytics',
    ),
    'performance': PageDefinition(
        'Performance',
        'Review S3 request activity, errors, queue pressure, and traffic.',
        'activity',
        'Object Storage Analytics',
    ),
    'forecast': PageDefinition(
        'Forecast',
        'Project storage growth and capacity exhaustion from operational metric history.',
        'line-chart',
        'Object Storage Analytics',
    ),
    'top_consumers': PageDefinition(
        'Top Consumers',
        'Rank buckets by storage, objects, request activity, and error pressure.',
        'users',
        'Object Storage Analytics',
    ),
    'alerts': PageDefinition(
        'Alerts & Anomalies',
        'Review metric-derived risk signals while Alertmanager lifecycle integration remains optional.',
        'triangle-alert',
        'Object Storage Analytics',
    ),
}


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


def _alertmanager_binding(system_id: str) -> dict[str, str | bool]:
    binding = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationBinding.asset_type == 'object_storage_system',
            IntegrationBinding.asset_key == str(system_id),
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.provider_type == 'alertmanager',
            IntegrationInstance.enabled.is_(True),
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .first()
    )
    if binding is None:
        return {
            'configured': False,
            'label': 'Not Configured',
            'tone': 'unknown',
            'description': (
                'Alertmanager is optional for this release. '
                'Metric-derived signals remain available from the operational metrics source.'
            ),
        }
    ready = str(binding.validation_status or '').strip().lower() == 'ready'
    return {
        'configured': True,
        'label': 'Ready' if ready else 'Validation Required',
        'tone': 'normal' if ready else 'warning',
        'description': 'Alert lifecycle correlation is reserved for the Alertmanager integration phase.',
    }


def _bucket_rows(
    system: ObjectStorageSystem,
    reader: EvidenceReader,
    *,
    include_activity: bool,
) -> list[dict[str, Any]]:
    usage = reader.vector('object_storage.bucket.usage')
    objects = reader.vector('object_storage.bucket.objects')
    quota = reader.vector('object_storage.bucket.quota')
    request_rate = reader.vector('object_storage.bucket.request_rate') if include_activity else {}
    error_rate = reader.vector('object_storage.bucket.error_rate') if include_activity else {}
    inventory = {bucket.name: bucket for bucket in system.buckets or ()}
    names = set(inventory) | set(usage) | set(objects) | set(quota) | set(request_rate) | set(error_rate)
    rows: list[dict[str, Any]] = []
    for name in names:
        bucket = inventory.get(name)
        size = usage.get(name)
        usage_source = reader.source_label if size is not None else 'Unavailable'
        if size is None and bucket is not None and bucket.size_bytes is not None:
            size = float(bucket.size_bytes)
            usage_source = 'Committed Snapshot'

        object_count = objects.get(name)
        objects_source = reader.source_label if object_count is not None else 'Unavailable'
        if object_count is None and bucket is not None and bucket.object_count is not None:
            object_count = float(bucket.object_count)
            objects_source = 'Committed Snapshot'

        quota_bytes = quota.get(name)
        quota_source = reader.source_label if quota_bytes is not None else 'Unavailable'
        if quota_bytes is None and bucket is not None and bucket.quota_bytes is not None:
            quota_bytes = float(bucket.quota_bytes)
            quota_source = 'Committed Snapshot'

        bucket_request_rate = request_rate.get(name)
        bucket_error_rate = error_rate.get(name)
        bucket_error_ratio = error_ratio(bucket_error_rate, bucket_request_rate)
        quota_utilization = utilization_percent(size, quota_bytes)
        quota_tone = utilization_tone(quota_utilization) if quota_bytes is not None else 'unknown'
        rows.append(
            {
                'name': name,
                'usage_bytes': size,
                'usage_display': format_bytes(size),
                'usage_source': usage_source,
                'objects': object_count,
                'objects_display': format_number(object_count),
                'objects_source': objects_source,
                'quota_bytes': quota_bytes,
                'quota_display': format_bytes(quota_bytes),
                'quota_source': quota_source,
                'quota_utilization': quota_utilization,
                'quota_utilization_display': format_percent(quota_utilization),
                'quota_tone': quota_tone,
                'request_rate': bucket_request_rate,
                'request_rate_display': format_rate(bucket_request_rate),
                'error_rate': bucket_error_rate,
                'error_rate_display': format_rate(bucket_error_rate),
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


def _add_bucket_metrics(
    payload: dict[str, Any],
    system: ObjectStorageSystem,
    reader: EvidenceReader,
    *,
    include_activity: bool,
) -> None:
    rows = _bucket_rows(system, reader, include_activity=include_activity)
    payload['bucket_rows'] = rows
    payload['bucket_analysis'] = build_bucket_analysis(rows, payload.get('usage_total'))


def _add_forecast_metrics(payload: dict[str, Any]) -> None:
    forecast = linear_forecast(payload.get('usage_trend', []), capacity_bytes=payload.get('capacity_total'))
    payload['forecast'] = forecast
    payload['forecast_display'] = {
        'growth_per_day': (
            format_bytes(forecast['growth_per_day']) + '/day'
            if forecast['growth_per_day'] is not None
            else 'N/A'
        ),
        'projected_7d': format_bytes(forecast['projected_7d']),
        'projected_30d': format_bytes(forecast['projected_30d']),
        'days_to_capacity': (
            f"{forecast['days_to_capacity']:.1f} days" if forecast['days_to_capacity'] is not None else 'N/A'
        ),
    }
    payload['forecast_posture'] = build_posture_view(
        forecast_posture(forecast['growth_per_day'], forecast['days_to_capacity'])
    )


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
    if page_key in {'overview', 'capacity', 'forecast'}:
        _add_usage_trend(payload, reader, time_range)
    if page_key in {'overview', 'performance', 'alerts'}:
        _add_request_metrics(payload, reader)
    if page_key == 'performance':
        _add_performance_metrics(payload, reader, time_range)
    if page_key in {'overview', 'capacity', 'top_consumers'}:
        _add_bucket_metrics(payload, system, reader, include_activity=page_key == 'top_consumers')
    if page_key in {'overview', 'forecast'}:
        _add_forecast_metrics(payload)
    if page_key == 'overview':
        _add_overview_posture(payload)
    return payload


def _base_context(page_key: str, query_args: Any) -> tuple[dict[str, Any], ObjectStorageSystem | None, str]:
    page = PAGES.get(page_key, PAGES['overview'])
    systems = _systems()
    system_id = str(query_args.get('system_id') or '').strip()
    system = _selected_system(systems, system_id)
    time_range = get_selected_time_range(query_args=query_args, default='24h')
    context: dict[str, Any] = {
        'page_key': page_key,
        'page': page,
        'systems': systems,
        'system': system,
        'selected_time_range': time_range,
        'allowed_time_ranges': get_allowed_time_ranges(),
        'dependency_blocker': None,
        'metrics_source': waiting_metrics_source(),
        'metrics_readiness': waiting_metrics_readiness(),
        'alertmanager': (
            _alertmanager_binding(system.id)
            if system is not None
            else {
                'configured': False,
                'label': 'Not Configured',
                'tone': 'unknown',
                'description': 'Select an Object Storage system.',
            }
        ),
        'metrics': {},
        'bucket_table': None,
        'query_diagnostics': [],
        'inventory_observed_at': system.inventory_observed_at if system is not None else None,
    }
    return context, system, time_range


def get_object_storage_analytics_context(page_key: str, query_args: Any) -> dict[str, Any]:
    context, system, time_range = _base_context(page_key, query_args)
    if system is None:
        context['dependency_blocker'] = system_required_blocker()
        return context

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

    if page_key in {'overview', 'capacity', 'top_consumers'}:
        context['bucket_table'] = build_bucket_table_view(
            context['metrics'].get('bucket_rows') or [],
            query_args,
            page_key=page_key,
            system=system,
            time_range=time_range,
        )
    return context


def get_object_storage_bucket_table_context(page_key: str, query_args: Any) -> dict[str, Any]:
    if page_key not in {'overview', 'capacity', 'top_consumers'}:
        page_key = 'overview'
    context, system, time_range = _base_context(page_key, query_args)
    if system is None:
        context['dependency_blocker'] = system_required_blocker()
        return context

    source, source_view, readiness, blocker = source_setup(system)
    context['metrics_source'] = source_view
    context['metrics_readiness'] = readiness
    if source is None or blocker is not None:
        context['dependency_blocker'] = blocker
        return context

    reader = EvidenceReader(source)
    core = _build_core_metrics(reader, system)
    rows = _bucket_rows(system, reader, include_activity=page_key == 'top_consumers')
    for row in rows:
        usage_total = core.get('usage_total')
        row['usage_share'] = utilization_percent(row.get('usage_bytes'), usage_total)
        row['usage_share_display'] = format_percent(row['usage_share'])
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
