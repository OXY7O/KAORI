# app/analytics/workload/service.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.coercion import as_dict, as_list, safe_float
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import ALLOWED_PER_PAGE_VALUES, get_allowed_time_ranges, get_selected_time_range
from app.analytics.common.payloads import get_empty_workload_payload
from app.analytics.common.presentation import present_prometheus_status
from app.analytics.utilization.service import UtilizationService
from app.analytics.workload.domain import build_governance_findings, build_workload_posture
from app.analytics.workload.formatting import get_workload_time_step
from app.analytics.workload.mapping import (
    WorkloadMappingEvidence,
    build_workload_mapping_payload,
    build_workload_scope_summary,
    parse_pod_owner_map,
    parse_pod_qos_map,
)
from app.analytics.workload.quota import (
    build_tenant_quota_summary,
    build_tenant_scope_summary,
    parse_resource_quota_map,
)
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


class WorkloadAnalysisService(AnalyticsBaseService):
    """Collect Workload Analysis evidence once and delegate domain evaluation."""

    REQUIRED_CAPABILITIES = (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'workload_metrics',
        'resource_requests_limits',
    )

    def __init__(self, utilization_service: UtilizationService) -> None:
        self.utilization_service = utilization_service
        self.consumer = utilization_service.consumer

    def requirements(self) -> ConsumerResult[dict[str, Any]]:
        return self.consumer.requirements(self.REQUIRED_CAPABILITIES)

    def get_prometheus_result(self, query: str) -> list[dict[str, Any]]:
        response = self.consumer.query(query, required_capabilities=self.REQUIRED_CAPABILITIES)
        data = response.get('data', {}) if isinstance(response, dict) else {}
        result = data.get('result', []) if isinstance(data, dict) else []
        return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []

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

    def get_tenant_quota_summary(self, selected_namespace: str = '') -> dict[str, Any]:
        return build_tenant_quota_summary(
            active_namespaces=self.get_prometheus_vector_map(
                query=NAMESPACE_ACTIVE_QUERY,
                label='namespace',
            ),
            hard=self.get_resource_quota_map(TENANT_QUOTA_HARD_QUERY),
            used=self.get_resource_quota_map(TENANT_QUOTA_USED_QUERY),
            cpu_actual=self.get_prometheus_vector_map(
                query=TENANT_CPU_ACTUAL_QUERY,
                label='namespace',
            ),
            memory_actual=self.get_prometheus_vector_map(
                query=TENANT_MEMORY_ACTUAL_QUERY,
                label='namespace',
            ),
            pod_actual=self.get_prometheus_vector_map(
                query=TENANT_POD_ACTUAL_QUERY,
                label='namespace',
            ),
            selected_namespace=selected_namespace,
        )

    def get_workload_mapping_payload(
        self,
        selected_namespace: str = '',
        time_range: str = '24h',
    ) -> dict[str, Any]:
        evidence = WorkloadMappingEvidence(
            cpu_requests=self._pod_vector(WORKLOAD_CPU_REQUESTS_QUERY),
            cpu_limits=self._pod_vector(WORKLOAD_CPU_LIMITS_QUERY),
            cpu_current=self._pod_vector(WORKLOAD_CPU_CURRENT_QUERY),
            cpu_peak=self._pod_vector(self.build_range_query(WORKLOAD_CPU_PEAK_QUERY_TEMPLATE, time_range)),
            memory_requests=self._pod_vector(WORKLOAD_MEMORY_REQUESTS_QUERY),
            memory_limits=self._pod_vector(WORKLOAD_MEMORY_LIMITS_QUERY),
            memory_current=self._pod_vector(WORKLOAD_MEMORY_CURRENT_QUERY),
            memory_peak=self._pod_vector(self.build_range_query(WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE, time_range)),
            owner_map=parse_pod_owner_map(self.get_prometheus_result(WORKLOAD_POD_OWNER_QUERY)),
            qos_map=parse_pod_qos_map(self.get_prometheus_result(WORKLOAD_QOS_QUERY)),
        )
        return build_workload_mapping_payload(evidence, selected_namespace=selected_namespace)

    def get_resource_quota_map(self, query: str) -> dict[str, dict[str, dict[str, float]]]:
        return parse_resource_quota_map(self.get_prometheus_result(query), self.extract_value)

    def get_governance_findings(
        self,
        tenant_quota_rows: list[dict[str, Any]],
        workload_mapping_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return build_governance_findings(tenant_quota_rows, workload_mapping_rows)

    def build_range_query(self, query_template: str, time_range: str) -> str:
        return query_template.replace('__TIME_RANGE__', time_range).replace(
            '__TIME_STEP__',
            get_workload_time_step(time_range),
        )

    def _pod_vector(self, query: str) -> dict[str, float]:
        return self.get_prometheus_vector_map(
            query=query,
            label='pod',
            secondary_label='namespace',
        )


def get_workload_analysis_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    """Build the committed cluster/time-range dataset; UI filters remain presentation state."""
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
        check_prometheus_connection=False,
    )
    time_range = get_selected_time_range(query_args=query_args)
    context.update(_empty_materialized_context(time_range))
    if utilization_service is None or cluster is None:
        context.update(get_empty_workload_payload('', time_range))
        return context

    service = WorkloadAnalysisService(utilization_service)
    requirement_result = service.requirements()
    if not requirement_result.ok:
        missing = list((requirement_result.payload or {}).get('missing_capabilities') or [])
        context['dependency_blocker'] = prometheus_capability_blocker(
            cluster,
            feature_label='Workload Analytics',
            missing_capabilities=missing,
        )
        context.update(get_empty_workload_payload('', time_range))
        return context

    try:
        prometheus_status = service.get_prometheus_status()
        context.update(_prometheus_context(prometheus_status))
        if not context['prometheus_connected']:
            context['dependency_blocker'] = prometheus_connection_blocker(
                cluster,
                detail=str(prometheus_status.get('error') or 'Prometheus health check did not complete successfully.'),
            )
            context.update(get_empty_workload_payload('', time_range))
            return context
        return _materialize_workload_context(context, service, time_range)
    except Exception as exc:
        context['dependency_blocker'] = prometheus_connection_blocker(cluster, detail=str(exc))
        context.update(get_empty_workload_payload('', time_range))
        return context


