# app/analytics/workload/service.py

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.analytics.common.presentation import present_prometheus_status
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
WORKLOAD_CPU_CURRENT_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_CURRENT_QUERY')
WORKLOAD_CPU_LIMITS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY')
WORKLOAD_CPU_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_PEAK_QUERY_TEMPLATE')
WORKLOAD_CPU_REQUESTS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY')
WORKLOAD_MEMORY_CURRENT_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_CURRENT_QUERY')
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
    selected_configuration: str = '',
    selected_qos: str = '',
    selected_risk: str = '',
) -> list[dict[str, Any]]:
    filtered_rows: list[dict[str, Any]] = []

    for row in rows:
        if selected_search:
            haystack = (f'{row.get("workload", "")} {row.get("namespace", "")}').lower()
            if selected_search.lower() not in haystack:
                continue

        if selected_type and row.get('type') != selected_type:
            continue

        if (
            selected_configuration
            and row.get('configuration_status', {}).get('label') != selected_configuration
        ):
            continue

        if selected_qos and row.get('qos', {}).get('label') != selected_qos:
            continue

        if selected_risk and row.get('risk', {}).get('label') != selected_risk:
            continue

        filtered_rows.append(row)

    return filtered_rows


def build_tenant_scope_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_namespaces = len(rows)
    covered_namespaces = sum(
        1 for row in rows if row.get('quota_status', {}).get('label') in {'Complete', 'Partial'}
    )
    near_limit_count = sum(
        1
        for row in rows
        if row.get('quota_pressure_available')
        and _safe_float(row.get('quota_usage_percent', 0)) >= 75
    )
    efficiency_risk_count = sum(
        1
        for row in rows
        if row.get('quota_pressure_available')
        and row.get('runtime_demand_available')
        and _safe_float(row.get('quota_usage_percent', 0)) >= 75
        and _safe_float(row.get('actual_usage_percent', 0)) < 40
    )
    quota_coverage_percent = safe_percent(covered_namespaces, total_namespaces)

    return {
        'scope_total': total_namespaces,
        'scope_covered': covered_namespaces,
        'scope_quota_coverage_percent': safe_round(quota_coverage_percent, 2),
        'scope_near_limit_count': near_limit_count,
        'scope_efficiency_risk_count': efficiency_risk_count,
        'summary_cards': [
            {
                'label': 'Namespaces',
                'value': total_namespaces,
                'caption': 'Top-Level Active Scope',
                'icon': 'network',
            },
            {
                'label': 'Quota Coverage',
                'value': f'{format_decimal(quota_coverage_percent)}%',
                'caption': f'{covered_namespaces} of {total_namespaces} Namespaces',
                'icon': 'shield-check',
            },
            {
                'label': 'Quota Near Limit',
                'value': near_limit_count,
                'caption': '75% or Higher',
                'icon': 'triangle-alert',
            },
            {
                'label': 'Allocation Efficiency Risk',
                'value': efficiency_risk_count,
                'caption': 'High Allocation, Low Runtime Demand',
                'icon': 'activity',
            },
        ],
    }


