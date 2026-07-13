from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, SupportsFloat, SupportsIndex

from sqlalchemy import select

from app.analytics.common.cache import get_or_set_cache
from app.analytics.overview.schema import (
    build_empty_overview_payload,
    classify_count_risk,
    classify_percent,
)
from app.extensions import db
from app.intelligence.recommendation_engine import (
    build_operational_recommendations,
    build_utilization_actionable_recommendations,
    count_actionable_recommendations,
)
from app.models.cluster import Cluster

FloatLike = str | bytes | SupportsFloat | SupportsIndex


def get_analytics_overview(
    *,
    selected_cluster_id: str | None,
    time_range: str = '24h',
    hydrate_live_sections: bool = False,
) -> dict[str, Any]:
    payload = build_empty_overview_payload()

    clusters = _get_clusters_for_filter()
    selected_cluster = _resolve_selected_cluster(
        clusters=clusters,
        selected_cluster_id=selected_cluster_id,
    )

    payload['clusters'] = clusters
    payload['selected_cluster'] = selected_cluster
    payload['selected_cluster_id'] = _get_cluster_id(selected_cluster)
    payload['selected_time_range'] = time_range or '24h'
    payload['last_analyzed_at'] = _utc_now_display()

    cluster_id = str(payload['selected_cluster_id'])
    selected_time_range = str(payload['selected_time_range'])

    if hydrate_live_sections:
        _hydrate_overview_live_sections(
            payload=payload,
            cluster_id=cluster_id,
            time_range=selected_time_range,
        )

    return payload


def _hydrate_overview_live_sections(
    *,
    payload: dict[str, Any],
    cluster_id: str,
    time_range: str,
) -> dict[str, Any]:
    payload['prometheus'] = _cached_snapshot(
        key=f'overview:prometheus:{cluster_id}',
        ttl_seconds=30,
        loader=lambda: _get_prometheus_status(cluster_id=cluster_id),
    )
    payload['resource_snapshot'] = _cached_snapshot(
        key=f'overview:resource:{cluster_id}:{time_range}',
        ttl_seconds=45,
        loader=lambda: _get_resource_snapshot(cluster_id=cluster_id, time_range=time_range),
    )
    payload['capacity_snapshot'] = _cached_snapshot(
        key=f'overview:capacity:{cluster_id}:{time_range}',
        ttl_seconds=60,
        loader=lambda: _get_capacity_snapshot(cluster_id=cluster_id, time_range=time_range),
    )
    payload['storage_snapshot'] = _cached_snapshot(
        key=f'overview:storage:{cluster_id}',
        ttl_seconds=60,
        loader=lambda: _get_storage_snapshot(cluster_id=cluster_id),
    )
    payload['workload_snapshot'] = _cached_snapshot(
        key=f'overview:workload:{cluster_id}',
        ttl_seconds=60,
        loader=lambda: _get_workload_snapshot(cluster_id=cluster_id),
    )
    payload['top_consumers'] = _cached_snapshot(
        key=f'overview:top-consumers:{cluster_id}:{time_range}',
        ttl_seconds=60,
        loader=lambda: _get_top_consumers_snapshot(cluster_id=cluster_id, time_range=time_range),
    )
    payload['forecast_snapshot'] = _cached_snapshot(
        key=f'overview:forecast:{cluster_id}:{time_range}',
        ttl_seconds=300,
        loader=lambda: _get_forecast_snapshot(cluster_id=cluster_id, time_range=time_range),
    )
    payload['alerts_snapshot'] = _cached_snapshot(
        key=f'overview:alerts:{cluster_id}',
        ttl_seconds=20,
        loader=lambda: _get_alerts_snapshot(cluster_id=cluster_id),
    )
    payload['health_summary'] = _build_health_summary(payload)
    payload['actionable_recommendations'] = _build_actionable_recommendation_overview(payload)
    payload['actionable_recommendation_count'] = payload['actionable_recommendations']['total_count']
    payload['recommendations'] = build_operational_recommendations(payload)

    return payload


def get_analytics_overview_section(
    *,
    section: str,
    selected_cluster_id: str | None,
    time_range: str = '24h',
) -> dict[str, Any]:
    payload = get_analytics_overview(
        selected_cluster_id=selected_cluster_id,
        time_range=time_range,
        hydrate_live_sections=False,
    )

    cluster_id = str(payload['selected_cluster_id'])
    selected_time_range = str(payload['selected_time_range'])

    if section == 'prometheus-status':
        _hydrate_prometheus_section(payload, cluster_id)
    elif section == 'resource-snapshot':
        _hydrate_resource_section(payload, cluster_id, selected_time_range)
    elif section == 'capacity-snapshot':
        _hydrate_capacity_section(payload, cluster_id, selected_time_range)
    elif section == 'storage-snapshot':
        _hydrate_storage_section(payload, cluster_id)
    elif section == 'workload-snapshot':
        _hydrate_workload_section(payload, cluster_id)
    elif section == 'top-consumers':
        _hydrate_top_consumers_section(payload, cluster_id, selected_time_range)
    elif section == 'forecast-snapshot':
        _hydrate_forecast_section(payload, cluster_id, selected_time_range)
    elif section == 'alerts-snapshot':
        _hydrate_alerts_section(payload, cluster_id)
    else:
        _hydrate_overview_live_sections(
            payload=payload,
            cluster_id=cluster_id,
            time_range=selected_time_range,
        )

    payload['loaded_section'] = section
    payload['last_analyzed_at'] = _utc_now_display()

    return payload


def _hydrate_prometheus_section(payload: dict[str, Any], cluster_id: str) -> None:
    payload['prometheus'] = _cached_snapshot(
        key=f'overview:prometheus:{cluster_id}',
        ttl_seconds=30,
        loader=lambda: _get_prometheus_status(cluster_id=cluster_id),
    )


def _hydrate_resource_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['prometheus'] = _cached_snapshot(
        key=f'overview:prometheus:{cluster_id}',
        ttl_seconds=30,
        loader=lambda: _get_prometheus_status(cluster_id=cluster_id),
    )
    payload['resource_snapshot'] = _cached_snapshot(
        key=f'overview:resource:{cluster_id}:{time_range}',
        ttl_seconds=45,
        loader=lambda: _get_resource_snapshot(cluster_id=cluster_id, time_range=time_range),
    )


