# app/analytics/capacity/service.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app

from app.analytics.common.base_service import AnalyticsBaseService, bytes_to_gib, raw_percent, safe_percent, safe_round
from app.analytics.common.clusters import get_selected_cluster
from app.analytics.common.coercion import as_dict as _as_dict
from app.analytics.common.params import get_allowed_time_ranges, get_query_value, get_selected_time_range
from app.analytics.common.payloads import get_capacity_review_paths, get_empty_capacity_payload
from app.analytics.common.presentation import present_prometheus_status
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import (
    cluster_required_blocker,
    prometheus_capability_blocker,
    prometheus_connection_blocker,
    prometheus_setup_blocker,
)
from app.integrations.prometheus.capabilities import definition as capability_definition
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.intelligence.recommendation_engine import (
    build_capacity_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.repository import resolve_instance_for_cluster
from app.prometheus.service import PrometheusService

CURRENT_WORKER_PODS_QUERY = get_query_expression('analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY')
WORKER_CPU_ALLOCATABLE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_ALLOCATABLE_QUERY')
WORKER_CPU_LIMITS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_LIMITS_TOTAL_QUERY')
WORKER_CPU_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.capacity.queries.WORKER_CPU_PEAK_QUERY_TEMPLATE')
WORKER_CPU_REQUESTS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_REQUESTS_TOTAL_QUERY')
WORKER_CPU_USAGE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_USAGE_QUERY')
WORKER_MEMORY_ALLOCATABLE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_ALLOCATABLE_QUERY')
WORKER_MEMORY_LIMITS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_LIMITS_TOTAL_QUERY')
WORKER_MEMORY_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_PEAK_QUERY_TEMPLATE')
WORKER_MEMORY_REQUESTS_TOTAL_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_REQUESTS_TOTAL_QUERY'
)
WORKER_MEMORY_USAGE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_USAGE_QUERY')
WORKER_POD_ALLOCATABLE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_POD_ALLOCATABLE_QUERY')

CAPACITY_TIME_RANGE_STEP_MAP = {
    '1h': '5m',
    '6h': '15m',
    '12h': '30m',
    '24h': '1h',
    '7d': '6h',
    '30d': '12h',
    '60d': '1d',
}


def get_capacity_time_step(
    time_range: str,
) -> str:
    return CAPACITY_TIME_RANGE_STEP_MAP.get(
        time_range,
        '1h',
    )


