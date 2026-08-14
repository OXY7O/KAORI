from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.analytics.common.params import get_allowed_time_ranges, get_selected_time_range
from app.analytics.object_storage.forecasting import linear_forecast
from app.analytics.object_storage.metrics import ObjectStorageMetricsService
from app.analytics.object_storage.parsing import matrix_points, vector_by_label, vector_scalar
from app.analytics.object_storage.presentation import (
    format_bytes,
    format_number,
    format_percent,
    format_rate,
    utilization_percent,
    utilization_tone,
)
from app.integrations.prometheus.exceptions import PrometheusError
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem
from app.prometheus.consumer import PrometheusConsumer


@dataclass(frozen=True)
class PageDefinition:
    title: str
    description: str
    icon: str
    eyebrow: str


PAGES: dict[str, PageDefinition] = {
    'overview': PageDefinition(
        'Overview',
        'Review object-storage operational posture, demand, and growth signals.',
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
        'Project storage growth and capacity exhaustion from Prometheus history.',
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
            joinedload(ObjectStorageSystem.minio_connection),
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
                'Metric-derived signals remain available from Prometheus.'
            ),
        }
    ready = str(binding.validation_status or '').strip().lower() == 'ready'
    return {
        'configured': True,
        'label': 'Ready' if ready else 'Validation Required',
        'tone': 'normal' if ready else 'warning',
        'description': 'Alert lifecycle correlation is reserved for the Alertmanager integration phase.',
    }


class _EvidenceReader:
    def __init__(self, metrics: ObjectStorageMetricsService) -> None:
        self.metrics = metrics
        self.diagnostics: list[str] = []

    def scalar(self, key: str) -> float | None:
        try:
            return vector_scalar(self.metrics.instant(key))
        except PrometheusError as exc:
            self.diagnostics.append(str(exc))
            return None

    def vector(self, key: str) -> dict[str, float]:
        try:
            return vector_by_label(self.metrics.instant(key), 'bucket')
        except PrometheusError as exc:
            self.diagnostics.append(str(exc))
            return {}

    def trend(self, key: str, time_range: str) -> list[dict[str, float]]:
        try:
            return matrix_points(self.metrics.range(key, time_range))
        except PrometheusError as exc:
            self.diagnostics.append(str(exc))
            return []


def _bucket_rows(system: ObjectStorageSystem, reader: _EvidenceReader) -> list[dict[str, Any]]:
    usage = reader.vector('object_storage.bucket.usage')
    objects = reader.vector('object_storage.bucket.objects')
    quota = reader.vector('object_storage.bucket.quota')
    request_rate = reader.vector('object_storage.bucket.request_rate')
    error_rate = reader.vector('object_storage.bucket.error_rate')
    inventory = {bucket.name: bucket for bucket in system.buckets or ()}
    names = set(inventory) | set(usage) | set(objects) | set(quota) | set(request_rate) | set(error_rate)
    rows: list[dict[str, Any]] = []
    for name in names:
        bucket = inventory.get(name)
        size = usage.get(name)
        source = 'Prometheus'
        if size is None and bucket is not None and bucket.size_bytes is not None:
            size = float(bucket.size_bytes)
            source = 'Committed Snapshot'
        object_count = objects.get(name)
        if object_count is None and bucket is not None and bucket.object_count is not None:
            object_count = float(bucket.object_count)
        quota_bytes = quota.get(name)
        if quota_bytes is None and bucket is not None and bucket.quota_bytes is not None:
            quota_bytes = float(bucket.quota_bytes)
        quota_utilization = utilization_percent(size, quota_bytes)
        rows.append(
            {
                'name': name,
                'usage_bytes': size,
                'usage_display': format_bytes(size),
                'objects': object_count,
                'objects_display': format_number(object_count),
                'quota_bytes': quota_bytes,
                'quota_display': format_bytes(quota_bytes),
                'quota_utilization': quota_utilization,
                'quota_utilization_display': format_percent(quota_utilization),
                'request_rate': request_rate.get(name),
                'request_rate_display': format_rate(request_rate.get(name)),
                'error_rate': error_rate.get(name),
                'error_rate_display': format_rate(error_rate.get(name)),
                'source': source,
            }
        )
    rows.sort(key=lambda item: float(item['usage_bytes'] or 0), reverse=True)
    return rows


