from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.analytics.capacity.service import get_capacity_page_context
from app.analytics.forecast.service import get_forecast_analysis_context
from app.analytics.storage.service import get_storage_analysis_context
from app.analytics.top_consumers.service import get_top_consumers_context
from app.analytics.utilization.materialization import get_utilization_trend_context
from app.analytics.workload.service import get_workload_analysis_context

ContextBuilder = Callable[[Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class AnalyticsDataset:
    key: str
    label: str
    builder: ContextBuilder
    default_parameters: tuple[dict[str, str], ...]
    freshness_minutes: int
    stale_grace_minutes: int


ANALYTICS_DATASETS: tuple[AnalyticsDataset, ...] = (
    AnalyticsDataset(
        key='analytics.utilization.trend',
        label='Utilization Trend',
        builder=get_utilization_trend_context,
        default_parameters=tuple({'trend_hours': value} for value in ('24', '168', '720', '1440')),
        freshness_minutes=15,
        stale_grace_minutes=720,
    ),
    AnalyticsDataset(
        key='analytics.capacity',
        label='Capacity Analysis',
        builder=get_capacity_page_context,
        default_parameters=tuple({'time_range': value} for value in ('24h', '7d', '30d', '60d')),
        freshness_minutes=20,
        stale_grace_minutes=1440,
    ),
    AnalyticsDataset(
        key='analytics.storage',
        label='Storage Analysis',
        builder=get_storage_analysis_context,
        default_parameters=tuple({'time_range': value} for value in ('24h', '7d', '30d', '60d')),
        freshness_minutes=20,
        stale_grace_minutes=1440,
    ),
    AnalyticsDataset(
        key='analytics.workload',
        label='Workload Analysis',
        builder=get_workload_analysis_context,
        default_parameters=tuple({'time_range': value} for value in ('24h', '7d', '30d', '60d')),
        freshness_minutes=20,
        stale_grace_minutes=1440,
    ),
    AnalyticsDataset(
        key='analytics.top_consumers',
        label='Top Consumers',
        builder=get_top_consumers_context,
        default_parameters=tuple({'time_range': value} for value in ('24h', '7d', '30d', '60d')),
        freshness_minutes=15,
        stale_grace_minutes=720,
    ),
)

FORECAST_DATASET = AnalyticsDataset(
    key='analytics.forecast',
    label='Capacity Forecast',
    builder=get_forecast_analysis_context,
    default_parameters=tuple(
        {
            'history_window': history_window,
            'forecast_horizon': forecast_horizon,
            'resource': 'all',
            'method': 'linear',
        }
        for history_window in ('30d', '90d')
        for forecast_horizon in ('90d', '180d', '365d')
    ),
    freshness_minutes=120,
    stale_grace_minutes=4320,
)

_DATASET_BY_KEY = {item.key: item for item in (*ANALYTICS_DATASETS, FORECAST_DATASET)}


def get_dataset(dataset_key: str) -> AnalyticsDataset:
    try:
        return _DATASET_BY_KEY[dataset_key]
    except KeyError as exc:
        raise LookupError(f'Unknown analytics dataset: {dataset_key}') from exc


def list_analytics_datasets() -> tuple[AnalyticsDataset, ...]:
    return ANALYTICS_DATASETS