def get_capacity_page_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    clusters = Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
    ).all()

    selected_time_range = get_selected_time_range(
        query_args=query_args,
    )

    cluster_id = get_query_value(
        query_args=query_args,
        name='cluster_id',
        default='',
    )

    cluster = get_selected_cluster(
        clusters=clusters,
        cluster_id=cluster_id,
    )

    empty_capacity_payload = get_empty_capacity_payload(
        selected_time_range=selected_time_range,
    )

    prometheus_status = present_prometheus_status({
        'configured': False,
        'connected': False,
        'response_time_ms': None,
        'label': 'Prometheus Not Configured',
    })

    if not cluster:
        return {
            'clusters': clusters,
            'cluster': None,
            'error': None,
            'prometheus_connected': False,
            'prometheus_status': present_prometheus_status({
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Waiting for Cluster',
            }),
            'dependency_blocker': cluster_required_blocker(),
            **empty_capacity_payload,
        }

    error = None
    prometheus_connected = False
    dependency_blocker = None
    capacity_payload = empty_capacity_payload.copy()

    prometheus_config = resolve_instance_for_cluster(cluster.id)

    if prometheus_config is None or not prometheus_config.endpoint.strip():
        return {
            'clusters': clusters,
            'cluster': cluster,
            'error': None,
            'prometheus_connected': False,
            'prometheus_status': present_prometheus_status({
                'configured': False,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Not Configured',
            }),
            'dependency_blocker': prometheus_setup_blocker(cluster),
            **empty_capacity_payload,
        }

    try:
        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )
        consumer = PrometheusConsumer(cluster)
        capacity_service = CapacityService(
            utilization_service,
            consumer,
        )

        prometheus_status = capacity_service.get_prometheus_status()

        prometheus_connected = bool(
            prometheus_status.get(
                'connected',
                False,
            )
        )

        if not prometheus_connected:
            dependency_blocker = prometheus_connection_blocker(
                cluster,
                detail=str(
                    prometheus_status.get('error')
                    or prometheus_status.get('description')
                    or 'Prometheus did not report a healthy connection.'
                ),
            )
        else:
            requirements = consumer.requirements(CapacityService.REQUIRED_CAPABILITIES)
            if not requirements.ok:
                missing = list((requirements.payload or {}).get('missing_capabilities') or [])
                labels: list[str] = []
                for key in missing:
                    definition = capability_definition(str(key))
                    labels.append(definition.label if definition is not None else str(key))
                dependency_blocker = prometheus_capability_blocker(
                    cluster,
                    feature_label='Capacity Analytics',
                    missing_capabilities=labels,
                )
            else:
                capacity_payload = capacity_service.get_capacity_analysis(
                    time_range=selected_time_range,
                )

    except PrometheusError as exc:
        message = str(exc) or 'Prometheus is not configured for the selected cluster.'
        prometheus_status = present_prometheus_status({
            'configured': True,
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Unavailable',
            'error': message,
        })
        dependency_blocker = prometheus_connection_blocker(
            cluster,
            detail=message,
        )
    except Exception as exc:
        current_app.logger.exception(
            exc,
        )

        dependency_blocker = prometheus_connection_blocker(
            cluster,
            detail=str(exc),
        )

    return {
        'clusters': clusters,
        'cluster': cluster,
        'error': error,
        'prometheus_connected': prometheus_connected,
        'prometheus_status': present_prometheus_status(prometheus_status),
        'dependency_blocker': dependency_blocker,
        **capacity_payload,
    }


