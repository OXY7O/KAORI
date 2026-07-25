# app/analytics/workload/service.py

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService, bytes_to_gib, raw_percent, safe_percent, safe_round
from app.analytics.common.coercion import as_dict as _as_dict
from app.analytics.common.coercion import as_list as _as_list
from app.analytics.common.coercion import safe_float as _safe_float
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_allowed_time_ranges,
    get_per_page_arg,
    get_positive_int_arg,
    get_query_value,
    get_selected_time_range,
)
from app.analytics.common.payloads import get_empty_workload_payload
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_capability_blocker, prometheus_connection_blocker
from app.integrations.consumer.contracts import ConsumerResult
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.intelligence.recommendation_engine import (
    build_workload_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)

NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.workload.queries.NAMESPACE_ACTIVE_QUERY')
TENANT_CPU_ACTUAL_QUERY = get_query_expression('analytics.workload.queries.TENANT_CPU_ACTUAL_QUERY')
TENANT_MEMORY_ACTUAL_QUERY = get_query_expression('analytics.workload.queries.TENANT_MEMORY_ACTUAL_QUERY')
TENANT_POD_ACTUAL_QUERY = get_query_expression('analytics.workload.queries.TENANT_POD_ACTUAL_QUERY')
TENANT_QUOTA_HARD_QUERY = get_query_expression('analytics.workload.queries.TENANT_QUOTA_HARD_QUERY')
TENANT_QUOTA_USED_QUERY = get_query_expression('analytics.workload.queries.TENANT_QUOTA_USED_QUERY')
WORKLOAD_CPU_AVG_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_AVG_QUERY')
WORKLOAD_CPU_LIMITS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY')
WORKLOAD_CPU_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_PEAK_QUERY_TEMPLATE')
WORKLOAD_CPU_REQUESTS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY')
WORKLOAD_MEMORY_AVG_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_AVG_QUERY')
WORKLOAD_MEMORY_LIMITS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_LIMITS_QUERY')
WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE = get_query_expression(
    'analytics.workload.queries.WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE'
)
WORKLOAD_MEMORY_REQUESTS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_REQUESTS_QUERY')
WORKLOAD_POD_OWNER_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_POD_OWNER_QUERY')
WORKLOAD_QOS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_QOS_QUERY')

WORKLOAD_TIME_RANGE_STEP_MAP = {
    '1h': '5m',
    '6h': '15m',
    '12h': '30m',
    '24h': '1h',
    '7d': '6h',
    '30d': '12h',
    '60d': '1d',
}


def get_workload_time_step(
    time_range: str,
) -> str:
    return WORKLOAD_TIME_RANGE_STEP_MAP.get(
        time_range,
        '1h',
    )


REQUIRED_QUOTA_KEYS = [
    'requests.cpu',
    'limits.cpu',
    'requests.memory',
    'limits.memory',
    'pods',
]


def format_decimal(
    value: float,
    digits: int = 2,
) -> str:
    return f'{safe_round(value, digits):.{digits}f}'


def format_cpu_core(
    value: float,
) -> str:
    return f'{format_decimal(value, 2)} core'


def format_memory_gib(
    value: float,
) -> str:
    return f'{format_decimal(bytes_to_gib(value), 2)} GiB'


def format_count(
    value: float,
) -> str:
    return f'{safe_round(value, 0):.0f}'


def filter_tenant_quota_rows(
    rows: list[dict[str, Any]],
    selected_search: str = '',
    selected_quota_status: str = '',
    selected_risk: str = '',
) -> list[dict[str, Any]]:
    filtered_rows: list[dict[str, Any]] = []

    for row in rows:
        if (
            selected_search
            and selected_search.lower()
            not in str(
                row.get(
                    'namespace',
                    '',
                )
            ).lower()
        ):
            continue

        if (
            selected_quota_status
            and row.get(
                'quota_status',
                {},
            ).get(
                'label',
            )
            != selected_quota_status
        ):
            continue

        if (
            selected_risk
            and row.get(
                'risk',
                {},
            ).get(
                'label',
            )
            != selected_risk
        ):
            continue

        filtered_rows.append(
            row,
        )

    return filtered_rows


def filter_workload_rows(
    rows: list[dict[str, Any]],
    selected_search: str = '',
    selected_type: str = '',
    selected_resource_status: str = '',
    selected_qos: str = '',
    selected_risk: str = '',
) -> list[dict[str, Any]]:
    filtered_rows: list[dict[str, Any]] = []

    for row in rows:
        if selected_search:
            haystack = (f'{row.get("workload", "")} {row.get("namespace", "")}').lower()

            if selected_search.lower() not in haystack:
                continue

        if (
            selected_type
            and row.get(
                'type',
            )
            != selected_type
        ):
            continue

        if (
            selected_resource_status
            and row.get(
                'resource_status',
                {},
            ).get(
                'label',
            )
            != selected_resource_status
        ):
            continue

        if (
            selected_qos
            and row.get(
                'qos',
                {},
            ).get(
                'label',
            )
            != selected_qos
        ):
            continue

        if (
            selected_risk
            and row.get(
                'risk',
                {},
            ).get(
                'label',
            )
            != selected_risk
        ):
            continue

        filtered_rows.append(
            row,
        )

    return filtered_rows


