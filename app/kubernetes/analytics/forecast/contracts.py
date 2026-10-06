from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

WARNING_THRESHOLD = 75.0
CRITICAL_THRESHOLD = 90.0

HISTORY_WINDOW_OPTIONS: list[dict[str, str]] = [
    {'value': '7d', 'label': '7 Days'},
    {'value': '30d', 'label': '30 Days'},
    {'value': '90d', 'label': '90 Days'},
]

FORECAST_HORIZON_OPTIONS: list[dict[str, str]] = [
    {'value': '7d', 'label': '7 Days'},
    {'value': '30d', 'label': '30 Days'},
    {'value': '90d', 'label': '90 Days'},
    {'value': '180d', 'label': '180 Days'},
    {'value': '365d', 'label': '365 Days'},
]

FORECAST_METHOD_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'holt_winters',
        'label': 'Holt-Winters',
        'description': 'Projects the selected horizon from level, trend, and weekly seasonal signals.',
    },
    {
        'value': 'linear',
        'label': 'Linear Trend',
        'description': 'Projects future usage from a simple historical trend baseline.',
    },
    {
        'value': 'conservative',
        'label': 'Conservative Trend',
        'description': 'Applies a 15% planning uplift to positive Holt-Winters projection growth.',
    },
]

FORECAST_RESOURCE_KEYS = ('cpu', 'memory', 'storage', 'pods')
FORECAST_TABS = (*FORECAST_RESOURCE_KEYS, 'trend', 'recommendations')


@dataclass(frozen=True, slots=True)
class ForecastResourceDefinition:
    key: str
    label: str
    unit: str
    icon: str
    description: str
    scope_label: str
    comparison_label: str
    capacity_label: str
    usage_query: str
    capacity_query: str


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    timestamp: datetime
    value: float