class CapacityService(AnalyticsBaseService):
    REQUIRED_CAPABILITIES = (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'capacity_metrics',
        'resource_requests_limits',
    )

    def __init__(
        self,
        utilization_service: UtilizationService,
        consumer: PrometheusConsumer,
    ) -> None:
        self.utilization_service = utilization_service
        self.consumer = consumer

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
        return [item for item in result if isinstance(item, dict)]

    def get_capacity_analysis(
        self,
        time_range: str = '24h',
    ) -> dict[str, Any]:
        summary = self.utilization_service.get_summary()

        cluster_info = self.utilization_service.get_cluster_info(
            summary,
        )

        capacity_summary = self.get_capacity_summary_from_summary(
            summary,
        )

        allocation_summary = self.get_cluster_allocation_summary(
            summary=summary,
            time_range=time_range,
        )

        worker_capacity_summary = self.get_worker_capacity_summary(
            cluster_info=cluster_info,
            capacity_summary=capacity_summary,
        )

        risk_summary = self.get_capacity_risk_summary(
            capacity_summary=capacity_summary,
        )

        governance_findings = self.get_capacity_governance_findings(
            capacity_summary=capacity_summary,
            allocation_summary=allocation_summary,
        )

        actionable_payload = {
            'cluster_info': cluster_info,
            'capacity_summary': capacity_summary,
            'worker_capacity_summary': worker_capacity_summary,
            'allocation_summary': allocation_summary,
            'risk_summary': risk_summary,
            'governance_findings': governance_findings,
            'selected_time_range': time_range,
        }

        actionable_recommendations = build_capacity_actionable_recommendations(
            actionable_payload,
        )

        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Continue Capacity Monitoring',
            default_description=(
                'No actionable capacity recommendation was generated from the current risk signals. '
                'Continue monitoring worker capacity, allocation, and headroom trends.'
            ),
            default_source='capacity',
            default_action_type='capacity_review',
            include_presentation_classes=False,
        )

        review_paths = get_capacity_review_paths()

        for card in recommendation_cards:
            source = str(card.get('source', ''))
            if source in {'capacity_risk', 'capacity_headroom'}:
                card['target_tab'] = 'risk'
            elif source == 'capacity_governance':
                card['target_tab'] = 'allocation'
            else:
                card['target_tab'] = 'summary'

        kpi_cards = self.get_kpi_cards(
            cluster_info=cluster_info,
            capacity_summary=capacity_summary,
        )

        return {
            'cluster_info': cluster_info,
            'capacity_summary': capacity_summary,
            'worker_capacity_summary': worker_capacity_summary,
            'allocation_summary': allocation_summary,
            'risk_summary': risk_summary,
            'governance_findings': governance_findings,
            'review_paths': review_paths,
            'actionable_recommendations': actionable_recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': count_actionable_recommendations(
                actionable_recommendations,
            ),
            'kpi_cards': kpi_cards,
            'selected_time_range': time_range,
            'allowed_time_ranges': get_allowed_time_ranges(),
        }

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
            get_capacity_time_step(
                time_range,
            ),
        )

    def get_capacity_summary_from_summary(
        self,
        summary: dict[str, Any],
    ) -> dict[str, dict[str, float]]:
        cpu_capacity = self.get_prometheus_scalar(
            WORKER_CPU_ALLOCATABLE_QUERY,
        )

        cpu_usage = self.get_prometheus_scalar(
            WORKER_CPU_USAGE_QUERY,
        )

        memory_capacity = self.get_prometheus_scalar(
            WORKER_MEMORY_ALLOCATABLE_QUERY,
        )

        memory_usage = self.get_prometheus_scalar(
            WORKER_MEMORY_USAGE_QUERY,
        )

        pod_capacity = self.get_prometheus_scalar(
            WORKER_POD_ALLOCATABLE_QUERY,
        )

        pod_usage = self.get_prometheus_scalar(
            CURRENT_WORKER_PODS_QUERY,
        )

        cpu_available = max(
            cpu_capacity - cpu_usage,
            0,
        )

        memory_available = max(
            memory_capacity - memory_usage,
            0,
        )

        pod_available = max(
            pod_capacity - pod_usage,
            0,
        )

        return {
            'cpu': {
                'evidence_available': cpu_capacity > 0,
                'capacity': safe_round(
                    cpu_capacity,
                ),
                'used': safe_round(
                    cpu_usage,
                ),
                'available': safe_round(
                    cpu_available,
                ),
                'headroom': safe_percent(
                    cpu_available,
                    cpu_capacity,
                ),
            },
            'memory': {
                'evidence_available': memory_capacity > 0,
                'capacity': bytes_to_gib(
                    memory_capacity,
                ),
                'used': bytes_to_gib(
                    memory_usage,
                ),
                'available': bytes_to_gib(
                    memory_available,
                ),
                'headroom': safe_percent(
                    memory_available,
                    memory_capacity,
                ),
            },
            'pods': {
                'evidence_available': pod_capacity > 0,
                'capacity': safe_round(
                    pod_capacity,
                    0,
                ),
                'used': safe_round(
                    pod_usage,
                    0,
                ),
                'available': safe_round(
                    pod_available,
                    0,
                ),
                'headroom': safe_percent(
                    pod_available,
                    pod_capacity,
                ),
            },
            'storage': {
                'evidence_available': float(summary.get('storage_capacity', 0) or 0) > 0,
                'capacity': bytes_to_gib(summary.get('storage_capacity', 0)),
                'used': bytes_to_gib(summary.get('storage_usage', 0)),
                'available': bytes_to_gib(summary.get('storage_available', 0)),
                'headroom': safe_percent(
                    summary.get('storage_available', 0),
                    summary.get('storage_capacity', 0),
                ),
            },
        }

    def get_allocation_status_findings(
        self,
        allocation_summary: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        resource_labels = {'cpu': 'CPU', 'memory': 'Memory', 'pods': 'Pods'}
        resource_icons = {'cpu': 'cpu', 'memory': 'memory-stick', 'pods': 'box'}
        findings: list[dict[str, Any]] = []

        for resource in ('cpu', 'memory', 'pods'):
            section = allocation_summary.get(resource, {})
            status = section.get('status', {})
            if not isinstance(status, dict):
                continue
            tone = str(status.get('tone', 'unknown'))
            if tone not in {'critical', 'warning'}:
                continue
            status_label = str(status.get('label', 'Unknown'))
            findings.append(
                {
                    'label': f'{resource_labels.get(resource, resource.title())} allocation status: {status_label}',
                    'severity': tone,
                    'tone': tone,
                    'icon': resource_icons.get(resource, 'activity'),
                    'filter': 'capacity-allocation',
                }
            )

        return findings

    def get_worker_capacity_summary(
        self,
        cluster_info: dict[str, Any],
        capacity_summary: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        return {
            'title': 'Worker Capacity Summary',
            'subtitle': (
                'Schedulable capacity is calculated from Ready worker nodes. '
                'Control-plane nodes are shown for context only.'
            ),
            'cards': self.get_kpi_cards(
                cluster_info=cluster_info,
                capacity_summary=capacity_summary,
            ),
        }

    def get_kpi_cards(
        self,
        cluster_info: dict[str, Any],
        capacity_summary: dict[str, dict[str, float]],
    ) -> list[dict[str, Any]]:
        return [
            {
                'label': 'Worker Nodes',
                'value': cluster_info.get(
                    'worker_nodes',
                    0,
                ),
                'caption': (
                    f'{cluster_info.get("ready_nodes", 0)} Ready, {cluster_info.get("not_ready_nodes", 0)} Not Ready'
                ),
                'footer': (
                    f'Total nodes {cluster_info.get("total_nodes", 0)} · '
                    f'Control-plane {cluster_info.get("master_nodes", 0)}'
                ),
                'icon': 'users',
            },
            {
                'label': 'Allocatable CPU',
                'value': (
                    f'{float(capacity_summary["cpu"]["capacity"] or 0):.2f} Cores'
                    if capacity_summary['cpu'].get('evidence_available')
                    else 'N/A'
                ),
                'caption': 'Ready worker nodes only',
                'footer': '',
                'icon': 'cpu',
            },
            {
                'label': 'Allocatable Memory',
                'value': (
                    f'{float(capacity_summary["memory"]["capacity"] or 0):.2f} GiB'
                    if capacity_summary['memory'].get('evidence_available')
                    else 'N/A'
                ),
                'caption': 'Ready worker nodes only',
                'footer': '',
                'icon': 'memory-stick',
            },
            {
                'label': 'Pod Capacity',
                'value': (
                    f'{int(float(capacity_summary["pods"]["capacity"] or 0))} Pods'
                    if capacity_summary['pods'].get('evidence_available')
                    else 'N/A'
                ),
                'caption': 'Ready worker nodes only',
                'footer': '',
                'icon': 'box',
            },
        ]

    def get_cluster_allocation_summary(
        self,
        summary: dict[str, Any],
        time_range: str,
    ) -> dict[str, dict[str, Any]]:
        cpu_allocatable = self.get_prometheus_scalar(
            WORKER_CPU_ALLOCATABLE_QUERY,
        )

        memory_allocatable_bytes = self.get_prometheus_scalar(
            WORKER_MEMORY_ALLOCATABLE_QUERY,
        )

        pod_capacity = self.get_prometheus_scalar(
            WORKER_POD_ALLOCATABLE_QUERY,
        )

        cpu_actual = self.get_prometheus_scalar(
            WORKER_CPU_USAGE_QUERY,
        )

        memory_actual_bytes = self.get_prometheus_scalar(
            WORKER_MEMORY_USAGE_QUERY,
        )

        current_pods = self.get_prometheus_scalar(
            CURRENT_WORKER_PODS_QUERY,
        )

        cpu_requests = self.get_prometheus_scalar(
            WORKER_CPU_REQUESTS_TOTAL_QUERY,
        )

        cpu_limits = self.get_prometheus_scalar(
            WORKER_CPU_LIMITS_TOTAL_QUERY,
        )

        memory_requests_bytes = self.get_prometheus_scalar(
            WORKER_MEMORY_REQUESTS_TOTAL_QUERY,
        )

        memory_limits_bytes = self.get_prometheus_scalar(
            WORKER_MEMORY_LIMITS_TOTAL_QUERY,
        )

        cpu_peak = self.get_prometheus_scalar(
            self.build_range_query(
                WORKER_CPU_PEAK_QUERY_TEMPLATE,
                time_range,
            ),
        )

        memory_peak_bytes = self.get_prometheus_scalar(
            self.build_range_query(
                WORKER_MEMORY_PEAK_QUERY_TEMPLATE,
                time_range,
            ),
        )

        if not cpu_peak:
            cpu_peak = cpu_actual

        if not memory_peak_bytes:
            memory_peak_bytes = memory_actual_bytes

        pod_remaining = max(
            pod_capacity - current_pods,
            0,
        )

        return {
            'cpu': {
                'title': 'CPU',
                'available': cpu_allocatable > 0,
                'unit': 'cores',
                'status': self.get_allocation_status(
                    requested=cpu_limits,
                    allocatable=cpu_allocatable,
                    resource='cpu',
                    actual=cpu_actual,
                    peak=cpu_peak,
                ),
                'items': self.build_cpu_allocation_items(
                    allocatable=cpu_allocatable,
                    requests=cpu_requests,
                    limits=cpu_limits,
                    actual=cpu_actual,
                    peak=cpu_peak,
                ),
            },
            'memory': {
                'title': 'Memory',
                'available': memory_allocatable_bytes > 0,
                'unit': 'GiB',
                'status': self.get_allocation_status(
                    requested=memory_limits_bytes,
                    allocatable=memory_allocatable_bytes,
                    resource='memory',
                    actual=memory_actual_bytes,
                    peak=memory_peak_bytes,
                ),
                'items': self.build_memory_allocation_items(
                    allocatable_bytes=memory_allocatable_bytes,
                    requests_bytes=memory_requests_bytes,
                    limits_bytes=memory_limits_bytes,
                    actual_bytes=memory_actual_bytes,
                    peak_bytes=memory_peak_bytes,
                ),
            },
            'pods': {
                'title': 'Pods',
                'available': pod_capacity > 0,
                'unit': 'pods',
                'status': self.get_allocation_status(
                    requested=current_pods,
                    allocatable=pod_capacity,
                    resource='pods',
                    actual=current_pods,
                    peak=current_pods,
                ),
                'items': self.build_pod_allocation_items(
                    capacity=pod_capacity,
                    current=current_pods,
                    remaining=pod_remaining,
                ),
            },
        }

    def build_cpu_allocation_items(
        self,
        allocatable: float,
        requests: float,
        limits: float,
        actual: float,
        peak: float,
    ) -> list[dict[str, Any]]:
        return [
            {
                'label': 'Allocatable',
                'display': f'{safe_round(allocatable)} cores (100%)',
                'percent': 100,
            },
            {
                'label': 'Configured Requests',
                'display': (f'{safe_round(requests)} cores ({safe_round(raw_percent(requests, allocatable), 1)}%)'),
                'percent': safe_percent(
                    requests,
                    allocatable,
                ),
            },
            {
                'label': 'Configured Limits',
                'display': (f'{safe_round(limits)} cores ({safe_round(raw_percent(limits, allocatable), 1)}%)'),
                'percent': safe_percent(
                    limits,
                    allocatable,
                ),
            },
            {
                'label': 'Actual Avg Usage',
                'display': (f'{safe_round(actual)} cores ({safe_round(raw_percent(actual, allocatable), 1)}%)'),
                'percent': safe_percent(
                    actual,
                    allocatable,
                ),
            },
            {
                'label': 'Peak Usage',
                'display': (f'{safe_round(peak)} cores ({safe_round(raw_percent(peak, allocatable), 1)}%)'),
                'percent': safe_percent(
                    peak,
                    allocatable,
                ),
            },
        ]

    def build_memory_allocation_items(
        self,
        allocatable_bytes: float,
        requests_bytes: float,
        limits_bytes: float,
        actual_bytes: float,
        peak_bytes: float,
    ) -> list[dict[str, Any]]:
        return [
            {
                'label': 'Allocatable',
                'display': f'{bytes_to_gib(allocatable_bytes)} GiB (100%)',
                'percent': 100,
            },
            {
                'label': 'Configured Requests',
                'display': (
                    f'{bytes_to_gib(requests_bytes)} GiB '
                    f'({safe_round(raw_percent(requests_bytes, allocatable_bytes), 1)}%)'
                ),
                'percent': safe_percent(
                    requests_bytes,
                    allocatable_bytes,
                ),
            },
            {
                'label': 'Configured Limits',
                'display': (
                    f'{bytes_to_gib(limits_bytes)} GiB ({safe_round(raw_percent(limits_bytes, allocatable_bytes), 1)}%)'
                ),
                'percent': safe_percent(
                    limits_bytes,
                    allocatable_bytes,
                ),
            },
            {
                'label': 'Actual Avg Usage',
                'display': (
                    f'{bytes_to_gib(actual_bytes)} GiB ({safe_round(raw_percent(actual_bytes, allocatable_bytes), 1)}%)'
                ),
                'percent': safe_percent(
                    actual_bytes,
                    allocatable_bytes,
                ),
            },
            {
                'label': 'Peak Usage',
                'display': (
                    f'{bytes_to_gib(peak_bytes)} GiB ({safe_round(raw_percent(peak_bytes, allocatable_bytes), 1)}%)'
                ),
                'percent': safe_percent(
                    peak_bytes,
                    allocatable_bytes,
                ),
            },
        ]

    def build_pod_allocation_items(
        self,
        capacity: float,
        current: float,
        remaining: float,
    ) -> list[dict[str, Any]]:
        return [
            {
                'label': 'Pod Capacity',
                'display': f'{safe_round(capacity, 0):.0f} pods (100%)',
                'percent': 100,
            },
            {
                'label': 'Current Pods',
                'display': (f'{safe_round(current, 0):.0f} pods ({safe_round(raw_percent(current, capacity), 1)}%)'),
                'percent': safe_percent(
                    current,
                    capacity,
                ),
            },
            {
                'label': 'Remaining Pod Slots',
                'display': (
                    f'{safe_round(remaining, 0):.0f} pods ({safe_round(raw_percent(remaining, capacity), 1)}%)'
                ),
                'percent': safe_percent(
                    remaining,
                    capacity,
                ),
            },
            {
                'label': 'Pod Usage',
                'display': f'{safe_round(raw_percent(current, capacity), 1)}%',
                'percent': safe_percent(
                    current,
                    capacity,
                ),
            },
        ]

    def get_capacity_risk_summary(
        self,
        capacity_summary: dict[str, dict[str, float]],
    ) -> list[dict[str, Any]]:
        icon_map = {
            'cpu': 'cpu',
            'memory': 'memory-stick',
            'pods': 'boxes',
            'storage': 'hard-drive',
        }

        risks: list[dict[str, Any]] = []

        for resource in ('cpu', 'memory', 'pods', 'storage'):
            item = capacity_summary.get(resource, {})
            capacity = self.to_float(item.get('capacity', 0))
            available = capacity > 0
            headroom = self.to_float(item.get('headroom', 0)) if available else None
            status = (
                self.get_headroom_status(headroom or 0)
                if available
                else {'label': 'Unknown', 'tone': 'unknown'}
            )

            risks.append(
                {
                    'resource': resource,
                    'label': 'Pods' if resource == 'pods' else resource.title(),
                    'headroom': headroom,
                    'evidence_available': available,
                    'status': status,
                    'icon': icon_map.get(resource, 'activity'),
                }
            )

        return risks


    def get_capacity_governance_findings(
        self,
        capacity_summary: dict[str, dict[str, float]],
        allocation_summary: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        findings = self.get_allocation_status_findings(allocation_summary)

        low_headroom = [
            resource
            for resource, item in capacity_summary.items()
            if resource in {'cpu', 'memory', 'pods', 'storage'}
            and self.to_float(item.get('capacity', 0)) > 0
            and self.to_float(item.get('headroom', 0)) < 30
        ]

        if low_headroom:
            findings.append(
                {
                    'label': f'Low capacity headroom detected on {", ".join(low_headroom)}',
                    'severity': 'critical',
                    'tone': 'critical',
                    'icon': 'circle-alert',
                    'filter': 'capacity-headroom',
                }
            )

        if not findings:
            findings.append(
                {
                    'label': 'No actionable capacity governance finding detected',
                    'severity': 'normal',
                    'tone': 'normal',
                    'icon': 'check-circle',
                    'filter': '',
                }
            )

        return findings

    def get_headroom_status(
        self,
        headroom: float,
    ) -> dict[str, str]:
        if headroom < 15:
            return {'label': 'Critical', 'tone': 'critical'}
        if headroom < 40:
            return {'label': 'Watch', 'tone': 'warning'}
        return {'label': 'Healthy', 'tone': 'normal'}

    def get_allocation_status(
        self,
        requested: float,
        allocatable: float,
        resource: str,
        actual: float | None = None,
        peak: float | None = None,
    ) -> dict[str, str]:
        if allocatable <= 0:
            return {'label': 'Unknown', 'tone': 'unknown'}

        requested_percent = raw_percent(requested, allocatable)
        actual_percent = raw_percent(actual if actual is not None else 0, allocatable)
        peak_percent = raw_percent(peak if peak is not None else 0, allocatable)
        pressure_percent = max(requested_percent, actual_percent, peak_percent)

        if requested_percent >= 100 and resource == 'cpu':
            return {'label': 'CPU Limit Overcommit', 'tone': 'critical'}
        if requested_percent >= 100 and resource == 'memory':
            return {'label': 'Memory Limit Overcommit', 'tone': 'critical'}
        if peak_percent >= 100:
            return {'label': f'{resource.title()} Peak Over Capacity', 'tone': 'critical'}
        if actual_percent >= 95:
            return {'label': f'{resource.title()} Usage Critical', 'tone': 'critical'}
        if pressure_percent >= 90:
            return {'label': 'Near Capacity', 'tone': 'warning'}
        if pressure_percent >= 75:
            return {'label': 'Watch', 'tone': 'warning'}
        return {'label': 'Healthy', 'tone': 'normal'}


def get_capacity_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> dict[str, Any]:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.capacity',
        parameters={'cluster_id': str(cluster_id), 'time_range': time_range},
    )
    context = result.context or {}
    capacity_summary = context.get('capacity_summary')
    if not isinstance(capacity_summary, dict):
        return _empty_capacity_snapshot()
    cpu_summary = _as_dict(capacity_summary.get('cpu', {}))
    memory_summary = _as_dict(capacity_summary.get('memory', {}))
    pods_summary = _as_dict(capacity_summary.get('pods', {}))
    recommendations = context.get('actionable_recommendations')
    return {
        'cpu_headroom': _safe_int(cpu_summary.get('available', 0)),
        'cpu_unit': 'Cores',
        'memory_headroom': _safe_int(memory_summary.get('available', 0)),
        'memory_unit': 'GiB',
        'pod_capacity_remaining': _safe_int(pods_summary.get('available', 0)),
        'pod_unit': 'Pods',
        'recommendation_count': count_actionable_recommendations(
            recommendations if isinstance(recommendations, list) else []
        ),
    }

def _empty_capacity_snapshot() -> dict[str, Any]:
    return {
        'cpu_headroom': 0,
        'cpu_unit': 'Cores',
        'memory_headroom': 0,
        'memory_unit': 'GiB',
        'pod_capacity_remaining': 0,
        'pod_unit': 'Pods',
        'recommendation_count': 0,
    }


def _safe_int(
    value: Any,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return int(
            value,
        )

    if isinstance(
        value,
        int | float | str,
    ):
        try:
            return int(
                round(
                    float(
                        value,
                    )
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    return 0
