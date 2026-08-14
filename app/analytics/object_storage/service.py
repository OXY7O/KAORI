from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import selectinload

from app.analytics.object_storage.forecasting import linear_forecast
from app.analytics.object_storage.presentation import (
    format_bytes,
    format_number,
    format_percent,
    format_rate,
    utilization_percent,
    utilization_tone,
)
from app.analytics.object_storage.sources import resolve_object_storage_metrics_source
from app.analytics.shared.metrics import (
    MetricReadinessState,
    MetricsReadinessSnapshot,
    MetricsSource,
    MetricsSourceError,
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


class _EvidenceReader:
    """Read canonical metrics once per request and fail fast on source-wide failures."""

    def __init__(self, source: MetricsSource) -> None:
        self.source = source
        self.diagnostics: list[str] = []
        self.source_wide_failure: MetricsSourceError | None = None
        self.failed_query_count = 0
        self.successful_query_count = 0

    @property
    def source_label(self) -> str:
        return self.source.identity.provider_label

    def _record_failure(self, exc: MetricsSourceError) -> None:
        self.failed_query_count += 1
        message = str(exc).strip()
        if message:
            self.diagnostics.append(message)
        if exc.source_wide:
            self.source_wide_failure = exc

    def scalar(self, key: str) -> float | None:
        if self.source_wide_failure is not None:
            return None
        try:
            value = self.source.scalar(key)
        except MetricsSourceError as exc:
            self._record_failure(exc)
            return None
        self.successful_query_count += 1
        return value

    def vector(self, key: str) -> dict[str, float]:
        if self.source_wide_failure is not None:
            return {}
        try:
            values = self.source.vector(key, 'bucket')
        except MetricsSourceError as exc:
            self._record_failure(exc)
            return {}
        self.successful_query_count += 1
        return values

    def trend(self, key: str, time_range: str) -> list[dict[str, float]]:
        if self.source_wide_failure is not None:
            return []
        try:
            points = self.source.trend(key, time_range)
        except MetricsSourceError as exc:
            self._record_failure(exc)
            return []
        self.successful_query_count += 1
        return points


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
        source = reader.source_label
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
    if all(value is None for value in (utilization, error_ratio, waiting, offline_nodes)):
        return [
            {
                'severity': 'unknown',
                'title': 'Metric Evidence Unavailable',
                'detail': 'Operational risk cannot be evaluated until metric evidence is available.',
            }
        ]

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
                    'Current operational metric evidence does not cross the baseline capacity, '
                    'error, queue, or node thresholds.'
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


def _metrics_readiness_view(snapshot: MetricsReadinessSnapshot) -> dict[str, Any]:
    state_labels = {
        MetricReadinessState.READY: ('Ready', 'normal'),
        MetricReadinessState.PARTIAL: ('Partial Evidence', 'warning'),
        MetricReadinessState.BLOCKED: ('Blocked', 'critical'),
        MetricReadinessState.NO_DATA: ('No Data', 'warning'),
        MetricReadinessState.UNSUPPORTED: ('Unsupported', 'unknown'),
        MetricReadinessState.NOT_VALIDATED: ('Validation Required', 'info'),
    }
    label, tone = state_labels.get(snapshot.state, ('Validation Required', 'info'))
    counts = {state.value: snapshot.count(state) for state in MetricReadinessState}
    required_items = [item for item in snapshot.items if item.tier == 'required']
    domain_items: dict[str, list[Any]] = defaultdict(list)
    for item in snapshot.items:
        domain_items[item.domain].append(item)
    domains: list[dict[str, Any]] = []
    for domain, items in domain_items.items():
        ready_count = sum(item.state == MetricReadinessState.READY for item in items)
        required = [item for item in items if item.tier == 'required']
        required_ready = sum(item.state == MetricReadinessState.READY for item in required)
        domain_state = 'ready' if ready_count == len(items) else 'partial'
        domains.append(
            {
                'label': domain,
                'status': domain_state,
                'status_label': 'Ready' if domain_state == 'ready' else 'Partial',
                'tone': 'normal' if domain_state == 'ready' else 'warning',
                'ready_count': ready_count,
                'total_count': len(items),
                'required_ready_count': required_ready,
                'required_total_count': len(required),
            }
        )
    checked_at: datetime | None = None
    if snapshot.checked_at:
        try:
            checked_at = datetime.fromisoformat(snapshot.checked_at)
        except ValueError:
            checked_at = None
    return {
        'profile': snapshot.profile,
        'profile_label': snapshot.profile_label,
        'status': snapshot.state.value,
        'label': label,
        'tone': tone,
        'checked_at': checked_at,
        'total_count': snapshot.total_count,
        'ready_count': counts[MetricReadinessState.READY.value],
        'no_data_count': counts[MetricReadinessState.NO_DATA.value],
        'unsupported_count': counts[MetricReadinessState.UNSUPPORTED.value],
        'blocked_count': counts[MetricReadinessState.BLOCKED.value],
        'required_ready_count': sum(item.state == MetricReadinessState.READY for item in required_items),
        'required_total_count': len(required_items),
        'domains': domains,
    }


def _waiting_metrics_readiness() -> dict[str, Any]:
    return {
        'profile': 'not-validated',
        'profile_label': 'Operational Metrics Contract',
        'status': 'not_validated',
        'label': 'Validation Required',
        'tone': 'info',
        'checked_at': None,
        'total_count': 0,
        'ready_count': 0,
        'no_data_count': 0,
        'unsupported_count': 0,
        'blocked_count': 0,
        'required_ready_count': 0,
        'required_total_count': 0,
        'domains': [],
    }


def _waiting_metrics_source() -> dict[str, Any]:
    return {
        'configured': False,
        'provider': None,
        'provider_label': 'Metrics Source',
        'label': 'Waiting for System',
        'tone': 'unknown',
        'detail': 'Select an object-storage system.',
    }


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
        'metrics_source': _waiting_metrics_source(),
        'metrics_readiness': _waiting_metrics_readiness(),
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
        'query_diagnostics': [],
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
        source = resolve_object_storage_metrics_source(system)
    except MetricsSourceError as exc:
        context['metrics_source'] = {
            'configured': False,
            'provider': exc.provider,
            'provider_label': 'Metrics Source',
            'label': 'Metrics Source Required',
            'tone': 'warning',
            'detail': str(exc),
        }
        context['dependency_blocker'] = {
            'title': 'Metrics Source Required',
            'description': str(exc),
            'action_label': 'Open Observability Integrations',
            'action_endpoint': 'integrations.observability',
        }
        return context

    identity = source.identity
    context['metrics_readiness'] = _metrics_readiness_view(source.readiness)
    context['metrics_source'] = {
        'configured': True,
        'provider': identity.provider,
        'provider_label': identity.provider_label,
        'instance_name': identity.instance_name,
        'label': 'Bound & Eligible',
        'tone': 'normal',
        'detail': identity.detail,
    }
    reader = _EvidenceReader(source)
    context['metrics'] = _build_metrics(page_key, reader, system, time_range)
    context['query_diagnostics'] = list(dict.fromkeys(item for item in reader.diagnostics if item))

    if reader.source_wide_failure is not None:
        context['metrics_source']['label'] = 'Source Unreachable'
        context['metrics_source']['tone'] = 'critical'
        context['metrics_source']['detail'] = str(reader.source_wide_failure)
    elif reader.failed_query_count:
        context['metrics_source']['label'] = 'Partial Evidence'
        context['metrics_source']['tone'] = 'warning'
        context['metrics_source']['detail'] = context['query_diagnostics'][0]

    return context
