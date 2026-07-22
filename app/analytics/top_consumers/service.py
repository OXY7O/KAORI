# app/analytics/top_consumers/service.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from app.analytics.common.base_service import AnalyticsBaseService, raw_percent, safe_round
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_per_page_arg,
    get_positive_int_arg,
    get_query_value,
)
from app.integrations.prometheus.query_profiles import get_query_expression
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_connection_blocker
from app.intelligence.recommendation_engine import (
    build_top_consumers_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster
from app.integrations.prometheus.exceptions import PrometheusError
from app.prometheus.service import PrometheusService

CPU_ALLOCATABLE_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_ALLOCATABLE_QUERY')
CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY')
CPU_LIMIT_BY_CONTAINER_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_QUERY')
CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY')
CPU_REQUEST_BY_CONTAINER_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_QUERY')
MEMORY_ALLOCATABLE_QUERY = get_query_expression('analytics.top_consumers.queries.MEMORY_ALLOCATABLE_QUERY')
MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY')
MEMORY_LIMIT_BY_CONTAINER_QUERY = get_query_expression('analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_QUERY')
MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY')
MEMORY_REQUEST_BY_CONTAINER_QUERY = get_query_expression('analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_QUERY')
NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.top_consumers.queries.NAMESPACE_ACTIVE_QUERY')
POD_CAPACITY_QUERY = get_query_expression('analytics.top_consumers.queries.POD_CAPACITY_QUERY')
PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY')
PVC_CAPACITY_BY_CLAIM_QUERY = get_query_expression('analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_QUERY')
TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY')
TOP_CPU_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY')
TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY')
TOP_MEMORY_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY')
TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY')
TOP_POD_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_POD_CONSUMERS_QUERY')
TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY')
TOP_PVC_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_PVC_CONSUMERS_QUERY')
TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY')
TOTAL_CPU_USAGE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_CPU_USAGE_QUERY')
TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY')
TOTAL_MEMORY_USAGE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_QUERY')
TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY')
TOTAL_PVC_CAPACITY_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_PVC_CAPACITY_QUERY')
TOTAL_PVC_USED_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_PVC_USED_BY_NAMESPACE_QUERY')
TOTAL_PVC_USED_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_PVC_USED_QUERY')
TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY')
TOTAL_RUNNING_PODS_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_RUNNING_PODS_QUERY')

RESOURCE_OPTIONS: list[dict[str, str]] = [
    {'value': 'all', 'label': 'All Resources'},
    {'value': 'cpu', 'label': 'CPU'},
    {'value': 'memory', 'label': 'Memory'},
    {'value': 'pods', 'label': 'Pods'},
    {'value': 'pvc', 'label': 'PVC'},
]

TOP_CONSUMERS_TIME_RANGE_OPTIONS: list[dict[str, str]] = [
    {'value': '1h', 'label': '1h'},
    {'value': '6h', 'label': '6h'},
    {'value': '12h', 'label': '12h'},
    {'value': '24h', 'label': '24h'},
    {'value': '7d', 'label': '7d'},
    {'value': '30d', 'label': '30d'},
    {'value': '60d', 'label': '60d'},
]

SORT_OPTIONS: list[dict[str, str]] = [
    {'value': 'usage_percent', 'label': 'Usage %'},
    {'value': 'usage', 'label': 'Current Usage'},
    {'value': 'risk', 'label': 'Risk'},
    {'value': 'namespace', 'label': 'Namespace'},
    {'value': 'resource', 'label': 'Resource Type'},
]

FOCUS_OPTIONS = {
    '',
    'missing_requests',
    'high_usage',
    'dominant_namespaces',
    'high_pvc',
}

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

RESOURCE_BADGE_CLASSES = {
    'cpu': 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300',
    'memory': 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300',
    'pods': 'bg-violet-50 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300',
    'pvc': 'bg-orange-50 text-orange-700 dark:bg-orange-950/60 dark:text-orange-300',
}

RISK_RANK = {
    'critical': 3,
    'warning': 2,
    'normal': 1,
    'unknown': 0,
}


class TopConsumersSnapshot(TypedDict):
    cpu: list[dict[str, Any]]
    memory: list[dict[str, Any]]
    storage: list[dict[str, Any]]
    recommendation_count: int


def get_selected_resource(
    query_args: Mapping[str, Any],
) -> str:
    selected_resource = get_query_value(
        query_args=query_args,
        name='resource',
        default='all',
    )

    allowed_values = {item['value'] for item in RESOURCE_OPTIONS}

    if selected_resource not in allowed_values:
        return 'all'

    return selected_resource


def get_selected_sort(
    query_args: Mapping[str, Any],
) -> str:
    selected_sort = get_query_value(
        query_args=query_args,
        name='sort',
        default='usage_percent',
    )

    allowed_values = {item['value'] for item in SORT_OPTIONS}

    if selected_sort not in allowed_values:
        return 'usage_percent'

    return selected_sort


def get_selected_top_consumers_time_range(
    query_args: Mapping[str, Any],
) -> str:
    selected_time_range = get_query_value(
        query_args=query_args,
        name='time_range',
        default='24h',
    )

    allowed_values = {item['value'] for item in TOP_CONSUMERS_TIME_RANGE_OPTIONS}

    if selected_time_range not in allowed_values:
        return '24h'

    return selected_time_range


def get_selected_focus(
    query_args: Mapping[str, Any],
) -> str:
    selected_focus = get_query_value(
        query_args=query_args,
        name='focus',
        default='',
    )

    if selected_focus not in FOCUS_OPTIONS:
        return ''

    return selected_focus


class TopConsumersService(AnalyticsBaseService):
    def __init__(
        self,
        utilization_service: UtilizationService,
    ) -> None:
        self.utilization_service = utilization_service

    def get_prometheus_status(
        self,
    ) -> dict[str, Any]:
        return self.utilization_service.get_prometheus_status()

    def get_namespace_options(
        self,
    ) -> list[str]:
        result = self.get_prometheus_result(
            NAMESPACE_ACTIVE_QUERY,
        )

        namespaces: set[str] = set()

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            namespace = metric.get(
                'namespace',
                '',
            )

            if (
                isinstance(
                    namespace,
                    str,
                )
                and namespace
            ):
                namespaces.add(
                    namespace,
                )

        return sorted(
            namespaces,
        )

    def get_top_consumers_payload(
        self,
        *,
        selected_namespace: str,
        selected_resource: str,
        selected_search: str,
        selected_sort: str,
        selected_focus: str,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        cpu_rows = self.get_cpu_consumer_rows(
            selected_namespace=selected_namespace,
        )
        memory_rows = self.get_memory_consumer_rows(
            selected_namespace=selected_namespace,
        )
        pod_rows = self.get_pod_consumer_rows(
            selected_namespace=selected_namespace,
        )
        pvc_rows = self.get_pvc_consumer_rows(
            selected_namespace=selected_namespace,
        )

        all_rows = cpu_rows + memory_rows + pod_rows + pvc_rows
        filtered_rows = self.filter_rows(
            rows=all_rows,
            selected_search=selected_search,
            selected_resource=selected_resource,
            selected_focus=selected_focus,
        )
        sorted_rows = self.sort_rows(
            rows=filtered_rows,
            selected_sort=selected_sort,
        )

        ranked_rows = []
        for index, row in enumerate(
            sorted_rows,
            start=1,
        ):
            updated_row = dict(
                row,
            )
            updated_row['rank'] = index
            ranked_rows.append(
                updated_row,
            )

        page_payload = self.paginate_consumer_rows(
            rows=ranked_rows,
            page=page,
            per_page=per_page,
        )

        payload = {
            'has_data': bool(all_rows),
            'message': None,
            'summary': self.get_summary_cards(
                cpu_rows=cpu_rows,
                memory_rows=memory_rows,
                pod_rows=pod_rows,
                pvc_rows=pvc_rows,
            ),
            'overview': self.get_overview_payload(
                cpu_rows=cpu_rows,
                memory_rows=memory_rows,
                pod_rows=pod_rows,
                pvc_rows=pvc_rows,
                selected_namespace=selected_namespace,
            ),
            'rows': page_payload['rows'],
            'all_rows': all_rows,
            'pagination': page_payload['pagination'],
            'total_rows': len(filtered_rows),
        }

        actionable_recommendations = build_top_consumers_actionable_recommendations(
            payload,
        )
        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Review top consumers',
            default_description='Review CPU, memory, pod, and PVC consumer hotspots.',
            default_source='top_consumers',
            default_action_type='consumer_review',
        )

        payload.update(
            {
                'actionable_recommendations': actionable_recommendations,
                'recommendation_cards': recommendation_cards,
                'recommendation_count': count_actionable_recommendations(
                    actionable_recommendations,
                ),
                'recommendations': recommendation_cards,
            }
        )

        return payload

    def get_cpu_consumer_rows(
        self,
        selected_namespace: str,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=TOP_CPU_CONSUMERS_QUERY,
            namespace_query=TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY,
        )
        request_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=CPU_REQUEST_BY_CONTAINER_QUERY,
            namespace_query=CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY,
        )
        limit_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=CPU_LIMIT_BY_CONTAINER_QUERY,
            namespace_query=CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY,
        )

        request_map = self.get_container_value_map(
            query=request_query,
        )
        limit_map = self.get_container_value_map(
            query=limit_query,
        )

        rows: list[dict[str, Any]] = []

        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(
                item,
            )
            namespace = get_metric_label(
                metric,
                'namespace',
            )
            pod = get_metric_label(
                metric,
                'pod',
            )
            container = get_metric_label(
                metric,
                'container',
            )

            if not namespace or not pod or not container:
                continue

            key = get_container_key(
                namespace=namespace,
                pod=pod,
                container=container,
            )
            usage = self.extract_value(
                item,
            )
            request = request_map.get(
                key,
                0.0,
            )
            limit = limit_map.get(
                key,
                0.0,
            )
            usage_percent = get_usage_percent(
                usage=usage,
                request=request,
                limit=limit,
            )
            risk = get_usage_risk(
                usage_percent,
            )

            rows.append(
                self.build_consumer_row(
                    namespace=namespace,
                    workload=build_workload_label(
                        primary=container,
                        secondary=pod,
                    ),
                    resource_type='cpu',
                    current_usage=usage,
                    current_display=format_cpu(
                        usage,
                    ),
                    request=request,
                    request_display=format_cpu(
                        request,
                    )
                    if request > 0
                    else '-',
                    limit=limit,
                    limit_display=format_cpu(
                        limit,
                    )
                    if limit > 0
                    else '-',
                    usage_percent=usage_percent,
                    risk=risk,
                    recommendation=get_resource_recommendation(
                        resource_type='cpu',
                        usage_percent=usage_percent,
                        request=request,
                        limit=limit,
                    ),
                    pod=pod,
                    container=container,
                )
            )

        return rows

    def get_memory_consumer_rows(
        self,
        selected_namespace: str,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=TOP_MEMORY_CONSUMERS_QUERY,
            namespace_query=TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY,
        )
        request_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=MEMORY_REQUEST_BY_CONTAINER_QUERY,
            namespace_query=MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY,
        )
        limit_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=MEMORY_LIMIT_BY_CONTAINER_QUERY,
            namespace_query=MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY,
        )

        request_map = self.get_container_value_map(
            query=request_query,
        )
        limit_map = self.get_container_value_map(
            query=limit_query,
        )

        rows: list[dict[str, Any]] = []

        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(
                item,
            )
            namespace = get_metric_label(
                metric,
                'namespace',
            )
            pod = get_metric_label(
                metric,
                'pod',
            )
            container = get_metric_label(
                metric,
                'container',
            )

            if not namespace or not pod or not container:
                continue

            key = get_container_key(
                namespace=namespace,
                pod=pod,
                container=container,
            )
            usage = self.extract_value(
                item,
            )
            request = request_map.get(
                key,
                0.0,
            )
            limit = limit_map.get(
                key,
                0.0,
            )
            usage_percent = get_usage_percent(
                usage=usage,
                request=request,
                limit=limit,
            )
            risk = get_usage_risk(
                usage_percent,
            )

            rows.append(
                self.build_consumer_row(
                    namespace=namespace,
                    workload=build_workload_label(
                        primary=container,
                        secondary=pod,
                    ),
                    resource_type='memory',
                    current_usage=usage,
                    current_display=format_bytes(
                        usage,
                    ),
                    request=request,
                    request_display=format_bytes(
                        request,
                    )
                    if request > 0
                    else '-',
                    limit=limit,
                    limit_display=format_bytes(
                        limit,
                    )
                    if limit > 0
                    else '-',
                    usage_percent=usage_percent,
                    risk=risk,
                    recommendation=get_resource_recommendation(
                        resource_type='memory',
                        usage_percent=usage_percent,
                        request=request,
                        limit=limit,
                    ),
                    pod=pod,
                    container=container,
                )
            )

        return rows

    def get_pod_consumer_rows(
        self,
        selected_namespace: str,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=TOP_POD_CONSUMERS_QUERY,
            namespace_query=TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY,
        )
        pod_capacity = self.get_prometheus_scalar(
            POD_CAPACITY_QUERY,
        )

        rows: list[dict[str, Any]] = []

        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(
                item,
            )
            namespace = get_metric_label(
                metric,
                'namespace',
            )

            if not namespace:
                continue

            usage = self.extract_value(
                item,
            )
            usage_percent = raw_percent(
                usage,
                pod_capacity,
            )
            risk = get_usage_risk(
                usage_percent,
            )

            rows.append(
                self.build_consumer_row(
                    namespace=namespace,
                    workload=namespace,
                    resource_type='pods',
                    current_usage=usage,
                    current_display=f'{int(usage)} pods',
                    request=0,
                    request_display='-',
                    limit=pod_capacity,
                    limit_display=f'{int(pod_capacity)} pods' if pod_capacity > 0 else '-',
                    usage_percent=usage_percent,
                    risk=risk,
                    recommendation=get_resource_recommendation(
                        resource_type='pods',
                        usage_percent=usage_percent,
                        request=0,
                        limit=pod_capacity,
                    ),
                    pod='',
                    container='',
                )
            )

        return rows

    def get_pvc_consumer_rows(
        self,
        selected_namespace: str,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=TOP_PVC_CONSUMERS_QUERY,
            namespace_query=TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY,
        )
        capacity_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=PVC_CAPACITY_BY_CLAIM_QUERY,
            namespace_query=PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY,
        )

        capacity_map = self.get_pvc_value_map(
            query=capacity_query,
        )

        rows: list[dict[str, Any]] = []

        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(
                item,
            )
            namespace = get_metric_label(
                metric,
                'namespace',
            )
            pvc_name = get_metric_label(
                metric,
                'persistentvolumeclaim',
            )

            if not namespace or not pvc_name:
                continue

            key = get_pvc_key(
                namespace=namespace,
                pvc_name=pvc_name,
            )
            usage = self.extract_value(
                item,
            )
            capacity = capacity_map.get(
                key,
                0.0,
            )
            usage_percent = raw_percent(
                usage,
                capacity,
            )
            risk = get_usage_risk(
                usage_percent,
            )

            rows.append(
                self.build_consumer_row(
                    namespace=namespace,
                    workload=pvc_name,
                    resource_type='pvc',
                    current_usage=usage,
                    current_display=format_bytes(
                        usage,
                    ),
                    request=0,
                    request_display='-',
                    limit=capacity,
                    limit_display=format_bytes(
                        capacity,
                    )
                    if capacity > 0
                    else '-',
                    usage_percent=usage_percent,
                    risk=risk,
                    recommendation=get_resource_recommendation(
                        resource_type='pvc',
                        usage_percent=usage_percent,
                        request=0,
                        limit=capacity,
                    ),
                    pod='',
                    container='',
                )
            )

        return rows

    def build_consumer_row(
        self,
        *,
        namespace: str,
        workload: str,
        resource_type: str,
        current_usage: float,
        current_display: str,
        request: float,
        request_display: str,
        limit: float,
        limit_display: str,
        usage_percent: float,
        risk: dict[str, str],
        recommendation: str,
        pod: str,
        container: str,
    ) -> dict[str, Any]:
        return {
            'rank': 0,
            'namespace': namespace,
            'workload': workload,
            'pod': pod,
            'container': container,
            'resource_type': resource_type,
            'resource_label': RESOURCE_LABELS.get(
                resource_type,
                resource_type.title(),
            ),
            'resource_icon': RESOURCE_ICONS.get(
                resource_type,
                'activity',
            ),
            'resource_class': RESOURCE_BADGE_CLASSES.get(
                resource_type,
                'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
            ),
            'current_usage': current_usage,
            'current_display': current_display,
            'request': request,
            'request_display': request_display,
            'limit': limit,
            'limit_display': limit_display,
            'usage_percent': safe_round(
                usage_percent,
                1,
            ),
            'usage_bar_percent': min(
                safe_round(
                    usage_percent,
                    1,
                ),
                100,
            ),
            'risk': risk,
            'recommendation': recommendation,
        }

    def get_container_value_map(
        self,
        query: str,
    ) -> dict[str, float]:
        values: dict[str, float] = {}

        for item in self.get_prometheus_result(query):
            metric = self.get_metric_dict(
                item,
            )
            namespace = get_metric_label(
                metric,
                'namespace',
            )
            pod = get_metric_label(
                metric,
                'pod',
            )
            container = get_metric_label(
                metric,
                'container',
            )

            if not namespace or not pod or not container:
                continue

            values[
                get_container_key(
                    namespace=namespace,
                    pod=pod,
                    container=container,
                )
            ] = self.extract_value(
                item,
            )

        return values

    def get_pvc_value_map(
        self,
        query: str,
    ) -> dict[str, float]:
        values: dict[str, float] = {}

        for item in self.get_prometheus_result(query):
            metric = self.get_metric_dict(
                item,
            )
            namespace = get_metric_label(
                metric,
                'namespace',
            )
            pvc_name = get_metric_label(
                metric,
                'persistentvolumeclaim',
            )

            if not namespace or not pvc_name:
                continue

            values[
                get_pvc_key(
                    namespace=namespace,
                    pvc_name=pvc_name,
                )
            ] = self.extract_value(
                item,
            )

        return values

    def get_metric_dict(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        metric = item.get(
            'metric',
            {},
        )

        if isinstance(
            metric,
            dict,
        ):
            return metric

        return {}

    def get_summary_cards(
        self,
        *,
        cpu_rows: list[dict[str, Any]],
        memory_rows: list[dict[str, Any]],
        pod_rows: list[dict[str, Any]],
        pvc_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cpu_allocatable = self.get_prometheus_scalar(
            CPU_ALLOCATABLE_QUERY,
        )
        memory_allocatable = self.get_prometheus_scalar(
            MEMORY_ALLOCATABLE_QUERY,
        )
        pod_capacity = self.get_prometheus_scalar(
            POD_CAPACITY_QUERY,
        )

        return {
            'highest_cpu': build_summary_card(
                rows=cpu_rows,
                title='Highest CPU Consumer',
                empty_label='No CPU data',
                empty_value='0 cores',
                capacity=cpu_allocatable,
                capacity_text='of cluster allocatable CPU',
            ),
            'highest_memory': build_summary_card(
                rows=memory_rows,
                title='Highest Memory Consumer',
                empty_label='No memory data',
                empty_value='0 B',
                capacity=memory_allocatable,
                capacity_text='of cluster allocatable memory',
            ),
            'highest_pods': build_summary_card(
                rows=pod_rows,
                title='Highest Pod Count',
                empty_label='No pod data',
                empty_value='0 pods',
                capacity=pod_capacity,
                capacity_text='of total pod capacity',
            ),
            'highest_pvc': build_summary_card(
                rows=pvc_rows,
                title='Highest PVC Usage',
                empty_label='No PVC data',
                empty_value='0%',
                capacity=None,
                capacity_text='PVC usage',
                use_usage_percent=True,
            ),
        }

    def get_overview_payload(
        self,
        *,
        cpu_rows: list[dict[str, Any]],
        memory_rows: list[dict[str, Any]],
        pod_rows: list[dict[str, Any]],
        pvc_rows: list[dict[str, Any]],
        selected_namespace: str,
    ) -> dict[str, Any]:
        total_cpu_usage = self.get_prometheus_scalar(
            render_namespace_query(
                namespace=selected_namespace,
                all_query=TOTAL_CPU_USAGE_QUERY,
                namespace_query=TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY,
            )
        )
        total_memory_usage = self.get_prometheus_scalar(
            render_namespace_query(
                namespace=selected_namespace,
                all_query=TOTAL_MEMORY_USAGE_QUERY,
                namespace_query=TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY,
            )
        )
        total_running_pods = self.get_prometheus_scalar(
            render_namespace_query(
                namespace=selected_namespace,
                all_query=TOTAL_RUNNING_PODS_QUERY,
                namespace_query=TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY,
            )
        )
        total_pvc_used = self.get_prometheus_scalar(
            render_namespace_query(
                namespace=selected_namespace,
                all_query=TOTAL_PVC_USED_QUERY,
                namespace_query=TOTAL_PVC_USED_BY_NAMESPACE_QUERY,
            )
        )
        total_pvc_capacity = self.get_prometheus_scalar(
            render_namespace_query(
                namespace=selected_namespace,
                all_query=TOTAL_PVC_CAPACITY_QUERY,
                namespace_query=TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY,
            )
        )
        cpu_allocatable = self.get_prometheus_scalar(
            CPU_ALLOCATABLE_QUERY,
        )
        memory_allocatable = self.get_prometheus_scalar(
            MEMORY_ALLOCATABLE_QUERY,
        )
        pod_capacity = self.get_prometheus_scalar(
            POD_CAPACITY_QUERY,
        )

        return {
            'cpu_chart': build_chart_series(
                rows=cpu_rows,
                unit='cores',
                total_usage=total_cpu_usage,
            ),
            'memory_chart': build_chart_series(
                rows=memory_rows,
                unit='bytes',
                total_usage=total_memory_usage,
            ),
            'summary': {
                'total_cpu_used': format_cpu(
                    total_cpu_usage,
                ),
                'total_cpu_percent': safe_round(
                    raw_percent(
                        total_cpu_usage,
                        cpu_allocatable,
                    ),
                    1,
                ),
                'total_memory_used': format_bytes(
                    total_memory_usage,
                ),
                'total_memory_percent': safe_round(
                    raw_percent(
                        total_memory_usage,
                        memory_allocatable,
                    ),
                    1,
                ),
                'total_pods': int(
                    total_running_pods,
                ),
                'total_pods_percent': safe_round(
                    raw_percent(
                        total_running_pods,
                        pod_capacity,
                    ),
                    1,
                ),
                'total_pvc_used': format_bytes(
                    total_pvc_used,
                ),
                'total_pvc_percent': safe_round(
                    raw_percent(
                        total_pvc_used,
                        total_pvc_capacity,
                    ),
                    1,
                ),
            },
        }

    def filter_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        selected_search: str,
        selected_resource: str,
        selected_focus: str,
    ) -> list[dict[str, Any]]:
        filtered_rows: list[dict[str, Any]] = []
        dominant_namespace_names = set(
            get_dominant_namespace_names(
                rows,
            )
        )

        for row in rows:
            resource_type = str(
                row.get(
                    'resource_type',
                    '',
                )
            )
            namespace = str(
                row.get(
                    'namespace',
                    '',
                )
            )
            usage_percent = float(
                row.get(
                    'usage_percent',
                    0,
                )
            )
            request = float(
                row.get(
                    'request',
                    0,
                )
            )

            if selected_focus == 'missing_requests':
                if resource_type not in [
                    'cpu',
                    'memory',
                ]:
                    continue

                if request > 0:
                    continue

            elif selected_focus == 'high_usage':
                if resource_type not in [
                    'cpu',
                    'memory',
                ]:
                    continue

                if usage_percent < 75:
                    continue

            elif selected_focus == 'dominant_namespaces':
                if namespace not in dominant_namespace_names:
                    continue

            elif selected_focus == 'high_pvc':
                if resource_type != 'pvc':
                    continue

                if usage_percent < 80:
                    continue

            if selected_resource != 'all' and resource_type != selected_resource:
                continue

            if selected_search:
                haystack = ' '.join(
                    str(
                        row.get(
                            key,
                            '',
                        )
                    )
                    for key in [
                        'namespace',
                        'workload',
                        'pod',
                        'container',
                        'resource_label',
                        'recommendation',
                    ]
                ).lower()

                if selected_search.lower() not in haystack:
                    continue

            filtered_rows.append(
                row,
            )

        return filtered_rows

    def sort_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        selected_sort: str,
    ) -> list[dict[str, Any]]:
        if selected_sort == 'usage':
            return sorted(
                rows,
                key=lambda row: float(row.get('current_usage', 0)),
                reverse=True,
            )

        if selected_sort == 'risk':
            return sorted(
                rows,
                key=lambda row: RISK_RANK.get(
                    str(row.get('risk', {}).get('key', 'unknown')),
                    0,
                ),
                reverse=True,
            )

        if selected_sort == 'namespace':
            return sorted(
                rows,
                key=lambda row: str(row.get('namespace', '')),
            )

        if selected_sort == 'resource':
            return sorted(
                rows,
                key=lambda row: str(row.get('resource_type', '')),
            )

        return sorted(
            rows,
            key=lambda row: float(row.get('usage_percent', 0)),
            reverse=True,
        )

    def paginate_consumer_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        return self.paginate_rows_with_options(
            rows=rows,
            page=page,
            per_page=per_page,
            allowed_per_page=ALLOWED_PER_PAGE_VALUES,
            default_per_page=5,
        )