def build_workload_scope_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_workloads = len(rows)
    request_complete_count = sum(
        1 for row in rows if row.get('request_coverage', {}).get('label') == 'Complete'
    )
    best_effort_count = sum(
        1 for row in rows if row.get('qos', {}).get('label') == 'BestEffort'
    )
    high_risk_count = sum(
        1 for row in rows if row.get('risk', {}).get('label') in {'High', 'Critical'}
    )
    complete_evidence_count = sum(
        1 for row in rows if row.get('metrics_coverage', {}).get('label') == 'Complete'
    )
    return {
        'scope_total': total_workloads,
        'scope_request_complete': request_complete_count,
        'scope_request_coverage_percent': safe_round(
            safe_percent(request_complete_count, total_workloads), 2
        ),
        'scope_best_effort_count': best_effort_count,
        'scope_high_risk_count': high_risk_count,
        'scope_complete_evidence_count': complete_evidence_count,
    }


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
        response = self.consumer.analytics_status()
        payload = response.payload if isinstance(response.payload, dict) else {}
        detail = None
        if not response.ok:
            detail = (
                response.diagnostics[0].detail
                if response.diagnostics and response.diagnostics[0].detail
                else (response.diagnostics[0].message if response.diagnostics else 'Prometheus is unavailable.')
            )
        return present_prometheus_status(
            {
                'configured': bool(payload.get('configured', True)),
                'connected': response.ok,
                'response_time_ms': payload.get('response_time_ms'),
                'last_checked_at': payload.get('last_checked_at'),
                'observation_degraded': bool(payload.get('observation_degraded')),
                'last_error': payload.get('last_error'),
                'error': detail,
            }
        )

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
        namespaces = self.get_prometheus_vector_map(query=NAMESPACE_ACTIVE_QUERY, label='namespace')
        hard = self.get_resource_quota_map(query=TENANT_QUOTA_HARD_QUERY)
        used = self.get_resource_quota_map(query=TENANT_QUOTA_USED_QUERY)
        cpu_actual = self.get_prometheus_vector_map(query=TENANT_CPU_ACTUAL_QUERY, label='namespace')
        memory_actual = self.get_prometheus_vector_map(query=TENANT_MEMORY_ACTUAL_QUERY, label='namespace')
        pod_actual = self.get_prometheus_vector_map(query=TENANT_POD_ACTUAL_QUERY, label='namespace')

        namespace_names = set(namespaces) | set(hard) | set(used)
        rows: list[dict[str, Any]] = []

        for namespace in sorted(namespace_names):
            if selected_namespace and namespace != selected_namespace:
                continue

            hard_values = hard.get(namespace, {})
            used_values = used.get(namespace, {})
            missing_keys = [key for key in REQUIRED_QUOTA_KEYS if key not in hard_values]
            quota_status = self.get_quota_status(hard_values=hard_values, missing_keys=missing_keys)

            quota_signals: list[tuple[float, str]] = []
            for key in REQUIRED_QUOTA_KEYS:
                denominator = _safe_float(hard_values.get(key))
                if denominator <= 0 or key not in used_values:
                    continue
                quota_signals.append(
                    (
                        raw_percent(_safe_float(used_values.get(key)), denominator),
                        self.get_resource_quota_label(key),
                    )
                )
            quota_pressure_available = bool(quota_signals)
            quota_usage_percent, quota_pressure_resource = (
                max(quota_signals, key=lambda item: item[0])
                if quota_signals
                else (0.0, 'Unavailable')
            )

            actual_signals: list[tuple[float, str]] = []
            if namespace in cpu_actual and _safe_float(hard_values.get('limits.cpu')) > 0:
                actual_signals.append(
                    (
                        raw_percent(
                            _safe_float(cpu_actual.get(namespace)),
                            _safe_float(hard_values.get('limits.cpu')),
                        ),
                        'CPU',
                    )
                )
            if namespace in memory_actual and _safe_float(hard_values.get('limits.memory')) > 0:
                actual_signals.append(
                    (
                        raw_percent(
                            _safe_float(memory_actual.get(namespace)),
                            _safe_float(hard_values.get('limits.memory')),
                        ),
                        'Memory',
                    )
                )
            if namespace in pod_actual and _safe_float(hard_values.get('pods')) > 0:
                actual_signals.append(
                    (
                        raw_percent(
                            _safe_float(pod_actual.get(namespace)),
                            _safe_float(hard_values.get('pods')),
                        ),
                        'Pods',
                    )
                )
            runtime_demand_available = bool(actual_signals)
            actual_usage_percent, runtime_demand_resource = (
                max(actual_signals, key=lambda item: item[0])
                if actual_signals
                else (0.0, 'Unavailable')
            )

            quota_usage_percent = safe_round(quota_usage_percent, 2)
            actual_usage_percent = safe_round(actual_usage_percent, 2)
            risk = self.get_tenant_analysis_risk(
                quota_status=quota_status['label'],
                quota_usage_percent=quota_usage_percent,
                actual_usage_percent=actual_usage_percent,
                quota_pressure_available=quota_pressure_available,
                runtime_demand_available=runtime_demand_available,
            )
            recommendation = self.get_tenant_recommendation(
                quota_status=quota_status['label'],
                missing_keys=missing_keys,
                quota_usage_percent=quota_usage_percent,
                actual_usage_percent=actual_usage_percent,
                quota_pressure_available=quota_pressure_available,
                runtime_demand_available=runtime_demand_available,
            )

            cpu_quota_raw = _safe_float(hard_values.get('limits.cpu'))
            cpu_requested_raw = _safe_float(used_values.get('requests.cpu'))
            cpu_limited_raw = _safe_float(used_values.get('limits.cpu'))
            cpu_actual_raw = _safe_float(cpu_actual.get(namespace))
            memory_quota_raw = _safe_float(hard_values.get('limits.memory'))
            memory_requested_raw = _safe_float(used_values.get('requests.memory'))
            memory_limited_raw = _safe_float(used_values.get('limits.memory'))
            memory_actual_raw = _safe_float(memory_actual.get(namespace))
            pod_actual_raw = _safe_float(pod_actual.get(namespace))

            rows.append(
                {
                    'namespace': namespace,
                    'quota_status': quota_status,
                    'quota_pressure_available': quota_pressure_available,
                    'quota_pressure_resource': quota_pressure_resource,
                    'quota_usage_percent': quota_usage_percent,
                    'quota_usage_percent_display': (
                        format_decimal(quota_usage_percent) if quota_pressure_available else 'N/A'
                    ),
                    'runtime_demand_available': runtime_demand_available,
                    'runtime_demand_resource': runtime_demand_resource,
                    'actual_usage_percent': actual_usage_percent,
                    'actual_usage_percent_display': (
                        format_decimal(actual_usage_percent) if runtime_demand_available else 'N/A'
                    ),
                    'risk': risk,
                    'recommendation': recommendation,
                    'missing_keys': missing_keys,
                    'missing_key_labels': [self.get_resource_quota_label(key) for key in missing_keys],
                    'hard': hard_values,
                    'used': used_values,
                    'hard_items': self.build_resource_quota_items(hard_values),
                    'used_items': self.build_resource_quota_items(used_values),
                    'actual': {
                        'cpu': format_cpu_core(cpu_actual_raw) if namespace in cpu_actual else 'N/A',
                        'memory': format_memory_gib(memory_actual_raw) if namespace in memory_actual else 'N/A',
                        'pods': format_count(pod_actual_raw) if namespace in pod_actual else 'N/A',
                    },
                    'cpu_quota': format_cpu_core(cpu_quota_raw),
                    'cpu_requested': format_cpu_core(cpu_requested_raw),
                    'cpu_limited': format_cpu_core(cpu_limited_raw),
                    'cpu_actual': format_cpu_core(cpu_actual_raw) if namespace in cpu_actual else 'N/A',
                    'cpu_actual_available': namespace in cpu_actual,
                    'cpu_requested_percent': safe_round(safe_percent(cpu_requested_raw, cpu_quota_raw), 2),
                    'cpu_limited_percent': safe_round(safe_percent(cpu_limited_raw, cpu_quota_raw), 2),
                    'cpu_actual_percent': safe_round(safe_percent(cpu_actual_raw, cpu_quota_raw), 2),
                    'memory_quota': format_memory_gib(memory_quota_raw),
                    'memory_requested': format_memory_gib(memory_requested_raw),
                    'memory_limited': format_memory_gib(memory_limited_raw),
                    'memory_actual': (
                        format_memory_gib(memory_actual_raw) if namespace in memory_actual else 'N/A'
                    ),
                    'memory_actual_available': namespace in memory_actual,
                    'memory_requested_percent': safe_round(
                        safe_percent(memory_requested_raw, memory_quota_raw), 2
                    ),
                    'memory_limited_percent': safe_round(
                        safe_percent(memory_limited_raw, memory_quota_raw), 2
                    ),
                    'memory_actual_percent': safe_round(
                        safe_percent(memory_actual_raw, memory_quota_raw), 2
                    ),
                    'workloads': format_count(pod_actual_raw) if namespace in pod_actual else 'N/A',
                }
            )

        return {**build_tenant_scope_summary(rows), 'rows': rows}

    def get_request_coverage(
        self,
        cpu_observed: int,
        memory_observed: int,
        pod_count: int,
    ) -> dict[str, Any]:
        complete = min(cpu_observed, memory_observed)
        if pod_count <= 0:
            return {'label': 'Unknown', 'tone': 'unknown', 'observed': 0, 'total': 0}
        if cpu_observed == pod_count and memory_observed == pod_count:
            return {'label': 'Complete', 'tone': 'normal', 'observed': pod_count, 'total': pod_count}
        if cpu_observed == 0 and memory_observed == 0:
            return {'label': 'Missing', 'tone': 'critical', 'observed': 0, 'total': pod_count}
        return {'label': 'Partial', 'tone': 'warning', 'observed': complete, 'total': pod_count}

    def get_limit_coverage(
        self,
        cpu_observed: int,
        memory_observed: int,
        pod_count: int,
    ) -> dict[str, Any]:
        if pod_count <= 0:
            return {'label': 'Unknown', 'tone': 'unknown', 'observed': 0, 'total': 0}
        if cpu_observed == pod_count and memory_observed == pod_count:
            return {'label': 'Complete', 'tone': 'normal', 'observed': pod_count, 'total': pod_count}
        if cpu_observed == 0 and memory_observed == 0:
            return {'label': 'Limits Unset', 'tone': 'warning', 'observed': 0, 'total': pod_count}
        if memory_observed < pod_count and cpu_observed == pod_count:
            return {
                'label': 'Memory Limit Missing',
                'tone': 'warning',
                'observed': memory_observed,
                'total': pod_count,
            }
        if cpu_observed < pod_count and memory_observed == pod_count:
            return {
                'label': 'CPU Limit Unset',
                'tone': 'info',
                'observed': cpu_observed,
                'total': pod_count,
            }
        return {
            'label': 'Partial',
            'tone': 'warning',
            'observed': min(cpu_observed, memory_observed),
            'total': pod_count,
        }

    def get_resource_configuration(
        self,
        request_coverage: dict[str, Any],
        limit_coverage: dict[str, Any],
    ) -> dict[str, str]:
        request_label = request_coverage.get('label', 'Unknown')
        limit_label = limit_coverage.get('label', 'Unknown')
        if request_label == 'Missing':
            return {'label': 'Requests Missing', 'tone': 'critical'}
        if request_label == 'Partial':
            return {'label': 'Requests Partial', 'tone': 'warning'}
        if request_label == 'Unknown':
            return {'label': 'Unknown', 'tone': 'unknown'}
        if limit_label == 'Memory Limit Missing':
            return {'label': 'Memory Limit Missing', 'tone': 'warning'}
        if limit_label == 'Limits Unset':
            return {'label': 'Limits Unset', 'tone': 'warning'}
        if limit_label == 'CPU Limit Unset':
            return {'label': 'CPU Limit Unset', 'tone': 'info'}
        if limit_label == 'Partial':
            return {'label': 'Limits Partial', 'tone': 'warning'}
        return {'label': 'Complete', 'tone': 'normal'}

    def get_workload_qos(
        self,
        qos_distribution: dict[str, int],
    ) -> dict[str, str]:
        if not qos_distribution:
            return {'label': 'Unknown'}
        if len(qos_distribution) > 1:
            return {'label': 'Mixed'}
        return {'label': next(iter(qos_distribution.keys()))}

    def get_metrics_coverage(
        self,
        pod_count: int,
        cpu_current_observed: int,
        memory_current_observed: int,
        cpu_peak_observed: int,
        memory_peak_observed: int,
    ) -> dict[str, Any]:
        complete_observed = min(
            cpu_current_observed,
            memory_current_observed,
            cpu_peak_observed,
            memory_peak_observed,
        )
        maximum_observed = max(
            cpu_current_observed,
            memory_current_observed,
            cpu_peak_observed,
            memory_peak_observed,
        )
        if pod_count <= 0 or maximum_observed == 0:
            return {
                'label': 'Unavailable',
                'tone': 'unknown',
                'observed': 0,
                'total': max(pod_count, 0),
                'description': 'No complete runtime and selected-window observations are available.',
            }
        if complete_observed == pod_count:
            return {
                'label': 'Complete',
                'tone': 'normal',
                'observed': pod_count,
                'total': pod_count,
                'description': f'{pod_count} of {pod_count} Pods',
            }
        return {
            'label': 'Partial',
            'tone': 'warning',
            'observed': complete_observed,
            'total': pod_count,
            'description': f'{complete_observed} of {pod_count} Pods',
        }

    def get_workload_recommendation(
        self,
        cpu_current_percent: float,
        cpu_peak_percent: float,
        memory_current_percent: float,
        memory_peak_percent: float,
        request_coverage: str,
        limit_coverage: str,
        metrics_coverage: str,
    ) -> str:
        if request_coverage == 'Missing':
            return 'Set CPU and memory requests'
        if request_coverage == 'Partial':
            return 'Complete CPU and memory requests'
        if limit_coverage == 'Memory Limit Missing':
            return 'Set memory limits according to workload policy'
        if limit_coverage == 'Limits Unset':
            return 'Review memory limit policy and confirm CPU limit intent'
        if limit_coverage == 'CPU Limit Unset':
            return 'Confirm the intentional CPU limit policy'
        if metrics_coverage != 'Complete':
            return 'Defer right-sizing until metrics coverage is complete'

        cpu_pressure = max(cpu_current_percent, cpu_peak_percent)
        memory_pressure = max(memory_current_percent, memory_peak_percent)
        if memory_pressure >= 90:
            return 'Increase memory request after validating selected-window demand'
        if cpu_pressure >= 90:
            return 'Increase CPU request after validating selected-window demand'
        if cpu_current_percent < 30 and cpu_peak_percent < 30 and memory_current_percent < 30 and memory_peak_percent < 30:
            return 'Reduce CPU and memory requests after owner validation'
        if cpu_current_percent < 30 and cpu_peak_percent < 30:
            return 'Reduce CPU request after owner validation'
        if memory_current_percent < 30 and memory_peak_percent < 30:
            return 'Reduce memory request after owner validation'
        return 'No right-sizing action needed'

    def get_workload_risk(
        self,
        request_coverage: str,
        limit_coverage: str,
        metrics_coverage: str,
        recommendation: str,
    ) -> dict[str, str]:
        recommendation_lower = recommendation.lower()
        if request_coverage == 'Missing' or 'increase' in recommendation_lower:
            return {'label': 'High', 'tone': 'critical'}
        if request_coverage == 'Partial':
            return {'label': 'High', 'tone': 'critical'}
        if limit_coverage in {'Memory Limit Missing', 'Limits Unset', 'Partial'}:
            return {'label': 'Medium', 'tone': 'warning'}
        if metrics_coverage == 'Unavailable':
            return {'label': 'Unknown', 'tone': 'unknown'}
        if metrics_coverage == 'Partial' or 'reduce' in recommendation_lower:
            return {'label': 'Medium', 'tone': 'warning'}
        return {'label': 'Low', 'tone': 'normal'}

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
            return {'label': 'Missing', 'tone': 'warning'}
        if missing_keys:
            return {'label': 'Partial', 'tone': 'warning'}
        return {'label': 'Complete', 'tone': 'normal'}

    def get_highest_quota_percent(
        self,
        hard_values: dict[str, float],
        used_values: dict[str, float],
    ) -> float:
        values = [
            raw_percent(_safe_float(used_values.get(key)), _safe_float(hard_values.get(key)))
            for key in REQUIRED_QUOTA_KEYS
            if key in used_values and _safe_float(hard_values.get(key)) > 0
        ]
        return max(values, default=0)

    def get_highest_actual_percent(
        self,
        hard_values: dict[str, float],
        cpu_actual: float,
        memory_actual: float,
        pod_actual: float,
    ) -> float:
        values = []
        if _safe_float(hard_values.get('limits.cpu')) > 0:
            values.append(raw_percent(cpu_actual, _safe_float(hard_values.get('limits.cpu'))))
        if _safe_float(hard_values.get('limits.memory')) > 0:
            values.append(raw_percent(memory_actual, _safe_float(hard_values.get('limits.memory'))))
        if _safe_float(hard_values.get('pods')) > 0:
            values.append(raw_percent(pod_actual, _safe_float(hard_values.get('pods'))))
        return max(values, default=0)

    def get_tenant_analysis_risk(
        self,
        quota_status: str,
        quota_usage_percent: float,
        actual_usage_percent: float,
        quota_pressure_available: bool = True,
        runtime_demand_available: bool = True,
    ) -> dict[str, str]:
        if quota_status == 'Missing':
            return {'label': 'Critical', 'tone': 'critical'}
        if quota_pressure_available and quota_usage_percent >= 90:
            return {'label': 'Critical', 'tone': 'critical'}
        if (
            quota_pressure_available
            and runtime_demand_available
            and quota_usage_percent >= 75
            and actual_usage_percent < 40
        ):
            return {'label': 'Medium', 'tone': 'warning'}
        if quota_pressure_available and quota_usage_percent >= 75:
            return {'label': 'High', 'tone': 'critical'}
        if quota_status == 'Partial':
            return {'label': 'Medium', 'tone': 'warning'}
        if not quota_pressure_available or not runtime_demand_available:
            return {'label': 'Unknown', 'tone': 'unknown'}
        return {'label': 'Low', 'tone': 'normal'}

    def get_tenant_recommendation(
        self,
        quota_status: str,
        missing_keys: list[str],
        quota_usage_percent: float,
        actual_usage_percent: float,
        quota_pressure_available: bool = True,
        runtime_demand_available: bool = True,
    ) -> str:
        if quota_status == 'Missing':
            return 'Create ResourceQuota'
        if missing_keys:
            return 'Add missing quota keys'
        if not quota_pressure_available:
            return 'Restore quota usage evidence before changing boundaries'
        if quota_usage_percent >= 90:
            if runtime_demand_available and actual_usage_percent < 50:
                return 'Right-size workload requests before increasing quota'
            return 'Review allocation or increase quota'
        if quota_usage_percent >= 75 and runtime_demand_available and actual_usage_percent < 40:
            return 'Right-size requests and limits'
        if quota_usage_percent >= 75:
            return 'Monitor quota and review allocation'
        if not runtime_demand_available:
            return 'Restore runtime demand evidence'
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
            query=WORKLOAD_CPU_REQUESTS_QUERY, label='pod', secondary_label='namespace'
        )
        cpu_limits = self.get_prometheus_vector_map(
            query=WORKLOAD_CPU_LIMITS_QUERY, label='pod', secondary_label='namespace'
        )
        cpu_current = self.get_prometheus_vector_map(
            query=WORKLOAD_CPU_CURRENT_QUERY, label='pod', secondary_label='namespace'
        )
        cpu_peak = self.get_prometheus_vector_map(
            query=self.build_range_query(WORKLOAD_CPU_PEAK_QUERY_TEMPLATE, time_range),
            label='pod', secondary_label='namespace'
        )
        memory_requests = self.get_prometheus_vector_map(
            query=WORKLOAD_MEMORY_REQUESTS_QUERY, label='pod', secondary_label='namespace'
        )
        memory_limits = self.get_prometheus_vector_map(
            query=WORKLOAD_MEMORY_LIMITS_QUERY, label='pod', secondary_label='namespace'
        )
        memory_current = self.get_prometheus_vector_map(
            query=WORKLOAD_MEMORY_CURRENT_QUERY, label='pod', secondary_label='namespace'
        )
        memory_peak = self.get_prometheus_vector_map(
            query=self.build_range_query(WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE, time_range),
            label='pod', secondary_label='namespace'
        )
        owner_map = self.get_pod_owner_map()
        qos_map = self.get_pod_qos_map()

        keys = (
            set(cpu_requests)
            | set(cpu_limits)
            | set(cpu_current)
            | set(cpu_peak)
            | set(memory_requests)
            | set(memory_limits)
            | set(memory_current)
            | set(memory_peak)
            | set(owner_map)
            | set(qos_map)
        )
        workload_map: dict[str, dict[str, Any]] = {}

        for key in sorted(keys):
            namespace, pod = self.split_composite_key(key)
            if selected_namespace and namespace != selected_namespace:
                continue
            owner = owner_map.get(key, self.infer_workload_owner(pod))
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
                    'cpu_current_raw': 0.0,
                    'cpu_peak_sum_raw': 0.0,
                    'memory_request_raw': 0.0,
                    'memory_limit_raw': 0.0,
                    'memory_current_raw': 0.0,
                    'memory_peak_sum_raw': 0.0,
                    'cpu_request_pods': 0,
                    'cpu_limit_pods': 0,
                    'cpu_current_pods': 0,
                    'cpu_peak_pods': 0,
                    'memory_request_pods': 0,
                    'memory_limit_pods': 0,
                    'memory_current_pods': 0,
                    'memory_peak_pods': 0,
                    'qos_distribution': {},
                }

            item = workload_map[workload_key]
            item['replicas'] += 1
            item['pods'].append(pod)
            for map_name, field_name, count_name in (
                (cpu_requests, 'cpu_request_raw', 'cpu_request_pods'),
                (cpu_limits, 'cpu_limit_raw', 'cpu_limit_pods'),
                (cpu_current, 'cpu_current_raw', 'cpu_current_pods'),
                (cpu_peak, 'cpu_peak_sum_raw', 'cpu_peak_pods'),
                (memory_requests, 'memory_request_raw', 'memory_request_pods'),
                (memory_limits, 'memory_limit_raw', 'memory_limit_pods'),
                (memory_current, 'memory_current_raw', 'memory_current_pods'),
                (memory_peak, 'memory_peak_sum_raw', 'memory_peak_pods'),
            ):
                if key in map_name:
                    item[field_name] += _safe_float(map_name.get(key))
                    item[count_name] += 1

            qos = qos_map.get(key, 'Unknown')
            item['qos_distribution'][qos] = item['qos_distribution'].get(qos, 0) + 1

        rows: list[dict[str, Any]] = []
        for item in workload_map.values():
            pod_count = item['replicas']
            request_coverage = self.get_request_coverage(
                item['cpu_request_pods'], item['memory_request_pods'], pod_count
            )
            limit_coverage = self.get_limit_coverage(
                item['cpu_limit_pods'], item['memory_limit_pods'], pod_count
            )
            configuration_status = self.get_resource_configuration(
                request_coverage, limit_coverage
            )
            metrics_coverage = self.get_metrics_coverage(
                pod_count,
                item['cpu_current_pods'],
                item['memory_current_pods'],
                item['cpu_peak_pods'],
                item['memory_peak_pods'],
            )
            qos = self.get_workload_qos(item['qos_distribution'])
            complete_metrics = metrics_coverage['label'] == 'Complete'
            cpu_current_available = (
                item['cpu_current_pods'] == pod_count and item['cpu_request_raw'] > 0
            )
            cpu_peak_available = (
                item['cpu_peak_pods'] == pod_count and item['cpu_request_raw'] > 0
            )
            memory_current_available = (
                item['memory_current_pods'] == pod_count and item['memory_request_raw'] > 0
            )
            memory_peak_available = (
                item['memory_peak_pods'] == pod_count and item['memory_request_raw'] > 0
            )

            cpu_current_percent = (
                safe_round(safe_percent(item['cpu_current_raw'], item['cpu_request_raw']), 2)
                if cpu_current_available
                else 0.0
            )
            cpu_peak_percent = (
                safe_round(safe_percent(item['cpu_peak_sum_raw'], item['cpu_request_raw']), 2)
                if cpu_peak_available
                else 0.0
            )
            memory_current_percent = (
                safe_round(safe_percent(item['memory_current_raw'], item['memory_request_raw']), 2)
                if memory_current_available
                else 0.0
            )
            memory_peak_percent = (
                safe_round(safe_percent(item['memory_peak_sum_raw'], item['memory_request_raw']), 2)
                if memory_peak_available
                else 0.0
            )

            recommendation = self.get_workload_recommendation(
                cpu_current_percent=cpu_current_percent,
                cpu_peak_percent=cpu_peak_percent,
                memory_current_percent=memory_current_percent,
                memory_peak_percent=memory_peak_percent,
                request_coverage=request_coverage['label'],
                limit_coverage=limit_coverage['label'],
                metrics_coverage=metrics_coverage['label'],
            )
            risk = self.get_workload_risk(
                request_coverage=request_coverage['label'],
                limit_coverage=limit_coverage['label'],
                metrics_coverage=metrics_coverage['label'],
                recommendation=recommendation,
            )

            rows.append(
                {
                    'workload': item['workload'],
                    'type': item['type'],
                    'namespace': item['namespace'],
                    'replicas': pod_count,
                    'request_coverage': request_coverage,
                    'limit_coverage': limit_coverage,
                    'configuration_status': configuration_status,
                    'metrics_coverage': metrics_coverage,
                    'qos': qos,
                    'risk': risk,
                    'recommendation': recommendation,
                    'cpu_request_raw': item['cpu_request_raw'],
                    'cpu_limit_raw': item['cpu_limit_raw'],
                    'cpu_current_raw': item['cpu_current_raw'],
                    'cpu_peak_sum_raw': item['cpu_peak_sum_raw'],
                    'memory_request_raw': item['memory_request_raw'],
                    'memory_limit_raw': item['memory_limit_raw'],
                    'memory_current_raw': item['memory_current_raw'],
                    'memory_peak_sum_raw': item['memory_peak_sum_raw'],
                    'cpu_request': (
                        format_cpu_core(item['cpu_request_raw'])
                        if item['cpu_request_pods']
                        else 'Unset'
                    ),
                    'cpu_limit': (
                        format_cpu_core(item['cpu_limit_raw'])
                        if item['cpu_limit_pods']
                        else 'Unset'
                    ),
                    'cpu_current': (
                        format_cpu_core(item['cpu_current_raw'])
                        if item['cpu_current_pods']
                        else 'N/A'
                    ),
                    'cpu_peak_sum': (
                        format_cpu_core(item['cpu_peak_sum_raw'])
                        if item['cpu_peak_pods']
                        else 'N/A'
                    ),
                    'memory_request': (
                        format_memory_gib(item['memory_request_raw'])
                        if item['memory_request_pods']
                        else 'Unset'
                    ),
                    'memory_limit': (
                        format_memory_gib(item['memory_limit_raw'])
                        if item['memory_limit_pods']
                        else 'Unset'
                    ),
                    'memory_current': (
                        format_memory_gib(item['memory_current_raw'])
                        if item['memory_current_pods']
                        else 'N/A'
                    ),
                    'memory_peak_sum': (
                        format_memory_gib(item['memory_peak_sum_raw'])
                        if item['memory_peak_pods']
                        else 'N/A'
                    ),
                    'cpu_request_utilization_available': cpu_current_available,
                    'cpu_peak_request_utilization_available': cpu_peak_available,
                    'memory_request_utilization_available': memory_current_available,
                    'memory_peak_request_utilization_available': memory_peak_available,
                    'cpu_request_utilization': cpu_current_percent,
                    'cpu_request_utilization_display': (
                        format_decimal(cpu_current_percent) if cpu_current_available else 'N/A'
                    ),
                    'cpu_peak_request_utilization': cpu_peak_percent,
                    'cpu_peak_request_utilization_display': (
                        format_decimal(cpu_peak_percent) if cpu_peak_available else 'N/A'
                    ),
                    'memory_request_utilization': memory_current_percent,
                    'memory_request_utilization_display': (
                        format_decimal(memory_current_percent)
                        if memory_current_available
                        else 'N/A'
                    ),
                    'memory_peak_request_utilization': memory_peak_percent,
                    'memory_peak_request_utilization_display': (
                        format_decimal(memory_peak_percent)
                        if memory_peak_available
                        else 'N/A'
                    ),
                    'detail': {
                        'pods': item['pods'],
                        'qos_distribution': item['qos_distribution'],
                    },
                }
            )

        rows.sort(
            key=lambda row: (
                self.get_risk_sort_weight(row['risk']['label']),
                row['namespace'],
                row['workload'],
            )
        )
        return {
            'rows': rows,
            'scope_summary': build_workload_scope_summary(rows),
            'filters': {
                'configuration': sorted(
                    {row['configuration_status']['label'] for row in rows}
                ),
                'qos': sorted({row['qos']['label'] for row in rows}),
                'risk': sorted({row['risk']['label'] for row in rows}),
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
        no_quota_count = sum(
            1 for row in tenant_quota_rows if row.get('quota_status', {}).get('label') == 'Missing'
        )
        missing_request_count = sum(
            1 for row in workload_mapping_rows if row.get('request_coverage', {}).get('label') in {'Missing', 'Partial'}
        )
        memory_limit_count = sum(
            1 for row in workload_mapping_rows if row.get('limit_coverage', {}).get('label') in {'Memory Limit Missing', 'Limits Unset', 'Partial'}
        )
        best_effort_count = sum(
            1 for row in workload_mapping_rows if row.get('qos', {}).get('label') == 'BestEffort'
        )
        incomplete_metrics_count = sum(
            1 for row in workload_mapping_rows if row.get('metrics_coverage', {}).get('label') != 'Complete'
        )
        over_requested_count = sum(
            1 for row in workload_mapping_rows if 'reduce' in str(row.get('recommendation', '')).lower()
        )

        findings: list[dict[str, Any]] = []
        if no_quota_count:
            findings.append({'label': f'{no_quota_count} Namespaces Without ResourceQuota', 'severity': 'warning', 'icon': 'triangle-alert', 'filter': 'missing-quota'})
        if missing_request_count:
            findings.append({'label': f'{missing_request_count} Workloads With Incomplete Requests', 'severity': 'critical', 'icon': 'shield-alert', 'filter': 'missing-request'})
        if memory_limit_count:
            findings.append({'label': f'{memory_limit_count} Workloads Need Memory Limit Review', 'severity': 'warning', 'icon': 'triangle-alert', 'filter': 'missing-limit'})
        if best_effort_count:
            findings.append({'label': f'{best_effort_count} BestEffort Workloads', 'severity': 'warning', 'icon': 'info', 'filter': 'best-effort'})
        if incomplete_metrics_count:
            findings.append({'label': f'{incomplete_metrics_count} Workloads Have Incomplete Metrics Coverage', 'severity': 'warning', 'icon': 'database-zap', 'filter': 'metrics-coverage'})
        if over_requested_count:
            findings.append({'label': f'{over_requested_count} Workloads Need Right-Sizing Review', 'severity': 'warning', 'icon': 'scale', 'filter': 'right-sizing'})
        if not findings:
            findings.append({'label': 'No Critical Governance Findings Detected', 'severity': 'healthy', 'icon': 'check-circle', 'filter': ''})
        return findings


def get_workload_analysis_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
        check_prometheus_connection=False,
    )
    workload_service = WorkloadAnalysisService(utilization_service) if utilization_service else None

    selected_namespace = get_query_value(query_args=query_args, name='namespace', default='')
    selected_time_range = get_selected_time_range(query_args=query_args)
    selected_tenant_search = get_query_value(query_args=query_args, name='tenant_search', default='')
    selected_tenant_quota_status = get_query_value(query_args=query_args, name='tenant_quota_status', default='')
    selected_tenant_risk = get_query_value(query_args=query_args, name='tenant_risk', default='')
    selected_workload_search = get_query_value(query_args=query_args, name='workload_search', default='')
    selected_workload_type = get_query_value(query_args=query_args, name='workload_type', default='')
    selected_workload_configuration = get_query_value(query_args=query_args, name='workload_configuration', default='')
    selected_workload_qos = get_query_value(query_args=query_args, name='workload_qos', default='')
    selected_workload_risk = get_query_value(query_args=query_args, name='workload_risk', default='')
    initial_tab = get_query_value(query_args=query_args, name='tab', default='quotas')
    if initial_tab not in {'quotas', 'mapping', 'recommendations'}:
        initial_tab = 'quotas'

    context.update(
        {
            'selected_namespace': selected_namespace,
            'selected_time_range': selected_time_range,
            'selected_tenant_search': selected_tenant_search,
            'selected_tenant_quota_status': selected_tenant_quota_status,
            'selected_tenant_risk': selected_tenant_risk,
            'selected_workload_search': selected_workload_search,
            'selected_workload_type': selected_workload_type,
            'selected_workload_configuration': selected_workload_configuration,
            'selected_workload_qos': selected_workload_qos,
            'selected_workload_risk': selected_workload_risk,
            'initial_tab': initial_tab,
            'allowed_per_page_values': ALLOWED_PER_PAGE_VALUES,
            'allowed_time_ranges': get_allowed_time_ranges(),
            'namespace_options': [],
            'tenant_quota_summary': {**build_tenant_scope_summary([]), 'rows': [], 'pagination': {}},
            'tenant_quota_rows': [],
            'quota_status_options': [],
            'tenant_risk_options': [],
            'workload_mapping_payload': {
                'rows': [],
                'filters': {},
                'pagination': {},
                'scope_summary': build_workload_scope_summary([]),
                'workload_type_options': [],
                'configuration_options': [],
                'qos_options': [],
                'risk_options': [],
            },
            'workload_mapping_rows': [],
            'workload_scope_summary': build_workload_scope_summary([]),
            'actionable_recommendations': [],
            'recommendation_cards': [],
            'recommendation_count': 0,
            'governance_findings': [],
            'workload_count_display': '0 Workloads',
            'recommendation_count_display': '0 Actionable',
            'finding_count_display': '0 Findings',
            'workload_posture': {
                'value': 'Pending',
                'description': 'Workload posture is available after integration requirements pass.',
                'tone': 'info',
                'icon': 'clock-3',
            },
            'prometheus_status_tone': 'critical',
            'prometheus_status_icon': 'circle-x',
            'prometheus_response_time_display': 'No Response',
        }
    )

    if workload_service is None or cluster is None:
        context.update(get_empty_workload_payload(selected_namespace, selected_time_range))
        return context

    requirement_result = workload_service.requirements()
    if not requirement_result.ok:
        missing = list((requirement_result.payload or {}).get('missing_capabilities') or [])
        context['dependency_blocker'] = prometheus_capability_blocker(
            cluster, feature_label='Workload Analytics', missing_capabilities=missing
        )
        context.update(get_empty_workload_payload(selected_namespace, selected_time_range))
        return context

    try:
        prometheus_status = workload_service.get_prometheus_status()
        context['prometheus_status'] = prometheus_status
        context['prometheus_connected'] = bool(prometheus_status.get('connected', False))
        if not context['prometheus_connected']:
            context['dependency_blocker'] = prometheus_connection_blocker(
                cluster,
                detail=str(prometheus_status.get('error') or 'Prometheus health check did not complete successfully.'),
            )
            context.update(get_empty_workload_payload(selected_namespace, selected_time_range))
            return context

        namespace_options = workload_service.get_all_namespace_options()
        if selected_namespace and selected_namespace not in namespace_options:
            selected_namespace = ''
        context['selected_namespace'] = selected_namespace

        tenant_quota_summary = workload_service.get_tenant_quota_summary(selected_namespace)
        tenant_all_rows = list(tenant_quota_summary['rows'])
        tenant_filtered = filter_tenant_quota_rows(
            tenant_all_rows,
            selected_tenant_search,
            selected_tenant_quota_status,
            selected_tenant_risk,
        )
        tenant_page = workload_service.paginate_rows(
            tenant_filtered,
            get_positive_int_arg(query_args=query_args, name='quota_page', default=1),
            get_per_page_arg(query_args=query_args, name='quota_per_page', default=5),
        )
        tenant_quota_summary['rows'] = tenant_page['rows']
        tenant_quota_summary['pagination'] = tenant_page['pagination']

        mapping_payload = workload_service.get_workload_mapping_payload(
            selected_namespace, selected_time_range
        )
        workload_all_rows = list(mapping_payload['rows'])
        workload_filtered = filter_workload_rows(
            workload_all_rows,
            selected_workload_search,
            selected_workload_type,
            selected_workload_configuration,
            selected_workload_qos,
            selected_workload_risk,
        )
        workload_page = workload_service.paginate_rows(
            workload_filtered,
            get_positive_int_arg(query_args=query_args, name='workload_page', default=1),
            get_per_page_arg(query_args=query_args, name='workload_per_page', default=5),
        )
        mapping_payload.update(
            {
                'rows': workload_page['rows'],
                'pagination': workload_page['pagination'],
                'scope_summary': build_workload_scope_summary(workload_all_rows),
                'workload_type_options': sorted({str(row.get('type') or '') for row in workload_all_rows if row.get('type')}),
                'configuration_options': sorted({str((row.get('configuration_status') or {}).get('label') or '') for row in workload_all_rows}),
                'qos_options': sorted({str((row.get('qos') or {}).get('label') or '') for row in workload_all_rows}),
                'risk_options': sorted({str((row.get('risk') or {}).get('label') or '') for row in workload_all_rows}),
            }
        )
        quota_status_options = sorted({str((row.get('quota_status') or {}).get('label') or '') for row in tenant_all_rows})
        tenant_risk_options = sorted({str((row.get('risk') or {}).get('label') or '') for row in tenant_all_rows})
        governance_findings = workload_service.get_governance_findings(tenant_all_rows, workload_all_rows)
        recommendation_payload = {
            'tenant_quota_summary': {**tenant_quota_summary, 'rows': tenant_all_rows},
            'tenant_quota_rows': tenant_all_rows,
            'workload_mapping_payload': {**mapping_payload, 'rows': workload_all_rows},
            'workload_mapping_rows': workload_all_rows,
            'governance_findings': governance_findings,
            'selected_namespace': selected_namespace,
            'selected_time_range': selected_time_range,
        }
        actionable_recommendations = build_workload_actionable_recommendations(recommendation_payload)
        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Continue Workload Governance Monitoring',
            default_description='No actionable workload recommendation was generated from the current quota, request, limit, QoS, and right-sizing signals.',
            default_source='workload_baseline',
            default_action_type='workload_governance',
        )
        recommendation_count = count_actionable_recommendations(actionable_recommendations)
        critical_count = sum(1 for item in governance_findings if item.get('severity') == 'critical')
        warning_count = sum(1 for item in governance_findings if item.get('severity') == 'warning')
        workload_posture = (
            {'value': 'Critical', 'description': 'Critical findings need immediate review.', 'tone': 'critical', 'icon': 'shield-alert'}
            if critical_count
            else {'value': 'Watch', 'description': 'Review quota, request, limit, metrics coverage, and QoS posture.', 'tone': 'warning', 'icon': 'triangle-alert'}
            if warning_count
            else {'value': 'Healthy', 'description': 'Workload signals are stable.', 'tone': 'normal', 'icon': 'circle-check'}
        )
        context.update(
            {
                'workload_count_display': f'{len(workload_all_rows)} Workloads',
                'recommendation_count_display': f'{recommendation_count} Actionable',
                'finding_count_display': f'{len(governance_findings)} Findings',
                'workload_posture': workload_posture,
                'prometheus_status_tone': prometheus_status.get('tone', 'critical'),
                'prometheus_status_icon': prometheus_status.get('icon', 'circle-x'),
                'prometheus_response_time_display': prometheus_status.get('response_time_display', 'No Response'),
                'namespace_options': namespace_options,
                'tenant_quota_summary': tenant_quota_summary,
                'tenant_quota_rows': tenant_all_rows,
                'quota_status_options': quota_status_options,
                'tenant_risk_options': tenant_risk_options,
                'workload_mapping_payload': mapping_payload,
                'workload_mapping_rows': workload_all_rows,
                'workload_scope_summary': build_workload_scope_summary(workload_all_rows),
                'governance_findings': governance_findings,
                'actionable_recommendations': actionable_recommendations,
                'recommendation_cards': recommendation_cards,
                'recommendation_count': recommendation_count,
            }
        )
        return context
    except Exception as exc:
        context['dependency_blocker'] = prometheus_connection_blocker(cluster, detail=str(exc))
        context.update(get_empty_workload_payload(selected_namespace, selected_time_range))
        return context


