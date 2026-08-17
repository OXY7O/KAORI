# app/kubernetes/analytics/common/payloads.py

from __future__ import annotations

from typing import Any

from app.common.analytics.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_allowed_time_ranges,
)


def get_empty_pagination() -> dict[str, Any]:
    return {
        'page': 1,
        'per_page': 5,
        'total_items': 0,
        'total_pages': 1,
        'start_item': 0,
        'end_item': 0,
        'has_previous': False,
        'has_next': False,
        'previous_page': 1,
        'next_page': 1,
        'per_page_options': ALLOWED_PER_PAGE_VALUES,
    }


def get_capacity_review_paths() -> list[dict[str, str]]:
    return [
        {
            'label': 'Review Workload Analysis',
            'description': 'Inspect quota, request, limit, and workload right-sizing evidence.',
            'icon': 'boxes',
            'href': '/analytics/workload',
        },
        {
            'label': 'Review Storage Analysis',
            'description': 'Inspect persistent volume, claim, and filesystem capacity evidence.',
            'icon': 'hard-drive',
            'href': '/analytics/storage',
        },
    ]


def get_empty_capacity_payload(
    selected_time_range: str,
) -> dict[str, Any]:
    empty_pagination = get_empty_pagination()

    empty_resource = {
        'evidence_available': False,
        'capacity_evidence_available': False,
        'usage_evidence_available': False,
        'capacity': None,
        'used': None,
        'available': None,
        'headroom': None,
        'scheduling_resource': True,
        'scope_label': 'Ready worker allocatable capacity',
    }
    unknown_allocation = {
        'available': False,
        'complete': False,
        'status': {
            'label': 'Unknown',
            'tone': 'unknown',
            'reason': 'Allocatable capacity evidence is unavailable.',
            'missing_metrics': [],
        },
        'items': [],
        'missing_metrics': [],
    }

    return {
        'cluster_info': {
            'kubernetes_version': '-',
            'total_nodes': 0,
            'ready_nodes': None,
            'not_ready_nodes': None,
            'worker_nodes': None,
            'ready_worker_nodes': None,
            'not_ready_worker_nodes': None,
            'worker_node_evidence_available': False,
            'master_nodes': 0,
        },
        'capacity_posture': {
            'label': 'Unknown',
            'tone': 'unknown',
            'reason': 'Ready-worker scheduling evidence is unavailable.',
            'evidence_complete': False,
        },
        'capacity_summary': {
            'cpu': dict(empty_resource),
            'memory': dict(empty_resource),
            'storage': {
                **empty_resource,
                'scheduling_resource': False,
                'scope_label': ('Operational node-filesystem reference; not Kubernetes allocatable capacity'),
            },
            'pods': dict(empty_resource),
        },
        'worker_capacity_summary': {
            'title': 'Worker Capacity Summary',
            'subtitle': (
                'Schedulable capacity is calculated from Ready worker nodes. '
                'Control-plane nodes are shown for context only.'
            ),
            'cards': [],
        },
        'allocation_summary': {
            'cpu': {'title': 'CPU', **unknown_allocation},
            'memory': {'title': 'Memory', **unknown_allocation},
            'pods': {'title': 'Pods', **unknown_allocation},
        },
        'storage_summary': {},
        'tenant_quota_summary': {
            'scope_evidence_available': False,
            'scope_total': 0,
            'scope_covered': 0,
            'scope_quota_coverage_percent': 0.0,
            'scope_quota_coverage_display': 'N/A',
            'scope_near_limit_count': 0,
            'scope_efficiency_risk_count': 0,
            'summary_cards': [],
            'rows': [],
            'pagination': empty_pagination,
        },
        'tenant_quota_rows': [],
        'quota_status_options': [],
        'tenant_risk_options': [],
        'workload_mapping_payload': {
            'rows': [],
            'filters': {},
            'pagination': empty_pagination,
            'workload_type_options': [],
            'configuration_options': [],
            'qos_options': [],
            'risk_options': [],
            'scope_summary': {
                'scope_evidence_available': False,
                'scope_total': 0,
                'scope_request_complete': 0,
                'scope_request_coverage_percent': 0.0,
                'scope_request_coverage_display': 'N/A',
                'scope_best_effort_count': 0,
                'scope_high_risk_count': 0,
                'scope_complete_evidence_count': 0,
            },
        },
        'workload_scope_summary': {
            'scope_evidence_available': False,
            'scope_total': 0,
            'scope_request_complete': 0,
            'scope_request_coverage_percent': 0.0,
            'scope_request_coverage_display': 'N/A',
            'scope_best_effort_count': 0,
            'scope_high_risk_count': 0,
            'scope_complete_evidence_count': 0,
        },
        'workload_mapping_rows': [],
        'quota_coverage': {
            'total_namespaces': 0,
            'quota_namespaces': 0,
            'coverage_percent': 0,
        },
        'risk_summary': [
            {
                'resource': resource,
                'label': {'cpu': 'CPU', 'memory': 'Memory', 'pods': 'Pods', 'storage': 'Node Filesystem'}[resource],
                'headroom': None,
                'evidence_available': False,
                'scheduling_resource': resource != 'storage',
                'scope_label': (
                    'Operational node-filesystem reference; not Kubernetes allocatable capacity'
                    if resource == 'storage'
                    else 'Ready worker allocatable capacity'
                ),
                'status': {'label': 'Unknown', 'tone': 'unknown'},
                'icon': icon,
            }
            for resource, icon in (
                ('cpu', 'cpu'),
                ('memory', 'memory-stick'),
                ('pods', 'boxes'),
                ('storage', 'hard-drive'),
            )
        ],
        'governance_findings': [
            {
                'label': 'No capacity data available',
                'severity': 'warning',
                'tone': 'warning',
                'icon': 'triangle-alert',
                'filter': '',
            },
        ],
        'review_paths': get_capacity_review_paths(),
        'recommendation_cards': [
            {
                'title': 'Connect Metrics Source Metrics',
                'description': (
                    'Capacity analysis requires metrics data from the selected Metrics Source to calculate '
                    'worker headroom, allocation, and capacity risk.'
                ),
                'priority': 'Info',
                'source': 'capacity',
                'source_label': 'Capacity Analysis',
                'icon': 'plug-zap',
                'target_tab': 'summary',
            },
        ],
        'kpi_cards': [],
        'selected_time_range': selected_time_range,
        'allowed_time_ranges': get_allowed_time_ranges(),
    }