def get_top_consumers_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
    )

    selected_namespace = get_query_value(
        query_args=query_args,
        name='namespace',
        default='',
    )
    selected_resource = get_selected_resource(
        query_args=query_args,
    )
    selected_time_range = get_selected_top_consumers_time_range(
        query_args=query_args,
    )
    selected_search = get_query_value(
        query_args=query_args,
        name='search',
        default='',
    )
    selected_sort = get_selected_sort(
        query_args=query_args,
    )
    selected_focus = get_selected_focus(
        query_args=query_args,
    )
    page = get_positive_int_arg(
        query_args=query_args,
        name='page',
        default=1,
    )
    per_page = get_per_page_arg(
        query_args=query_args,
        name='per_page',
        default=5,
    )

    context.update(
        {
            'selected_namespace': selected_namespace,
            'selected_resource': selected_resource,
            'selected_time_range': selected_time_range,
            'selected_search': selected_search,
            'selected_focus': selected_focus,
            'selected_sort': selected_sort,
            'resource_options': RESOURCE_OPTIONS,
            'sort_options': SORT_OPTIONS,
            'allowed_time_ranges': TOP_CONSUMERS_TIME_RANGE_OPTIONS,
            'allowed_per_page_values': ALLOWED_PER_PAGE_VALUES,
            'namespace_options': [],
            'consumer_payload': get_empty_top_consumers_payload(
                message='No cluster available. Add a Kubernetes cluster first.',
                page=page,
                per_page=per_page,
            ),
        }
    )

    if utilization_service is None or cluster is None:
        return context

    top_consumers_service = TopConsumersService(
        utilization_service=utilization_service,
    )

    try:
        prometheus_status = top_consumers_service.get_prometheus_status()
    except PrometheusError as exc:
        prometheus_status = {
            'connected': False,
            'label': 'Prometheus Disconnected',
            'response_time_ms': None,
            'error': str(exc),
        }
    except Exception as exc:
        prometheus_status = {
            'connected': False,
            'label': 'Prometheus Error',
            'response_time_ms': None,
            'error': str(exc),
        }

    context['prometheus_status'] = prometheus_status
    context['prometheus_connected'] = bool(
        prometheus_status.get(
            'connected',
            False,
        )
    )

    if not prometheus_status.get(
        'connected',
        False,
    ):
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=safe_message(
                value=prometheus_status.get('error'),
                default='Prometheus health check did not complete successfully.',
            ),
        )
        context['consumer_payload'] = get_empty_top_consumers_payload(
            message=safe_message(
                value=prometheus_status.get(
                    'error',
                ),
                default='Prometheus is not connected for the selected cluster.',
            ),
            page=page,
            per_page=per_page,
        )

        return context

    try:
        namespace_options = top_consumers_service.get_namespace_options()
    except Exception:
        namespace_options = []

    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    context['selected_namespace'] = selected_namespace
    context['namespace_options'] = namespace_options

    try:
        consumer_payload = top_consumers_service.get_top_consumers_payload(
            selected_namespace=selected_namespace,
            selected_resource=selected_resource,
            selected_search=selected_search,
            selected_sort=selected_sort,
            selected_focus=selected_focus,
            page=page,
            per_page=per_page,
        )
    except PrometheusError as exc:
        consumer_payload = get_empty_top_consumers_payload(
            message=str(
                exc,
            ),
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        consumer_payload = get_empty_top_consumers_payload(
            message=f'Top consumers query failed: {exc}',
            page=page,
            per_page=per_page,
        )

    context['consumer_payload'] = consumer_payload

    return context


def render_namespace_query(
    *,
    namespace: str,
    all_query: str,
    namespace_query: str,
) -> str:
    if not namespace:
        return all_query

    escaped_namespace = namespace.replace(
        '\\',
        '\\\\',
    ).replace(
        '"',
        '\\"',
    )

    return namespace_query.replace(
        '$namespace',
        escaped_namespace,
    )


def get_metric_label(
    metric: dict[str, Any],
    label: str,
) -> str:
    value = metric.get(
        label,
        '',
    )

    if isinstance(
        value,
        str,
    ):
        return value

    return ''


def get_container_key(
    *,
    namespace: str,
    pod: str,
    container: str,
) -> str:
    return f'{namespace}/{pod}/{container}'


def get_pvc_key(
    *,
    namespace: str,
    pvc_name: str,
) -> str:
    return f'{namespace}/{pvc_name}'


def build_workload_label(
    *,
    primary: str,
    secondary: str,
) -> str:
    if primary and secondary:
        return f'{primary} / {secondary}'

    return primary or secondary or '-'


def get_usage_percent(
    *,
    usage: float,
    request: float,
    limit: float,
) -> float:
    if limit > 0:
        return raw_percent(
            usage,
            limit,
        )

    if request > 0:
        return raw_percent(
            usage,
            request,
        )

    return 0.0


def get_usage_risk(
    percent: float,
) -> dict[str, str]:
    if percent >= 90:
        return {
            'key': 'critical',
            'label': 'Critical',
            'class': 'bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300',
        }

    if percent >= 75:
        return {
            'key': 'warning',
            'label': 'Warning',
            'class': 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300',
        }

    return {
        'key': 'normal',
        'label': 'Normal',
        'class': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
    }


def get_resource_recommendation(
    *,
    resource_type: str,
    usage_percent: float,
    request: float,
    limit: float,
) -> str:
    if resource_type == 'pvc':
        if usage_percent >= 90:
            return 'Clean up or expand PVC'
        if usage_percent >= 75:
            return 'Expand PVC capacity'
        return 'Monitor storage growth'

    if resource_type == 'pods':
        if usage_percent >= 75:
            return 'Review pod capacity'
        return 'Monitor growth'

    if request <= 0:
        if resource_type == 'cpu':
            return 'Add CPU request'
        return 'Add memory request'

    if limit <= 0:
        if resource_type == 'cpu':
            return 'Add CPU limit'
        return 'Add memory limit'

    if usage_percent >= 90:
        if resource_type == 'cpu':
            return 'Increase CPU limit'
        return 'Increase memory limit'

    if usage_percent >= 75:
        if resource_type == 'cpu':
            return 'Increase CPU request/limit'
        return 'Increase memory request/limit'

    return 'Monitor growth'


def get_dominant_namespace_names(
    rows: list[dict[str, Any]],
) -> list[str]:
    namespace_scores: dict[str, int] = {}

    for row in rows:
        namespace = str(
            row.get(
                'namespace',
                '',
            )
        )
        usage_percent = float(
            row.get(
                'usage_percent',
                0,
            )
        )

        if not namespace:
            continue

        if usage_percent < 75:
            continue

        namespace_scores[namespace] = (
            namespace_scores.get(
                namespace,
                0,
            )
            + 1
        )

    sorted_namespaces = sorted(
        namespace_scores.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
        reverse=True,
    )

    return [namespace for namespace, _ in sorted_namespaces[:2]]


def build_summary_card(
    *,
    rows: list[dict[str, Any]],
    title: str,
    empty_label: str,
    empty_value: str,
    capacity: float | None,
    capacity_text: str,
    use_usage_percent: bool = False,
) -> dict[str, Any]:
    if not rows:
        return {
            'title': title,
            'label': empty_label,
            'value': empty_value,
            'subtitle': 'No data available',
            'risk': get_usage_risk(0),
        }

    top_row = max(
        rows,
        key=lambda row: float(row.get('current_usage', 0)),
    )

    if use_usage_percent:
        value = f'{float(top_row.get("usage_percent", 0)):.1f}%'
        subtitle = f'{top_row.get("current_display", "-")} of {top_row.get("limit_display", "-")} used'
    else:
        value = str(
            top_row.get(
                'current_display',
                '-',
            )
        )
        percent = raw_percent(
            float(
                top_row.get(
                    'current_usage',
                    0,
                )
            ),
            capacity or 0,
        )
        subtitle = f'{safe_round(percent, 1)}% {capacity_text}'

    return {
        'title': title,
        'label': str(
            top_row.get(
                'workload',
                '-',
            )
        ),
        'value': value,
        'subtitle': subtitle,
        'risk': top_row.get(
            'risk',
            get_usage_risk(0),
        ),
    }


def build_chart_series(
    *,
    rows: list[dict[str, Any]],
    unit: str,
    total_usage: float,
) -> dict[str, Any]:
    top_rows = sorted(
        rows,
        key=lambda row: float(row.get('current_usage', 0)),
        reverse=True,
    )[:10]

    max_usage = max(
        [
            float(
                row.get(
                    'current_usage',
                    0,
                )
            )
            for row in top_rows
        ],
        default=0,
    )

    chart_rows: list[dict[str, Any]] = []
    values: list[float] = []

    for index, row in enumerate(
        top_rows,
        start=1,
    ):
        raw_value = float(
            row.get(
                'current_usage',
                0,
            )
        )

        display_value = raw_value
        value_suffix = 'cores'

        if unit == 'bytes':
            display_value = raw_value / (1024**3)
            value_suffix = 'GiB'

        rounded_value = safe_round(
            display_value,
            2,
        )
        values.append(
            rounded_value,
        )

        workload = str(
            row.get(
                'workload',
                '-',
            )
        )
        namespace = str(
            row.get(
                'namespace',
                '-',
            )
        )
        pod = str(
            row.get(
                'pod',
                '',
            )
        )
        container = str(
            row.get(
                'container',
                '',
            )
        )

        primary_name = workload
        secondary_parts = [
            namespace,
        ]

        if container:
            primary_name = container

        if pod:
            secondary_parts.append(
                pod,
            )
        elif workload and workload != namespace:
            secondary_parts.append(
                workload,
            )

        percent_of_total = raw_percent(
            raw_value,
            total_usage,
        )
        bar_percent = raw_percent(
            raw_value,
            max_usage,
        )

        chart_rows.append(
            {
                'rank': index,
                'primary_name': primary_name,
                'secondary_name': ' · '.join([part for part in secondary_parts if part]),
                'full_name': workload,
                'namespace': namespace,
                'value': rounded_value,
                'value_display': f'{rounded_value} {value_suffix}',
                'percent_of_total': safe_round(
                    percent_of_total,
                    1,
                ),
                'bar_percent': min(
                    safe_round(
                        bar_percent,
                        1,
                    ),
                    100,
                ),
            }
        )

    return {
        'labels': [
            str(
                row.get(
                    'primary_name',
                    '-',
                )
            )
            for row in chart_rows
        ],
        'values': values,
        'rows': chart_rows,
    }


def get_empty_top_consumers_payload(
    *,
    message: str,
    page: int,
    per_page: int,
) -> dict[str, Any]:
    return {
        'has_data': False,
        'message': message,
        'summary': {
            'highest_cpu': {
                'title': 'Highest CPU Consumer',
                'label': 'No CPU data',
                'value': '0 cores',
                'subtitle': 'No data available',
                'risk': get_usage_risk(0),
            },
            'highest_memory': {
                'title': 'Highest Memory Consumer',
                'label': 'No memory data',
                'value': '0 B',
                'subtitle': 'No data available',
                'risk': get_usage_risk(0),
            },
            'highest_pods': {
                'title': 'Highest Pod Count',
                'label': 'No pod data',
                'value': '0 pods',
                'subtitle': 'No data available',
                'risk': get_usage_risk(0),
            },
            'highest_pvc': {
                'title': 'Highest PVC Usage',
                'label': 'No PVC data',
                'value': '0%',
                'subtitle': 'No data available',
                'risk': get_usage_risk(0),
            },
        },
        'overview': {
            'cpu_chart': {
                'labels': [],
                'values': [],
            },
            'memory_chart': {
                'labels': [],
                'values': [],
            },
            'summary': {
                'total_cpu_used': '0 cores',
                'total_cpu_percent': 0,
                'total_memory_used': '0 B',
                'total_memory_percent': 0,
                'total_pods': 0,
                'total_pods_percent': 0,
                'total_pvc_used': '0 B',
                'total_pvc_percent': 0,
            },
        },
        'rows': [],
        'pagination': {
            'current_page': page,
            'total_pages': 1,
            'total_items': 0,
            'per_page': per_page,
            'has_prev': False,
            'has_next': False,
            'prev_page': 1,
            'next_page': 1,
        },
        'actionable_recommendations': [],
        'recommendation_cards': [
            {
                'title': 'Connect Prometheus Metrics',
                'description': 'Top consumer analysis requires Prometheus metrics to calculate CPU, memory, pod, and PVC usage.',
                'priority': 'Warning',
                'source': 'top_consumers',
                'source_label': 'Top Consumers',
                'resource': 'consumer',
                'action_type': 'prometheus_review',
                'href': '/integrations/prometheus',
                'icon': 'plug-zap',
                'icon_class': 'bg-amber-100 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
                'priority_class': 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
                'is_actionable': 'Yes',
            }
        ],
        'recommendation_count': 1,
        'recommendations': [
            {
                'title': 'Connect Prometheus Metrics',
                'description': 'Top consumer analysis requires Prometheus metrics to calculate CPU, memory, pod, and PVC usage.',
                'priority': 'Warning',
                'source': 'top_consumers',
                'source_label': 'Top Consumers',
                'resource': 'consumer',
                'action_type': 'prometheus_review',
                'href': '/integrations/prometheus',
                'icon': 'plug-zap',
                'icon_class': 'bg-amber-100 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
                'priority_class': 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
                'is_actionable': 'Yes',
            }
        ],
        'total_rows': 0,
    }


def safe_message(
    *,
    value: Any,
    default: str,
) -> str:
    if (
        isinstance(
            value,
            str,
        )
        and value
    ):
        return value

    if value is None:
        return default

    return str(
        value,
    )


def format_cpu(
    value: float,
) -> str:
    return f'{safe_round(value, 2)} cores'


def format_bytes(
    value: float,
) -> str:
    if value <= 0:
        return '0 B'

    units = [
        'B',
        'KiB',
        'MiB',
        'GiB',
        'TiB',
        'PiB',
    ]
    size = float(value)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f'{size:.0f} {units[unit_index]}'

    return f'{size:.2f} {units[unit_index]}'


def get_top_consumers_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> TopConsumersSnapshot:
    _ = time_range

    cluster = Cluster.query.filter_by(
        id=cluster_id,
    ).first()

    if not cluster:
        return _empty_top_consumers_snapshot()

    try:
        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        top_consumers_service = TopConsumersService(
            utilization_service=utilization_service,
        )

        cpu_rows = top_consumers_service.get_cpu_consumer_rows(
            selected_namespace='',
        )
        memory_rows = top_consumers_service.get_memory_consumer_rows(
            selected_namespace='',
        )
        pvc_rows = top_consumers_service.get_pvc_consumer_rows(
            selected_namespace='',
        )

        actionable_recommendations = build_top_consumers_actionable_recommendations(
            {
                'all_rows': cpu_rows + memory_rows + pvc_rows,
                'rows': cpu_rows + memory_rows + pvc_rows,
            }
        )

        return {
            'cpu': _build_top_consumer_items(
                rows=cpu_rows,
                name_key='pod',
                fallback_name_key='workload',
                limit=5,
            ),
            'memory': _build_top_consumer_items(
                rows=memory_rows,
                name_key='pod',
                fallback_name_key='workload',
                limit=5,
            ),
            'storage': _build_top_consumer_items(
                rows=pvc_rows,
                name_key='workload',
                fallback_name_key='workload',
                limit=5,
            ),
            'recommendation_count': count_actionable_recommendations(
                actionable_recommendations,
            ),
        }

    except Exception:
        return _empty_top_consumers_snapshot()


def _empty_top_consumers_snapshot() -> TopConsumersSnapshot:
    return {
        'cpu': [],
        'memory': [],
        'storage': [],
        'recommendation_count': 0,
    }


def _build_top_consumer_items(
    *,
    rows: list[dict[str, Any]],
    name_key: str,
    fallback_name_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    sorted_rows = sorted(
        rows,
        key=lambda row: _safe_float(
            row.get(
                'current_usage',
                0,
            )
        ),
        reverse=True,
    )

    top_rows = sorted_rows[:limit]
    max_value = max(
        [
            _safe_float(
                row.get(
                    'current_usage',
                    0,
                )
            )
            for row in top_rows
        ],
        default=0,
    )

    items: list[dict[str, Any]] = []

    for row in top_rows:
        namespace = str(
            row.get(
                'namespace',
                '',
            )
        )
        primary_name = str(
            row.get(
                name_key,
                '',
            )
        )
        fallback_name = str(
            row.get(
                fallback_name_key,
                '',
            )
        )
        workload = str(
            row.get(
                'workload',
                '',
            )
        )
        container = str(
            row.get(
                'container',
                '',
            )
        )
        raw_value = _safe_float(
            row.get(
                'current_usage',
                0,
            )
        )
        usage_percent = _safe_float(
            row.get(
                'usage_percent',
                0,
            )
        )

        display_name = primary_name or fallback_name or workload or '-'

        if namespace and display_name != '-':
            full_name = f'{namespace}/{display_name}'
        else:
            full_name = display_name

        if container:
            full_name = f'{full_name} · {container}'

        items.append(
            {
                'name': full_name,
                'namespace': namespace,
                'pod': str(
                    row.get(
                        'pod',
                        '',
                    )
                ),
                'container': container,
                'workload': workload,
                'value': str(
                    row.get(
                        'current_display',
                        '-',
                    )
                ),
                'raw_value': raw_value,
                'percent': _safe_int(
                    usage_percent
                    if usage_percent > 0
                    else _raw_percent(
                        raw_value,
                        max_value,
                    )
                ),
                'bar_percent': _safe_int(
                    _raw_percent(
                        raw_value,
                        max_value,
                    )
                ),
                'risk': row.get(
                    'risk',
                    {},
                ),
                'recommendation': str(
                    row.get(
                        'recommendation',
                        '',
                    )
                ),
            }
        )

    return items


def _raw_percent(
    value: float,
    total: float,
) -> float:
    if total <= 0:
        return 0.0

    return min(
        100.0,
        value / total * 100,
    )


def _safe_float(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        return float(
            value,
        )

    if isinstance(
        value,
        int | float | str,
    ):
        try:
            return float(
                value,
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    return 0.0


def _safe_int(
    value: Any,
) -> int:
    return int(
        round(
            _safe_float(
                value,
            )
        )
    )