def get_workload_snapshot(cluster_id: str, time_range: str = '24h') -> dict[str, Any] | None:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.workload',
        parameters={'cluster_id': str(cluster_id), 'time_range': time_range},
    )
    if not result.available:
        return None
    context = result.context or {}
    rows = as_list(context.get('workload_mapping_rows', []))
    counters = {
        'missing_cpu_requests': 0,
        'missing_memory_requests': 0,
        'cpu_limits_unset': 0,
        'memory_limits_missing': 0,
        'over_provisioned': 0,
        'under_provisioned': 0,
    }
    for raw_row in rows:
        row = as_dict(raw_row)
        counters['missing_cpu_requests'] += int(safe_float(row.get('cpu_request_raw')) <= 0)
        counters['missing_memory_requests'] += int(safe_float(row.get('memory_request_raw')) <= 0)
        counters['cpu_limits_unset'] += int(safe_float(row.get('cpu_limit_raw')) <= 0)
        counters['memory_limits_missing'] += int(safe_float(row.get('memory_limit_raw')) <= 0)
        recommendation = str(row.get('recommendation') or '').casefold()
        counters['over_provisioned'] += int('reduce' in recommendation)
        counters['under_provisioned'] += int('increase' in recommendation)
    actionable_recommendations = context.get('actionable_recommendations')
    return {
        **counters,
        'recommendation_count': count_actionable_recommendations(
            actionable_recommendations if isinstance(actionable_recommendations, list) else []
        ),
    }


def _materialize_workload_context(
    context: dict[str, Any],
    service: WorkloadAnalysisService,
    time_range: str,
) -> dict[str, Any]:
    tenant_summary = service.get_tenant_quota_summary()
    tenant_rows = list(tenant_summary.get('rows') or [])
    tenant_summary['pagination'] = {}
    mapping_payload = service.get_workload_mapping_payload(time_range=time_range)
    workload_rows = list(mapping_payload.get('rows') or [])
    mapping_payload.update(
        {
            'rows': workload_rows,
            'pagination': {},
            'scope_summary': build_workload_scope_summary(workload_rows),
        }
    )
    findings = build_governance_findings(tenant_rows, workload_rows)
    recommendations = build_workload_actionable_recommendations(
        {
            'tenant_quota_summary': tenant_summary,
            'tenant_quota_rows': tenant_rows,
            'workload_mapping_payload': mapping_payload,
            'workload_mapping_rows': workload_rows,
            'governance_findings': findings,
            'selected_namespace': '',
            'selected_time_range': time_range,
        }
    )
    cards = format_recommendation_cards(
        recommendations,
        default_title='Continue Workload Governance Monitoring',
        default_description=(
            'No actionable workload recommendation was generated from the current quota, '
            'request, limit, QoS, and right-sizing signals.'
        ),
        default_source='workload_baseline',
        default_action_type='workload_governance',
    )
    recommendation_count = count_actionable_recommendations(recommendations)
    context.update(
        {
            'namespace_options': sorted(
                {
                    str(row.get('namespace') or '')
                    for row in [*tenant_rows, *workload_rows]
                    if str(row.get('namespace') or '')
                }
            ),
            'tenant_quota_summary': tenant_summary,
            'tenant_quota_rows': tenant_rows,
            'workload_mapping_payload': mapping_payload,
            'workload_mapping_rows': workload_rows,
            'workload_scope_summary': build_workload_scope_summary(workload_rows),
            'governance_findings': findings,
            'actionable_recommendations': recommendations,
            'recommendation_cards': cards,
            'recommendation_count': recommendation_count,
            'workload_count_display': f'{len(workload_rows)} Workloads',
            'recommendation_count_display': f'{recommendation_count} Actionable',
            'finding_count_display': f'{len(findings)} Findings',
            'workload_posture': build_workload_posture(tenant_rows, workload_rows, findings),
        }
    )
    return context


def _empty_materialized_context(time_range: str) -> dict[str, Any]:
    return {
        'selected_namespace': '',
        'selected_time_range': time_range,
        'selected_tenant_search': '',
        'selected_tenant_quota_status': '',
        'selected_tenant_risk': '',
        'selected_workload_search': '',
        'selected_workload_type': '',
        'selected_workload_configuration': '',
        'selected_workload_qos': '',
        'selected_workload_risk': '',
        'initial_tab': 'quotas',
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


def _prometheus_context(status: dict[str, Any]) -> dict[str, Any]:
    return {
        'prometheus_status': status,
        'prometheus_connected': bool(status.get('connected', False)),
        'prometheus_status_tone': status.get('tone', 'critical'),
        'prometheus_status_icon': status.get('icon', 'circle-x'),
        'prometheus_response_time_display': status.get('response_time_display', 'No Response'),
    }