class WorkloadAnalysisService(AnalyticsBaseService):
    REQUIRED_CAPABILITIES = (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'workload_metrics',
        'resource_requests_limits',
    )

    def __init__(
        self,
        utilization_service: UtilizationService,
    ) -> None:
        self.utilization_service = utilization_service
        self.consumer = utilization_service.consumer

    def requirements(self) -> ConsumerResult[dict[str, Any]]:
        return self.consumer.requirements(self.REQUIRED_CAPABILITIES)

    def get_prometheus_result(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        response = self.consumer.query(
            query,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )
        data = response.get('data', {}) if isinstance(response, dict) else {}
        result = data.get('result', []) if isinstance(data, dict) else []
        return result if isinstance(result, list) else []

    def get_prometheus_status(self) -> dict[str, Any]:
        response = self.consumer.status()
        payload = response.payload if isinstance(response.payload, dict) else {}
        response_time = payload.get('response_time_ms')
        return {
            'connected': response.ok,
            'response_time_ms': response_time,
            'response_time_display': f'{response_time} ms' if response_time is not None else 'No response',
            'label': 'Prometheus Connected' if response.ok else 'Prometheus Unavailable',
            'description': (
                'Integration runtime and workload capability contract are available.'
                if response.ok
                else (response.diagnostics[0].message if response.diagnostics else 'Prometheus is unavailable.')
            ),
            'tone': 'normal' if response.ok else 'critical',
            'icon': 'circle-check' if response.ok else 'circle-x',
        }

    def get_all_namespace_options(
        self,
    ) -> list[str]:
        active_namespaces = self.get_prometheus_vector_map(
            query=NAMESPACE_ACTIVE_QUERY,
            label='namespace',
        )

        quota_hard = self.get_resource_quota_map(
            query=TENANT_QUOTA_HARD_QUERY,
        )

        quota_used = self.get_resource_quota_map(
            query=TENANT_QUOTA_USED_QUERY,
        )

        runtime_namespaces = self.get_prometheus_vector_map(
            query=TENANT_POD_ACTUAL_QUERY,
            label='namespace',
        )

        namespaces = set(
            active_namespaces.keys(),
        )

        namespaces.update(
            quota_hard.keys(),
        )

        namespaces.update(
            quota_used.keys(),
        )

        namespaces.update(
            runtime_namespaces.keys(),
        )

        return sorted(namespace for namespace in namespaces if namespace)

    def get_pod_owner_map(
        self,
    ) -> dict[str, dict[str, str]]:
        result = self.get_prometheus_result(
            WORKLOAD_POD_OWNER_QUERY,
        )

        values: dict[str, dict[str, str]] = {}

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

            pod = metric.get(
                'pod',
                '',
            )

            owner_kind = metric.get(
                'owner_kind',
                'Pod',
            )

            owner_name = metric.get(
                'owner_name',
                pod,
            )

            if (
                not isinstance(
                    namespace,
                    str,
                )
                or not isinstance(
                    pod,
                    str,
                )
                or not namespace
                or not pod
            ):
                continue

            if not isinstance(
                owner_kind,
                str,
            ):
                owner_kind = 'Pod'

            if not isinstance(
                owner_name,
                str,
            ):
                owner_name = pod

            if owner_kind == 'ReplicaSet':
                owner_kind = 'Deployment'
                owner_name = self.strip_replicaset_hash(
                    owner_name,
                )

            values[f'{namespace}/{pod}'] = {
                'kind': owner_kind,
                'name': owner_name,
            }

        return values

    def get_pod_qos_map(
        self,
    ) -> dict[str, str]:
        result = self.get_prometheus_result(
            WORKLOAD_QOS_QUERY,
        )

        values: dict[str, str] = {}

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

            pod = metric.get(
                'pod',
                '',
            )

            qos_class = metric.get(
                'qos_class',
                '',
            )

            if (
                not isinstance(
                    namespace,
                    str,
                )
                or not isinstance(
                    pod,
                    str,
                )
                or not isinstance(
                    qos_class,
                    str,
                )
                or not namespace
                or not pod
                or not qos_class
            ):
                continue

            values[f'{namespace}/{pod}'] = qos_class

        return values

    def infer_workload_owner(
        self,
        pod_name: str,
    ) -> dict[str, str]:
        workload_name = self.strip_pod_suffix(
            pod_name,
        )

        return {
            'kind': 'Workload',
            'name': workload_name,
        }

    def strip_pod_suffix(
        self,
        pod_name: str,
    ) -> str:
        match = re.match(
            r'^(?P<name>.+)-[a-z0-9]{8,10}-[a-z0-9]{5}$',
            pod_name,
        )

        if match:
            return match.group(
                'name',
            )

        match = re.match(
            r'^(?P<name>.+)-[a-z0-9]{5}$',
            pod_name,
        )

        if match:
            return match.group(
                'name',
            )

        return pod_name

    def strip_replicaset_hash(
        self,
        owner_name: str,
    ) -> str:
        return re.sub(
            r'-[a-z0-9]{8,10}$',
            '',
            owner_name,
        )

    def get_tenant_quota_summary(
        self,
        selected_namespace: str,
    ) -> dict[str, Any]:
        namespaces = self.get_prometheus_vector_map(
            query=NAMESPACE_ACTIVE_QUERY,
            label='namespace',
        )

        hard = self.get_resource_quota_map(
            query=TENANT_QUOTA_HARD_QUERY,
        )

        used = self.get_resource_quota_map(
            query=TENANT_QUOTA_USED_QUERY,
        )

        cpu_actual = self.get_prometheus_vector_map(
            query=TENANT_CPU_ACTUAL_QUERY,
            label='namespace',
        )

        memory_actual = self.get_prometheus_vector_map(
            query=TENANT_MEMORY_ACTUAL_QUERY,
            label='namespace',
        )

        pod_actual = self.get_prometheus_vector_map(
            query=TENANT_POD_ACTUAL_QUERY,
            label='namespace',
        )

        namespace_names = set(
            namespaces.keys(),
        )

        namespace_names.update(
            hard.keys(),
        )

        namespace_names.update(
            used.keys(),
        )

        rows: list[dict[str, Any]] = []

        for namespace in sorted(
            namespace_names,
        ):
            if selected_namespace and namespace != selected_namespace:
                continue

            hard_values = hard.get(
                namespace,
                {},
            )

            used_values = used.get(
                namespace,
                {},
            )

            missing_keys = [
                key
                for key in REQUIRED_QUOTA_KEYS
                if not hard_values.get(
                    key,
                    0,
                )
            ]

            quota_status = self.get_quota_status(
                hard_values=hard_values,
                missing_keys=missing_keys,
            )

            quota_usage_percent = self.get_highest_quota_percent(
                hard_values=hard_values,
                used_values=used_values,
            )

            actual_usage_percent = self.get_highest_actual_percent(
                hard_values=hard_values,
                cpu_actual=cpu_actual.get(
                    namespace,
                    0,
                ),
                memory_actual=memory_actual.get(
                    namespace,
                    0,
                ),
                pod_actual=pod_actual.get(
                    namespace,
                    0,
                ),
            )

            quota_usage_percent = safe_round(
                quota_usage_percent,
                2,
            )

            actual_usage_percent = safe_round(
                actual_usage_percent,
                2,
            )

            risk = self.get_tenant_analysis_risk(
                quota_status=quota_status['label'],
                quota_usage_percent=quota_usage_percent,
                actual_usage_percent=actual_usage_percent,
            )

            recommendation = self.get_tenant_recommendation(
                quota_status=quota_status['label'],
                missing_keys=missing_keys,
                quota_usage_percent=quota_usage_percent,
                actual_usage_percent=actual_usage_percent,
            )

            cpu_quota_raw = hard_values.get(
                'limits.cpu',
                0,
            )

            cpu_requested_raw = used_values.get(
                'requests.cpu',
                0,
            )

            cpu_limited_raw = used_values.get(
                'limits.cpu',
                0,
            )

            cpu_actual_raw = cpu_actual.get(
                namespace,
                0,
            )

            memory_quota_raw = hard_values.get(
                'limits.memory',
                0,
            )

            memory_requested_raw = used_values.get(
                'requests.memory',
                0,
            )

            memory_limited_raw = used_values.get(
                'limits.memory',
                0,
            )

            memory_actual_raw = memory_actual.get(
                namespace,
                0,
            )

            pod_actual_raw = pod_actual.get(
                namespace,
                0,
            )

            rows.append(
                {
                    'namespace': namespace,
                    'quota_status': quota_status,
                    'quota_usage_percent': quota_usage_percent,
                    'quota_usage_percent_display': format_decimal(
                        quota_usage_percent,
                    ),
                    'actual_usage_percent': actual_usage_percent,
                    'actual_usage_percent_display': format_decimal(
                        actual_usage_percent,
                    ),
                    'risk': risk,
                    'recommendation': recommendation,
                    'missing_keys': missing_keys,
                    'missing_key_labels': [
                        self.get_resource_quota_label(
                            key,
                        )
                        for key in missing_keys
                    ],
                    'hard': hard_values,
                    'used': used_values,
                    'hard_items': self.build_resource_quota_items(
                        hard_values,
                    ),
                    'used_items': self.build_resource_quota_items(
                        used_values,
                    ),
                    'actual': {
                        'cpu': format_cpu_core(
                            cpu_actual_raw,
                        ),
                        'memory': format_memory_gib(
                            memory_actual_raw,
                        ),
                        'pods': format_count(
                            pod_actual_raw,
                        ),
                    },
                    'cpu_quota': format_cpu_core(
                        cpu_quota_raw,
                    ),
                    'cpu_requested': format_cpu_core(
                        cpu_requested_raw,
                    ),
                    'cpu_limited': format_cpu_core(
                        cpu_limited_raw,
                    ),
                    'cpu_actual': format_cpu_core(
                        cpu_actual_raw,
                    ),
                    'cpu_requested_percent': safe_round(
                        safe_percent(
                            cpu_requested_raw,
                            cpu_quota_raw,
                        ),
                        2,
                    ),
                    'cpu_requested_percent_display': format_decimal(
                        safe_percent(
                            cpu_requested_raw,
                            cpu_quota_raw,
                        )
                    ),
                    'cpu_limited_percent': safe_round(
                        safe_percent(
                            cpu_limited_raw,
                            cpu_quota_raw,
                        ),
                        2,
                    ),
                    'cpu_limited_percent_display': format_decimal(
                        safe_percent(
                            cpu_limited_raw,
                            cpu_quota_raw,
                        )
                    ),
                    'cpu_actual_percent': safe_round(
                        safe_percent(
                            cpu_actual_raw,
                            cpu_quota_raw,
                        ),
                        2,
                    ),
                    'cpu_actual_percent_display': format_decimal(
                        safe_percent(
                            cpu_actual_raw,
                            cpu_quota_raw,
                        )
                    ),
                    'memory_quota': format_memory_gib(
                        memory_quota_raw,
                    ),
                    'memory_requested': format_memory_gib(
                        memory_requested_raw,
                    ),
                    'memory_limited': format_memory_gib(
                        memory_limited_raw,
                    ),
                    'memory_actual': format_memory_gib(
                        memory_actual_raw,
                    ),
                    'memory_requested_percent': safe_round(
                        safe_percent(
                            memory_requested_raw,
                            memory_quota_raw,
                        ),
                        2,
                    ),
                    'memory_requested_percent_display': format_decimal(
                        safe_percent(
                            memory_requested_raw,
                            memory_quota_raw,
                        )
                    ),
                    'memory_limited_percent': safe_round(
                        safe_percent(
                            memory_limited_raw,
                            memory_quota_raw,
                        ),
                        2,
                    ),
                    'memory_limited_percent_display': format_decimal(
                        safe_percent(
                            memory_limited_raw,
                            memory_quota_raw,
                        )
                    ),
                    'memory_actual_percent': safe_round(
                        safe_percent(
                            memory_actual_raw,
                            memory_quota_raw,
                        ),
                        2,
                    ),
                    'memory_actual_percent_display': format_decimal(
                        safe_percent(
                            memory_actual_raw,
                            memory_quota_raw,
                        )
                    ),
                    'workloads': format_count(
                        pod_actual_raw,
                    ),
                }
            )

        total_namespaces = len(
            rows,
        )

        covered_namespaces = len([row for row in rows if row['quota_status']['label'] != 'Missing'])

        near_limit_count = len([row for row in rows if row['quota_usage_percent'] >= 75])

        efficiency_risk_count = len(
            [row for row in rows if (row['quota_usage_percent'] >= 75 and row['actual_usage_percent'] < 40)]
        )

        quota_coverage_percent = safe_percent(
            covered_namespaces,
            total_namespaces,
        )

        near_limit_percent = safe_percent(
            near_limit_count,
            total_namespaces,
        )

        efficiency_risk_percent = safe_percent(
            efficiency_risk_count,
            total_namespaces,
        )

        return {
            'summary_cards': [
                {
                    'label': 'Namespaces',
                    'value': total_namespaces,
                    'caption': 'Selected scope',
                    'icon': 'network',
                    'icon_class': 'bg-blue-100 text-blue-600',
                },
                {
                    'label': 'Quota Coverage',
                    'value': f'{format_decimal(quota_coverage_percent)}%',
                    'caption': (f'{covered_namespaces} of {total_namespaces} namespaces'),
                    'icon': 'shield-check',
                    'icon_class': 'bg-cyan-100 text-cyan-600',
                },
                {
                    'label': 'Quota Near Limit',
                    'value': near_limit_count,
                    'caption': f'{format_decimal(near_limit_percent)}%',
                    'icon': 'triangle-alert',
                    'icon_class': 'bg-orange-100 text-orange-600',
                },
                {
                    'label': 'Quota Efficiency Risk',
                    'value': efficiency_risk_count,
                    'caption': f'{format_decimal(efficiency_risk_percent)}%',
                    'icon': 'activity',
                    'icon_class': 'bg-violet-100 text-violet-600',
                },
            ],
            'rows': rows,
        }

    def get_resource_status(
        self,
        cpu_request: float,
        cpu_limit: float,
        memory_request: float,
        memory_limit: float,
    ) -> dict[str, str]:
        missing_request = not cpu_request or not memory_request
        missing_limit = not cpu_limit or not memory_limit

        if missing_request and missing_limit:
            return {
                'label': 'BestEffort',
                'class': 'bg-red-100 text-red-700',
            }

        if missing_request:
            return {
                'label': 'Missing Request',
                'class': 'bg-amber-100 text-amber-700',
            }

        if missing_limit:
            return {
                'label': 'Missing Limit',
                'class': 'bg-amber-100 text-amber-700',
            }

        return {
            'label': 'Complete',
            'class': 'bg-emerald-100 text-emerald-700',
        }

    def get_workload_qos(
        self,
        qos_distribution: dict[str, int],
    ) -> dict[str, str]:
        if not qos_distribution:
            return {
                'label': 'Unknown',
                'class': 'bg-slate-100 text-slate-700',
            }

        if len(qos_distribution) > 1:
            return {
                'label': 'Mixed',
                'class': 'bg-indigo-100 text-indigo-700',
            }

        qos = next(
            iter(
                qos_distribution.keys(),
            )
        )

        class_map = {
            'Guaranteed': 'bg-emerald-100 text-emerald-700',
            'Burstable': 'bg-blue-100 text-blue-700',
            'BestEffort': 'bg-red-100 text-red-700',
        }

        return {
            'label': qos,
            'class': class_map.get(
                qos,
                'bg-slate-100 text-slate-700',
            ),
        }

    def get_efficiency_score(
        self,
        cpu_usage: float,
        cpu_request: float,
        memory_usage: float,
        memory_request: float,
    ) -> float:
        cpu_score = safe_percent(
            cpu_usage,
            cpu_request,
        )

        memory_score = safe_percent(
            memory_usage,
            memory_request,
        )

        if not cpu_request and not memory_request:
            return 0

        if cpu_request and memory_request:
            return safe_round(
                (cpu_score + memory_score) / 2,
                2,
            )

        return safe_round(
            cpu_score or memory_score,
            2,
        )

    def get_workload_recommendation(
        self,
        cpu_usage: float,
        cpu_request: float,
        cpu_limit: float,
        memory_usage: float,
        memory_request: float,
        memory_limit: float,
        resource_status: str,
    ) -> str:
        if resource_status == 'BestEffort':
            return 'Review BestEffort workload'

        if not cpu_request and not memory_request:
            return 'Set CPU and memory requests'

        if not cpu_request:
            return 'Set CPU request'

        if not memory_request:
            return 'Set memory request'

        if not memory_limit:
            return 'Set memory limit'

        if not cpu_limit:
            return 'Review CPU limit policy'

        cpu_efficiency = safe_percent(
            cpu_usage,
            cpu_request,
        )

        memory_efficiency = safe_percent(
            memory_usage,
            memory_request,
        )

        if cpu_efficiency < 30 and memory_efficiency < 30:
            return 'Reduce requests'

        if cpu_efficiency < 30:
            return 'Reduce CPU request'

        if memory_efficiency < 30:
            return 'Reduce memory request'

        if memory_efficiency > 90:
            return 'Increase memory request'

        if cpu_efficiency > 90:
            return 'Increase CPU request'

        return 'No action needed'

    def get_workload_risk(
        self,
        resource_status: str,
        efficiency: float,
        recommendation: str,
    ) -> dict[str, str]:
        if resource_status in [
            'BestEffort',
            'Missing Request',
        ]:
            return {
                'label': 'High',
                'class': 'bg-red-100 text-red-700',
            }

        if 'increase' in recommendation.lower():
            return {
                'label': 'High',
                'class': 'bg-red-100 text-red-700',
            }

        if resource_status in [
            'Missing Limit',
            'Partial',
        ]:
            return {
                'label': 'Medium',
                'class': 'bg-amber-100 text-amber-700',
            }

        if efficiency < 40:
            return {
                'label': 'Medium',
                'class': 'bg-amber-100 text-amber-700',
            }

        return {
            'label': 'Low',
            'class': 'bg-emerald-100 text-emerald-700',
        }

    def get_risk_sort_weight(
        self,
        risk: str,
    ) -> int:
        weights = {
            'High': 0,
            'Critical': 0,
            'Medium': 1,
            'Low': 2,
        }

        return weights.get(
            risk,
            3,
        )

    def build_range_query(
        self,
        query_template: str,
        time_range: str,
    ) -> str:
        return query_template.replace(
            '__TIME_RANGE__',
            time_range,
        ).replace(
            '__TIME_STEP__',
            get_workload_time_step(
                time_range,
            ),
        )

    def get_resource_quota_map(
        self,
        query: str,
    ) -> dict[str, dict[str, float]]:
        result = self.get_prometheus_result(
            query,
        )

        values: dict[str, dict[str, float]] = {}

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

            resource = metric.get(
                'resource',
                '',
            )

            if (
                not isinstance(
                    namespace,
                    str,
                )
                or not namespace
                or not isinstance(
                    resource,
                    str,
                )
                or not resource
            ):
                continue

            if namespace not in values:
                values[namespace] = {}

            values[namespace][resource] = self.extract_value(
                item,
            )

        return values

    def get_quota_status(
        self,
        hard_values: dict[str, float],
        missing_keys: list[str],
    ) -> dict[str, str]:
        if not hard_values:
            return {
                'label': 'Missing',
                'class': 'bg-red-100 text-red-700',
            }

        if missing_keys:
            return {
                'label': 'Partial',
                'class': 'bg-amber-100 text-amber-700',
            }

        return {
            'label': 'Complete',
            'class': 'bg-emerald-100 text-emerald-700',
        }

    def get_highest_quota_percent(
        self,
        hard_values: dict[str, float],
        used_values: dict[str, float],
    ) -> float:
        values = [
            raw_percent(
                used_values.get(
                    key,
                    0,
                ),
                hard_values.get(
                    key,
                    0,
                ),
            )
            for key in REQUIRED_QUOTA_KEYS
        ]

        return max(
            values,
            default=0,
        )

    def get_highest_actual_percent(
        self,
        hard_values: dict[str, float],
        cpu_actual: float,
        memory_actual: float,
        pod_actual: float,
    ) -> float:
        values = [
            raw_percent(
                cpu_actual,
                hard_values.get(
                    'limits.cpu',
                    0,
                ),
            ),
            raw_percent(
                memory_actual,
                hard_values.get(
                    'limits.memory',
                    0,
                ),
            ),
            raw_percent(
                pod_actual,
                hard_values.get(
                    'pods',
                    0,
                ),
            ),
        ]

        return max(
            values,
            default=0,
        )

    def get_tenant_analysis_risk(
        self,
        quota_status: str,
        quota_usage_percent: float,
        actual_usage_percent: float,
    ) -> dict[str, str]:
        if quota_status == 'Missing':
            return {
                'label': 'Critical',
                'class': 'bg-red-100 text-red-700',
            }

        if quota_usage_percent >= 90:
            return {
                'label': 'Critical',
                'class': 'bg-red-100 text-red-700',
            }

        if quota_usage_percent >= 75 and actual_usage_percent < 40:
            return {
                'label': 'Medium',
                'class': 'bg-amber-100 text-amber-700',
            }

        if quota_usage_percent >= 75:
            return {
                'label': 'High',
                'class': 'bg-orange-100 text-orange-700',
            }

        if quota_status == 'Partial':
            return {
                'label': 'Medium',
                'class': 'bg-amber-100 text-amber-700',
            }

        return {
            'label': 'Low',
            'class': 'bg-emerald-100 text-emerald-700',
        }

    def get_tenant_recommendation(
        self,
        quota_status: str,
        missing_keys: list[str],
        quota_usage_percent: float,
        actual_usage_percent: float,
    ) -> str:
        if quota_status == 'Missing':
            return 'Create ResourceQuota'

        if missing_keys:
            return 'Add missing quota keys'

        if quota_usage_percent >= 90:
            if actual_usage_percent < 50:
                return 'Right-size workload requests before increasing quota'

            return 'Review allocation or increase quota'

        if quota_usage_percent >= 75 and actual_usage_percent < 40:
            return 'Right-size requests and limits'

        if quota_usage_percent >= 75:
            return 'Monitor quota and review allocation'

        return 'Quota looks healthy'

    def get_resource_quota_label(
        self,
        key: str,
    ) -> str:
        label_map = {
            'requests.cpu': 'Requests CPU',
            'limits.cpu': 'Limits CPU',
            'requests.memory': 'Requests Memory',
            'limits.memory': 'Limits Memory',
            'pods': 'Pods',
        }

        return label_map.get(
            key,
            key,
        )

    def format_resource_quota_value(
        self,
        key: str,
        value: float,
    ) -> str:
        if key.endswith(
            '.cpu',
        ):
            return format_cpu_core(
                value,
            )

        if key.endswith(
            '.memory',
        ):
            return format_memory_gib(
                value,
            )

        if key == 'pods':
            return f'{format_count(value)} pods'

        return format_decimal(
            value,
        )

    def build_resource_quota_items(
        self,
        values: dict[str, float],
    ) -> list[dict[str, str]]:
        return [
            {
                'label': self.get_resource_quota_label(
                    key,
                ),
                'value': self.format_resource_quota_value(
                    key=key,
                    value=value,
                ),
            }
            for key, value in sorted(
                values.items(),
            )
        ]

    def get_workload_mapping_payload(
        self,
        selected_namespace: str,
        time_range: str,
    ) -> dict[str, Any]:
        cpu_requests = self.get_prometheus_vector_map(
            query=WORKLOAD_CPU_REQUESTS_QUERY,
            label='pod',
            secondary_label='namespace',
        )

        cpu_limits = self.get_prometheus_vector_map(
            query=WORKLOAD_CPU_LIMITS_QUERY,
            label='pod',
            secondary_label='namespace',
        )

        cpu_avg = self.get_prometheus_vector_map(
            query=WORKLOAD_CPU_AVG_QUERY,
            label='pod',
            secondary_label='namespace',
        )

        cpu_peak = self.get_prometheus_vector_map(
            query=self.build_range_query(
                WORKLOAD_CPU_PEAK_QUERY_TEMPLATE,
                time_range,
            ),
            label='pod',
            secondary_label='namespace',
        )

        memory_requests = self.get_prometheus_vector_map(
            query=WORKLOAD_MEMORY_REQUESTS_QUERY,
            label='pod',
            secondary_label='namespace',
        )

        memory_limits = self.get_prometheus_vector_map(
            query=WORKLOAD_MEMORY_LIMITS_QUERY,
            label='pod',
            secondary_label='namespace',
        )

        memory_avg = self.get_prometheus_vector_map(
            query=WORKLOAD_MEMORY_AVG_QUERY,
            label='pod',
            secondary_label='namespace',
        )

        memory_peak = self.get_prometheus_vector_map(
            query=self.build_range_query(
                WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE,
                time_range,
            ),
            label='pod',
            secondary_label='namespace',
        )

        owner_map = self.get_pod_owner_map()
        qos_map = self.get_pod_qos_map()

        keys = set(
            cpu_requests.keys(),
        )

        keys.update(
            cpu_limits.keys(),
        )

        keys.update(
            cpu_avg.keys(),
        )

        keys.update(
            memory_requests.keys(),
        )

        keys.update(
            memory_limits.keys(),
        )

        keys.update(
            memory_avg.keys(),
        )

        workload_map: dict[str, dict[str, Any]] = {}

        for key in sorted(
            keys,
        ):
            namespace, pod = self.split_composite_key(
                key,
            )

            if selected_namespace and namespace != selected_namespace:
                continue

            owner = owner_map.get(
                key,
                self.infer_workload_owner(
                    pod,
                ),
            )

            workload_key = f'{namespace}/{owner["name"]}'

            if workload_key not in workload_map:
                workload_map[workload_key] = {
                    'workload': owner['name'],
                    'type': owner['kind'],
                    'namespace': namespace,
                    'replicas': 0,
                    'pods': [],
                    'cpu_request_raw': 0.0,
                    'cpu_limit_raw': 0.0,
                    'cpu_avg_raw': 0.0,
                    'cpu_peak_raw': 0.0,
                    'memory_request_raw': 0.0,
                    'memory_limit_raw': 0.0,
                    'memory_avg_raw': 0.0,
                    'memory_peak_raw': 0.0,
                    'qos_distribution': {},
                }

            item = workload_map[workload_key]

            item['replicas'] += 1

            item['pods'].append(
                pod,
            )

            item['cpu_request_raw'] += cpu_requests.get(
                key,
                0,
            )

            item['cpu_limit_raw'] += cpu_limits.get(
                key,
                0,
            )

            item['cpu_avg_raw'] += cpu_avg.get(
                key,
                0,
            )

            item['cpu_peak_raw'] += cpu_peak.get(
                key,
                cpu_avg.get(
                    key,
                    0,
                ),
            )

            item['memory_request_raw'] += memory_requests.get(
                key,
                0,
            )

            item['memory_limit_raw'] += memory_limits.get(
                key,
                0,
            )

            item['memory_avg_raw'] += memory_avg.get(
                key,
                0,
            )

            item['memory_peak_raw'] += memory_peak.get(
                key,
                memory_avg.get(
                    key,
                    0,
                ),
            )

            qos = qos_map.get(
                key,
                'Unknown',
            )

            qos_distribution = item['qos_distribution']

            qos_distribution[qos] = (
                qos_distribution.get(
                    qos,
                    0,
                )
                + 1
            )

        rows: list[dict[str, Any]] = []

        for item in workload_map.values():
            resource_status = self.get_resource_status(
                cpu_request=item['cpu_request_raw'],
                cpu_limit=item['cpu_limit_raw'],
                memory_request=item['memory_request_raw'],
                memory_limit=item['memory_limit_raw'],
            )

            qos = self.get_workload_qos(
                item['qos_distribution'],
            )

            efficiency = self.get_efficiency_score(
                cpu_usage=item['cpu_avg_raw'],
                cpu_request=item['cpu_request_raw'],
                memory_usage=item['memory_avg_raw'],
                memory_request=item['memory_request_raw'],
            )

            recommendation = self.get_workload_recommendation(
                cpu_usage=item['cpu_avg_raw'],
                cpu_request=item['cpu_request_raw'],
                cpu_limit=item['cpu_limit_raw'],
                memory_usage=item['memory_avg_raw'],
                memory_request=item['memory_request_raw'],
                memory_limit=item['memory_limit_raw'],
                resource_status=resource_status['label'],
            )

            risk = self.get_workload_risk(
                resource_status=resource_status['label'],
                efficiency=efficiency,
                recommendation=recommendation,
            )

            rows.append(
                {
                    'workload': item['workload'],
                    'type': item['type'],
                    'namespace': item['namespace'],
                    'replicas': item['replicas'],
                    'resource_status': resource_status,
                    'qos': qos,
                    'cpu_summary': (
                        f'Req {format_cpu_core(item["cpu_request_raw"])} · '
                        f'Lim {format_cpu_core(item["cpu_limit_raw"])} · '
                        f'Avg {format_cpu_core(item["cpu_avg_raw"])} · '
                        f'Peak {format_cpu_core(item["cpu_peak_raw"])}'
                    ),
                    'memory_summary': (
                        f'Req {format_memory_gib(item["memory_request_raw"])} · '
                        f'Lim {format_memory_gib(item["memory_limit_raw"])} · '
                        f'Avg {format_memory_gib(item["memory_avg_raw"])} · '
                        f'Peak {format_memory_gib(item["memory_peak_raw"])}'
                    ),
                    'efficiency': efficiency,
                    'efficiency_display': format_decimal(
                        efficiency,
                    ),
                    'risk': risk,
                    'recommendation': recommendation,
                    'cpu_request_raw': item['cpu_request_raw'],
                    'cpu_limit_raw': item['cpu_limit_raw'],
                    'cpu_avg_raw': item['cpu_avg_raw'],
                    'cpu_peak_raw': item['cpu_peak_raw'],
                    'memory_request_raw': item['memory_request_raw'],
                    'memory_limit_raw': item['memory_limit_raw'],
                    'memory_avg_raw': item['memory_avg_raw'],
                    'memory_peak_raw': item['memory_peak_raw'],
                    'detail': {
                        'pods': item['pods'],
                        'qos_distribution': item['qos_distribution'],
                    },
                    'cpu_request': format_cpu_core(
                        item['cpu_request_raw'],
                    ),
                    'cpu_limit': format_cpu_core(
                        item['cpu_limit_raw'],
                    ),
                    'cpu_avg': format_cpu_core(
                        item['cpu_avg_raw'],
                    ),
                    'cpu_peak': format_cpu_core(
                        item['cpu_peak_raw'],
                    ),
                    'memory_request': format_memory_gib(
                        item['memory_request_raw'],
                    ),
                    'memory_limit': format_memory_gib(
                        item['memory_limit_raw'],
                    ),
                    'memory_avg': format_memory_gib(
                        item['memory_avg_raw'],
                    ),
                    'memory_peak': format_memory_gib(
                        item['memory_peak_raw'],
                    ),
                }
            )

        rows.sort(
            key=lambda row: (
                self.get_risk_sort_weight(
                    row['risk']['label'],
                ),
                row['namespace'],
                row['workload'],
            )
        )

        return {
            'rows': rows,
            'filters': {
                'resource_status': [
                    'All',
                    'Complete',
                    'Partial',
                    'Missing Request',
                    'Missing Limit',
                    'BestEffort',
                    'No Metrics',
                ],
                'qos': [
                    'All',
                    'Guaranteed',
                    'Burstable',
                    'BestEffort',
                    'Mixed',
                    'Unknown',
                ],
                'risk': [
                    'All',
                    'Low',
                    'Medium',
                    'High',
                ],
            },
        }

    def paginate_rows(
        self,
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

    def get_governance_findings(
        self,
        tenant_quota_rows: list[dict[str, Any]],
        workload_mapping_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        no_quota_count = len(
            [
                row
                for row in tenant_quota_rows
                if row.get(
                    'quota_status',
                    {},
                ).get(
                    'label',
                )
                == 'Missing'
            ]
        )

        missing_request_count = len(
            [
                row
                for row in workload_mapping_rows
                if row.get(
                    'resource_status',
                    {},
                ).get(
                    'label',
                )
                in [
                    'Missing Request',
                    'BestEffort',
                ]
            ]
        )

        missing_limit_count = len(
            [
                row
                for row in workload_mapping_rows
                if row.get(
                    'resource_status',
                    {},
                ).get(
                    'label',
                )
                in [
                    'Missing Limit',
                    'BestEffort',
                ]
            ]
        )

        best_effort_count = len(
            [
                row
                for row in workload_mapping_rows
                if row.get(
                    'qos',
                    {},
                ).get(
                    'label',
                )
                == 'BestEffort'
            ]
        )

        over_requested_count = len(
            [
                row
                for row in workload_mapping_rows
                if 'reduce'
                in str(
                    row.get(
                        'recommendation',
                        '',
                    )
                ).lower()
            ]
        )

        findings: list[dict[str, Any]] = []

        if no_quota_count:
            findings.append(
                {
                    'label': f'{no_quota_count} namespaces without ResourceQuota',
                    'severity': 'warning',
                    'icon': 'triangle-alert',
                    'filter': 'missing-quota',
                }
            )

        if missing_request_count:
            findings.append(
                {
                    'label': f'{missing_request_count} workloads missing requests',
                    'severity': 'warning',
                    'icon': 'triangle-alert',
                    'filter': 'missing-request',
                }
            )

        if missing_limit_count:
            findings.append(
                {
                    'label': f'{missing_limit_count} workloads missing limits',
                    'severity': 'warning',
                    'icon': 'triangle-alert',
                    'filter': 'missing-limit',
                }
            )

        if best_effort_count:
            findings.append(
                {
                    'label': f'{best_effort_count} BestEffort workloads',
                    'severity': 'warning',
                    'icon': 'info',
                    'filter': 'best-effort',
                }
            )

        if over_requested_count:
            findings.append(
                {
                    'label': f'{over_requested_count} workloads over-requested',
                    'severity': 'critical',
                    'icon': 'circle-alert',
                    'filter': 'over-requested',
                }
            )

        if not findings:
            findings.append(
                {
                    'label': 'No critical governance findings detected',
                    'severity': 'healthy',
                    'icon': 'check-circle',
                    'filter': '',
                }
            )

        return findings


def get_workload_analysis_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
        check_prometheus_connection=False,
    )

    workload_service: WorkloadAnalysisService | None = None

    if utilization_service is not None:
        workload_service = WorkloadAnalysisService(
            utilization_service,
        )

    selected_namespace = get_query_value(
        query_args=query_args,
        name='namespace',
        default='',
    )

    selected_time_range = get_selected_time_range(
        query_args=query_args,
    )

    selected_tenant_search = get_query_value(
        query_args=query_args,
        name='tenant_search',
        default='',
    )

    selected_tenant_quota_status = get_query_value(
        query_args=query_args,
        name='tenant_quota_status',
        default='',
    )

    selected_tenant_risk = get_query_value(
        query_args=query_args,
        name='tenant_risk',
        default='',
    )

    selected_workload_search = get_query_value(
        query_args=query_args,
        name='workload_search',
        default='',
    )

    selected_workload_type = get_query_value(
        query_args=query_args,
        name='workload_type',
        default='',
    )

    selected_workload_resource_status = get_query_value(
        query_args=query_args,
        name='workload_resource_status',
        default='',
    )

    selected_workload_qos = get_query_value(
        query_args=query_args,
        name='workload_qos',
        default='',
    )

    selected_workload_risk = get_query_value(
        query_args=query_args,
        name='workload_risk',
        default='',
    )

    context.update(
        {
            'selected_namespace': selected_namespace,
            'selected_time_range': selected_time_range,
            'selected_tenant_search': selected_tenant_search,
            'selected_tenant_quota_status': selected_tenant_quota_status,
            'selected_tenant_risk': selected_tenant_risk,
            'selected_workload_search': selected_workload_search,
            'selected_workload_type': selected_workload_type,
            'selected_workload_resource_status': selected_workload_resource_status,
            'selected_workload_qos': selected_workload_qos,
            'selected_workload_risk': selected_workload_risk,
            'allowed_per_page_values': ALLOWED_PER_PAGE_VALUES,
            'allowed_time_ranges': get_allowed_time_ranges(),
            'namespace_options': [],
            'tenant_quota_summary': {
                'summary_cards': [],
                'rows': [],
                'pagination': {},
            },
            'tenant_quota_rows': [],
            'quota_status_options': [],
            'tenant_risk_options': [],
            'workload_mapping_payload': {
                'rows': [],
                'filters': {},
                'pagination': {},
                'workload_type_options': [],
                'resource_status_options': [],
                'qos_options': [],
                'risk_options': [],
            },
            'workload_mapping_rows': [],
            'actionable_recommendations': [],
            'recommendation_cards': [],
            'recommendation_count': 0,
            'governance_findings': [],
            'workload_count_display': '0 workloads',
            'recommendation_count_display': '0 actionable',
            'finding_count_display': '0 findings',
            'workload_posture': {
                'value': 'Pending',
                'description': 'Workload posture is available after integration requirements pass.',
                'tone': 'info',
                'icon': 'clock-3',
            },
            'prometheus_status_tone': 'critical',
            'prometheus_status_icon': 'circle-x',
            'prometheus_response_time_display': 'No response',
        }
    )

    if workload_service is None or cluster is None:
        context.update(
            get_empty_workload_payload(
                selected_namespace=selected_namespace,
                selected_time_range=selected_time_range,
            )
        )

        return context

    requirement_result = workload_service.requirements()
    if not requirement_result.ok:
        missing = list((requirement_result.payload or {}).get('missing_capabilities') or [])
        context['dependency_blocker'] = prometheus_capability_blocker(
            cluster,
            feature_label='Workload Analytics',
            missing_capabilities=missing,
        )
        context.update(
            get_empty_workload_payload(
                selected_namespace=selected_namespace,
                selected_time_range=selected_time_range,
            )
        )
        return context

    try:
        prometheus_status = workload_service.get_prometheus_status()

        context['prometheus_status'] = prometheus_status
        context['prometheus_connected'] = bool(
            prometheus_status.get(
                'connected',
                False,
            )
        )

        if not context['prometheus_connected']:
            context['dependency_blocker'] = prometheus_connection_blocker(
                cluster,
                detail=str(prometheus_status.get('error') or 'Prometheus health check did not complete successfully.'),
            )
            context.update(
                get_empty_workload_payload(
                    selected_namespace=selected_namespace,
                    selected_time_range=selected_time_range,
                )
            )
            return context

        namespace_options = workload_service.get_all_namespace_options()

        if selected_namespace and selected_namespace not in namespace_options:
            selected_namespace = ''

        context['selected_namespace'] = selected_namespace
        context['namespace_options'] = namespace_options

        tenant_quota_summary = workload_service.get_tenant_quota_summary(
            selected_namespace=selected_namespace,
        )

        tenant_quota_all_rows = tenant_quota_summary['rows']

        tenant_quota_filtered_rows = filter_tenant_quota_rows(
            rows=tenant_quota_all_rows,
            selected_search=selected_tenant_search,
            selected_quota_status=selected_tenant_quota_status,
            selected_risk=selected_tenant_risk,
        )

        tenant_quota_page = workload_service.paginate_rows(
            rows=tenant_quota_filtered_rows,
            page=get_positive_int_arg(
                query_args=query_args,
                name='quota_page',
                default=1,
            ),
            per_page=get_per_page_arg(
                query_args=query_args,
                name='quota_per_page',
                default=5,
            ),
        )

        tenant_quota_summary['rows'] = tenant_quota_page['rows']
        tenant_quota_summary['pagination'] = tenant_quota_page['pagination']

        workload_mapping_payload = workload_service.get_workload_mapping_payload(
            selected_namespace=selected_namespace,
            time_range=selected_time_range,
        )

        workload_mapping_all_rows = workload_mapping_payload['rows']

        workload_mapping_filtered_rows = filter_workload_rows(
            rows=workload_mapping_all_rows,
            selected_search=selected_workload_search,
            selected_type=selected_workload_type,
            selected_resource_status=selected_workload_resource_status,
            selected_qos=selected_workload_qos,
            selected_risk=selected_workload_risk,
        )

        workload_mapping_page = workload_service.paginate_rows(
            rows=workload_mapping_filtered_rows,
            page=get_positive_int_arg(
                query_args=query_args,
                name='workload_page',
                default=1,
            ),
            per_page=get_per_page_arg(
                query_args=query_args,
                name='workload_per_page',
                default=5,
            ),
        )

        workload_mapping_payload['rows'] = workload_mapping_page['rows']
        workload_mapping_payload['pagination'] = workload_mapping_page['pagination']
        workload_mapping_payload['workload_type_options'] = sorted(
            {
                row.get(
                    'type',
                    '',
                )
                for row in workload_mapping_all_rows
                if row.get(
                    'type',
                )
            }
        )
        workload_mapping_payload['resource_status_options'] = sorted(
            {
                row.get(
                    'resource_status',
                    {},
                ).get(
                    'label',
                    '',
                )
                for row in workload_mapping_all_rows
                if row.get(
                    'resource_status',
                )
            }
        )
        workload_mapping_payload['qos_options'] = sorted(
            {
                row.get(
                    'qos',
                    {},
                ).get(
                    'label',
                    '',
                )
                for row in workload_mapping_all_rows
                if row.get(
                    'qos',
                )
            }
        )
        workload_mapping_payload['risk_options'] = sorted(
            {
                row.get(
                    'risk',
                    {},
                ).get(
                    'label',
                    '',
                )
                for row in workload_mapping_all_rows
                if row.get(
                    'risk',
                )
            }
        )

        quota_status_options = sorted(
            {
                row.get(
                    'quota_status',
                    {},
                ).get(
                    'label',
                    '',
                )
                for row in tenant_quota_all_rows
                if row.get(
                    'quota_status',
                )
            }
        )

        tenant_risk_options = sorted(
            {
                row.get(
                    'risk',
                    {},
                ).get(
                    'label',
                    '',
                )
                for row in tenant_quota_all_rows
                if row.get(
                    'risk',
                )
            }
        )

        governance_findings = workload_service.get_governance_findings(
            tenant_quota_rows=tenant_quota_all_rows,
            workload_mapping_rows=workload_mapping_all_rows,
        )

        recommendation_payload = {
            'tenant_quota_summary': {
                **tenant_quota_summary,
                'rows': tenant_quota_all_rows,
            },
            'tenant_quota_rows': tenant_quota_all_rows,
            'workload_mapping_payload': {
                **workload_mapping_payload,
                'rows': workload_mapping_all_rows,
            },
            'workload_mapping_rows': workload_mapping_all_rows,
            'governance_findings': governance_findings,
            'selected_namespace': selected_namespace,
            'selected_time_range': selected_time_range,
        }

        actionable_recommendations = build_workload_actionable_recommendations(
            recommendation_payload,
        )

        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Continue workload governance monitoring',
            default_description=(
                'No actionable workload recommendation was generated from the current '
                'quota, request, limit, QoS, and right-sizing signals.'
            ),
            default_source='workload_baseline',
            default_action_type='workload_governance',
        )

        recommendation_count = count_actionable_recommendations(
            actionable_recommendations,
        )

        critical_finding_count = sum(1 for item in governance_findings if item.get('severity') == 'critical')
        warning_finding_count = sum(1 for item in governance_findings if item.get('severity') == 'warning')
        if critical_finding_count:
            workload_posture = {
                'value': 'Critical',
                'description': 'Critical findings need immediate review.',
                'tone': 'critical',
                'icon': 'shield-alert',
            }
        elif warning_finding_count:
            workload_posture = {
                'value': 'Watch',
                'description': 'Review quota, limits, and QoS posture.',
                'tone': 'warning',
                'icon': 'triangle-alert',
            }
        else:
            workload_posture = {
                'value': 'Healthy',
                'description': 'Workload signals are stable.',
                'tone': 'normal',
                'icon': 'circle-check',
            }

        context.update(
            {
                'workload_count_display': f'{len(workload_mapping_all_rows)} workloads',
                'recommendation_count_display': f'{recommendation_count} actionable',
                'finding_count_display': f'{len(governance_findings)} findings',
                'workload_posture': workload_posture,
                'prometheus_status_tone': prometheus_status.get('tone', 'critical'),
                'prometheus_status_icon': prometheus_status.get('icon', 'circle-x'),
                'prometheus_response_time_display': prometheus_status.get('response_time_display', 'No response'),
                'namespace_options': namespace_options,
                'tenant_quota_summary': tenant_quota_summary,
                'tenant_quota_rows': tenant_quota_all_rows,
                'quota_status_options': quota_status_options,
                'tenant_risk_options': tenant_risk_options,
                'workload_mapping_payload': workload_mapping_payload,
                'workload_mapping_rows': workload_mapping_all_rows,
                'governance_findings': governance_findings,
                'actionable_recommendations': actionable_recommendations,
                'recommendation_cards': recommendation_cards,
                'recommendation_count': recommendation_count,
            }
        )

        return context
    except (PrometheusError, Exception) as exc:
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=str(exc),
        )
        context.update(
            get_empty_workload_payload(
                selected_namespace=selected_namespace,
                selected_time_range=selected_time_range,
            )
        )
        return context


