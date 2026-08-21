from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, SupportsFloat, SupportsIndex

from flask import current_app, has_app_context
from sqlalchemy import select

from app.common.analytics.coercion import as_dict as _as_dict
from app.extensions.db import db
from app.intelligence.recommendation_engine import (
    build_operational_recommendations,
    build_utilization_actionable_recommendations,
    count_actionable_recommendations,
)
from app.kubernetes.analytics.common.presentation import present_metrics_source_status
from app.kubernetes.analytics.overview.health import build_health_summary
from app.kubernetes.analytics.overview.schema import build_empty_overview_payload, classify_count_risk, classify_percent
from app.kubernetes.analytics.overview.sections import get_overview_section
from app.kubernetes.analytics.overview.snapshot_summary import (
    OVERVIEW_SNAPSHOT_DATASETS,
    overview_snapshot_parameters,
    present_snapshot_summary,
)
from app.models.analytics import AnalyticsSnapshot
from app.models.cluster import Cluster

FloatLike = str | bytes | SupportsFloat | SupportsIndex


@dataclass(frozen=True, slots=True)
class ActionableDomain:
    key: str
    evidence_key: str
    label: str
    href: str
    source_description: str
    aggregate_title: str = ''
    aggregate_noun: str = ''
    aggregate_guidance: str = ''
    icon: str = ''
    critical_threshold: int = 5

    @property
    def has_aggregate_item(self) -> bool:
        return bool(self.aggregate_title)


ACTIONABLE_DOMAINS: tuple[ActionableDomain, ...] = (
    ActionableDomain(
        key='capacity',
        evidence_key='capacity',
        label='Capacity',
        href='/analytics/capacity',
        source_description='Based on capacity headroom and governance findings.',
        aggregate_title='Review Capacity Actionable Findings',
        aggregate_noun='capacity',
        aggregate_guidance='Open Capacity Analysis to inspect headroom, allocation, and governance findings.',
        icon='bar-chart-3',
    ),
    ActionableDomain(
        key='utilization',
        evidence_key='resource',
        label='Utilization',
        href='/analytics/utilization',
        source_description='Based on utilization pressure and top consumer signals.',
    ),
    ActionableDomain(
        key='storage',
        evidence_key='storage',
        label='Storage',
        href='/analytics/storage',
        source_description='Based on filesystem, PVC, PV, and storage risk signals.',
        aggregate_title='Review Storage Actionable Findings',
        aggregate_noun='storage',
        aggregate_guidance='Open Storage Analysis to inspect filesystem, PVC, PV, and expansion risks.',
        icon='database',
    ),
    ActionableDomain(
        key='workload',
        evidence_key='workload',
        label='Workload',
        href='/analytics/workload',
        source_description='Based on quota, request, limit, QoS, and right-sizing signals.',
        aggregate_title='Review Workload Governance Findings',
        aggregate_noun='workload governance',
        aggregate_guidance=(
            'Open Workload Analysis to inspect quota, requests, limits, QoS, and right-sizing signals.'
        ),
        icon='boxes',
        critical_threshold=10,
    ),
    ActionableDomain(
        key='forecast',
        evidence_key='forecast',
        label='Forecast',
        href='/analytics/forecast',
        source_description='Based on forecasted growth and projected threshold breaches.',
        aggregate_title='Review Forecast Capacity Findings',
        aggregate_noun='forecast',
        aggregate_guidance=('Open Resource Forecast to inspect projected threshold breaches and growth trends.'),
        icon='line-chart',
        critical_threshold=3,
    ),
    ActionableDomain(
        key='top_consumers',
        evidence_key='top_consumers',
        label='Top Consumers',
        href='/analytics/top-consumers',
        source_description='Based on CPU, memory, pod, PVC, and namespace hotspot signals.',
        aggregate_title='Review Top Consumer Hotspot Findings',
        aggregate_noun='top consumer',
        aggregate_guidance='Open Top Consumers to inspect CPU, memory, pod, and PVC hotspots.',
        icon='list-ordered',
    ),
    ActionableDomain(
        key='alerts',
        evidence_key='alerts',
        label='Alerts & Anomalies',
        href='/analytics/alerts?tab=alerts',
        source_description='Based on active alerts, source health, and anomaly candidates.',
        aggregate_title='Review Alert and Anomaly Findings',
        aggregate_noun='alert/anomaly',
        aggregate_guidance=('Open Alerts & Anomalies to inspect active alerts, source health, and anomaly candidates.'),
        icon='bell',
    ),
)