def get_workload_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> dict[str, Any] | None:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.workload',
        parameters={'cluster_id': str(cluster_id), 'time_range': time_range},
    )
    context = result.context or {}
    rows = _as_list(context.get('workload_mapping_rows', []))
    if not result.available:
        return None

    missing_cpu_requests = 0
    missing_memory_requests = 0
    cpu_limits_unset = 0
    memory_limits_missing = 0
    over_provisioned = 0
    under_provisioned = 0

    for row in rows:
        item = _as_dict(row)
        if _safe_float(item.get('cpu_request_raw', 0)) <= 0:
            missing_cpu_requests += 1
        if _safe_float(item.get('memory_request_raw', 0)) <= 0:
            missing_memory_requests += 1
        if _safe_float(item.get('cpu_limit_raw', 0)) <= 0:
            cpu_limits_unset += 1
        if _safe_float(item.get('memory_limit_raw', 0)) <= 0:
            memory_limits_missing += 1

        recommendation = str(item.get('recommendation', '')).lower()
        over_provisioned += int('reduce' in recommendation)
        under_provisioned += int('increase' in recommendation)

    return {
        'missing_cpu_requests': missing_cpu_requests,
        'missing_memory_requests': missing_memory_requests,
        'cpu_limits_unset': cpu_limits_unset,
        'memory_limits_missing': memory_limits_missing,
        'over_provisioned': over_provisioned,
        'under_provisioned': under_provisioned,
        'recommendation_count': count_actionable_recommendations(
            context.get('actionable_recommendations')
            if isinstance(context.get('actionable_recommendations'), list)
            else []
        ),
    }


