from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.analytics.alerts.application import get_alerts_materialization_context
from app.analytics.capacity.service import get_capacity_page_context
from app.analytics.forecast.service import get_forecast_analysis_context
from app.analytics.storage.service import get_storage_analysis_context
from app.analytics.top_consumers.service import get_top_consumers_context
from app.analytics.utilization.materialization import (
    get_utilization_node_context,
    get_utilization_summary_context,
    get_utilization_trend_context,
)
from app.analytics.workload.service import get_workload_analysis_context
from app.dashboards.kubernetes.snapshot_builder import build_dashboard_alerts_context

ContextBuilder = Callable[[Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class AnalyticsDataset:
    key: str
    label: str
    builder: ContextBuilder
    default_parameters: tuple[dict[str, str], ...]
    freshness_minutes: int
    stale_grace_minutes: int
    snapshot_parameter_keys: tuple[str, ...] = ()
    required_binding_capabilities: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    source_kind: str = 'prometheus'


ANALYTICS_DATASETS: tuple[AnalyticsDataset, ...] = (
    AnalyticsDataset(
        key='dashboard.kubernetes.alerts',
        label='Kubernetes Dashboard Alerts',
        builder=build_dashboard_alerts_context,
        default_parameters=({},),
        freshness_minutes=5,
        stale_grace_minutes=30,
        required_binding_capabilities=('metrics', 'alert_metrics'),
        source_kind='alert',
    ),
    AnalyticsDataset(
        key='analytics.alerts',
        label='Alerts and Anomalies',
        builder=get_alerts_materialization_context,
        default_parameters=({'source': 'auto'},),
        freshness_minutes=5,
        stale_grace_minutes=30,
        snapshot_parameter_keys=('source',),
        required_binding_capabilities=('metrics', 'alert_metrics'),
        source_kind='alert',
    ),
    AnalyticsDataset(
        key='analytics.utilization.summary',
        label='Utilization Summary',
        builder=get_utilization_summary_context,
        default_parameters=({},),
        freshness_minutes=10,
        stale_grace_minutes=120,
        required_binding_capabilities=('metrics', 'utilization'),
        required_capabilities=(
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'utilization_metrics',
            'node_filesystem_identity',
        ),
    ),
    AnalyticsDataset(
        key='analytics.utilization.trend',
        label='Utilization Trend',
        builder=get_utilization_trend_context,
        default_parameters=tuple({'trend_hours': value} for value in ('1', '6', '12', '24', '168', '720', '1440')),
        freshness_minutes=15,
        stale_grace_minutes=720,
        snapshot_parameter_keys=('trend_hours', 'trend_node'),
        required_binding_capabilities=('metrics', 'utilization'),
        required_capabilities=(
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'utilization_metrics',
            'node_filesystem_identity',
        ),
    ),
    AnalyticsDataset(
        key='analytics.utilization.node',
        label='Utilization Node Detail',
        builder=get_utilization_node_context,
        default_parameters=(),
        freshness_minutes=10,
        stale_grace_minutes=120,
        snapshot_parameter_keys=('node',),
        required_binding_capabilities=('metrics', 'utilization'),
        required_capabilities=(
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'utilization_metrics',
            'node_filesystem_identity',
        ),
    ),
    AnalyticsDataset(
        key='analytics.capacity',
        label='Capacity Analysis',
        builder=get_capacity_page_context,
        default_parameters=tuple({'time_range': value} for value in ('1h', '6h', '12h', '24h', '7d', '30d', '60d')),
        freshness_minutes=20,
        stale_grace_minutes=1440,
        snapshot_parameter_keys=('time_range',),
        required_binding_capabilities=('metrics', 'capacity'),
        required_capabilities=(
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'capacity_metrics',
            'resource_requests_limits',
        ),
    ),
    AnalyticsDataset(
        key='analytics.storage',
        label='Storage Analysis',
        builder=get_storage_analysis_context,
        default_parameters=({},),
        freshness_minutes=20,
        stale_grace_minutes=1440,
        required_binding_capabilities=('metrics', 'storage'),
        required_capabilities=(
            'instant_query',
            'kubernetes_identity',
            'pvc_usage',
            'node_filesystem_identity',
        ),
    ),
    AnalyticsDataset(
        key='analytics.workload',
        label='Workload Analysis',
        builder=get_workload_analysis_context,
        default_parameters=tuple({'time_range': value} for value in ('1h', '6h', '12h', '24h', '7d', '30d', '60d')),
        freshness_minutes=20,
        stale_grace_minutes=1440,
        snapshot_parameter_keys=('time_range',),
        required_binding_capabilities=('metrics', 'workload'),
        required_capabilities=(
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'workload_metrics',
            'resource_requests_limits',
        ),
    ),
    AnalyticsDataset(
        key='analytics.top_consumers',
        label='Top Consumers',
        builder=get_top_consumers_context,
        default_parameters=({},),
        freshness_minutes=15,
        stale_grace_minutes=720,
        snapshot_parameter_keys=('namespace',),
        required_binding_capabilities=('metrics', 'top_consumers'),
        required_capabilities=(
            'instant_query',
            'kubernetes_identity',
            'workload_metrics',
            'resource_requests_limits',
            'capacity_metrics',
            'pvc_usage',
        ),
    ),
)

FORECAST_DATASET = AnalyticsDataset(
    key='analytics.forecast',
    label='Capacity Forecast',
    builder=get_forecast_analysis_context,
    default_parameters=tuple(
        {'history_window': history_window}
        for history_window in ('7d', '30d', '90d')
    ),
    freshness_minutes=120,
    stale_grace_minutes=4320,
    snapshot_parameter_keys=('history_window', 'namespace'),
    required_binding_capabilities=('metrics', 'forecast'),
    required_capabilities=('range_query', 'long_term_history', 'capacity_metrics'),
)

_DATASET_BY_KEY = {item.key: item for item in (*ANALYTICS_DATASETS, FORECAST_DATASET)}


def get_dataset(dataset_key: str) -> AnalyticsDataset:
    try:
        return _DATASET_BY_KEY[dataset_key]
    except KeyError as exc:
        raise LookupError(f'Unknown analytics dataset: {dataset_key}') from exc


def source_binding_capabilities(dataset_key: str) -> tuple[str, ...]:
    """Return the minimum binding scope required to execute a dataset.

    Domain-specific binding capabilities remain part of Operational Domain
    Readiness, but they must not prevent a connected metrics binding from
    attempting the actual worker query. The query result is the authoritative
    runtime evidence for materialization.
    """

    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'prometheus':
        return ('metrics',)
    return dataset.required_binding_capabilities


def source_technical_capabilities(dataset_key: str) -> tuple[str, ...]:
    """Return transport capabilities required before the worker may query.

    High-level domain capabilities such as ``workload_metrics`` and
    ``node_filesystem_identity`` are advisory readiness evidence. Instant and
    range query support are the execution boundary enforced before dispatch.
    """

    dataset = get_dataset(dataset_key)
    return tuple(
        capability
        for capability in dataset.required_capabilities
        if capability in {'instant_query', 'range_query'}
    )


def list_analytics_datasets() -> tuple[AnalyticsDataset, ...]:
    return ANALYTICS_DATASETS


def canonical_parameters(dataset_key: str, parameters: Mapping[str, Any] | None) -> dict[str, str]:
    dataset = get_dataset(dataset_key)
    source = parameters or {}
    allowed = {'cluster_id', *dataset.snapshot_parameter_keys}
    return {
        str(key): str(value)
        for key, value in sorted(source.items())
        if key in allowed and value is not None and str(value).strip() != ''
    }
