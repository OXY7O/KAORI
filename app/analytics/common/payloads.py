# app/analytics/common/payloads.py

from __future__ import annotations

from typing import Any

from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_allowed_time_ranges,
)


def get_empty_pagination() -> dict[str, Any]:
    return {
        'page': 1,
        'per_page': 10,
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
        'capacity': 0,
        'used': 0,
        'available': 0,
        'headroom': 0,
    }
    unknown_allocation = {
        'available': False,
        'status': {'label': 'Unknown', 'tone': 'unknown'},
        'items': [],
    }

    return {
        'cluster_info': {
            'kubernetes_version': '-',
            'total_nodes': 0,
            'ready_nodes': 0,
            'not_ready_nodes': 0,
            'worker_nodes': 0,
            'master_nodes': 0,
            'cpu_capacity': 0,
            'memory_capacity': 0,
            'pod_capacity': 0,
        },
        'capacity_summary': {
            'cpu': dict(empty_resource),
            'memory': dict(empty_resource),
            'storage': dict(empty_resource),
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
                'scope_total': 0,
                'scope_request_complete': 0,
                'scope_request_coverage_percent': 0.0,
                'scope_best_effort_count': 0,
                'scope_high_risk_count': 0,
                'scope_complete_evidence_count': 0,
            },
        },
        'workload_scope_summary': {
            'scope_total': 0,
            'scope_request_complete': 0,
            'scope_request_coverage_percent': 0.0,
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
                'label': 'Pods' if resource == 'pods' else resource.title(),
                'headroom': None,
                'evidence_available': False,
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
                'title': 'Connect Prometheus Metrics',
                'description': (
                    'Capacity analysis requires Prometheus metrics to calculate '
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
    selected_time_range: str,
) -> dict[str, Any]:
    empty_pagination = {**get_empty_pagination(), 'per_page': 5}

    return {
        'storage_summary': {
            'node_filesystem': {
                'selected_node': '',
                'available_nodes': [],
                'scope_label': 'All Nodes',
                'summary': {
                    'evidence_available': False,
                    'capacity': 'N/A',
                    'used': 'N/A',
                    'free': 'N/A',
                    'usage_percent': None,
                    'free_percent': None,
                    'highest_usage': None,
                    'highest_node': '-',
                    'risk': {'label': 'Unknown', 'tone': 'unknown'},
                },
                'all_rows': [],
                'rows': [],
                'pagination': empty_pagination,
            },
            'persistent_storage': {
                'pv': {
                    'evidence_available': False,
                    'count': 0,
                    'capacity': 'N/A',
                    'observed_claim_usage': 'N/A',
                    'requested_claim_capacity': 'N/A',
                    'unallocated_provisioned_difference': 'N/A',
                    'claim_usage_vs_provisioned_percent': None,
                    'requested_vs_provisioned_percent': None,
                    'scope_label': 'Cluster',
                },
                'pvc': {
                    'evidence_available': False,
                    'count': 0,
                    'requested': 'N/A',
                    'used': 'N/A',
                    'free': 'N/A',
                    'used_percent': None,
                    'free_percent': None,
                    'scope_label': f'Namespace · {selected_namespace}' if selected_namespace else 'All Namespaces',
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
        'namespace_options': [],
        'selected_namespace': selected_namespace,
        'selected_time_range': selected_time_range,
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
                'scope_total': 0,
                'scope_request_complete': 0,
                'scope_request_coverage_percent': 0.0,
                'scope_best_effort_count': 0,
                'scope_high_risk_count': 0,
                'scope_complete_evidence_count': 0,
            },
        },
        'workload_mapping_rows': [],
        'workload_scope_summary': {
            'scope_total': 0,
            'scope_request_complete': 0,
            'scope_request_coverage_percent': 0.0,
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