def get_analytics_overview(
    *,
    selected_cluster_id: str | None,
    time_range: str = '24h',
    hydrate_snapshot_sections: bool = False,
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

    if hydrate_snapshot_sections:
        _hydrate_overview_snapshot_sections(
            payload=payload,
            cluster_id=cluster_id,
            time_range=selected_time_range,
        )

    return payload


def _hydrate_overview_snapshot_sections(
    *,
    payload: dict[str, Any],
    cluster_id: str,
    time_range: str,
) -> dict[str, Any]:
    payload['metrics_source'] = _get_metrics_source_status(cluster_id=cluster_id)
    payload['resource_snapshot'] = _get_resource_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    payload['capacity_snapshot'] = _get_capacity_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    payload['storage_snapshot'] = _get_storage_snapshot(cluster_id=cluster_id)
    payload['workload_snapshot'] = _get_workload_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    payload['top_consumers'] = _get_top_consumers_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    payload['forecast_snapshot'] = _get_forecast_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    payload['alerts_snapshot'] = _get_alerts_snapshot(cluster_id=cluster_id)
    payload['snapshot_summary'] = _get_snapshot_summary(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    payload['health_summary'] = build_health_summary(payload)
    payload['actionable_recommendations'] = _build_actionable_recommendation_overview(payload)
    payload['actionable_recommendation_count'] = payload['actionable_recommendations']['total_count']
    evidence_complete = bool(payload['actionable_recommendations'].get('evidence_complete', False))
    has_actionable_findings = payload['actionable_recommendation_count'] > 0
    if evidence_complete or has_actionable_findings:
        payload['recommendations'] = [
            recommendation
            for recommendation in build_operational_recommendations(payload)
            if bool(recommendation.get('is_actionable', False))
        ]
    else:
        payload['recommendations'] = []

    return payload


def get_analytics_overview_section(
    *,
    section: str,
    selected_cluster_id: str | None,
    time_range: str = '24h',
) -> dict[str, Any]:
    section_definition = get_overview_section(section)
    if section_definition is None:
        raise LookupError(f'Unknown Analytics Overview section: {section}')

    payload = get_analytics_overview(
        selected_cluster_id=selected_cluster_id,
        time_range=time_range,
        hydrate_snapshot_sections=False,
    )

    cluster_id = str(payload['selected_cluster_id'])
    selected_time_range = str(payload['selected_time_range'])
    hydration = section_definition.hydration

    if hydration == 'resource':
        _hydrate_resource_section(payload, cluster_id, selected_time_range)
    elif hydration == 'capacity':
        _hydrate_capacity_section(payload, cluster_id, selected_time_range)
    elif hydration == 'storage':
        _hydrate_storage_section(payload, cluster_id)
    elif hydration == 'workload':
        _hydrate_workload_section(payload, cluster_id, selected_time_range)
    elif hydration == 'top-consumers':
        _hydrate_top_consumers_section(payload, cluster_id, selected_time_range)
    elif hydration == 'forecast':
        _hydrate_forecast_section(payload, cluster_id, selected_time_range)
    elif hydration == 'alerts':
        _hydrate_alerts_section(payload, cluster_id)
    elif hydration == 'composite':
        _hydrate_overview_snapshot_sections(
            payload=payload,
            cluster_id=cluster_id,
            time_range=selected_time_range,
        )
    else:
        raise RuntimeError(f'Unsupported Analytics Overview hydration owner: {hydration}')

    payload['loaded_section'] = section
    payload['last_analyzed_at'] = _utc_now_display()

    return payload


def _hydrate_resource_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['resource_snapshot'] = _get_resource_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )


def _hydrate_capacity_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['capacity_snapshot'] = _get_capacity_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )


def _hydrate_storage_section(payload: dict[str, Any], cluster_id: str) -> None:
    payload['storage_snapshot'] = _get_storage_snapshot(cluster_id=cluster_id)


def _hydrate_workload_section(
    payload: dict[str, Any],
    cluster_id: str,
    time_range: str,
) -> None:
    payload['workload_snapshot'] = _get_workload_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )


def _hydrate_top_consumers_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['top_consumers'] = _get_top_consumers_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )


def _hydrate_forecast_section(payload: dict[str, Any], cluster_id: str, time_range: str) -> None:
    payload['forecast_snapshot'] = _get_forecast_snapshot(
        cluster_id=cluster_id,
        time_range=time_range,
    )


def _hydrate_alerts_section(payload: dict[str, Any], cluster_id: str) -> None:
    payload['alerts_snapshot'] = _get_alerts_snapshot(cluster_id=cluster_id)


def _get_snapshot_summary(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    expected_parameters = overview_snapshot_parameters(
        cluster_id=cluster_id,
        time_range=time_range,
    )
    if not cluster_id:
        return present_snapshot_summary(
            [],
            time_range=time_range,
            expected_parameters=expected_parameters,
        )

    try:
        snapshots = db.session.scalars(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.cluster_id == cluster_id,
                AnalyticsSnapshot.dataset_key.in_(tuple(OVERVIEW_SNAPSHOT_DATASETS)),
            )
        ).all()
    except Exception:
        snapshots = []

    return present_snapshot_summary(
        snapshots,
        time_range=time_range,
        expected_parameters=expected_parameters,
    )


def _utc_now_display() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')


def _get_clusters_for_filter() -> list[dict[str, Any]]:
    try:
        clusters = db.session.scalars(
            select(Cluster).order_by(Cluster.created_at.asc(), Cluster.id.asc()),
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

    try:
        ready_cluster_ids = {
            str(cluster_id)
            for cluster_id in db.session.scalars(
                select(AnalyticsSnapshot.cluster_id)
                .where(
                    AnalyticsSnapshot.status == 'ready',
                    AnalyticsSnapshot.payload_json.is_not(None),
                )
                .distinct()
            ).all()
        }
    except Exception:
        ready_cluster_ids = set()

    for cluster in clusters:
        if str(cluster.get('id')) in ready_cluster_ids:
            return cluster

    try:
        from app.integrations.observability.metrics_source.application.resolver import resolve_metrics_sources
        from app.integrations.observability.metrics_source.scope import KUBERNETES_CLUSTER_SCOPE

        for cluster in clusters:
            resolution = resolve_metrics_sources(
                scope_type=KUBERNETES_CLUSTER_SCOPE,
                scope_key=str(cluster.get('id')),
                required_binding_capabilities=('metrics',),
                required_technical_capabilities=('instant_query',),
            )
            if resolution.selected is not None:
                return cluster
    except Exception:
        pass

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


def _get_metrics_source_status(*, cluster_id: str) -> dict[str, Any]:
    if not cluster_id:
        return present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'label': 'Waiting for Cluster',
            }
        )

    metrics_source_result = _call_optional_snapshot(
        module_path='app.kubernetes.analytics.utilization.snapshots',
        function_names=['get_metrics_source_status_snapshot'],
        cluster_id=cluster_id,
    )
    if not metrics_source_result:
        return present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'label': 'Metrics Source Not Configured',
            }
        )
    return present_metrics_source_status(metrics_source_result)


