# app/analytics/top_consumers/service.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from app.analytics.common.base_service import AnalyticsBaseService, raw_percent, safe_round
from app.analytics.common.coercion import safe_float as _safe_float
from app.analytics.common.coercion import safe_int as _safe_int
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_per_page_arg,
    get_positive_int_arg,
    get_query_value,
)
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_connection_blocker
from app.integrations.prometheus.query_profiles import get_query_expression
from app.intelligence.recommendation_engine import (
    build_top_consumers_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)

CPU_ALLOCATABLE_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_ALLOCATABLE_QUERY')
CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY'
)
CPU_LIMIT_BY_CONTAINER_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_QUERY')
CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY'
)
CPU_REQUEST_BY_CONTAINER_QUERY = get_query_expression('analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_QUERY')
MEMORY_ALLOCATABLE_QUERY = get_query_expression('analytics.top_consumers.queries.MEMORY_ALLOCATABLE_QUERY')
MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY'
)
MEMORY_LIMIT_BY_CONTAINER_QUERY = get_query_expression(
    'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_QUERY'
)
MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY'
)
MEMORY_REQUEST_BY_CONTAINER_QUERY = get_query_expression(
    'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_QUERY'
)
NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.top_consumers.queries.NAMESPACE_ACTIVE_QUERY')
POD_CAPACITY_QUERY = get_query_expression('analytics.top_consumers.queries.POD_CAPACITY_QUERY')
PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY'
)
PVC_CAPACITY_BY_CLAIM_QUERY = get_query_expression('analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_QUERY')
TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY'
)
TOP_CPU_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY')
TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY'
)
TOP_MEMORY_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY')
TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY'
)
POD_OWNER_QUERY = get_query_expression('analytics.top_consumers.queries.POD_OWNER_QUERY')
POD_OWNER_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.POD_OWNER_BY_NAMESPACE_QUERY'
)
TOP_POD_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_POD_CONSUMERS_QUERY')
TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY'
)
TOP_PVC_CONSUMERS_QUERY = get_query_expression('analytics.top_consumers.queries.TOP_PVC_CONSUMERS_QUERY')
TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY'
)
TOTAL_CPU_USAGE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_CPU_USAGE_QUERY')
TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY'
)
TOTAL_MEMORY_USAGE_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_QUERY')
TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY'
)
TOTAL_PVC_CAPACITY_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_PVC_CAPACITY_QUERY')
TOTAL_PVC_USED_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOTAL_PVC_USED_BY_NAMESPACE_QUERY'
)
TOTAL_PVC_USED_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_PVC_USED_QUERY')
TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY = get_query_expression(
    'analytics.top_consumers.queries.TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY'
)
TOTAL_RUNNING_PODS_QUERY = get_query_expression('analytics.top_consumers.queries.TOTAL_RUNNING_PODS_QUERY')

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


class TopConsumersSnapshot(TypedDict):
    cpu: list[dict[str, Any]]
    memory: list[dict[str, Any]]
    storage: list[dict[str, Any]]
    pods: list[dict[str, Any]]
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


def get_sort_options(selected_resource: str) -> list[dict[str, str]]:
    return SINGLE_RESOURCE_SORT_OPTIONS if selected_resource != 'all' else ALL_RESOURCE_SORT_OPTIONS


def get_selected_sort(
    query_args: Mapping[str, Any],
    selected_resource: str = 'all',
) -> str:
    default_sort = 'absolute' if selected_resource != 'all' else 'priority'
    selected_sort = get_query_value(
        query_args=query_args,
        name='sort',
        default=default_sort,
    )
    allowed_values = {item['value'] for item in get_sort_options(selected_resource)}
    return selected_sort if selected_sort in allowed_values else default_sort


def get_selected_priority(query_args: Mapping[str, Any]) -> str:
    selected_priority = get_query_value(
        query_args=query_args,
        name='priority',
        default='',
    )
    allowed_values = {item['value'] for item in PRIORITY_OPTIONS}
    return selected_priority if selected_priority in allowed_values else ''