def get_workload_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> dict[str, Any]:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.workload',
        parameters={'cluster_id': str(cluster_id), 'time_range': time_range},
    )
    context = result.context or {}
    rows = _as_list(context.get('workload_mapping_rows', []))
    if not result.available:
        return _empty_workload_snapshot()
    missing_cpu_requests = 0
    missing_memory_requests = 0
    missing_cpu_limits = 0
    missing_memory_limits = 0
    over_provisioned = 0
    under_provisioned = 0
    for row in rows:
        item = _as_dict(row)
        if _safe_float(item.get('cpu_request_raw', 0)) <= 0:
            missing_cpu_requests += 1
        if _safe_float(item.get('memory_request_raw', 0)) <= 0:
            missing_memory_requests += 1
        if _safe_float(item.get('cpu_limit_raw', 0)) <= 0:
            missing_cpu_limits += 1
        if _safe_float(item.get('memory_limit_raw', 0)) <= 0:
            missing_memory_limits += 1
        recommendation = str(item.get('recommendation', '')).lower()
        over_provisioned += int('reduce' in recommendation)
        under_provisioned += int('increase' in recommendation)
    return {
        'missing_cpu_requests': missing_cpu_requests,
        'missing_memory_requests': missing_memory_requests,
        'missing_cpu_limits': missing_cpu_limits,
        'missing_memory_limits': missing_memory_limits,
        'over_provisioned': over_provisioned,
        'under_provisioned': under_provisioned,
        'recommendation_count': count_actionable_recommendations(
            context.get('actionable_recommendations')
            if isinstance(context.get('actionable_recommendations'), list)
            else []
        ),
    }