def _get_resource_snapshot(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['resource_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.kubernetes.analytics.utilization.snapshots',
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
        'available': True,
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
    if value is None:
        return {
            'label': label,
            'value': 'N/A',
            'unit': '%',
            'status': 'Unknown',
            'tone': 'gray',
            'icon': icon,
            'description': f'{description} This metric is not present in the committed dataset.',
            'href': href,
            'percent': None,
        }

    percent = max(0, min(100, int(round(float(value)))))
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
        module_path='app.kubernetes.analytics.capacity.service',
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
        'available': True,
        'cpu_headroom': {
            **default['cpu_headroom'],
            'value': raw.get('cpu_headroom') if raw.get('cpu_headroom') is not None else raw.get('cpu_available', '-'),
            'unit': raw.get('cpu_unit', 'Cores'),
            'status': 'Available',
            'tone': 'blue',
        },
        'memory_headroom': {
            **default['memory_headroom'],
            'value': raw.get('memory_headroom')
            if raw.get('memory_headroom') is not None
            else raw.get('memory_available', '-'),
            'unit': raw.get('memory_unit', 'GiB'),
            'status': 'Available',
            'tone': 'blue',
        },
        'pod_capacity_remaining': {
            **default['pod_capacity_remaining'],
            'value': (
                raw.get('pod_capacity_remaining')
                if raw.get('pod_capacity_remaining') is not None
                else raw.get('pods_available', '-')
            ),
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
        module_path='app.kubernetes.analytics.storage.service',
        function_names=[
            'get_storage_snapshot',
            'get_storage_overview_snapshot',
        ],
        cluster_id=cluster_id,
    )

    if not raw:
        return default

    used_percent = _maybe_float(
        raw.get('used_percent') if raw.get('used_percent') is not None else raw.get('pvc_used_percent')
    )
    free_percent = (
        _maybe_float(raw.get('free_percent'))
        if raw.get('free_percent') is not None
        else (max(0.0, 100.0 - used_percent) if used_percent is not None else None)
    )
    risk_count = _safe_int(_as_float_like(raw.get('pvc_risk_count') or raw.get('risk_count')))
    recommendation_count = _get_snapshot_recommendation_count(
        raw,
        fallback_count=risk_count,
    )
    risk_meta = classify_count_risk(risk_count)
    pressure_available = used_percent is not None and free_percent is not None
    status = risk_meta['label'] if pressure_available or risk_count else 'Unknown'
    tone = risk_meta['tone'] if pressure_available or risk_count else 'unknown'

    return {
        'available': True,
        'pressure_available': pressure_available,
        'pvc_requested': raw.get('pvc_requested') or raw.get('requested') or 'N/A',
        'pvc_capacity': raw.get('pvc_capacity') or raw.get('capacity') or 'N/A',
        'pvc_used': raw.get('pvc_used') or raw.get('used') or 'N/A',
        'pvc_free': raw.get('pvc_free') or raw.get('free') or 'N/A',
        'pvc_risk_count': risk_count,
        'used_percent': round(used_percent, 2) if used_percent is not None else None,
        'free_percent': round(free_percent, 2) if free_percent is not None else None,
        'top_namespace': raw.get('top_namespace') or raw.get('top_storage_namespace') or '-',
        'status': status,
        'tone': tone,
        'href': '/analytics/storage',
        'recommendation_count': recommendation_count,
    }


def _get_workload_snapshot(*, cluster_id: str, time_range: str) -> dict[str, Any]:
    default = build_empty_overview_payload()['workload_snapshot']

    if not cluster_id:
        return default

    raw = _call_optional_snapshot(
        module_path='app.kubernetes.analytics.workload.service',
        function_names=[
            'get_workload_snapshot',
        ],
        cluster_id=cluster_id,
        time_range=time_range,
    )

    if not raw:
        return default

    missing_cpu_requests = _safe_int(_as_float_like(raw.get('missing_cpu_requests')))
    missing_memory_requests = _safe_int(_as_float_like(raw.get('missing_memory_requests')))
    cpu_limits_unset = _safe_int(_as_float_like(raw.get('cpu_limits_unset')))
    memory_limits_missing = _safe_int(_as_float_like(raw.get('memory_limits_missing')))
    over_provisioned = _safe_int(_as_float_like(raw.get('over_provisioned')))
    under_provisioned = _safe_int(_as_float_like(raw.get('under_provisioned')))

    issue_count = (
        missing_cpu_requests + missing_memory_requests + memory_limits_missing + over_provisioned + under_provisioned
    )

    recommendation_count = _get_snapshot_recommendation_count(
        raw,
        fallback_count=issue_count,
    )

    risk_meta = classify_count_risk(issue_count)

    return {
        'available': True,
        'missing_cpu_requests': missing_cpu_requests,
        'missing_memory_requests': missing_memory_requests,
        'cpu_limits_unset': cpu_limits_unset,
        'memory_limits_missing': memory_limits_missing,
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
        module_path='app.kubernetes.analytics.top_consumers.service',
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
        'available': True,
        'cpu': _normalize_consumer_items(raw.get('cpu', [])),
        'memory': _normalize_consumer_items(raw.get('memory', [])),
        'storage': _normalize_consumer_items(raw.get('storage', [])),
        'pods': _normalize_consumer_items(raw.get('pods', [])),
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
        module_path='app.kubernetes.analytics.forecast.presentation',
        function_names=[
            'get_forecast_snapshot',
            'get_forecast_overview_snapshot',
        ],
        cluster_id=cluster_id,
        time_range=time_range,
    )

    if not raw:
        return default

    forecast_risk = str(raw.get('forecast_risk', 'Unknown'))
    risk_count = _safe_int(_as_float_like(raw.get('risk_count')))

    if risk_count == 0 and forecast_risk.lower() in ['medium', 'high', 'critical']:
        risk_count = 1

    risk_note = raw.get('risk_note') or (
        f'{risk_count} metric(s) may breach warning thresholds in the forecast window.'
        if risk_count > 0
        else 'No forecast risk detected in the selected time range.'
    )

    return {
        'available': True,
        'cpu_trend': raw.get('cpu_trend', 'Unknown'),
        'memory_trend': raw.get('memory_trend', 'Unknown'),
        'storage_trend': raw.get('storage_trend', 'Unknown'),
        'pod_trend': raw.get('pod_trend', 'Unknown'),
        'risk_count': risk_count,
        'risk_note': risk_note,
        'forecast_risk': forecast_risk,
        'forecast_horizon': raw.get('forecast_horizon', '30 days'),
        'highest_projected_resource': raw.get('highest_projected_resource', 'N/A'),
        'highest_projected_percent': (
            _as_float_like(raw.get('highest_projected_percent'))
            if raw.get('highest_projected_percent') is not None
            else None
        ),
        'nearest_warning': raw.get('nearest_warning', {}),
        'nearest_critical': raw.get('nearest_critical', {}),
        'series': _normalize_forecast_series(raw.get('series', [])),
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
        module_path='app.kubernetes.analytics.alerts.snapshots',
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

    source_connected = bool(raw.get('source_connected', False))
    recommendation_fallback_count = critical_alerts + warning_alerts + recent_anomalies + (0 if source_connected else 1)

    risk_count = firing_alerts + critical_alerts + warning_alerts + pending_alerts
    risk_meta = classify_count_risk(risk_count)
    evidence_complete = bool(raw.get('evidence_complete', source_connected))
    status = str(raw.get('status') or risk_meta['label'])
    tone = str(raw.get('tone') or risk_meta['tone'])

    return {
        'available': True,
        'firing_alerts': firing_alerts,
        'pending_alerts': pending_alerts,
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'recent_anomalies': recent_anomalies,
        'highest_severity': raw.get('highest_severity') or '-',
        'highest_severity_description': (
            raw.get('highest_severity_description') or 'No active critical alert detected.'
        ),
        'status': status,
        'tone': tone,
        'evidence_complete': evidence_complete,
        'anomaly_evidence_partial': bool(raw.get('anomaly_evidence_partial', False)),
        'href': '/analytics/alerts?tab=alerts',
        'source_connected': source_connected,
        'recommendation_count': _get_snapshot_recommendation_count(
            raw,
            fallback_count=recommendation_fallback_count,
        ),
    }


def _build_actionable_recommendation_overview(
    payload: dict[str, Any],
) -> dict[str, Any]:
    context = _build_actionable_context(payload)
    items = _build_actionable_domain_items(context)
    actionable_items = [
        *items['capacity'],
        *context['utilization_recommendations'],
        *items['storage'],
        *items['workload'],
        *items['forecast'],
        *items['top_consumers'],
        *items['alerts'],
    ]
    critical_count = _count_recommendations_by_priority(actionable_items, 'Critical')
    warning_count = _count_recommendations_by_priority(actionable_items, 'Warning')
    total_count = sum(context['counts'].values())
    status = _actionable_status(
        total_count=total_count,
        critical_count=critical_count,
        evidence_available=context['evidence_available'],
        evidence_complete=context['evidence_complete'],
    )

    return {
        'total_count': total_count,
        **status,
        'evidence_available': context['evidence_available'],
        'evidence_complete': context['evidence_complete'],
        'available_dataset_count': context['available_dataset_count'],
        'expected_dataset_count': context['expected_dataset_count'],
        'sources': _build_actionable_sources(context),
        'priority_summary': {'critical': critical_count, 'warning': warning_count},
        'items': actionable_items,
        'capacity_recommendations': items['capacity'],
        'utilization_recommendations': context['utilization_recommendations'],
        'storage_recommendations': items['storage'],
        'workload_recommendations': items['workload'],
        'forecast_recommendations': items['forecast'],
        'top_consumers_recommendations': items['top_consumers'],
        'alerts_recommendations': items['alerts'],
    }


def _build_actionable_context(payload: dict[str, Any]) -> dict[str, Any]:
    snapshots = {
        'capacity': _as_dict(payload.get('capacity_snapshot')),
        'resource': _as_dict(payload.get('resource_snapshot')),
        'storage': _as_dict(payload.get('storage_snapshot')),
        'workload': _as_dict(payload.get('workload_snapshot')),
        'top_consumers': _as_dict(payload.get('top_consumers')),
        'forecast': _as_dict(payload.get('forecast_snapshot')),
        'alerts': _as_dict(payload.get('alerts_snapshot')),
    }
    summary = _as_dict(payload.get('snapshot_summary'))
    available_count = _safe_int(_as_float_like(summary.get('available_dataset_count')))
    current_count = _safe_int(_as_float_like(summary.get('current_dataset_count')))
    expected_count = max(
        1,
        _safe_int(_as_float_like(summary.get('expected_dataset_count', 7))),
    )
    utilization_recommendations = _build_utilization_actionable_recommendations_from_overview(payload)
    counts = {
        'capacity': _get_capacity_actionable_recommendation_count(snapshots['capacity']),
        'utilization': count_actionable_recommendations(utilization_recommendations),
        'storage': _get_snapshot_actionable_count(
            snapshots['storage'],
            fallback_keys=['pvc_risk_count'],
        ),
        'workload': _get_workload_actionable_count(snapshots['workload']),
        'forecast': _get_snapshot_actionable_count(
            snapshots['forecast'],
            fallback_keys=['risk_count'],
        ),
        'top_consumers': _get_snapshot_actionable_count(
            snapshots['top_consumers'],
            fallback_keys=['recommendation_count'],
        ),
        'alerts': _get_alerts_actionable_count(snapshots['alerts']),
    }
    return {
        'snapshots': snapshots,
        'counts': counts,
        'utilization_recommendations': utilization_recommendations,
        'available_dataset_count': available_count,
        'expected_dataset_count': expected_count,
        'evidence_available': available_count > 0,
        'evidence_complete': current_count >= expected_count,
    }


def _build_actionable_domain_items(context: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    counts = context['counts']
    return {
        domain.key: _build_actionable_items_from_count(
            count=counts[domain.key],
            title=domain.aggregate_title,
            description=(
                f'{counts[domain.key]} actionable {domain.aggregate_noun} recommendation(s) were detected. '
                f'{domain.aggregate_guidance}'
            ),
            source=domain.key,
            source_label=domain.label,
            href=domain.href,
            icon=domain.icon,
            warning_threshold=1,
            critical_threshold=domain.critical_threshold,
        )
        for domain in ACTIONABLE_DOMAINS
        if domain.has_aggregate_item
    }


def _actionable_status(
    *,
    total_count: int,
    critical_count: int,
    evidence_available: bool,
    evidence_complete: bool,
) -> dict[str, str]:
    if critical_count > 0:
        return {
            'status': 'Critical',
            'tone': 'red',
            'description': 'Critical actionable recommendation detected across analytics domains.',
        }
    if total_count > 0:
        return {
            'status': 'Review',
            'tone': 'amber',
            'description': 'Actionable recommendation detected across analytics domains.',
        }
    if not evidence_available:
        return {
            'status': 'Unknown',
            'tone': 'gray',
            'description': 'Committed analytics evidence is not available for recommendation assessment.',
        }
    if not evidence_complete:
        return {
            'status': 'Limited',
            'tone': 'amber',
            'description': (
                'No actionable finding is present in the available datasets, but evidence coverage is incomplete.'
            ),
        }
    return {
        'status': 'Normal',
        'tone': 'green',
        'description': 'No actionable recommendation detected across current analytics datasets.',
    }


def _build_actionable_sources(context: dict[str, Any]) -> list[dict[str, Any]]:
    counts = context['counts']
    snapshots = context['snapshots']
    sources = [
        _build_actionable_source(
            label=domain.label,
            count=counts[domain.key],
            href=domain.href,
            description=domain.source_description,
            available=bool(snapshots[domain.evidence_key].get('available', False)),
        )
        for domain in ACTIONABLE_DOMAINS
    ]
    return [source for source in sources if source['available']]


def _build_actionable_source(
    *,
    label: str,
    count: int,
    href: str,
    description: str,
    available: bool,
) -> dict[str, Any]:
    return {
        'label': label,
        'count': count,
        'href': href,
        'tone': _get_count_tone(count),
        'description': description,
        'available': available,
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
    if not snapshot.get('available', False):
        return 0

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
    if not workload_snapshot.get('available', False):
        return 0

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
            'memory_limits_missing',
            'over_provisioned',
            'under_provisioned',
        ]
    )


def _get_alerts_actionable_count(
    alerts_snapshot: dict[str, Any],
) -> int:
    if not alerts_snapshot.get('available', False):
        return 0

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
            'title': 'Review Capacity Actionable Findings',
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
    ) or not capacity_snapshot.get('available', False):
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
    resource_snapshot = _as_dict(payload.get('resource_snapshot'))
    if not resource_snapshot.get('available', False):
        return []

    recommendation_payload = {
        'risk_assessment': _build_utilization_risk_assessment_from_resource_snapshot(resource_snapshot),
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

        value = str(
            item.get('display_value')
            or item.get('value_label')
            or item.get('value')
            or item.get('percent')
            or 'Not Available'
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


def _log_optional_snapshot_failure(
    *,
    module_path: str,
    function_name: str | None,
) -> None:
    if not has_app_context():
        return
    current_app.logger.exception(
        'Analytics Overview could not load committed snapshot presenter %s%s.',
        module_path,
        f'.{function_name}' if function_name else '',
    )


def _call_optional_snapshot(
    *,
    module_path: str,
    function_names: list[str],
    **kwargs: Any,
) -> dict[str, Any] | None:
    try:
        module = __import__(module_path, fromlist=['*'])
    except Exception:
        _log_optional_snapshot_failure(
            module_path=module_path,
            function_name=None,
        )
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
                _log_optional_snapshot_failure(
                    module_path=module_path,
                    function_name=function_name,
                )
                continue
        except Exception:
            _log_optional_snapshot_failure(
                module_path=module_path,
                function_name=function_name,
            )
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
            value = item.get('value') or item.get('usage') or 0
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
                'confidence': str(item.get('confidence') or 'Not Available'),
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


def _maybe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


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