def _hydrate_capacity_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['capacity_snapshot'] = _cached_snapshot(
        key=f'overview:capacity:{cluster_id}:{time_range}',
        ttl_seconds=60,
        loader=lambda: _get_capacity_snapshot(cluster_id=cluster_id, time_range=time_range),
    )


def _hydrate_storage_section(payload: dict[str, Any], cluster_id: str) -> None:
    payload['storage_snapshot'] = _cached_snapshot(
        key=f'overview:storage:{cluster_id}',
        ttl_seconds=60,
        loader=lambda: _get_storage_snapshot(cluster_id=cluster_id),
    )


def _hydrate_workload_section(payload: dict[str, Any], cluster_id: str) -> None:
    payload['workload_snapshot'] = _cached_snapshot(
        key=f'overview:workload:{cluster_id}',
        ttl_seconds=60,
        loader=lambda: _get_workload_snapshot(cluster_id=cluster_id),
    )


def _hydrate_top_consumers_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['top_consumers'] = _cached_snapshot(
        key=f'overview:top-consumers:{cluster_id}:{time_range}',
        ttl_seconds=60,
        loader=lambda: _get_top_consumers_snapshot(cluster_id=cluster_id, time_range=time_range),
    )


def _hydrate_forecast_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['forecast_snapshot'] = _cached_snapshot(
        key=f'overview:forecast:{cluster_id}:{time_range}',
        ttl_seconds=300,
        loader=lambda: _get_forecast_snapshot(cluster_id=cluster_id, time_range=time_range),
    )


def _hydrate_alerts_section(payload: dict[str, Any], cluster_id: str) -> None:
    payload['alerts_snapshot'] = _cached_snapshot(
        key=f'overview:alerts:{cluster_id}',
        ttl_seconds=20,
        loader=lambda: _get_alerts_snapshot(cluster_id=cluster_id),
    )


def _cached_snapshot(
    *,
    key: str,
    ttl_seconds: int,
    loader: Any,
) -> dict[str, Any]:
    return get_or_set_cache(
        key=key,
        ttl_seconds=ttl_seconds,
        loader=loader,
    )


def _utc_now_display() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')


def _get_clusters_for_filter() -> list[dict[str, Any]]:
    try:
        clusters = db.session.scalars(
            select(Cluster).order_by(Cluster.name.asc()),
        ).all()

        return [_normalize_cluster(cluster) for cluster in clusters]
    except Exception:
        return []


def _resolve_selected_cluster(
    *,
    clusters: list[dict[str, Any]],
    selected_cluster_id: str | None,
) -> dict[str, Any] | None:
    if not clusters:
        return None

    if selected_cluster_id:
        for cluster in clusters:
            if str(cluster.get('id')) == str(selected_cluster_id):
                return cluster

    return clusters[0]


def _normalize_cluster(cluster: Any) -> dict[str, Any]:
    if isinstance(cluster, dict):
        return {
            'id': str(cluster.get('id', '')),
            'name': str(cluster.get('name') or 'Unknown Cluster'),
            'environment': str(cluster.get('environment') or ''),
            'status': str(cluster.get('status') or ''),
        }

    return {
        'id': str(getattr(cluster, 'id', '')),
        'name': str(getattr(cluster, 'name', 'Unknown Cluster') or 'Unknown Cluster'),
        'environment': str(getattr(cluster, 'environment', '') or ''),
        'status': str(getattr(cluster, 'status', '') or ''),
    }


def _get_cluster_id(cluster: dict[str, Any] | None) -> str:
    if not cluster:
        return ''

    return str(cluster.get('id', ''))


def _get_prometheus_status(*, cluster_id: str) -> dict[str, Any]:
    default = {
        'configured': False,
        'connected': False,
        'status': 'not_configured',
        'status_label': 'Not configured',
        'status_tone': 'gray',
        'endpoint': '',
        'response_time_ms': None,
        'message': 'Prometheus configuration is not available for this cluster.',
        'last_checked_at': _utc_now_display(),
    }

    if not cluster_id:
        return default

    prometheus_result = _call_optional_snapshot(
        module_path='app.analytics.utilization.service',
        function_names=[
            'get_prometheus_status_snapshot',
        ],
        cluster_id=cluster_id,
    )

    if not prometheus_result:
        return default

    connected = bool(
        prometheus_result.get('connected') or prometheus_result.get('success') or prometheus_result.get('is_connected'),
    )

    return {
        'configured': bool(
            prometheus_result.get(
                'configured',
                True,
            )
        ),
        'connected': connected,
        'status': str(
            prometheus_result.get(
                'status',
                'connected' if connected else 'disconnected',
            )
        ),
        'status_label': str(
            prometheus_result.get(
                'status_label',
                'Connected' if connected else 'Disconnected',
            )
        ),
        'status_tone': str(
            prometheus_result.get(
                'status_tone',
                'green' if connected else 'red',
            )
        ),
        'endpoint': str(
            prometheus_result.get(
                'endpoint',
                '',
            )
            or ''
        ),
        'response_time_ms': prometheus_result.get(
            'response_time_ms',
        ),
        'message': str(
            prometheus_result.get(
                'message',
                'Prometheus connection is healthy.' if connected else 'Prometheus connection failed.',
            )
        ),
        'last_checked_at': _utc_now_display(),
    }