def get_selected_tab(query_args: Mapping[str, Any]) -> str:
    selected_tab = get_query_value(query_args=query_args, name='tab', default='rankings')
    return selected_tab if selected_tab in {'rankings', 'records', 'recommendations'} else 'rankings'


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
    def __init__(self, utilization_service: UtilizationService) -> None:
        self.utilization_service = utilization_service

    def get_prometheus_status(self) -> dict[str, Any]:
        return self.utilization_service.get_prometheus_status()

    def get_namespace_options(self) -> list[str]:
        namespaces: set[str] = set()
        for item in self.get_prometheus_result(NAMESPACE_ACTIVE_QUERY):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            if namespace:
                namespaces.add(namespace)
        return sorted(namespaces)

    def get_top_consumers_payload(
        self,
        *,
        selected_namespace: str,
        selected_resource: str,
        selected_search: str,
        selected_sort: str,
        selected_priority: str,
        selected_focus: str,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        scope = self.get_scope_metrics(selected_namespace)
        owner_map = self.get_pod_owner_map(selected_namespace)

        cpu_rows = self.get_cpu_consumer_rows(
            selected_namespace=selected_namespace,
            total_usage=scope['cpu']['total'],
            owner_map=owner_map,
        )
        memory_rows = self.get_memory_consumer_rows(
            selected_namespace=selected_namespace,
            total_usage=scope['memory']['total'],
            owner_map=owner_map,
        )
        pod_rows = self.get_pod_consumer_rows(
            selected_namespace=selected_namespace,
            total_usage=scope['pods']['total'],
            capacity=scope['pods']['capacity'],
        )
        pvc_rows = self.get_pvc_consumer_rows(
            selected_namespace=selected_namespace,
            total_usage=scope['pvc']['total'],
        )
        rows_by_resource = {
            'cpu': cpu_rows,
            'memory': memory_rows,
            'pods': pod_rows,
            'pvc': pvc_rows,
        }
        all_rows = cpu_rows + memory_rows + pod_rows + pvc_rows
        coverage = self.build_multi_resource_coverage(rows_by_resource, scope)
        filtered_rows = self.filter_rows(
            rows=all_rows,
            selected_search=selected_search,
            selected_resource=selected_resource,
            selected_priority=selected_priority,
            selected_focus=selected_focus,
        )
        sorted_rows = self.sort_rows(
            rows=filtered_rows,
            selected_sort=selected_sort,
            selected_resource=selected_resource,
        )
        ranked_rows = [dict(row, rank=index) for index, row in enumerate(sorted_rows, start=1)]
        page_payload = self.paginate_consumer_rows(rows=ranked_rows, page=page, per_page=per_page)

        payload = {
            'has_data': bool(all_rows),
            'message': None,
            'scope': {
                'label': f'Namespace · {selected_namespace}' if selected_namespace else 'Cluster',
                'namespace': selected_namespace,
                'snapshot_dimension': 'namespace' if selected_namespace else 'cluster',
            },
            'coverage': coverage,
            'summary': self.get_summary_cards(rows_by_resource),
            'overview': self.get_overview_payload(rows_by_resource, scope, coverage),
            'rows': page_payload['rows'],
            'all_rows': all_rows,
            'pagination': page_payload['pagination'],
            'total_rows': len(filtered_rows),
            'scope_total_rows': len(all_rows),
        }
        actionable_recommendations = build_top_consumers_actionable_recommendations(payload)
        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Review Top Consumers',
            default_description='Review CPU, memory, pod, and PVC consumer hotspots.',
            default_source='top_consumers',
            default_action_type='consumer_review',
        )
        payload.update(
            {
                'actionable_recommendations': actionable_recommendations,
                'recommendation_cards': recommendation_cards,
                'recommendation_count': count_actionable_recommendations(actionable_recommendations),
                'recommendations': recommendation_cards,
            }
        )
        payload['posture'] = self.get_page_posture(payload)
        return payload

    def get_scope_metrics(self, selected_namespace: str) -> dict[str, dict[str, float]]:
        return {
            'cpu': {
                'total': self.get_prometheus_scalar(render_namespace_query(
                    namespace=selected_namespace,
                    all_query=TOTAL_CPU_USAGE_QUERY,
                    namespace_query=TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY,
                )),
                'capacity': self.get_prometheus_scalar(CPU_ALLOCATABLE_QUERY),
            },
            'memory': {
                'total': self.get_prometheus_scalar(render_namespace_query(
                    namespace=selected_namespace,
                    all_query=TOTAL_MEMORY_USAGE_QUERY,
                    namespace_query=TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY,
                )),
                'capacity': self.get_prometheus_scalar(MEMORY_ALLOCATABLE_QUERY),
            },
            'pods': {
                'total': self.get_prometheus_scalar(render_namespace_query(
                    namespace=selected_namespace,
                    all_query=TOTAL_RUNNING_PODS_QUERY,
                    namespace_query=TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY,
                )),
                'capacity': self.get_prometheus_scalar(POD_CAPACITY_QUERY),
            },
            'pvc': {
                'total': self.get_prometheus_scalar(render_namespace_query(
                    namespace=selected_namespace,
                    all_query=TOTAL_PVC_USED_QUERY,
                    namespace_query=TOTAL_PVC_USED_BY_NAMESPACE_QUERY,
                )),
                'capacity': self.get_prometheus_scalar(render_namespace_query(
                    namespace=selected_namespace,
                    all_query=TOTAL_PVC_CAPACITY_QUERY,
                    namespace_query=TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY,
                )),
            },
        }

    def get_pod_owner_map(self, selected_namespace: str) -> dict[str, dict[str, str]]:
        query = render_namespace_query(
            namespace=selected_namespace,
            all_query=POD_OWNER_QUERY,
            namespace_query=POD_OWNER_BY_NAMESPACE_QUERY,
        )
        owners: dict[str, dict[str, str]] = {}
        for item in self.get_prometheus_result(query):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            pod = get_metric_label(metric, 'pod')
            owner_name = get_metric_label(metric, 'owner_name')
            owner_kind = get_metric_label(metric, 'owner_kind')
            if not namespace or not pod or not owner_name:
                continue
            key = f'{namespace}/{pod}'
            candidate = {
                'name': owner_name,
                'kind': owner_kind or 'Workload',
                'controller': get_metric_label(metric, 'owner_is_controller'),
            }
            current = owners.get(key)
            if current is None or candidate['controller'].lower() == 'true':
                owners[key] = candidate
        return owners

    def get_cpu_consumer_rows(
        self,
        *,
        selected_namespace: str,
        total_usage: float,
        owner_map: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        return self.get_compute_consumer_rows(
            selected_namespace=selected_namespace,
            total_usage=total_usage,
            owner_map=owner_map,
            resource_type='cpu',
            usage_query_all=TOP_CPU_CONSUMERS_QUERY,
            usage_query_namespace=TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY,
            request_query_all=CPU_REQUEST_BY_CONTAINER_QUERY,
            request_query_namespace=CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY,
            limit_query_all=CPU_LIMIT_BY_CONTAINER_QUERY,
            limit_query_namespace=CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY,
        )

    def get_memory_consumer_rows(
        self,
        *,
        selected_namespace: str,
        total_usage: float,
        owner_map: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        return self.get_compute_consumer_rows(
            selected_namespace=selected_namespace,
            total_usage=total_usage,
            owner_map=owner_map,
            resource_type='memory',
            usage_query_all=TOP_MEMORY_CONSUMERS_QUERY,
            usage_query_namespace=TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY,
            request_query_all=MEMORY_REQUEST_BY_CONTAINER_QUERY,
            request_query_namespace=MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY,
            limit_query_all=MEMORY_LIMIT_BY_CONTAINER_QUERY,
            limit_query_namespace=MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY,
        )

    def get_compute_consumer_rows(
        self,
        *,
        selected_namespace: str,
        total_usage: float,
        owner_map: dict[str, dict[str, str]],
        resource_type: str,
        usage_query_all: str,
        usage_query_namespace: str,
        request_query_all: str,
        request_query_namespace: str,
        limit_query_all: str,
        limit_query_namespace: str,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=usage_query_all,
            namespace_query=usage_query_namespace,
        )
        request_map = self.get_container_value_map(query=render_namespace_query(
            namespace=selected_namespace,
            all_query=request_query_all,
            namespace_query=request_query_namespace,
        ))
        limit_map = self.get_container_value_map(query=render_namespace_query(
            namespace=selected_namespace,
            all_query=limit_query_all,
            namespace_query=limit_query_namespace,
        ))
        rows: list[dict[str, Any]] = []
        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            pod = get_metric_label(metric, 'pod')
            container = get_metric_label(metric, 'container')
            if not namespace or not pod or not container:
                continue
            key = get_container_key(namespace=namespace, pod=pod, container=container)
            usage = self.extract_value(item)
            request = request_map.get(key, 0.0)
            limit = limit_map.get(key, 0.0)
            request_utilization = raw_percent(usage, request) if request > 0 else None
            limit_utilization = raw_percent(usage, limit) if limit > 0 else None
            pressure_candidates = [value for value in (request_utilization, limit_utilization) if value is not None]
            pressure_percent = max(pressure_candidates) if pressure_candidates else None
            risk = get_compute_risk(
                resource_type=resource_type,
                request=request,
                limit=limit,
                request_utilization=request_utilization,
                limit_utilization=limit_utilization,
            )
            owner = owner_map.get(f'{namespace}/{pod}', {})
            identity = build_compute_identity(
                namespace=namespace,
                pod=pod,
                container=container,
                owner_name=str(owner.get('name') or ''),
                owner_kind=str(owner.get('kind') or ''),
            )
            current_display = format_cpu(usage) if resource_type == 'cpu' else format_bytes(usage)
            request_display = (
                format_cpu(request) if resource_type == 'cpu' else format_bytes(request)
            ) if request > 0 else 'N/A'
            limit_display = (
                format_cpu(limit) if resource_type == 'cpu' else format_bytes(limit)
            ) if limit > 0 else 'N/A'
            rows.append(self.build_consumer_row(
                identity=identity,
                namespace=namespace,
                resource_type=resource_type,
                current_usage=usage,
                current_display=current_display,
                total_usage=total_usage,
                request=request,
                request_display=request_display,
                limit=limit,
                limit_display=limit_display,
                request_utilization=request_utilization,
                limit_utilization=limit_utilization,
                pressure_percent=pressure_percent,
                pressure_basis='Request / Limit',
                risk=risk,
                recommendation=get_resource_recommendation(
                    resource_type=resource_type,
                    pressure_percent=pressure_percent,
                    request=request,
                    limit=limit,
                ),
                pod=pod,
                container=container,
                workload_owner=str(owner.get('name') or ''),
                workload_owner_kind=str(owner.get('kind') or ''),
            ))
        return rows

    def get_pod_consumer_rows(
        self,
        *,
        selected_namespace: str,
        total_usage: float,
        capacity: float,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=TOP_POD_CONSUMERS_QUERY,
            namespace_query=TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY,
        )
        rows: list[dict[str, Any]] = []
        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            if not namespace:
                continue
            usage = self.extract_value(item)
            pressure_percent = raw_percent(usage, capacity) if capacity > 0 else None
            risk = get_ratio_risk(pressure_percent)
            rows.append(self.build_consumer_row(
                identity={
                    'entity_type': 'namespace',
                    'entity_label': 'Namespace',
                    'icon': 'folder-tree',
                    'primary': namespace,
                    'secondary': 'Namespace Pod Density',
                    'tertiary': '',
                },
                namespace=namespace,
                resource_type='pods',
                current_usage=usage,
                current_display=f'{int(usage)} Pods',
                total_usage=total_usage,
                request=0,
                request_display='N/A',
                limit=capacity,
                limit_display=f'{int(capacity)} Pods' if capacity > 0 else 'N/A',
                request_utilization=None,
                limit_utilization=None,
                pressure_percent=pressure_percent,
                pressure_basis='Cluster Pod Capacity',
                risk=risk,
                recommendation=get_resource_recommendation(
                    resource_type='pods',
                    pressure_percent=pressure_percent,
                    request=0,
                    limit=capacity,
                ),
                pod='',
                container='',
            ))
        return rows

    def get_pvc_consumer_rows(
        self,
        *,
        selected_namespace: str,
        total_usage: float,
    ) -> list[dict[str, Any]]:
        usage_query = render_namespace_query(
            namespace=selected_namespace,
            all_query=TOP_PVC_CONSUMERS_QUERY,
            namespace_query=TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY,
        )
        capacity_map = self.get_pvc_value_map(query=render_namespace_query(
            namespace=selected_namespace,
            all_query=PVC_CAPACITY_BY_CLAIM_QUERY,
            namespace_query=PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY,
        ))
        rows: list[dict[str, Any]] = []
        for item in self.get_prometheus_result(usage_query):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            pvc_name = get_metric_label(metric, 'persistentvolumeclaim')
            if not namespace or not pvc_name:
                continue
            usage = self.extract_value(item)
            capacity = capacity_map.get(get_pvc_key(namespace=namespace, pvc_name=pvc_name), 0.0)
            pressure_percent = raw_percent(usage, capacity) if capacity > 0 else None
            risk = get_ratio_risk(pressure_percent)
            rows.append(self.build_consumer_row(
                identity={
                    'entity_type': 'pvc',
                    'entity_label': 'PersistentVolumeClaim',
                    'icon': 'database',
                    'primary': pvc_name,
                    'secondary': namespace,
                    'tertiary': 'PersistentVolumeClaim',
                },
                namespace=namespace,
                resource_type='pvc',
                current_usage=usage,
                current_display=format_bytes(usage),
                total_usage=total_usage,
                request=0,
                request_display='N/A',
                limit=capacity,
                limit_display=format_bytes(capacity) if capacity > 0 else 'N/A',
                request_utilization=None,
                limit_utilization=None,
                pressure_percent=pressure_percent,
                pressure_basis='Claim Capacity',
                risk=risk,
                recommendation=get_resource_recommendation(
                    resource_type='pvc',
                    pressure_percent=pressure_percent,
                    request=0,
                    limit=capacity,
                ),
                pod='',
                container='',
                pvc_name=pvc_name,
            ))
        return rows

    def build_consumer_row(
        self,
        *,
        identity: dict[str, str],
        namespace: str,
        resource_type: str,
        current_usage: float,
        current_display: str,
        total_usage: float,
        request: float,
        request_display: str,
        limit: float,
        limit_display: str,
        request_utilization: float | None,
        limit_utilization: float | None,
        pressure_percent: float | None,
        pressure_basis: str,
        risk: dict[str, str],
        recommendation: str,
        pod: str,
        container: str,
        workload_owner: str = '',
        workload_owner_kind: str = '',
        pvc_name: str = '',
    ) -> dict[str, Any]:
        contribution_percent = raw_percent(current_usage, total_usage) if total_usage > 0 else None
        pressure_display = f'{safe_round(pressure_percent, 1)}%' if pressure_percent is not None else 'N/A'
        contribution_display = f'{safe_round(contribution_percent, 1)}%' if contribution_percent is not None else 'N/A'
        return {
            'rank': 0,
            'identity': identity,
            'entity_type': identity.get('entity_type', 'consumer'),
            'namespace': namespace,
            'workload': workload_owner or identity.get('primary', '-'),
            'workload_owner': workload_owner,
            'workload_owner_kind': workload_owner_kind,
            'pod': pod,
            'container': container,
            'pvc_name': pvc_name,
            'resource_type': resource_type,
            'resource_label': RESOURCE_LABELS.get(resource_type, resource_type.title()),
            'resource_icon': RESOURCE_ICONS.get(resource_type, 'activity'),
            'current_usage': current_usage,
            'current_display': current_display,
            'scope_total': total_usage,
            'contribution_percent': safe_round(contribution_percent, 1) if contribution_percent is not None else None,
            'contribution_display': contribution_display,
            'contribution_bar_percent': min(safe_round(contribution_percent, 1), 100) if contribution_percent is not None else 0,
            'request': request,
            'request_display': request_display,
            'limit': limit,
            'limit_display': limit_display,
            'request_utilization': safe_round(request_utilization, 1) if request_utilization is not None else None,
            'request_utilization_display': f'{safe_round(request_utilization, 1)}%' if request_utilization is not None else 'N/A',
            'limit_utilization': safe_round(limit_utilization, 1) if limit_utilization is not None else None,
            'limit_utilization_display': f'{safe_round(limit_utilization, 1)}%' if limit_utilization is not None else 'N/A',
            'pressure_percent': safe_round(pressure_percent, 1) if pressure_percent is not None else None,
            'pressure_display': pressure_display,
            'pressure_bar_percent': min(safe_round(pressure_percent, 1), 100) if pressure_percent is not None else 0,
            'pressure_basis': pressure_basis,
            'pressure_available': pressure_percent is not None,
            'risk': risk,
            'recommendation': recommendation,
            'request_state': get_request_state(request, resource_type),
            'limit_state': get_limit_state(limit, resource_type),
        }

    def get_container_value_map(self, query: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for item in self.get_prometheus_result(query):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            pod = get_metric_label(metric, 'pod')
            container = get_metric_label(metric, 'container')
            if namespace and pod and container:
                values[get_container_key(namespace=namespace, pod=pod, container=container)] = self.extract_value(item)
        return values

    def get_pvc_value_map(self, query: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for item in self.get_prometheus_result(query):
            metric = self.get_metric_dict(item)
            namespace = get_metric_label(metric, 'namespace')
            pvc_name = get_metric_label(metric, 'persistentvolumeclaim')
            if namespace and pvc_name:
                values[get_pvc_key(namespace=namespace, pvc_name=pvc_name)] = self.extract_value(item)
        return values

    @staticmethod
    def get_metric_dict(item: dict[str, Any]) -> dict[str, Any]:
        metric = item.get('metric', {})
        return metric if isinstance(metric, dict) else {}

    def build_multi_resource_coverage(
        self,
        rows_by_resource: dict[str, list[dict[str, Any]]],
        scope: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        items: dict[str, dict[str, str]] = {}
        for key, rows in rows_by_resource.items():
            total_available = scope[key]['total'] > 0
            capacity_available = scope[key]['capacity'] > 0
            if not rows:
                state = evidence_state('unavailable')
            elif total_available and capacity_available and all(row.get('pressure_available') for row in rows):
                state = evidence_state('complete')
            else:
                state = evidence_state('partial')
            items[key] = {**state, 'resource_label': RESOURCE_LABELS[key]}
        complete_count = sum(1 for item in items.values() if item['key'] == 'complete')
        unavailable_count = sum(1 for item in items.values() if item['key'] == 'unavailable')
        return {
            'items': items,
            'complete_count': complete_count,
            'partial_count': len(items) - complete_count - unavailable_count,
            'unavailable_count': unavailable_count,
            'label': f'{complete_count} of {len(items)} Resources Complete',
        }

    def get_summary_cards(self, rows_by_resource: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        return {
            'highest_cpu': build_summary_card(
                rows=rows_by_resource['cpu'],
                title='Highest CPU Consumption',
                selector='absolute',
            ),
            'highest_memory': build_summary_card(
                rows=rows_by_resource['memory'],
                title='Highest Memory Consumption',
                selector='absolute',
            ),
            'highest_pods': build_summary_card(
                rows=rows_by_resource['pods'],
                title='Highest Pod Density',
                selector='absolute',
            ),
            'highest_pvc': build_summary_card(
                rows=rows_by_resource['pvc'],
                title='Highest PVC Utilization',
                selector='pressure',
            ),
        }

    def get_overview_payload(
        self,
        rows_by_resource: dict[str, list[dict[str, Any]]],
        scope: dict[str, dict[str, float]],
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        definitions = {
            'cpu': ('CPU Consumers', 'Ranked by observed CPU consumption.', 'cpu', 'Cores'),
            'memory': ('Memory Consumers', 'Ranked by observed memory consumption.', 'memory-stick', 'Bytes'),
            'pods': ('Pod-Dense Namespaces', 'Ranked by running pod count within the selected scope.', 'boxes', 'Pods'),
            'pvc': ('PVC Consumers', 'Ranked by claim utilization pressure.', 'database', 'Capacity'),
        }
        rankings: list[dict[str, Any]] = []
        for key in ('cpu', 'memory', 'pods', 'pvc'):
            title, description, icon, unit = definitions[key]
            sort_key = 'pressure_percent' if key == 'pvc' else 'current_usage'
            rows = sorted(
                rows_by_resource[key],
                key=lambda row: _safe_float(row.get(sort_key, -1)),
                reverse=True,
            )[:5]
            rankings.append({
                'key': key,
                'title': title,
                'description': description,
                'icon': icon,
                'unit': unit,
                'total_value': format_scope_total(key, scope[key]['total']),
                'capacity_value': format_scope_total(key, scope[key]['capacity']),
                'capacity_label': 'Cluster Capacity' if key in {'cpu', 'memory', 'pods'} else 'Claim Capacity',
                'coverage': coverage['items'][key],
                'rows': [dict(row, rank=index) for index, row in enumerate(rows, start=1)],
            })
        return {'rankings': rankings}

    def filter_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        selected_search: str,
        selected_resource: str,
        selected_priority: str,
        selected_focus: str,
    ) -> list[dict[str, Any]]:
        dominant_namespaces = set(get_dominant_namespace_names(rows))
        filtered_rows: list[dict[str, Any]] = []
        for row in rows:
            resource_type = str(row.get('resource_type') or '')
            risk_key = str((row.get('risk') or {}).get('key') or 'unknown')
            request = _safe_float(row.get('request', 0))
            pressure = row.get('pressure_percent')
            namespace = str(row.get('namespace') or '')
            if selected_focus == 'missing_requests' and not (
                resource_type in {'cpu', 'memory'} and request <= 0
            ):
                continue
            if selected_focus == 'high_usage' and not (
                resource_type in {'cpu', 'memory'} and pressure is not None and _safe_float(pressure) >= 75
            ):
                continue
            if selected_focus == 'dominant_namespaces' and namespace not in dominant_namespaces:
                continue
            if selected_focus == 'high_pvc' and not (
                resource_type == 'pvc' and pressure is not None and _safe_float(pressure) >= 80
            ):
                continue
            if selected_resource != 'all' and resource_type != selected_resource:
                continue
            if selected_priority and risk_key != selected_priority:
                continue
            if selected_search:
                identity = row.get('identity') if isinstance(row.get('identity'), dict) else {}
                haystack = ' '.join(str(value) for value in (
                    namespace,
                    identity.get('primary', ''),
                    identity.get('secondary', ''),
                    identity.get('tertiary', ''),
                    row.get('pod', ''),
                    row.get('container', ''),
                    row.get('pvc_name', ''),
                    row.get('resource_label', ''),
                    row.get('recommendation', ''),
                )).lower()
                if selected_search.lower() not in haystack:
                    continue
            filtered_rows.append(row)
        return filtered_rows

    def sort_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        selected_sort: str,
        selected_resource: str,
    ) -> list[dict[str, Any]]:
        if selected_sort == 'absolute' and selected_resource != 'all':
            return sorted(rows, key=lambda row: _safe_float(row.get('current_usage', 0)), reverse=True)
        if selected_sort == 'pressure' and selected_resource != 'all':
            return sorted(rows, key=lambda row: _safe_float(row.get('pressure_percent', -1)), reverse=True)
        if selected_sort == 'contribution':
            return sorted(rows, key=lambda row: _safe_float(row.get('contribution_percent', -1)), reverse=True)
        if selected_sort == 'namespace':
            return sorted(rows, key=lambda row: (str(row.get('namespace', '')), str(row.get('resource_type', ''))))
        if selected_sort == 'resource':
            return sorted(rows, key=lambda row: (str(row.get('resource_type', '')), -_safe_float(row.get('contribution_percent', -1))))
        return sorted(
            rows,
            key=lambda row: (
                RISK_RANK.get(str((row.get('risk') or {}).get('key') or 'unknown'), 0),
                _safe_float(row.get('pressure_percent', -1)),
                _safe_float(row.get('contribution_percent', -1)),
            ),
            reverse=True,
        )

    def paginate_consumer_rows(self, *, rows: list[dict[str, Any]], page: int, per_page: int) -> dict[str, Any]:
        return self.paginate_rows_with_options(
            rows=rows,
            page=page,
            per_page=per_page,
            allowed_per_page=ALLOWED_PER_PAGE_VALUES,
            default_per_page=5,
        )

    def get_page_posture(self, payload: dict[str, Any]) -> dict[str, str]:
        rows = list(payload.get('all_rows') or [])
        coverage = payload.get('coverage') if isinstance(payload.get('coverage'), dict) else {}
        incomplete = _safe_int(coverage.get('partial_count', 0)) + _safe_int(coverage.get('unavailable_count', 0))
        critical = [row for row in rows if (row.get('risk') or {}).get('key') == 'critical']
        warning = [row for row in rows if (row.get('risk') or {}).get('key') == 'warning']
        pressure_rows = [row for row in rows if row.get('pressure_percent') is not None]
        highest = max(pressure_rows, key=lambda row: _safe_float(row.get('pressure_percent', 0)), default=None)
        if not rows:
            state = {'label': 'Unknown', 'tone': 'unknown', 'icon': 'database-zap', 'description': 'No consumer evidence is available.'}
        elif critical:
            state = {'label': 'Critical', 'tone': 'critical', 'icon': 'shield-alert', 'description': 'Critical consumer pressure or missing request coverage requires immediate review.'}
        elif incomplete:
            state = {'label': 'Evidence Incomplete', 'tone': 'warning', 'icon': 'database-zap', 'description': 'One or more resource evidence sets are partial or unavailable.'}
        elif warning:
            state = {'label': 'Review', 'tone': 'warning', 'icon': 'triangle-alert', 'description': 'Consumer pressure requires operational review.'}
        else:
            state = {'label': 'Healthy', 'tone': 'normal', 'icon': 'circle-check', 'description': 'Complete consumer evidence is within the normal range.'}
        if highest:
            state['highest_pressure'] = f"{highest.get('resource_label', 'Resource')} · {highest.get('pressure_display', 'N/A')}"
        else:
            state['highest_pressure'] = 'N/A'
        return state

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
    selected_time_range = 'current'
    selected_search = get_query_value(
        query_args=query_args,
        name='search',
        default='',
    )
    selected_sort = get_selected_sort(query_args, selected_resource)
    selected_priority = get_selected_priority(query_args)
    initial_tab = get_selected_tab(query_args)
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
            'selected_priority': selected_priority,
            'selected_sort': selected_sort,
            'initial_tab': initial_tab,
            'resource_options': RESOURCE_OPTIONS,
            'priority_options': PRIORITY_OPTIONS,
            'focus_options': FOCUS_FILTER_OPTIONS,
            'sort_options': get_sort_options(selected_resource),
            'allowed_time_ranges': (),
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

    prometheus_status = top_consumers_service.get_prometheus_status()

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

    namespace_options = top_consumers_service.get_namespace_options()

    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    context['selected_namespace'] = selected_namespace
    context['namespace_options'] = namespace_options

    consumer_payload = top_consumers_service.get_top_consumers_payload(
        selected_namespace=selected_namespace,
        selected_resource=selected_resource,
        selected_search=selected_search,
        selected_sort=selected_sort,
        selected_priority=selected_priority,
        selected_focus=selected_focus,
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


def build_compute_identity(
    *,
    namespace: str,
    pod: str,
    container: str,
    owner_name: str,
    owner_kind: str,
) -> dict[str, str]:
    if owner_name:
        return {
            'entity_type': 'container',
            'entity_label': 'Workload Owner',
            'icon': 'boxes',
            'primary': owner_name,
            'secondary': f'{owner_kind or "Workload"} · {namespace}',
            'tertiary': f'{pod} · {container}',
        }
    return {
        'entity_type': 'container',
        'entity_label': 'Pod',
        'icon': 'container',
        'primary': pod,
        'secondary': namespace,
        'tertiary': container,
    }


def semantic_state(key: str, label: str | None = None) -> dict[str, str]:
    labels = {
        'critical': 'Critical',
        'warning': 'Warning',
        'info': 'Info',
        'normal': 'Normal',
        'unknown': 'Unknown',
    }
    normalized = key if key in labels else 'unknown'
    return {'key': normalized, 'label': label or labels[normalized], 'tone': normalized}


def evidence_state(key: str) -> dict[str, str]:
    states = {
        'complete': ('Complete', 'normal'),
        'partial': ('Partial', 'warning'),
        'unavailable': ('Unavailable', 'unknown'),
    }
    label, tone = states.get(key, states['unavailable'])
    return {'key': key if key in states else 'unavailable', 'label': label, 'tone': tone}


def get_ratio_risk(percent: float | None) -> dict[str, str]:
    if percent is None:
        return semantic_state('unknown')
    if percent >= 90:
        return semantic_state('critical')
    if percent >= 75:
        return semantic_state('warning')
    return semantic_state('normal')


def get_compute_risk(
    *,
    resource_type: str,
    request: float,
    limit: float,
    request_utilization: float | None,
    limit_utilization: float | None,
) -> dict[str, str]:
    if request <= 0:
        return semantic_state('critical', 'Request Missing')
    highest = max(
        [value for value in (request_utilization, limit_utilization) if value is not None],
        default=None,
    )
    if highest is not None and highest >= 90:
        return semantic_state('critical')
    if highest is not None and highest >= 75:
        return semantic_state('warning')
    if resource_type == 'memory' and limit <= 0:
        return semantic_state('warning', 'Memory Limit Missing')
    if resource_type == 'cpu' and limit <= 0:
        return semantic_state('info', 'CPU Limit Unset')
    return semantic_state('normal')


def get_request_state(request: float, resource_type: str) -> dict[str, str]:
    if resource_type not in {'cpu', 'memory'}:
        return semantic_state('unknown', 'Not Applicable')
    return semantic_state('normal', 'Configured') if request > 0 else semantic_state('critical', 'Missing')


def get_limit_state(limit: float, resource_type: str) -> dict[str, str]:
    if resource_type == 'cpu':
        return semantic_state('normal', 'Configured') if limit > 0 else semantic_state('info', 'Intentionally Unset / Review Policy')
    if resource_type == 'memory':
        return semantic_state('normal', 'Configured') if limit > 0 else semantic_state('warning', 'Missing')
    return semantic_state('unknown', 'Not Applicable')


def get_resource_recommendation(
    *,
    resource_type: str,
    pressure_percent: float | None,
    request: float,
    limit: float,
) -> str:
    if resource_type == 'pvc':
        if pressure_percent is None:
            return 'Restore PVC capacity evidence'
        if pressure_percent >= 90:
            return 'Clean up or expand PVC capacity'
        if pressure_percent >= 75:
            return 'Plan PVC expansion and review retention'
        return 'Monitor claim growth'
    if resource_type == 'pods':
        if pressure_percent is None:
            return 'Restore cluster pod-capacity evidence'
        if pressure_percent >= 75:
            return 'Review pod density and worker capacity'
        return 'Monitor namespace pod growth'
    if request <= 0:
        return 'Add CPU request' if resource_type == 'cpu' else 'Add memory request'
    if resource_type == 'memory' and limit <= 0:
        return 'Review missing memory limit coverage'
    if pressure_percent is not None and pressure_percent >= 90:
        return 'Review scaling and resource boundaries immediately'
    if pressure_percent is not None and pressure_percent >= 75:
        return 'Validate demand and right-size resource boundaries'
    if resource_type == 'cpu' and limit <= 0:
        return 'Validate intentional CPU limit policy'
    return 'Continue monitoring consumption and contribution'


def get_dominant_namespace_names(rows: list[dict[str, Any]]) -> list[str]:
    namespace_scores: dict[str, float] = {}
    for row in rows:
        namespace = str(row.get('namespace') or '')
        if not namespace:
            continue
        contribution = _safe_float(row.get('contribution_percent', 0))
        risk = str((row.get('risk') or {}).get('key') or 'unknown')
        if contribution < 20 and risk not in {'warning', 'critical'}:
            continue
        namespace_scores[namespace] = namespace_scores.get(namespace, 0.0) + contribution + RISK_RANK.get(risk, 0) * 5
    return [namespace for namespace, _ in sorted(namespace_scores.items(), key=lambda item: (item[1], item[0]), reverse=True)[:3]]


def build_summary_card(
    *,
    rows: list[dict[str, Any]],
    title: str,
    selector: str,
) -> dict[str, Any]:
    if not rows:
        return {
            'title': title,
            'value': 'N/A',
            'subtitle': 'Evidence unavailable',
            'identity': {
                'entity_label': 'Consumer',
                'primary': 'No Data',
                'secondary': '',
                'tertiary': '',
            },
            'risk': semantic_state('unknown'),
        }
    key = 'pressure_percent' if selector == 'pressure' else 'current_usage'
    eligible = [row for row in rows if row.get(key) is not None]
    if not eligible:
        return {
            'title': title,
            'value': 'N/A',
            'subtitle': 'Required denominator unavailable',
            'identity': rows[0].get('identity', {}),
            'risk': semantic_state('unknown'),
        }
    top_row = max(eligible, key=lambda row: _safe_float(row.get(key, 0)))
    if selector == 'pressure':
        value = str(top_row.get('pressure_display') or 'N/A')
        subtitle = f"{top_row.get('current_display', 'N/A')} of {top_row.get('limit_display', 'N/A')}"
    else:
        value = str(top_row.get('current_display') or 'N/A')
        subtitle = f"{top_row.get('contribution_display', 'N/A')} of selected-scope consumption"
    return {
        'title': title,
        'value': value,
        'subtitle': subtitle,
        'identity': top_row.get('identity', {}),
        'risk': top_row.get('risk', semantic_state('unknown')),
    }


def format_scope_total(resource_type: str, value: float) -> str:
    if value <= 0:
        return 'N/A'
    if resource_type == 'cpu':
        return format_cpu(value)
    if resource_type in {'memory', 'pvc'}:
        return format_bytes(value)
    return f'{int(value)} Pods'


def get_empty_top_consumers_payload(
    *,
    message: str,
    page: int,
    per_page: int,
) -> dict[str, Any]:
    empty_summary = {
        key: {
            'title': title,
            'value': 'N/A',
            'subtitle': 'Evidence unavailable',
            'identity': {'entity_label': 'Consumer', 'primary': 'No Data', 'secondary': '', 'tertiary': ''},
            'risk': semantic_state('unknown'),
        }
        for key, title in {
            'highest_cpu': 'Highest CPU Consumption',
            'highest_memory': 'Highest Memory Consumption',
            'highest_pods': 'Highest Pod Density',
            'highest_pvc': 'Highest PVC Utilization',
        }.items()
    }
    coverage_items = {
        key: {**evidence_state('unavailable'), 'resource_label': RESOURCE_LABELS[key]}
        for key in ('cpu', 'memory', 'pods', 'pvc')
    }
    return {
        'has_data': False,
        'message': message,
        'scope': {'label': 'Cluster', 'namespace': '', 'snapshot_dimension': 'cluster'},
        'coverage': {
            'items': coverage_items,
            'complete_count': 0,
            'partial_count': 0,
            'unavailable_count': 4,
            'label': '0 of 4 Resources Complete',
        },
        'posture': {
            'label': 'Unknown',
            'tone': 'unknown',
            'icon': 'database-zap',
            'description': message,
            'highest_pressure': 'N/A',
        },
        'summary': empty_summary,
        'overview': {'rankings': []},
        'rows': [],
        'all_rows': [],
        'pagination': {
            'page': page,
            'current_page': page,
            'total_pages': 1,
            'total_items': 0,
            'per_page': per_page,
            'start_item': 0,
            'end_item': 0,
            'has_prev': False,
            'has_next': False,
            'prev_page': 1,
            'next_page': 1,
        },
        'actionable_recommendations': [],
        'recommendation_cards': [{
            'title': 'Connect Prometheus Metrics',
            'description': 'Top consumer analysis requires Prometheus metrics to calculate CPU, memory, pod, and PVC evidence.',
            'priority': 'Warning',
            'source': 'top_consumers',
            'source_label': 'Top Consumers',
            'resource': 'consumer',
            'action_type': 'prometheus_review',
            'href': '/integrations/prometheus',
            'icon': 'plug-zap',
            'is_actionable': 'Yes',
        }],
        'recommendation_count': 1,
        'recommendations': [],
        'total_rows': 0,
        'scope_total_rows': 0,
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
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.top_consumers',
        parameters={'cluster_id': str(cluster_id)},
    )
    payload = (result.context or {}).get('consumer_payload') if result.available else None
    if not isinstance(payload, dict):
        return _empty_top_consumers_snapshot()
    rows = list(payload.get('all_rows') or [])
    cpu_rows = [row for row in rows if row.get('resource_type') == 'cpu']
    memory_rows = [row for row in rows if row.get('resource_type') == 'memory']
    pvc_rows = [row for row in rows if row.get('resource_type') == 'pvc']
    pod_rows = [row for row in rows if row.get('resource_type') == 'pods']
    return {
        'cpu': _build_top_consumer_items(rows=cpu_rows, name_key='pod', fallback_name_key='workload', limit=5),
        'memory': _build_top_consumer_items(rows=memory_rows, name_key='pod', fallback_name_key='workload', limit=5),
        'storage': _build_top_consumer_items(
            rows=pvc_rows,
            name_key='workload',
            fallback_name_key='workload',
            limit=5,
        ),
        'pods': _build_top_consumer_items(
            rows=pod_rows,
            name_key='namespace',
            fallback_name_key='workload',
            limit=5,
        ),
        'recommendation_count': _safe_int(payload.get('recommendation_count', 0)),
    }

def _empty_top_consumers_snapshot() -> TopConsumersSnapshot:
    return {
        'cpu': [],
        'memory': [],
        'storage': [],
        'pods': [],
        'recommendation_count': 0,
    }


def _build_top_consumer_items(
    *,
    rows: list[dict[str, Any]],
    name_key: str,
    fallback_name_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    del name_key, fallback_name_key
    sorted_rows = sorted(
        rows,
        key=lambda row: _safe_float(row.get('current_usage', 0)),
        reverse=True,
    )
    top_rows = sorted_rows[:limit]
    max_value = max(
        [_safe_float(row.get('current_usage', 0)) for row in top_rows],
        default=0,
    )
    items: list[dict[str, Any]] = []

    for row in top_rows:
        identity = row.get('identity') if isinstance(row.get('identity'), dict) else {}
        namespace = str(row.get('namespace') or '')
        primary = str(identity.get('primary') or row.get('workload') or row.get('pod') or row.get('pvc_name') or '-')
        secondary = str(identity.get('secondary') or namespace)
        tertiary = str(identity.get('tertiary') or '')
        raw_value = _safe_float(row.get('current_usage', 0))
        pressure = row.get('pressure_percent')
        contribution = row.get('contribution_percent')
        semantic_percent = (
            _safe_float(pressure)
            if pressure is not None
            else _safe_float(contribution)
            if contribution is not None
            else _raw_percent(raw_value, max_value)
        )

        items.append(
            {
                'name': primary,
                'namespace': namespace,
                'pod': str(row.get('pod') or ''),
                'container': str(row.get('container') or ''),
                'workload': str(row.get('workload_owner') or row.get('workload') or ''),
                'identity': {
                    'primary': primary,
                    'secondary': secondary,
                    'tertiary': tertiary,
                },
                'value': str(row.get('current_display') or 'N/A'),
                'raw_value': raw_value,
                'percent': _safe_int(semantic_percent),
                'bar_percent': _safe_int(_raw_percent(raw_value, max_value)),
                'pressure_percent': row.get('pressure_percent'),
                'contribution_percent': row.get('contribution_percent'),
                'risk': row.get('risk', {}),
                'recommendation': str(row.get('recommendation') or ''),
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


def present_top_consumers_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply record-level controls to the committed cluster or namespace snapshot."""
    from copy import deepcopy

    presented = deepcopy(context)
    selected_namespace = get_query_value(query_args=query_args, name='namespace', default='')
    selected_resource = get_selected_resource(query_args)
    selected_search = get_query_value(query_args=query_args, name='search', default='')
    selected_priority = get_selected_priority(query_args)
    selected_focus = get_selected_focus(query_args)
    selected_sort = get_selected_sort(query_args, selected_resource)
    selected_tab = get_selected_tab(query_args)
    page = get_positive_int_arg(query_args=query_args, name='page', default=1)
    per_page = get_per_page_arg(query_args=query_args, name='per_page', default=5)

    namespace_options = list(presented.get('namespace_options') or [])
    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    payload = deepcopy(presented.get('consumer_payload') or {})
    all_rows = list(payload.get('all_rows') or [])
    service = TopConsumersService.__new__(TopConsumersService)
    filtered_rows = service.filter_rows(
        rows=all_rows,
        selected_search=selected_search,
        selected_resource=selected_resource,
        selected_priority=selected_priority,
        selected_focus=selected_focus,
    )
    sorted_rows = service.sort_rows(
        rows=filtered_rows,
        selected_sort=selected_sort,
        selected_resource=selected_resource,
    )
    ranked_rows = [dict(row, rank=index) for index, row in enumerate(sorted_rows, start=1)]
    page_payload = AnalyticsBaseService().paginate_rows_with_options(
        rows=ranked_rows,
        page=page,
        per_page=per_page,
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )
    payload.update({
        'has_data': bool(all_rows),
        'rows': page_payload['rows'],
        'pagination': page_payload['pagination'],
        'total_rows': len(filtered_rows),
        'scope_total_rows': len(all_rows),
    })
    recommendations = build_top_consumers_actionable_recommendations(payload)
    recommendation_cards = format_recommendation_cards(
        recommendations,
        default_title='Review Top Consumers',
        default_description='Review CPU, memory, pod, and PVC consumer hotspots.',
        default_source='top_consumers',
        default_action_type='consumer_review',
    )
    payload.update({
        'actionable_recommendations': recommendations,
        'recommendation_cards': recommendation_cards,
        'recommendation_count': count_actionable_recommendations(recommendations),
        'recommendations': recommendation_cards,
    })
    presented.update({
        'selected_namespace': selected_namespace,
        'selected_resource': selected_resource,
        'selected_time_range': 'current',
        'selected_search': selected_search,
        'selected_priority': selected_priority,
        'selected_focus': selected_focus,
        'selected_sort': selected_sort,
        'initial_tab': selected_tab,
        'resource_options': RESOURCE_OPTIONS,
        'priority_options': PRIORITY_OPTIONS,
        'focus_options': FOCUS_FILTER_OPTIONS,
        'sort_options': get_sort_options(selected_resource),
        'allowed_per_page_values': ALLOWED_PER_PAGE_VALUES,
        'consumer_payload': payload,
    })
    return presented

