from __future__ import annotations

from typing import Any

from app.kubernetes.analytics.common.base_service import bytes_to_gib, safe_round

REQUIRED_QUOTA_KEYS = (
    'requests.cpu',
    'limits.cpu',
    'requests.memory',
    'limits.memory',
    'pods',
)

WORKLOAD_TIME_RANGE_STEP_MAP = {
    '1h': '5m',
    '6h': '15m',
    '12h': '30m',
    '24h': '1h',
    '7d': '6h',
    '30d': '12h',
    '60d': '1d',
}


def get_workload_time_step(time_range: str) -> str:
    return WORKLOAD_TIME_RANGE_STEP_MAP.get(time_range, '1h')


def format_decimal(value: float, digits: int = 2) -> str:
    return f'{safe_round(value, digits):.{digits}f}'


def format_cpu_core(value: float) -> str:
    return f'{format_decimal(value, 2)} core'


def format_memory_gib(value: float) -> str:
    return f'{format_decimal(bytes_to_gib(value), 2)} GiB'


def format_count(value: float) -> str:
    return f'{safe_round(value, 0):.0f}'


def resource_quota_label(key: str) -> str:
    return {
        'requests.cpu': 'Requests CPU',
        'limits.cpu': 'Limits CPU',
        'requests.memory': 'Requests Memory',
        'limits.memory': 'Limits Memory',
        'pods': 'Pods',
    }.get(key, key)


def format_resource_quota_value(key: str, value: float) -> str:
    if key.endswith('.cpu'):
        return format_cpu_core(value)
    if key.endswith('.memory'):
        return format_memory_gib(value)
    if key == 'pods':
        return f'{format_count(value)} pods'
    return format_decimal(value)


def build_resource_quota_items(values: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {
            'label': resource_quota_label(key),
            'value': format_resource_quota_value(key, value),
        }
        for key, value in sorted(values.items())
    ]
