from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import current_app

from app.analytics.capacity.domain import (
    build_allocation_summary,
    build_capacity_posture,
    build_capacity_summary,
    build_cluster_info,
    build_governance_findings,
    build_kpi_cards,
    build_risk_summary,
)
from app.analytics.capacity.evidence import (
    CAPACITY_REQUIRED_CAPABILITIES,
    CapacityEvidenceCollector,
)
from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.clusters import get_selected_cluster
from app.analytics.common.coercion import as_dict
from app.analytics.common.params import (
    get_allowed_time_ranges,
    get_query_value,
    get_selected_time_range,
)
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
from app.intelligence.recommendation_engine import (
    build_capacity_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.models import Cluster
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.repository import resolve_instance_for_cluster
from app.prometheus.service import PrometheusService


def get_capacity_page_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    selected_time_range = get_selected_time_range(query_args=query_args)
    cluster_id = get_query_value(query_args=query_args, name='cluster_id', default='')
    cluster = get_selected_cluster(clusters=clusters, cluster_id=cluster_id)
    empty_payload = get_empty_capacity_payload(selected_time_range=selected_time_range)

    if not cluster:
        return {
            'clusters': clusters,
            'cluster': None,
            'error': None,
            'prometheus_connected': False,
            'prometheus_status': present_prometheus_status(
                {
                    'configured': False,
                    'connected': False,
                    'response_time_ms': None,
                    'label': 'Waiting for Cluster',
                }
            ),
            'dependency_blocker': cluster_required_blocker(),
            **empty_payload,
        }

    prometheus_config = resolve_instance_for_cluster(cluster.id)
    if prometheus_config is None or not prometheus_config.endpoint.strip():
        return {
            'clusters': clusters,
            'cluster': cluster,
            'error': None,
            'prometheus_connected': False,
            'prometheus_status': present_prometheus_status(
                {
                    'configured': False,
                    'connected': False,
                    'response_time_ms': None,
                    'label': 'Prometheus Not Configured',
                }
            ),
            'dependency_blocker': prometheus_setup_blocker(cluster),
            **empty_payload,
        }

    prometheus_connected = False
    dependency_blocker = None
    prometheus_status = present_prometheus_status(
        {
            'configured': True,
            'connected': False,
            'response_time_ms': None,
            'label': 'Prometheus Unavailable',
        }
    )
    capacity_payload = empty_payload.copy()

    try:
        prometheus = PrometheusService(cluster)
        utilization_service = UtilizationService(prometheus)
        consumer = PrometheusConsumer(cluster)
        capacity_service = CapacityService(utilization_service, consumer)
        prometheus_status = capacity_service.get_prometheus_status()
        prometheus_connected = bool(prometheus_status.get('connected', False))

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
                labels = []
                for key in missing:
                    capability = capability_definition(str(key))
                    labels.append(capability.label if capability is not None else str(key))
                dependency_blocker = prometheus_capability_blocker(
                    cluster,
                    feature_label='Capacity Analytics',
                    missing_capabilities=labels,
                )
            else:
                capacity_payload = capacity_service.get_capacity_analysis(time_range=selected_time_range)
    except PrometheusError as exc:
        message = str(exc) or 'Prometheus is not configured for the selected cluster.'
        prometheus_status = present_prometheus_status(
            {
                'configured': True,
                'connected': False,
                'response_time_ms': None,
                'label': 'Prometheus Unavailable',
                'error': message,
            }
        )
        dependency_blocker = prometheus_connection_blocker(cluster, detail=message)
    except Exception as exc:
        current_app.logger.exception(exc)
        dependency_blocker = prometheus_connection_blocker(cluster, detail=str(exc))

    return {
        'clusters': clusters,
        'cluster': cluster,
        'error': None,
        'prometheus_connected': prometheus_connected,
        'prometheus_status': present_prometheus_status(prometheus_status),
        'dependency_blocker': dependency_blocker,
        **capacity_payload,
    }


class CapacityService(AnalyticsBaseService):
    REQUIRED_CAPABILITIES = CAPACITY_REQUIRED_CAPABILITIES

    def __init__(
        self,
        utilization_service: UtilizationService,
        consumer: PrometheusConsumer,
    ) -> None:
        self.utilization_service = utilization_service
        self.evidence_collector = CapacityEvidenceCollector(consumer)

    def get_capacity_analysis(self, time_range: str = '24h') -> dict[str, Any]:
        evidence = self.evidence_collector.collect(time_range=time_range)
        capacity_summary = build_capacity_summary(evidence)
        allocation_summary = build_allocation_summary(evidence)
        capacity_posture = build_capacity_posture(
            capacity_summary,
            allocation_summary,
        )
        cluster_info = build_cluster_info(
            evidence,
            kubernetes_version=self.utilization_service.get_kubernetes_version(),
            total_nodes=self.utilization_service.get_total_nodes(),
            ready_nodes=self.utilization_service.get_ready_nodes(),
            not_ready_nodes=self.utilization_service.get_not_ready_nodes(),
            control_plane_nodes=self.utilization_service.get_master_nodes(),
        )
        kpi_cards = build_kpi_cards(cluster_info, capacity_summary)
        worker_capacity_summary = {
            'title': 'Worker Capacity Summary',
            'subtitle': (
                'Schedulable capacity is calculated from Ready worker nodes. '
                'Control-plane nodes are shown for context only.'
            ),
            'cards': kpi_cards,
        }
        risk_summary = build_risk_summary(capacity_summary)
        governance_findings = build_governance_findings(
            capacity_summary,
            allocation_summary,
        )
        actionable_payload = {
            'cluster_info': cluster_info,
            'capacity_summary': capacity_summary,
            'capacity_posture': capacity_posture,
            'worker_capacity_summary': worker_capacity_summary,
            'allocation_summary': allocation_summary,
            'risk_summary': risk_summary,
            'governance_findings': governance_findings,
            'selected_time_range': time_range,
        }
        actionable_recommendations = build_capacity_actionable_recommendations(actionable_payload)
        recommendation_cards = format_recommendation_cards(
            actionable_recommendations,
            default_title='Continue Capacity Monitoring',
            default_description=(
                'No actionable capacity recommendation was generated from current '
                'Ready-worker headroom and commitment signals.'
            ),
            default_source='capacity',
            default_action_type='capacity_review',
            include_presentation_classes=False,
        )
        for card in recommendation_cards:
            source = str(card.get('source', ''))
            if source in {'capacity_risk', 'capacity_headroom'}:
                card['target_tab'] = 'risk'
            elif source == 'capacity_governance':
                card['target_tab'] = 'allocation'
            else:
                card['target_tab'] = 'summary'

        return {
            'cluster_info': cluster_info,
            'capacity_summary': capacity_summary,
            'capacity_posture': capacity_posture,
            'worker_capacity_summary': worker_capacity_summary,
            'allocation_summary': allocation_summary,
            'risk_summary': risk_summary,
            'governance_findings': governance_findings,
            'review_paths': get_capacity_review_paths(),
            'actionable_recommendations': actionable_recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': count_actionable_recommendations(actionable_recommendations),
            'kpi_cards': kpi_cards,
            'selected_time_range': time_range,
            'allowed_time_ranges': get_allowed_time_ranges(),
        }


def get_capacity_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> dict[str, Any] | None:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.capacity',
        parameters={'cluster_id': str(cluster_id), 'time_range': time_range},
    )
    if not result.available:
        return None
    context = result.context or {}
    capacity_summary = context.get('capacity_summary')
    if not isinstance(capacity_summary, dict):
        return None

    cpu = as_dict(capacity_summary.get('cpu', {}))
    memory = as_dict(capacity_summary.get('memory', {}))
    pods = as_dict(capacity_summary.get('pods', {}))
    recommendations = context.get('actionable_recommendations')
    return {
        'cpu_headroom': _available_number(cpu, 'available'),
        'cpu_unit': 'Cores',
        'memory_headroom': _available_number(memory, 'available'),
        'memory_unit': 'GiB',
        'pod_capacity_remaining': _available_number(pods, 'available'),
        'pod_unit': 'Pods',
        'recommendation_count': count_actionable_recommendations(
            recommendations if isinstance(recommendations, list) else []
        ),
    }


def _available_number(item: dict[str, Any], key: str) -> int | None:
    if item.get('evidence_available') is False:
        return None
    value = item.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