def present_workload_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply top-level scope, local record filters, and pagination to committed data."""
    from copy import deepcopy

    presented = deepcopy(context)
    selected_namespace = get_query_value(query_args=query_args, name='namespace', default='')
    selected_tenant_search = get_query_value(query_args=query_args, name='tenant_search', default='')
    selected_tenant_quota_status = get_query_value(query_args=query_args, name='tenant_quota_status', default='')
    selected_tenant_risk = get_query_value(query_args=query_args, name='tenant_risk', default='')
    selected_workload_search = get_query_value(query_args=query_args, name='workload_search', default='')
    selected_workload_type = get_query_value(query_args=query_args, name='workload_type', default='')
    selected_workload_configuration = get_query_value(query_args=query_args, name='workload_configuration', default='')
    selected_workload_qos = get_query_value(query_args=query_args, name='workload_qos', default='')
    selected_workload_risk = get_query_value(query_args=query_args, name='workload_risk', default='')
    initial_tab = get_query_value(query_args=query_args, name='tab', default='quotas')
    if initial_tab not in {'quotas', 'mapping', 'recommendations'}:
        initial_tab = 'quotas'

    namespace_options = list(presented.get('namespace_options') or [])
    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    tenant_scope_rows = list(presented.get('tenant_quota_rows') or [])
    workload_scope_rows = list(presented.get('workload_mapping_rows') or [])
    if selected_namespace:
        tenant_scope_rows = [row for row in tenant_scope_rows if str(row.get('namespace') or '') == selected_namespace]
        workload_scope_rows = [row for row in workload_scope_rows if str(row.get('namespace') or '') == selected_namespace]

    tenant_filtered = filter_tenant_quota_rows(
        tenant_scope_rows, selected_tenant_search, selected_tenant_quota_status, selected_tenant_risk
    )
    workload_filtered = filter_workload_rows(
        workload_scope_rows,
        selected_workload_search,
        selected_workload_type,
        selected_workload_configuration,
        selected_workload_qos,
        selected_workload_risk,
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

    tenant_summary = build_tenant_scope_summary(tenant_scope_rows)
    tenant_summary.update({'rows': tenant_page['rows'], 'pagination': tenant_page['pagination']})
    workload_scope_summary = build_workload_scope_summary(workload_scope_rows)
    mapping_payload = deepcopy(presented.get('workload_mapping_payload') or {})
    mapping_payload.update(
        {
            'rows': workload_page['rows'],
            'pagination': workload_page['pagination'],
            'scope_summary': workload_scope_summary,
            'workload_type_options': sorted({str(row.get('type') or '') for row in workload_scope_rows if row.get('type')}),
            'configuration_options': sorted({str((row.get('configuration_status') or {}).get('label') or '') for row in workload_scope_rows}),
            'qos_options': sorted({str((row.get('qos') or {}).get('label') or '') for row in workload_scope_rows}),
            'risk_options': sorted({str((row.get('risk') or {}).get('label') or '') for row in workload_scope_rows}),
        }
    )
    quota_status_options = sorted({str((row.get('quota_status') or {}).get('label') or '') for row in tenant_scope_rows})
    tenant_risk_options = sorted({str((row.get('risk') or {}).get('label') or '') for row in tenant_scope_rows})
    governance_findings = [
        finding
        for finding in list(presented.get('governance_findings') or [])
        if not selected_namespace or str(finding.get('namespace') or '') in {'', selected_namespace}
    ]
    recommendation_payload = {
        'tenant_quota_summary': {**tenant_summary, 'rows': tenant_scope_rows},
        'tenant_quota_rows': tenant_scope_rows,
        'workload_mapping_payload': {**mapping_payload, 'rows': workload_scope_rows},
        'workload_mapping_rows': workload_scope_rows,
        'governance_findings': governance_findings,
        'selected_namespace': selected_namespace,
        'selected_time_range': presented.get('selected_time_range', '24h'),
    }
    recommendations = build_workload_actionable_recommendations(recommendation_payload)
    recommendation_cards = format_recommendation_cards(
        recommendations,
        default_title='Continue Workload Governance Monitoring',
        default_description='No actionable workload recommendation was generated from the current quota, request, limit, QoS, and right-sizing signals.',
        default_source='workload_baseline',
        default_action_type='workload_governance',
    )
    critical_count = sum(1 for item in governance_findings if item.get('severity') == 'critical')
    warning_count = sum(1 for item in governance_findings if item.get('severity') == 'warning')
    workload_posture = (
        {'value': 'Critical', 'description': 'Critical findings need immediate review.', 'tone': 'critical', 'icon': 'shield-alert'}
        if critical_count
        else {'value': 'Watch', 'description': 'Review quota, request, limit, metrics coverage, and QoS posture.', 'tone': 'warning', 'icon': 'triangle-alert'}
        if warning_count
        else {'value': 'Healthy', 'description': 'Workload signals are stable.', 'tone': 'normal', 'icon': 'circle-check'}
    )
    recommendation_count = count_actionable_recommendations(recommendations)
    presented.update(
        {
            'selected_namespace': selected_namespace,
            'selected_tenant_search': selected_tenant_search,
            'selected_tenant_quota_status': selected_tenant_quota_status,
            'selected_tenant_risk': selected_tenant_risk,
            'selected_workload_search': selected_workload_search,
            'selected_workload_type': selected_workload_type,
            'selected_workload_configuration': selected_workload_configuration,
            'selected_workload_qos': selected_workload_qos,
            'selected_workload_risk': selected_workload_risk,
            'initial_tab': initial_tab,
            'tenant_quota_summary': tenant_summary,
            'tenant_quota_rows': tenant_scope_rows,
            'quota_status_options': quota_status_options,
            'tenant_risk_options': tenant_risk_options,
            'workload_mapping_payload': mapping_payload,
            'workload_mapping_rows': workload_scope_rows,
            'workload_scope_summary': workload_scope_summary,
            'governance_findings': governance_findings,
            'actionable_recommendations': recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': recommendation_count,
            'workload_count_display': f'{len(workload_scope_rows)} Workloads',
            'recommendation_count_display': f'{recommendation_count} Actionable',
            'finding_count_display': f'{len(governance_findings)} Findings',
            'workload_posture': workload_posture,
        }
    )
    return presented