def _signals(
    *,
    utilization: float | None,
    error_ratio: float | None,
    waiting: float | None,
    offline_nodes: float | None,
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    if utilization is not None and utilization >= 95:
        signals.append(
            {
                'severity': 'critical',
                'title': 'Capacity Critical',
                'detail': f'Usable capacity is {utilization:.1f}% consumed.',
            }
        )
    elif utilization is not None and utilization >= 85:
        signals.append(
            {
                'severity': 'warning',
                'title': 'Capacity Pressure',
                'detail': f'Usable capacity is {utilization:.1f}% consumed.',
            }
        )
    if error_ratio is not None and error_ratio >= 10:
        signals.append(
            {
                'severity': 'critical',
                'title': 'Request Error Pressure',
                'detail': f'Observed request error ratio is {error_ratio:.1f}%.',
            }
        )
    elif error_ratio is not None and error_ratio >= 5:
        signals.append(
            {
                'severity': 'warning',
                'title': 'Request Error Increase',
                'detail': f'Observed request error ratio is {error_ratio:.1f}%.',
            }
        )
    if waiting is not None and waiting > 0:
        signals.append(
            {
                'severity': 'warning',
                'title': 'Requests Waiting',
                'detail': f'{waiting:,.0f} requests are currently waiting.',
            }
        )
    if offline_nodes is not None and offline_nodes > 0:
        signals.append(
            {
                'severity': 'critical',
                'title': 'Offline Storage Nodes',
                'detail': f'{offline_nodes:,.0f} storage nodes are offline.',
            }
        )
    if not signals:
        signals.append(
            {
                'severity': 'normal',
                'title': 'No Metric-Derived Risk',
                'detail': (
                    'Current Prometheus evidence does not cross the baseline capacity, error, queue, or node thresholds.'
                ),
            }
        )
    return signals


def _build_metrics(
    page_key: str,
    reader: _EvidenceReader,
    system: ObjectStorageSystem,
    time_range: str,
) -> dict[str, Any]:
    total = reader.scalar('object_storage.capacity.total_bytes')
    free = reader.scalar('object_storage.capacity.free_bytes')
    used = reader.scalar('object_storage.usage.total_bytes')
    objects = reader.scalar('object_storage.usage.objects')
    buckets = reader.scalar('object_storage.usage.buckets')
    inventory = _inventory_totals(system)
    utilization = utilization_percent(used, total)
    payload: dict[str, Any] = {
        'capacity_total': total,
        'capacity_total_display': format_bytes(total),
        'capacity_free': free,
        'capacity_free_display': format_bytes(free),
        'usage_total': used,
        'usage_total_display': format_bytes(used),
        'object_count': objects,
        'object_count_display': format_number(objects),
        'bucket_count': buckets,
        'bucket_count_display': format_number(buckets),
        'utilization': utilization,
        'utilization_display': format_percent(utilization),
        'utilization_tone': utilization_tone(utilization),
        'inventory_size_display': format_bytes(inventory['size_bytes']),
        'inventory_object_count_display': format_number(inventory['object_count']),
        'inventory_bucket_count_display': format_number(inventory['bucket_count']),
    }
    if page_key in {'overview', 'capacity', 'forecast'}:
        payload['usage_trend'] = reader.trend('object_storage.usage.total_bytes', time_range)
    if page_key in {'overview', 'performance', 'alerts'}:
        request_rate = reader.scalar('object_storage.requests.rate')
        error_rate = reader.scalar('object_storage.requests.error_rate')
        waiting = reader.scalar('object_storage.requests.waiting')
        offline_nodes = reader.scalar('object_storage.health.offline_nodes')
        error_ratio = (
            (error_rate / request_rate * 100.0)
            if request_rate and error_rate is not None
            else 0.0 if request_rate else None
        )
        payload.update(
            {
                'request_rate': request_rate,
                'request_rate_display': format_rate(request_rate),
                'error_rate': error_rate,
                'error_rate_display': format_rate(error_rate),
                'error_ratio': error_ratio,
                'error_ratio_display': format_percent(error_ratio),
                'waiting': waiting,
                'waiting_display': format_number(waiting),
                'offline_nodes': offline_nodes,
                'offline_nodes_display': format_number(offline_nodes),
                'signals': _signals(
                    utilization=utilization,
                    error_ratio=error_ratio,
                    waiting=waiting,
                    offline_nodes=offline_nodes,
                ),
            }
        )
    if page_key == 'performance':
        payload.update(
            {
                'inflight': reader.scalar('object_storage.requests.inflight'),
                'received_bps': reader.scalar('object_storage.traffic.received_bps'),
                'sent_bps': reader.scalar('object_storage.traffic.sent_bps'),
                'request_trend': reader.trend('object_storage.requests.rate', time_range),
                'error_trend': reader.trend('object_storage.requests.error_rate', time_range),
            }
        )
        payload['inflight_display'] = format_number(payload['inflight'])
        payload['received_bps_display'] = (
            format_bytes(payload['received_bps']) + '/s' if payload['received_bps'] is not None else 'N/A'
        )
        payload['sent_bps_display'] = (
            format_bytes(payload['sent_bps']) + '/s' if payload['sent_bps'] is not None else 'N/A'
        )
    if page_key in {'overview', 'capacity', 'top_consumers'}:
        payload['bucket_rows'] = _bucket_rows(system, reader)
    if page_key == 'forecast':
        payload['forecast'] = linear_forecast(payload.get('usage_trend', []), capacity_bytes=total)
        forecast = payload['forecast']
        payload['forecast_display'] = {
            'growth_per_day': (
                format_bytes(forecast['growth_per_day']) + '/day'
                if forecast['growth_per_day'] is not None
                else 'N/A'
            ),
            'projected_7d': format_bytes(forecast['projected_7d']),
            'projected_30d': format_bytes(forecast['projected_30d']),
            'days_to_capacity': (
                f"{forecast['days_to_capacity']:.1f} days"
                if forecast['days_to_capacity'] is not None
                else 'N/A'
            ),
        }
    return payload


def get_object_storage_analytics_context(page_key: str, query_args: Any) -> dict[str, Any]:
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
        'prometheus': {
            'configured': False,
            'label': 'Waiting for System',
            'tone': 'unknown',
            'detail': 'Select an object-storage system.',
        },
        'alertmanager': (
            _alertmanager_binding(system.id)
            if system is not None
            else {
                'configured': False,
                'label': 'Not Configured',
                'tone': 'unknown',
                'description': 'Select an object-storage system.',
            }
        ),
        'metrics': {},
        'inventory_observed_at': system.inventory_observed_at if system is not None else None,
    }
    if system is None:
        context['dependency_blocker'] = {
            'title': 'Object Storage System Required',
            'description': 'Register and collect Object Storage Inventory before opening operational analytics.',
            'action_label': 'Open Object Storage Inventory',
            'action_endpoint': 'object_storage_inventory.overview',
        }
        return context
    try:
        consumer = PrometheusConsumer.for_asset(
            scope_type='object_storage_system',
            scope_key=system.id,
            scope_name=system.name,
        )
    except PrometheusError as exc:
        context['prometheus'] = {
            'configured': False,
            'label': 'Prometheus Binding Required',
            'tone': 'warning',
            'detail': str(exc),
        }
        context['dependency_blocker'] = {
            'title': 'Prometheus Binding Required',
            'description': str(exc),
            'action_label': 'Open Prometheus Integration',
            'action_endpoint': 'integrations.prometheus',
        }
        return context

    context['prometheus'] = {
        'configured': True,
        'label': 'Bound & Eligible',
        'tone': 'normal',
        'detail': f'{consumer.config.name} · {consumer.binding.validation_profile or "binding validated"}',
    }
    reader = _EvidenceReader(ObjectStorageMetricsService(consumer))
    context['metrics'] = _build_metrics(page_key, reader, system, time_range)
    context['query_diagnostics'] = list(dict.fromkeys(item for item in reader.diagnostics if item))
    if reader.diagnostics and not any(
        value for key, value in context['metrics'].items() if key.endswith('_display') and value != 'N/A'
    ):
        context['prometheus']['label'] = 'Metrics Unavailable'
        context['prometheus']['tone'] = 'warning'
        context['prometheus']['detail'] = reader.diagnostics[0]
    return context