def get_empty_storage_payload(
    selected_namespace: str,
) -> dict[str, Any]:
    empty_pagination = get_empty_pagination()
    unknown_risk = {'label': 'Unknown', 'tone': 'unknown'}
    return {
        'storage_summary': {
            'node_filesystem': {
                'query_observed': False,
                'selected_node': '',
                'available_nodes': [],
                'scope_label': 'All Nodes',
                'summary': {
                    'query_observed': False,
                    'evidence_available': False,
                    'evidence_complete': False,
                    'observed_node_count': 0,
                    'complete_node_count': 0,
                    'incomplete_node_count': 0,
                    'capacity': 'N/A',
                    'used': 'N/A',
                    'free': 'N/A',
                    'usage_percent': None,
                    'free_percent': None,
                    'highest_usage': None,
                    'highest_node': '-',
                    'highest_mountpoint': '-',
                    'risk': unknown_risk,
                },
                'all_rows': [],
                'rows': [],
                'pagination': empty_pagination,
            },
            'persistent_storage': {
                'pvc_inventory_observed': False,
                'pvc_status_observed': False,
                'pv_inventory_observed': False,
                'pv_status_observed': False,
                'pv': {
                    'inventory_evidence_available': False,
                    'status_evidence_available': False,
                    'capacity_evidence_available': False,
                    'capacity_evidence_complete': False,
                    'requested_claim_evidence_available': False,
                    'requested_claim_evidence_complete': False,
                    'observed_claim_usage_evidence_available': False,
                    'observed_claim_usage_evidence_complete': False,
                    'unallocated_evidence_available': False,
                    'evidence_available': False,
                    'evidence_complete': False,
                    'has_resources': False,
                    'count': 0,
                    'count_display': 'N/A',
                    'capacity_observed_count': 0,
                    'total_claim_count': 0,
                    'requested_claim_observed_count': 0,
                    'observed_claim_usage_count': 0,
                    'requested_claim_gap_count': 0,
                    'observed_claim_usage_gap_count': 0,
                    'requested_claim_coverage_percent': None,
                    'observed_claim_usage_coverage_percent': None,
                    'requested_claim_coverage_display': 'N/A',
                    'observed_claim_usage_coverage_display': 'N/A',
                    'capacity': 'N/A',
                    'observed_claim_usage': 'N/A',
                    'requested_claim_capacity': 'N/A',
                    'unallocated_provisioned_difference': 'N/A',
                    'claim_usage_vs_provisioned_percent': None,
                    'requested_vs_provisioned_percent': None,
                    'scope_label': 'Cluster',
                    'risk': unknown_risk,
                    'critical_count': 0,
                    'warning_count': 0,
                    'unknown_count': 0,
                },
                'pvc': {
                    'inventory_evidence_available': False,
                    'status_evidence_available': False,
                    'requested_evidence_available': False,
                    'capacity_evidence_available': False,
                    'used_evidence_available': False,
                    'free_evidence_available': False,
                    'pressure_evidence_available': False,
                    'requested_evidence_complete': False,
                    'capacity_evidence_complete': False,
                    'used_evidence_complete': False,
                    'free_evidence_complete': False,
                    'pressure_evidence_complete': False,
                    'evidence_available': False,
                    'evidence_complete': False,
                    'has_resources': False,
                    'count': 0,
                    'count_display': 'N/A',
                    'total_pvc_count': 0,
                    'requested_observed_count': 0,
                    'capacity_observed_count': 0,
                    'used_observed_count': 0,
                    'free_observed_count': 0,
                    'pressure_observed_count': 0,
                    'evidence_gap_count': 0,
                    'requested_coverage_percent': None,
                    'capacity_coverage_percent': None,
                    'used_coverage_percent': None,
                    'free_coverage_percent': None,
                    'pressure_coverage_percent': None,
                    'requested_coverage_display': 'N/A',
                    'capacity_coverage_display': 'N/A',
                    'used_coverage_display': 'N/A',
                    'free_coverage_display': 'N/A',
                    'pressure_coverage_display': 'N/A',
                    'requested': 'N/A',
                    'capacity': 'N/A',
                    'used': 'N/A',
                    'free': 'N/A',
                    'pressure_capacity': 'N/A',
                    'pressure_used': 'N/A',
                    'pressure_free': 'N/A',
                    'used_percent': None,
                    'free_percent': None,
                    'scope_label': (f'Namespace · {selected_namespace}' if selected_namespace else 'All Namespaces'),
                    'risk': unknown_risk,
                    'critical_count': 0,
                    'warning_count': 0,
                    'unknown_count': 0,
                },
                'pvc_all_rows': [],
                'pvc_rows': [],
                'pvc_pagination': empty_pagination,
                'pvc_selected_search': '',
                'pvc_status_options': [],
                'pvc_storage_class_options': [],
                'pvc_selected_status': '',
                'pvc_selected_storage_class': '',
                'pv_all_rows': [],
                'pv_rows': [],
                'pv_pagination': empty_pagination,
                'pv_selected_search': '',
                'pv_status_options': [],
                'pv_storage_class_options': [],
                'pv_selected_status': '',
                'pv_selected_storage_class': '',
            },
        },
        'storage_posture': {
            'label': 'Unknown',
            'tone': 'unknown',
            'reason': 'No committed storage evidence is available.',
            'evidence_complete': False,
            'critical_count': 0,
            'warning_count': 0,
        },
        'storage_pressure_lanes': [],
        'storage_evidence': {},
        'namespace_options': [],
        'selected_namespace': selected_namespace,
        'selected_time_range': 'current',
        'allowed_time_ranges': (),
        'selected_storage_node': '',
        'selected_storage_tab': 'capacity',
        'initial_tab': 'capacity',
        'selected_pvc_search': '',
        'selected_pvc_status': '',
        'selected_pvc_storage_class': '',
        'selected_pv_search': '',
        'selected_pv_status': '',
        'selected_pv_storage_class': '',
    }