def _get_resource_snapshot(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['resource_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.utilization.service',
        function_names=[
            'get_utilization_snapshot',
            'get_resource_snapshot',
            'get_resource_utilization_snapshot',
        ],
        cluster_id=cluster_id,
        time_range=time_range,
    )

    if not raw:
        return default

    cpu_percent = _pick_number(raw, ['cpu_percent', 'cpu_usage_percent', 'cpu_utilization'])
    memory_percent = _pick_number(
        raw,
        ['memory_percent', 'memory_usage_percent', 'memory_utilization'],
    )
    storage_percent = _pick_number(
        raw,
        ['storage_percent', 'storage_usage_percent', 'storage_utilization'],
    )
    pod_percent = _pick_number(raw, ['pod_percent', 'pod_usage_percent', 'pod_utilization'])

    return {
        'cpu': _resource_card(
            label='CPU Utilization',
            value=cpu_percent,
            icon='cpu',
            description='Cluster CPU utilization snapshot.',
            href='/analytics/utilization',
        ),
        'memory': _resource_card(
            label='Memory Utilization',
            value=memory_percent,
            icon='memory-stick',
            description='Cluster memory utilization snapshot.',
            href='/analytics/utilization',
        ),
        'storage': _resource_card(
            label='Storage Utilization',
            value=storage_percent,
            icon='database',
            description='Cluster storage utilization snapshot.',
            href='/analytics/storage',
        ),
        'pods': _resource_card(
            label='Pod Utilization',
            value=pod_percent,
            icon='boxes',
            description='Cluster pod capacity utilization snapshot.',
            href='/analytics/utilization',
        ),
    }


def _resource_card(
    *,
    label: str,
    value: float | None,
    icon: str,
    description: str,
    href: str,
) -> dict[str, Any]:
    percent = int(round(float(value or 0)))
    meta = classify_percent(percent)

    return {
        'label': label,
        'value': _format_percent_value(percent),
        'unit': '%',
        'status': meta['label'],
        'tone': meta['tone'],
        'icon': icon,
        'description': description,
        'href': href,
        'percent': percent,
    }


def _get_capacity_snapshot(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['capacity_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.capacity.service',
        function_names=[
            'get_capacity_snapshot',
            'get_capacity_overview_snapshot',
        ],
        cluster_id=cluster_id,
        time_range=time_range,
    )

    if not raw:
        return default

    recommendation_count = _safe_int(
        _as_float_like(raw.get('recommendation_count') or raw.get('recommendations_count')),
    )

    return {
        'cpu_headroom': {
            **default['cpu_headroom'],
            'value': raw.get('cpu_headroom') or raw.get('cpu_available') or '-',
            'unit': raw.get('cpu_unit', 'Cores'),
            'status': 'Available',
            'tone': 'blue',
        },
        'memory_headroom': {
            **default['memory_headroom'],
            'value': raw.get('memory_headroom') or raw.get('memory_available') or '-',
            'unit': raw.get('memory_unit', 'GiB'),
            'status': 'Available',
            'tone': 'blue',
        },
        'pod_capacity_remaining': {
            **default['pod_capacity_remaining'],
            'value': raw.get('pod_capacity_remaining') or raw.get('pods_available') or '-',
            'unit': raw.get('pod_unit', 'Pods'),
            'status': 'Available',
            'tone': 'blue',
        },
        'recommendations': {
            **default['recommendations'],
            'value': recommendation_count,
            'status': 'Review' if recommendation_count > 0 else 'Normal',
            'tone': 'amber' if recommendation_count > 0 else 'green',
        },
    }


def _get_storage_snapshot(*, cluster_id: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['storage_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.storage.service',
        function_names=[
            'get_storage_snapshot',
            'get_storage_overview_snapshot',
        ],
        cluster_id=cluster_id,
    )

    if not raw:
        return default

    used_percent = _safe_float(_as_float_like(raw.get('used_percent') or raw.get('pvc_used_percent')))
    free_percent = max(0.0, 100.0 - used_percent)
    risk_count = _safe_int(_as_float_like(raw.get('pvc_risk_count') or raw.get('risk_count')))
    recommendation_count = _get_snapshot_recommendation_count(
        raw,
        fallback_count=risk_count,
    )
    risk_meta = classify_count_risk(risk_count)

    return {
        'pvc_requested': raw.get('pvc_requested') or raw.get('requested') or '0 GiB',
        'pvc_used': raw.get('pvc_used') or raw.get('used') or '0 GiB',
        'pvc_free': raw.get('pvc_free') or raw.get('free') or '0 GiB',
        'pvc_risk_count': risk_count,
        'used_percent': round(used_percent, 2),
        'free_percent': round(free_percent, 2),
        'top_namespace': raw.get('top_namespace') or raw.get('top_storage_namespace') or '-',
        'status': risk_meta['label'],
        'tone': risk_meta['tone'],
        'href': '/analytics/storage',
        'recommendation_count': recommendation_count,
    }


def _get_workload_snapshot(*, cluster_id: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['workload_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.workload.service',
        function_names=[
            'get_workload_snapshot',
            'get_workload_overview_snapshot',
            'get_workload_efficiency_snapshot',
        ],
        cluster_id=cluster_id,
    )

    if not raw:
        return default

    missing_cpu_requests = _safe_int(_as_float_like(raw.get('missing_cpu_requests')))
    missing_memory_requests = _safe_int(_as_float_like(raw.get('missing_memory_requests')))
    missing_cpu_limits = _safe_int(_as_float_like(raw.get('missing_cpu_limits')))
    missing_memory_limits = _safe_int(_as_float_like(raw.get('missing_memory_limits')))
    over_provisioned = _safe_int(_as_float_like(raw.get('over_provisioned')))
    under_provisioned = _safe_int(_as_float_like(raw.get('under_provisioned')))

    issue_count = (
        missing_cpu_requests
        + missing_memory_requests
        + missing_cpu_limits
        + missing_memory_limits
        + over_provisioned
        + under_provisioned
    )

    recommendation_count = _get_snapshot_recommendation_count(
        raw,
        fallback_count=issue_count,
    )

    risk_meta = classify_count_risk(issue_count)

    return {
        'missing_cpu_requests': missing_cpu_requests,
        'missing_memory_requests': missing_memory_requests,
        'missing_cpu_limits': missing_cpu_limits,
        'missing_memory_limits': missing_memory_limits,
        'over_provisioned': over_provisioned,
        'under_provisioned': under_provisioned,
        'status': risk_meta['label'],
        'tone': risk_meta['tone'],
        'href': '/analytics/workload',
        'recommendation_count': recommendation_count,
    }


def _get_top_consumers_snapshot(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['top_consumers']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.top_consumers.service',
        function_names=[
            'get_top_consumers_snapshot',
            'get_top_consumers_overview_snapshot',
        ],
        cluster_id=cluster_id,
        time_range=time_range,
    )

    if not raw:
        return default

    return {
        'cpu': _normalize_consumer_items(raw.get('cpu', [])),
        'memory': _normalize_consumer_items(raw.get('memory', [])),
        'storage': _normalize_consumer_items(raw.get('storage', [])),
        'href': '/analytics/top-consumers',
        'recommendation_count': _get_snapshot_recommendation_count(
            raw,
            fallback_count=0,
        ),
    }


def _get_forecast_snapshot(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['forecast_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.forecast.service',
        function_names=[
            'get_forecast_snapshot',
            'get_forecast_overview_snapshot',
        ],
        cluster_id=cluster_id,
        time_range=time_range,
    )

    if not raw:
        return default

    forecast_risk = str(
        raw.get(
            'forecast_risk',
            'Low',
        )
    )

    risk_count = _safe_int(
        _as_float_like(
            raw.get(
                'risk_count',
            )
        )
    )

    if risk_count == 0 and forecast_risk.lower() in [
        'medium',
        'high',
        'critical',
    ]:
        risk_count = 1

    risk_note = raw.get(
        'risk_note',
    ) or (
        f'{risk_count} metric(s) may breach warning thresholds in the forecast window.'
        if risk_count > 0
        else 'No forecast risk detected in the selected time range.'
    )

    return {
        'cpu_trend': raw.get(
            'cpu_trend',
            'Unknown',
        ),
        'memory_trend': raw.get(
            'memory_trend',
            'Unknown',
        ),
        'storage_trend': raw.get(
            'storage_trend',
            'Unknown',
        ),
        'pod_trend': raw.get(
            'pod_trend',
            'Unknown',
        ),
        'risk_count': risk_count,
        'risk_note': risk_note,
        'forecast_risk': forecast_risk,
        'forecast_horizon': raw.get(
            'forecast_horizon',
            '30 days',
        ),
        'highest_projected_resource': raw.get(
            'highest_projected_resource',
            'N/A',
        ),
        'highest_projected_percent': _safe_int(
            _as_float_like(
                raw.get(
                    'highest_projected_percent',
                    0,
                )
            )
        ),
        'nearest_warning': raw.get(
            'nearest_warning',
            {},
        ),
        'nearest_critical': raw.get(
            'nearest_critical',
            {},
        ),
        'series': _normalize_forecast_series(
            raw.get(
                'series',
                [],
            )
        ),
        'href': '/analytics/forecast',
        'recommendation_count': _get_snapshot_recommendation_count(
            raw,
            fallback_count=risk_count,
        ),
    }


def _get_alerts_snapshot(*, cluster_id: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['alerts_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.analytics.alerts.service',
        function_names=[
            'get_alerts_snapshot',
            'get_alerts_overview_snapshot',
        ],
        cluster_id=cluster_id,
    )

    if not raw:
        return default

    firing_alerts = _safe_int(_as_float_like(raw.get('firing_alerts')))
    critical_alerts = _safe_int(_as_float_like(raw.get('critical_alerts')))
    warning_alerts = _safe_int(_as_float_like(raw.get('warning_alerts')))
    pending_alerts = _safe_int(_as_float_like(raw.get('pending_alerts')))
    recent_anomalies = _safe_int(_as_float_like(raw.get('recent_anomalies')))

    source_connected = bool(
        raw.get(
            'source_connected',
            False,
        )
    )
    anomaly_count = recent_anomalies
    recommendation_fallback_count = critical_alerts + warning_alerts + anomaly_count + (0 if source_connected else 1)

    risk_count = firing_alerts + critical_alerts + warning_alerts + pending_alerts
    risk_meta = classify_count_risk(risk_count)

    return {
        'firing_alerts': firing_alerts,
        'pending_alerts': pending_alerts,
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'recent_anomalies': recent_anomalies,
        'highest_severity': raw.get('highest_severity') or '-',
        'highest_severity_description': raw.get('highest_severity_description') or 'No active critical alert detected.',
        'status': risk_meta['label'],
        'tone': risk_meta['tone'],
        'href': '/analytics/alerts-anomalies',
        'source_connected': source_connected,
        'recommendation_count': _get_snapshot_recommendation_count(
            raw,
            fallback_count=recommendation_fallback_count,
        ),
    }


def _build_actionable_recommendation_overview(
    payload: dict[str, Any],
) -> dict[str, Any]:
    capacity_snapshot = _as_dict(
        payload.get(
            'capacity_snapshot',
        )
    )
    storage_snapshot = _as_dict(
        payload.get(
            'storage_snapshot',
        )
    )
    workload_snapshot = _as_dict(
        payload.get(
            'workload_snapshot',
        )
    )
    top_consumers_snapshot = _as_dict(
        payload.get(
            'top_consumers',
        )
    )
    forecast_snapshot = _as_dict(
        payload.get(
            'forecast_snapshot',
        )
    )
    alerts_snapshot = _as_dict(
        payload.get(
            'alerts_snapshot',
        )
    )

    capacity_count = _get_capacity_actionable_recommendation_count(
        capacity_snapshot,
    )

    utilization_recommendations = _build_utilization_actionable_recommendations_from_overview(
        payload,
    )
    utilization_count = count_actionable_recommendations(
        utilization_recommendations,
    )

    storage_count = _get_snapshot_actionable_count(
        storage_snapshot,
        fallback_keys=[
            'pvc_risk_count',
        ],
    )
    workload_count = _get_workload_actionable_count(
        workload_snapshot,
    )
    forecast_count = _get_snapshot_actionable_count(
        forecast_snapshot,
        fallback_keys=[
            'risk_count',
        ],
    )
    top_consumers_count = _get_snapshot_actionable_count(
        top_consumers_snapshot,
        fallback_keys=[
            'recommendation_count',
        ],
    )
    alerts_count = _get_alerts_actionable_count(
        alerts_snapshot,
    )

    capacity_items = _build_actionable_items_from_count(
        count=capacity_count,
        title='Review capacity actionable findings',
        description=(
            f'{capacity_count} actionable capacity recommendation(s) were detected. '
            'Open Capacity Analysis to inspect headroom, allocation, and governance findings.'
        ),
        source='capacity',
        source_label='Capacity',
        href='/analytics/capacity',
        icon='bar-chart-3',
        warning_threshold=1,
        critical_threshold=5,
    )
    storage_items = _build_actionable_items_from_count(
        count=storage_count,
        title='Review storage actionable findings',
        description=(
            f'{storage_count} actionable storage recommendation(s) were detected. '
            'Open Storage Analysis to inspect filesystem, PVC, PV, and expansion risks.'
        ),
        source='storage',
        source_label='Storage',
        href='/analytics/storage',
        icon='database',
        warning_threshold=1,
        critical_threshold=5,
    )
    workload_items = _build_actionable_items_from_count(
        count=workload_count,
        title='Review workload governance findings',
        description=(
            f'{workload_count} actionable workload recommendation(s) were detected. '
            'Open Workload Analysis to inspect quota, requests, limits, QoS, and right-sizing signals.'
        ),
        source='workload',
        source_label='Workload',
        href='/analytics/workload',
        icon='boxes',
        warning_threshold=1,
        critical_threshold=10,
    )
    forecast_items = _build_actionable_items_from_count(
        count=forecast_count,
        title='Review forecast capacity findings',
        description=(
            f'{forecast_count} actionable forecast recommendation(s) were detected. '
            'Open Resource Forecast to inspect projected threshold breaches and growth trends.'
        ),
        source='forecast',
        source_label='Forecast',
        href='/analytics/forecast',
        icon='line-chart',
        warning_threshold=1,
        critical_threshold=3,
    )
    top_consumers_items = _build_actionable_items_from_count(
        count=top_consumers_count,
        title='Review top consumer hotspot findings',
        description=(
            f'{top_consumers_count} actionable top consumer recommendation(s) were detected. '
            'Open Top Consumers to inspect CPU, memory, pod, and PVC hotspots.'
        ),
        source='top_consumers',
        source_label='Top Consumers',
        href='/analytics/top-consumers',
        icon='list-ordered',
        warning_threshold=1,
        critical_threshold=5,
    )
    alerts_items = _build_actionable_items_from_count(
        count=alerts_count,
        title='Review alert and anomaly findings',
        description=(
            f'{alerts_count} actionable alert/anomaly recommendation(s) were detected. '
            'Open Alerts & Anomalies to inspect active alerts, source health, and anomaly candidates.'
        ),
        source='alerts',
        source_label='Alerts & Anomalies',
        href='/analytics/alerts-anomalies',
        icon='bell',
        warning_threshold=1,
        critical_threshold=5,
    )

    actionable_items = [
        *capacity_items,
        *utilization_recommendations,
        *storage_items,
        *workload_items,
        *forecast_items,
        *top_consumers_items,
        *alerts_items,
    ]

    critical_count = _count_recommendations_by_priority(
        actionable_items,
        'Critical',
    )
    warning_count = _count_recommendations_by_priority(
        actionable_items,
        'Warning',
    )
    total_count = (
        capacity_count
        + utilization_count
        + storage_count
        + workload_count
        + forecast_count
        + top_consumers_count
        + alerts_count
    )

    if critical_count > 0:
        status = 'Critical'
        tone = 'red'
        description = 'Critical actionable recommendation detected across analytics domains.'
    elif total_count > 0:
        status = 'Review'
        tone = 'amber'
        description = 'Actionable recommendation detected across analytics domains.'
    else:
        status = 'Normal'
        tone = 'green'
        description = 'No actionable recommendation detected across analytics domains.'

    sources = [
        _build_actionable_source(
            label='Capacity',
            count=capacity_count,
            href='/analytics/capacity',
            description='Based on capacity headroom and governance findings.',
        ),
        _build_actionable_source(
            label='Utilization',
            count=utilization_count,
            href='/analytics/utilization',
            description='Based on utilization pressure and top consumer signals.',
        ),
        _build_actionable_source(
            label='Storage',
            count=storage_count,
            href='/analytics/storage',
            description='Based on filesystem, PVC, PV, and storage risk signals.',
        ),
        _build_actionable_source(
            label='Workload',
            count=workload_count,
            href='/analytics/workload',
            description='Based on quota, request, limit, QoS, and right-sizing signals.',
        ),
        _build_actionable_source(
            label='Forecast',
            count=forecast_count,
            href='/analytics/forecast',
            description='Based on forecasted growth and projected threshold breaches.',
        ),
        _build_actionable_source(
            label='Top Consumers',
            count=top_consumers_count,
            href='/analytics/top-consumers',
            description='Based on CPU, memory, pod, PVC, and namespace hotspot signals.',
        ),
        _build_actionable_source(
            label='Alerts & Anomalies',
            count=alerts_count,
            href='/analytics/alerts-anomalies',
            description='Based on active alerts, source health, and anomaly candidates.',
        ),
    ]

    return {
        'total_count': total_count,
        'status': status,
        'tone': tone,
        'description': description,
        'sources': sources,
        'priority_summary': {
            'critical': critical_count,
            'warning': warning_count,
        },
        'items': actionable_items,
        'capacity_recommendations': capacity_items,
        'utilization_recommendations': utilization_recommendations,
        'storage_recommendations': storage_items,
        'workload_recommendations': workload_items,
        'forecast_recommendations': forecast_items,
        'top_consumers_recommendations': top_consumers_items,
        'alerts_recommendations': alerts_items,
    }


def _build_actionable_source(
    *,
    label: str,
    count: int,
    href: str,
    description: str,
) -> dict[str, Any]:
    return {
        'label': label,
        'count': count,
        'href': href,
        'tone': _get_count_tone(count),
        'description': description,
    }


def _build_actionable_items_from_count(
    *,
    count: int,
    title: str,
    description: str,
    source: str,
    source_label: str,
    href: str,
    icon: str,
    warning_threshold: int,
    critical_threshold: int,
) -> list[dict[str, Any]]:
    if count < warning_threshold:
        return []

    priority = 'Critical' if count >= critical_threshold else 'Warning'

    return [
        {
            'title': title,
            'description': description,
            'priority': priority,
            'source': source,
            'source_label': source_label,
            'resource': source,
            'action_type': 'review',
            'href': href,
            'icon': icon,
            'is_actionable': True,
            'action_label': f'Open {source_label}',
        }
    ]


def _get_count_tone(
    count: int,
) -> str:
    if count >= 5:
        return 'red'

    if count > 0:
        return 'amber'

    return 'green'


def _get_snapshot_recommendation_count(
    raw: dict[str, Any],
    *,
    fallback_count: int,
) -> int:
    return _safe_int(
        _as_float_like(
            raw.get(
                'recommendation_count',
                raw.get(
                    'actionable_recommendation_count',
                    raw.get(
                        'recommendations_count',
                        fallback_count,
                    ),
                ),
            )
        )
    )


def _get_snapshot_actionable_count(
    snapshot: dict[str, Any],
    *,
    fallback_keys: list[str],
) -> int:
    explicit_count = _safe_int(
        _as_float_like(
            snapshot.get(
                'recommendation_count',
                snapshot.get(
                    'actionable_recommendation_count',
                    snapshot.get(
                        'recommendations_count',
                    ),
                ),
            )
        )
    )

    if explicit_count > 0:
        return explicit_count

    return sum(
        _safe_int(
            _as_float_like(
                snapshot.get(
                    key,
                    0,
                )
            )
        )
        for key in fallback_keys
    )


def _get_workload_actionable_count(
    workload_snapshot: dict[str, Any],
) -> int:
    explicit_count = _get_snapshot_actionable_count(
        workload_snapshot,
        fallback_keys=[],
    )

    if explicit_count > 0:
        return explicit_count

    return sum(
        _safe_int(
            _as_float_like(
                workload_snapshot.get(
                    key,
                    0,
                )
            )
        )
        for key in [
            'missing_cpu_requests',
            'missing_memory_requests',
            'missing_cpu_limits',
            'missing_memory_limits',
            'over_provisioned',
            'under_provisioned',
        ]
    )


def _get_alerts_actionable_count(
    alerts_snapshot: dict[str, Any],
) -> int:
    explicit_count = _get_snapshot_actionable_count(
        alerts_snapshot,
        fallback_keys=[],
    )

    if explicit_count > 0:
        return explicit_count

    source_connected = bool(
        alerts_snapshot.get(
            'source_connected',
            False,
        )
    )

    return (
        _safe_int(
            _as_float_like(
                alerts_snapshot.get(
                    'critical_alerts',
                    0,
                )
            )
        )
        + _safe_int(
            _as_float_like(
                alerts_snapshot.get(
                    'warning_alerts',
                    0,
                )
            )
        )
        + _safe_int(
            _as_float_like(
                alerts_snapshot.get(
                    'recent_anomalies',
                    0,
                )
            )
        )
        + (0 if source_connected else 1)
    )


def _build_capacity_actionable_items_from_count(
    capacity_count: int,
) -> list[dict[str, str]]:
    if capacity_count <= 0:
        return []

    priority = 'Critical' if capacity_count >= 5 else 'Warning'

    return [
        {
            'title': 'Review capacity actionable findings',
            'description': (
                f'{capacity_count} actionable capacity recommendation(s) were detected from '
                'Capacity Analysis. Open Capacity Analysis to inspect headroom, allocation, and governance findings.'
            ),
            'priority': priority,
            'source': 'Capacity Analysis',
            'is_actionable': 'Yes',
        }
    ]


def _get_capacity_actionable_recommendation_count(
    capacity_snapshot: Any,
) -> int:
    if not isinstance(
        capacity_snapshot,
        dict,
    ):
        return 0

    recommendations = capacity_snapshot.get(
        'recommendations',
        {},
    )

    if not isinstance(
        recommendations,
        dict,
    ):
        return 0

    return _safe_int(
        _as_float_like(
            recommendations.get(
                'value',
                0,
            )
        )
    )


def _build_utilization_actionable_recommendations_from_overview(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendation_payload = {
        'risk_assessment': _build_utilization_risk_assessment_from_resource_snapshot(
            payload.get(
                'resource_snapshot',
                {},
            )
        ),
        'top_cpu_consumers': _normalize_overview_consumers_for_recommendations(
            (
                payload.get(
                    'top_consumers',
                    {},
                )
                or {}
            ).get(
                'cpu',
                [],
            )
        ),
        'top_memory_consumers': _normalize_overview_consumers_for_recommendations(
            (
                payload.get(
                    'top_consumers',
                    {},
                )
                or {}
            ).get(
                'memory',
                [],
            )
        ),
    }

    return build_utilization_actionable_recommendations(
        recommendation_payload,
    )


def _build_utilization_risk_assessment_from_resource_snapshot(
    resource_snapshot: Any,
) -> dict[str, dict[str, int | float | str]]:
    if not isinstance(
        resource_snapshot,
        dict,
    ):
        resource_snapshot = {}

    return {
        'cpu': _overview_resource_risk_item(
            resource_snapshot,
            'cpu',
        ),
        'memory': _overview_resource_risk_item(
            resource_snapshot,
            'memory',
        ),
        'storage': _overview_resource_risk_item(
            resource_snapshot,
            'storage',
        ),
        'pods': _overview_resource_risk_item(
            resource_snapshot,
            'pods',
        ),
    }


def _overview_resource_risk_item(
    resource_snapshot: dict[str, Any],
    resource_key: str,
) -> dict[str, int | float | str]:
    item = resource_snapshot.get(
        resource_key,
        {},
    )

    if not isinstance(
        item,
        dict,
    ):
        item = {}

    utilization = _safe_float(
        _as_float_like(
            item.get(
                'percent',
                0,
            )
        )
    )

    status = 'Normal'

    if utilization > 90:
        status = 'Critical'
    elif utilization >= 75:
        status = 'Warning'

    return {
        'status': status,
        'reason': f'Utilization {utilization:.2f}%',
        'pressure_nodes': 0,
        'utilization': utilization,
    }


def _normalize_overview_consumers_for_recommendations(
    items: Any,
) -> list[dict[str, str | float]]:
    normalized: list[dict[str, str | float]] = []

    if not isinstance(
        items,
        list,
    ):
        return normalized

    for item in items[:5]:
        if not isinstance(
            item,
            dict,
        ):
            continue

        value = _safe_float(
            _as_float_like(
                item.get(
                    'value',
                    item.get(
                        'percent',
                        0,
                    ),
                )
            )
        )

        normalized.append(
            {
                'namespace': str(
                    item.get(
                        'namespace',
                        '-',
                    )
                    or '-'
                ),
                'pod': str(
                    item.get(
                        'pod',
                        item.get(
                            'name',
                            '-',
                        ),
                    )
                    or '-'
                ),
                'value': value,
            }
        )

    return normalized


def _count_recommendations_by_priority(
    recommendations: list[dict[str, Any]],
    priority: str,
) -> int:
    normalized_priority = priority.lower()

    return sum(
        1
        for item in recommendations
        if str(
            item.get(
                'priority',
                '',
            )
        ).lower()
        == normalized_priority
    )


def _build_health_summary(payload: dict[str, Any]) -> dict[str, Any]:
    default = deepcopy(build_empty_overview_payload()['health_summary'])

    resource_snapshot = payload.get('resource_snapshot', {})
    storage_snapshot = payload.get('storage_snapshot', {})
    workload_snapshot = payload.get('workload_snapshot', {})
    forecast_snapshot = payload.get('forecast_snapshot', {})
    alerts_snapshot = payload.get('alerts_snapshot', {})

    cpu_percent = _safe_float(_get_nested_float(resource_snapshot, 'cpu', 'percent'))
    memory_percent = _safe_float(_get_nested_float(resource_snapshot, 'memory', 'percent'))
    storage_percent = _safe_float(_get_nested_float(resource_snapshot, 'storage', 'percent'))
    pod_percent = _safe_float(_get_nested_float(resource_snapshot, 'pods', 'percent'))

    resource_pressures = {
        'CPU': cpu_percent,
        'Memory': memory_percent,
        'Storage': storage_percent,
        'Pods': pod_percent,
    }

    highest_pressure_resource = max(
        resource_pressures,
        key=lambda resource_name: resource_pressures[resource_name],
    )
    max_pressure = resource_pressures[highest_pressure_resource]
    pressure_meta = classify_percent(max_pressure)

    firing_alerts = _safe_int(_as_float_like(alerts_snapshot.get('firing_alerts')))
    pending_alerts = _safe_int(_as_float_like(alerts_snapshot.get('pending_alerts')))
    critical_alerts = _safe_int(_as_float_like(alerts_snapshot.get('critical_alerts')))
    warning_alerts = _safe_int(_as_float_like(alerts_snapshot.get('warning_alerts')))
    recent_anomalies = _safe_int(_as_float_like(alerts_snapshot.get('recent_anomalies')))

    active_alerts = firing_alerts + pending_alerts

    forecast_risk_count = _safe_int(_as_float_like(forecast_snapshot.get('risk_count')))
    forecast_risk_value = str(
        forecast_snapshot.get(
            'forecast_risk',
            'Low',
        )
    )
    highest_projected_resource = str(
        forecast_snapshot.get(
            'highest_projected_resource',
            'N/A',
        )
    )
    highest_projected_percent = _safe_int(
        _as_float_like(
            forecast_snapshot.get(
                'highest_projected_percent',
                0,
            )
        )
    )

    pvc_risk_count = _safe_int(_as_float_like(storage_snapshot.get('pvc_risk_count')))

    workload_issue_count = (
        _safe_int(_as_float_like(workload_snapshot.get('missing_cpu_requests')))
        + _safe_int(_as_float_like(workload_snapshot.get('missing_memory_requests')))
        + _safe_int(_as_float_like(workload_snapshot.get('missing_cpu_limits')))
        + _safe_int(_as_float_like(workload_snapshot.get('missing_memory_limits')))
        + _safe_int(_as_float_like(workload_snapshot.get('over_provisioned')))
        + _safe_int(_as_float_like(workload_snapshot.get('under_provisioned')))
    )

    forecast_is_high = forecast_risk_value.lower() in [
        'high',
        'critical',
    ]
    forecast_is_medium = forecast_risk_value.lower() in [
        'medium',
        'warning',
    ]

    if critical_alerts > 0 or max_pressure >= 90 or forecast_is_high:
        cluster_value = 'Critical'
        cluster_tone = 'red'
        cluster_status = 'critical'
        cluster_desc = 'Critical signal detected from alerts, resource pressure, or forecast risk.'
    elif (
        active_alerts > 0
        or warning_alerts > 0
        or recent_anomalies > 0
        or max_pressure >= 75
        or pvc_risk_count > 0
        or workload_issue_count > 0
        or forecast_risk_count > 0
        or forecast_is_medium
    ):
        cluster_value = 'Warning'
        cluster_tone = 'amber'
        cluster_status = 'warning'
        cluster_desc = 'Operational warning detected. Review the prioritized recommendations.'
    else:
        cluster_value = 'Healthy'
        cluster_tone = 'green'
        cluster_status = 'normal'
        cluster_desc = 'No critical operational signal detected.'

    capacity_risk_score = 0

    if max_pressure >= 75:
        capacity_risk_score += 1

    if max_pressure >= 90:
        capacity_risk_score += 1

    if pvc_risk_count > 0:
        capacity_risk_score += 1

    if forecast_risk_count > 0 or forecast_is_medium:
        capacity_risk_score += 1

    if forecast_is_high:
        capacity_risk_score += 2

    if workload_issue_count > 0:
        capacity_risk_score += 1

    if workload_issue_count >= 10:
        capacity_risk_score += 1

    if capacity_risk_score >= 4:
        capacity_value = 'High'
        capacity_tone = 'red'
        capacity_status = 'critical'
        capacity_desc = 'Multiple capacity indicators require immediate review.'
    elif capacity_risk_score > 0:
        capacity_value = 'Medium'
        capacity_tone = 'amber'
        capacity_status = 'warning'
        capacity_desc = 'Capacity risk is present across one or more signals.'
    else:
        capacity_value = 'Low'
        capacity_tone = 'green'
        capacity_status = 'normal'
        capacity_desc = 'Capacity risk is currently low.'

    if active_alerts > 0:
        active_alert_description = (
            f'{firing_alerts} firing and {pending_alerts} pending alert(s). '
            f'{critical_alerts} critical, {warning_alerts} warning.'
        )
    elif recent_anomalies > 0:
        active_alert_description = f'No firing alerts, but {recent_anomalies} anomaly candidate(s) detected.'
    else:
        active_alert_description = 'No firing or pending alert detected.'

    if forecast_risk_count > 0 or forecast_is_medium or forecast_is_high:
        forecast_value = forecast_risk_value
        forecast_status = 'critical' if forecast_is_high else 'warning'
        forecast_tone = 'red' if forecast_is_high else 'purple'
        forecast_description = (
            f'{highest_projected_resource} projected at {highest_projected_percent}% '
            f'within {forecast_snapshot.get("forecast_horizon", "forecast window")}.'
        )
    else:
        forecast_value = 'Low'
        forecast_status = 'normal'
        forecast_tone = 'green'
        forecast_description = 'No forecast risk detected.'

    top_namespace = str(storage_snapshot.get('top_namespace') or '-')

    if top_namespace != '-' and pvc_risk_count > 0:
        top_namespace_status = 'warning'
        top_namespace_tone = 'blue'
        top_namespace_description = f'{pvc_risk_count} PVC risk item(s) detected. Highest storage namespace signal.'
    elif top_namespace != '-':
        top_namespace_status = 'normal'
        top_namespace_tone = 'blue'
        top_namespace_description = 'Highest storage usage namespace.'
    else:
        top_namespace_status = 'unknown'
        top_namespace_tone = 'gray'
        top_namespace_description = 'Namespace risk data is not available.'

    return {
        **default,
        'cluster_health': {
            **default['cluster_health'],
            'value': cluster_value,
            'status': cluster_status,
            'tone': cluster_tone,
            'description': cluster_desc,
        },
        'resource_pressure': {
            **default['resource_pressure'],
            'value': pressure_meta['label'],
            'status': pressure_meta['status'],
            'tone': pressure_meta['tone'],
            'description': f'{highest_pressure_resource} is the highest signal at {int(round(max_pressure))}%.',
        },
        'capacity_risk': {
            **default['capacity_risk'],
            'value': capacity_value,
            'status': capacity_status,
            'tone': capacity_tone,
            'description': capacity_desc,
        },
        'active_alerts': {
            **default['active_alerts'],
            'value': active_alerts,
            'status': 'warning' if active_alerts else 'normal',
            'tone': 'red' if critical_alerts else 'amber' if active_alerts else 'green',
            'description': active_alert_description,
        },
        'forecast_risk': {
            **default['forecast_risk'],
            'value': forecast_value,
            'status': forecast_status,
            'tone': forecast_tone,
            'description': forecast_description,
        },
        'top_risk_namespace': {
            **default['top_risk_namespace'],
            'value': top_namespace,
            'status': top_namespace_status,
            'tone': top_namespace_tone,
            'description': top_namespace_description,
        },
    }


def _call_optional_snapshot(
    *,
    module_path: str,
    function_names: list[str],
    **kwargs: Any,
) -> dict[str, Any] | None:
    try:
        module = __import__(module_path, fromlist=['*'])
    except Exception:
        return None

    for function_name in function_names:
        func = getattr(module, function_name, None)

        if not callable(func):
            continue

        try:
            result = func(**kwargs)
        except TypeError:
            try:
                result = func(kwargs.get('cluster_id'))
            except Exception:
                continue
        except Exception:
            continue

        if isinstance(result, dict):
            return result

    return None


def _normalize_consumer_items(items: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    if not isinstance(items, list):
        return normalized

    for item in items[:4]:
        if isinstance(item, dict):
            name = item.get('name') or item.get('workload') or item.get('namespace') or '-'
            namespace = item.get('namespace', '')
            value = item.get('value') or item.get('usage') or item.get('percent') or 0
            raw_percent = item.get('percent') or item.get('usage_percent') or value
            percent = _safe_float(_as_float_like(raw_percent))
            display_value = item.get('display_value') or item.get('value_label') or str(value)
        else:
            name = getattr(item, 'name', '-')
            namespace = getattr(item, 'namespace', '')
            value = getattr(item, 'value', 0)
            raw_percent = getattr(item, 'percent', value)
            percent = _safe_float(_as_float_like(raw_percent))
            display_value = str(value)

        normalized.append(
            {
                'name': str(name),
                'namespace': str(namespace),
                'value': value,
                'display_value': str(display_value),
                'percent': min(max(percent, 0.0), 100.0),
            },
        )

    return normalized


def _normalize_forecast_series(
    series: Any,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    if not isinstance(
        series,
        list,
    ):
        return normalized

    for item in series[:4]:
        if not isinstance(
            item,
            dict,
        ):
            continue

        historical_points = str(
            item.get(
                'historical_points',
                '',
            )
            or ''
        )
        forecast_points = str(
            item.get(
                'forecast_points',
                '',
            )
            or ''
        )

        if not historical_points and not forecast_points:
            continue

        normalized.append(
            {
                'key': str(
                    item.get(
                        'key',
                        '',
                    )
                ),
                'label': str(
                    item.get(
                        'label',
                        '',
                    )
                ),
                'historical_points': historical_points,
                'forecast_points': forecast_points,
                'latest_percent': _safe_int(
                    _as_float_like(
                        item.get(
                            'latest_percent',
                            0,
                        )
                    )
                ),
                'projected_percent': _safe_int(
                    _as_float_like(
                        item.get(
                            'projected_percent',
                            0,
                        )
                    )
                ),
                'trend': str(
                    item.get(
                        'trend',
                        'Stable',
                    )
                ),
            }
        )

    return normalized


def _pick_number(raw: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = raw.get(key)

        if value is None:
            continue

        float_like = _as_float_like(value)
        if float_like is not None:
            return _safe_float(float_like)

    return None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _get_nested_float(source: Any, first_key: str, second_key: str) -> FloatLike | None:
    if not isinstance(source, dict):
        return None

    first_value = source.get(first_key)
    if not isinstance(first_value, dict):
        return None

    return _as_float_like(first_value.get(second_key))


def _as_float_like(value: Any) -> FloatLike | None:
    if isinstance(value, int | float | str | bytes):
        return value

    return None


def _format_percent_value(value: float) -> int:
    return int(round(value))


def _safe_float(value: FloatLike | None) -> float:
    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: FloatLike | None) -> int:
    if value is None:
        return 0

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