def _empty_workload_snapshot() -> dict[str, Any]:
    return {
        'missing_cpu_requests': 0,
        'missing_memory_requests': 0,
        'missing_cpu_limits': 0,
        'missing_memory_limits': 0,
        'over_provisioned': 0,
        'under_provisioned': 0,
        'recommendation_count': 0,
    }


def present_workload_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply namespace, table filters, and pagination without querying Prometheus again."""
    from copy import deepcopy

    presented = deepcopy(context)
    selected_namespace = get_query_value(query_args=query_args, name='namespace', default='')
    selected_tenant_search = get_query_value(query_args=query_args, name='tenant_search', default='')
    selected_tenant_quota_status = get_query_value(
        query_args=query_args,
        name='tenant_quota_status',
        default='',
    )
    selected_tenant_risk = get_query_value(query_args=query_args, name='tenant_risk', default='')
    selected_workload_search = get_query_value(query_args=query_args, name='workload_search', default='')
    selected_workload_type = get_query_value(query_args=query_args, name='workload_type', default='')
    selected_workload_resource_status = get_query_value(
        query_args=query_args,
        name='workload_resource_status',
        default='',
    )
    selected_workload_qos = get_query_value(query_args=query_args, name='workload_qos', default='')
    selected_workload_risk = get_query_value(query_args=query_args, name='workload_risk', default='')

    namespace_options = list(presented.get('namespace_options') or [])
    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    tenant_all_rows = list(presented.get('tenant_quota_rows') or [])
    workload_all_rows = list(presented.get('workload_mapping_rows') or [])
    if selected_namespace:
        tenant_all_rows = [row for row in tenant_all_rows if str(row.get('namespace') or '') == selected_namespace]
        workload_all_rows = [
            row for row in workload_all_rows if str(row.get('namespace') or '') == selected_namespace
        ]

    tenant_filtered = filter_tenant_quota_rows(
        rows=tenant_all_rows,
        selected_search=selected_tenant_search,
        selected_quota_status=selected_tenant_quota_status,
        selected_risk=selected_tenant_risk,
    )
    workload_filtered = filter_workload_rows(
        rows=workload_all_rows,
        selected_search=selected_workload_search,
        selected_type=selected_workload_type,
        selected_resource_status=selected_workload_resource_status,
        selected_qos=selected_workload_qos,
        selected_risk=selected_workload_risk,
    )

    paginator = AnalyticsBaseService()
    tenant_page = paginator.paginate_rows_with_options(
        rows=tenant_filtered,
        page=get_positive_int_arg(query_args=query_args, name='quota_page', default=1),
        per_page=get_per_page_arg(query_args=query_args, name='quota_per_page', default=5),
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
    )
    workload_page = paginator.paginate_rows_with_options(
        rows=workload_filtered,
        page=get_positive_int_arg(query_args=query_args, name='workload_page', default=1),
        per_page=get_per_page_arg(query_args=query_args, name='workload_per_page', default=5),
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
    )

    tenant_summary = deepcopy(presented.get('tenant_quota_summary') or {})
    tenant_summary['rows'] = tenant_page['rows']
    tenant_summary['pagination'] = tenant_page['pagination']

    mapping_payload = deepcopy(presented.get('workload_mapping_payload') or {})
    mapping_payload['rows'] = workload_page['rows']
    mapping_payload['pagination'] = workload_page['pagination']
    mapping_payload['workload_type_options'] = sorted(
        {str(row.get('type') or '') for row in workload_all_rows if row.get('type')}
    )
    mapping_payload['resource_status_options'] = sorted(
        {
            str((row.get('resource_status') or {}).get('label') or '')
            for row in workload_all_rows
            if row.get('resource_status')
        }
    )
    mapping_payload['qos_options'] = sorted(
        {
            str((row.get('qos') or {}).get('label') or '')
            for row in workload_all_rows
            if row.get('qos')
        }
    )
    mapping_payload['risk_options'] = sorted(
        {
            str((row.get('risk') or {}).get('label') or '')
            for row in workload_all_rows
            if row.get('risk')
        }
    )

    quota_status_options = sorted(
        {
            str((row.get('quota_status') or {}).get('label') or '')
            for row in tenant_all_rows
            if row.get('quota_status')
        }
    )
    tenant_risk_options = sorted(
        {
            str((row.get('risk') or {}).get('label') or '')
            for row in tenant_all_rows
            if row.get('risk')
        }
    )

    governance_findings = [
        finding
        for finding in list(presented.get('governance_findings') or [])
        if not selected_namespace or str(finding.get('namespace') or '') in {'', selected_namespace}
    ]
    recommendation_payload = {
        'tenant_quota_summary': {**tenant_summary, 'rows': tenant_all_rows},
        'tenant_quota_rows': tenant_all_rows,
        'workload_mapping_payload': {**mapping_payload, 'rows': workload_all_rows},
        'workload_mapping_rows': workload_all_rows,
        'governance_findings': governance_findings,
        'selected_namespace': selected_namespace,
        'selected_time_range': presented.get('selected_time_range', '24h'),
    }
    recommendations = build_workload_actionable_recommendations(recommendation_payload)
    recommendation_cards = format_recommendation_cards(
        recommendations,
        default_title='Continue workload governance monitoring',
        default_description=(
            'No actionable workload recommendation was generated from the current '
            'quota, request, limit, QoS, and right-sizing signals.'
        ),
        default_source='workload_baseline',
        default_action_type='workload_governance',
    )
    critical_count = sum(1 for item in governance_findings if item.get('severity') == 'critical')
    warning_count = sum(1 for item in governance_findings if item.get('severity') == 'warning')
    if critical_count:
        workload_posture = {
            'value': 'Critical',
            'description': 'Critical findings need immediate review.',
            'tone': 'critical',
            'icon': 'shield-alert',
        }
    elif warning_count:
        workload_posture = {
            'value': 'Watch',
            'description': 'Review quota, limits, and QoS posture.',
            'tone': 'warning',
            'icon': 'triangle-alert',
        }
    else:
        workload_posture = {
            'value': 'Healthy',
            'description': 'Workload signals are stable.',
            'tone': 'normal',
            'icon': 'circle-check',
        }

    presented.update(
        {
            'selected_namespace': selected_namespace,
            'selected_tenant_search': selected_tenant_search,
            'selected_tenant_quota_status': selected_tenant_quota_status,
            'selected_tenant_risk': selected_tenant_risk,
            'selected_workload_search': selected_workload_search,
            'selected_workload_type': selected_workload_type,
            'selected_workload_resource_status': selected_workload_resource_status,
            'selected_workload_qos': selected_workload_qos,
            'selected_workload_risk': selected_workload_risk,
            'tenant_quota_summary': tenant_summary,
            'tenant_quota_rows': tenant_all_rows,
            'quota_status_options': quota_status_options,
            'tenant_risk_options': tenant_risk_options,
            'workload_mapping_payload': mapping_payload,
            'workload_mapping_rows': workload_all_rows,
            'governance_findings': governance_findings,
            'actionable_recommendations': recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': count_actionable_recommendations(recommendations),
            'workload_count_display': f'{len(workload_all_rows)} workloads',
            'recommendation_count_display': f'{count_actionable_recommendations(recommendations)} actionable',
            'finding_count_display': f'{len(governance_findings)} findings',
            'workload_posture': workload_posture,
        }
    )
    return presented