def get_empty_workload_payload(
    selected_namespace: str,
    selected_time_range: str,
) -> dict[str, Any]:
    empty_pagination = get_empty_pagination()

    return {
        'namespace_options': [],
        'tenant_quota_summary': {
            'scope_evidence_available': False,
            'scope_total': 0,
            'scope_covered': 0,
            'scope_quota_coverage_percent': 0.0,
            'scope_quota_coverage_display': 'N/A',
            'scope_near_limit_count': 0,
            'scope_efficiency_risk_count': 0,
            'summary_cards': [],
            'rows': [],
            'pagination': empty_pagination,
        },
        'tenant_quota_rows': [],
        'quota_status_options': [],
        'tenant_risk_options': [],
        'workload_mapping_payload': {
            'rows': [],
            'filters': {},
            'pagination': empty_pagination,
            'workload_type_options': [],
            'configuration_options': [],
            'qos_options': [],
            'risk_options': [],
            'scope_summary': {
                'scope_evidence_available': False,
                'scope_total': 0,
                'scope_request_complete': 0,
                'scope_request_coverage_percent': 0.0,
                'scope_request_coverage_display': 'N/A',
                'scope_best_effort_count': 0,
                'scope_high_risk_count': 0,
                'scope_complete_evidence_count': 0,
            },
        },
        'workload_mapping_rows': [],
        'workload_scope_summary': {
            'scope_evidence_available': False,
            'scope_total': 0,
            'scope_request_complete': 0,
            'scope_request_coverage_percent': 0.0,
            'scope_request_coverage_display': 'N/A',
            'scope_best_effort_count': 0,
            'scope_high_risk_count': 0,
            'scope_complete_evidence_count': 0,
        },
        'recommendation_cards': [],
        'governance_findings': [],
        'selected_namespace': selected_namespace,
        'selected_time_range': selected_time_range,
        'selected_tenant_search': '',
        'selected_tenant_quota_status': '',
        'selected_tenant_risk': '',
        'selected_workload_search': '',
        'selected_workload_type': '',
        'selected_workload_configuration': '',
        'selected_workload_qos': '',
        'selected_workload_risk': '',
    }
