from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.analytics.shared.params import get_per_page_arg, get_positive_int_arg, get_query_value

TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION = 3

RESOURCE_OPTIONS: list[dict[str, str]] = [
    {'value': 'all', 'label': 'All Resources'},
    {'value': 'cpu', 'label': 'CPU'},
    {'value': 'memory', 'label': 'Memory'},
    {'value': 'pods', 'label': 'Pods'},
    {'value': 'pvc', 'label': 'PVC'},
]

ALL_RESOURCE_SORT_OPTIONS: list[dict[str, str]] = [
    {'value': 'priority', 'label': 'Operational Priority'},
    {'value': 'contribution', 'label': 'Contribution to Scope'},
    {'value': 'namespace', 'label': 'Namespace'},
    {'value': 'resource', 'label': 'Resource Type'},
]

SINGLE_RESOURCE_SORT_OPTIONS: list[dict[str, str]] = [
    {'value': 'absolute', 'label': 'Absolute Consumption'},
    {'value': 'pressure', 'label': 'Pressure Ratio'},
    {'value': 'priority', 'label': 'Operational Priority'},
    {'value': 'namespace', 'label': 'Namespace'},
]

PRIORITY_OPTIONS: list[dict[str, str]] = [
    {'value': '', 'label': 'All Priorities'},
    {'value': 'critical', 'label': 'Critical'},
    {'value': 'warning', 'label': 'Warning'},
    {'value': 'info', 'label': 'Info'},
    {'value': 'normal', 'label': 'Normal'},
    {'value': 'unknown', 'label': 'Unknown'},
]

FOCUS_OPTIONS = {
    '',
    'missing_requests',
    'high_usage',
    'dominant_namespaces',
    'high_pvc',
}

FOCUS_FILTER_OPTIONS: list[dict[str, str]] = [
    {'value': '', 'label': 'All Record Focus'},
    {'value': 'missing_requests', 'label': 'Missing Requests'},
    {'value': 'high_usage', 'label': 'High Compute Pressure'},
    {'value': 'dominant_namespaces', 'label': 'Dominant Namespaces'},
    {'value': 'high_pvc', 'label': 'High PVC Usage'},
]

RESOURCE_LABELS = {
    'cpu': 'CPU',
    'memory': 'Memory',
    'pods': 'Pods',
    'pvc': 'PVC',
}

RESOURCE_ICONS = {
    'cpu': 'cpu',
    'memory': 'memory-stick',
    'pods': 'boxes',
    'pvc': 'database',
}

RISK_RANK = {
    'critical': 4,
    'warning': 3,
    'info': 2,
    'normal': 1,
    'unknown': 0,
}

TOP_CONSUMER_TABS = {'rankings', 'records', 'recommendations'}


def get_selected_resource(query_args: Mapping[str, Any]) -> str:
    selected = get_query_value(
        query_args=query_args,
        name='resource',
        default='all',
    )
    allowed = {item['value'] for item in RESOURCE_OPTIONS}
    return selected if selected in allowed else 'all'


def get_sort_options(selected_resource: str) -> list[dict[str, str]]:
    return SINGLE_RESOURCE_SORT_OPTIONS if selected_resource != 'all' else ALL_RESOURCE_SORT_OPTIONS


def get_selected_sort(
    query_args: Mapping[str, Any],
    selected_resource: str = 'all',
) -> str:
    default_sort = 'absolute' if selected_resource != 'all' else 'priority'
    selected = get_query_value(
        query_args=query_args,
        name='sort',
        default=default_sort,
    )
    allowed = {item['value'] for item in get_sort_options(selected_resource)}
    return selected if selected in allowed else default_sort


def get_selected_priority(query_args: Mapping[str, Any]) -> str:
    selected = get_query_value(
        query_args=query_args,
        name='priority',
        default='',
    )
    allowed = {item['value'] for item in PRIORITY_OPTIONS}
    return selected if selected in allowed else ''


def get_selected_tab(
    query_args: Mapping[str, Any],
    default: str = 'rankings',
) -> str:
    selected = get_query_value(
        query_args=query_args,
        name='tab',
        default=default,
    )
    return selected if selected in TOP_CONSUMER_TABS else default


def get_selected_focus(query_args: Mapping[str, Any]) -> str:
    selected = get_query_value(
        query_args=query_args,
        name='focus',
        default='',
    )
    return selected if selected in FOCUS_OPTIONS else ''


@dataclass(frozen=True, slots=True)
class TopConsumersSelection:
    namespace: str = ''
    resource: str = 'all'
    search: str = ''
    sort: str = 'priority'
    priority: str = ''
    focus: str = ''
    page: int = 1
    per_page: int = 5

    @classmethod
    def from_mapping(cls, query_args: Mapping[str, Any]) -> TopConsumersSelection:
        resource = get_selected_resource(query_args)
        return cls(
            namespace=get_query_value(query_args=query_args, name='namespace', default=''),
            resource=resource,
            search=get_query_value(query_args=query_args, name='search', default=''),
            sort=get_selected_sort(query_args, resource),
            priority=get_selected_priority(query_args),
            focus=get_selected_focus(query_args),
            page=get_positive_int_arg(query_args=query_args, name='page', default=1),
            per_page=get_per_page_arg(query_args=query_args, name='per_page', default=5),
        )
