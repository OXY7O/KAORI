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


def get_empty_capacity_payload(
    selected_time_range: str,
) -> dict[str, Any]:
    empty_pagination = get_empty_pagination()

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
            'cpu': {
                'capacity': 0,
                'used': 0,
                'available': 0,
                'headroom': 0,
            },
            'memory': {
                'capacity': 0,
                'used': 0,
                'available': 0,
                'headroom': 0,
            },
            'storage': {
                'capacity': 0,
                'used': 0,
                'available': 0,
                'headroom': 0,
            },
            'pods': {
                'capacity': 0,
                'used': 0,
                'available': 0,
                'headroom': 0,
            },
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
            'cpu': {
                'title': 'CPU',
                'status': {
                    'label': 'Unknown',
                    'class': 'bg-slate-100 text-slate-700',
                },
                'items': [],
            },
            'memory': {
                'title': 'Memory',
                'status': {
                    'label': 'Unknown',
                    'class': 'bg-slate-100 text-slate-700',
                },
                'items': [],
            },
            'pods': {
                'title': 'Pods',
                'status': {
                    'label': 'Unknown',
                    'class': 'bg-slate-100 text-slate-700',
                },
                'items': [],
            },
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
            'resource_status_options': [],
            'qos_options': [],
            'risk_options': [],
        },
        'workload_mapping_rows': [],
        'quota_coverage': {
            'total_namespaces': 0,
            'quota_namespaces': 0,
            'coverage_percent': 0,
        },
        'risk_summary': [],
        'governance_findings': [
            {
                'label': 'No capacity data available',
                'severity': 'warning',
                'icon': 'triangle-alert',
                'filter': '',
            },
        ],
        'recommendation_cards': [
            {
                'title': 'Connect Prometheus Metrics',
                'description': (
                    'Capacity analysis requires Prometheus metrics to calculate '
                    'worker headroom, allocation, and capacity risk.'
                ),
                'icon': 'plug-zap',
                'icon_class': 'bg-amber-100 text-amber-600',
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
    empty_pagination = get_empty_pagination()

    return {
        'storage_summary': {
            'node_filesystem': {
                'selected_node': '',
                'available_nodes': [],
                'summary': {
                    'capacity': '-',
                    'used': '-',
                    'free': '-',
                    'usage_percent': 0,
                    'free_percent': 0,
                    'highest_usage': 0,
                    'highest_node': '-',
                },
                'rows': [],
            },
            'persistent_storage': {
                'pv': {
                    'count': 0,
                    'capacity': '-',
                    'used': '-',
                    'free': '-',
                    'used_percent': 0,
                    'free_percent': 0,
                },
                'pvc': {
                    'count': 0,
                    'requested': '-',
                    'used': '-',
                    'free': '-',
                    'used_percent': 0,
                    'free_percent': 0,
                },
                'pvc_rows': [],
                'pvc_pagination': empty_pagination,
                'pvc_selected_search': '',
                'pvc_status_options': [],
                'pvc_storage_class_options': [],
                'pvc_selected_status': '',
                'pvc_selected_storage_class': '',
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
        'selected_storage_tab': 'pvc',
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
            'resource_status_options': [],
            'qos_options': [],
            'risk_options': [],
        },
        'workload_mapping_rows': [],
        'recommendation_cards': [],
        'governance_findings': [],
        'selected_namespace': selected_namespace,
        'selected_time_range': selected_time_range,
        'selected_tenant_search': '',
        'selected_tenant_quota_status': '',
        'selected_tenant_risk': '',
        'selected_workload_search': '',
        'selected_workload_type': '',
        'selected_workload_resource_status': '',
        'selected_workload_qos': '',
        'selected_workload_risk': '',
    }
