from __future__ import annotations

from app.analytics.workload.service import (
    filter_tenant_quota_rows,
    filter_workload_rows,
    format_count,
    format_cpu_core,
    format_memory_gib,
    get_workload_time_step,
)


def test_workload_time_ranges_and_display_units_are_stable() -> None:
    assert get_workload_time_step('1h') == '5m'
    assert get_workload_time_step('60d') == '1d'
    assert get_workload_time_step('unknown') == '1h'
    assert format_cpu_core(1.234) == '1.23 core'
    assert format_memory_gib(1024**3) == '1.00 GiB'
    assert format_count(2.6) == '3'


def test_tenant_quota_filters_apply_all_selected_dimensions() -> None:
    rows = [
        {
            'namespace': 'payments-prod',
            'quota_status': {'label': 'Configured'},
            'risk': {'label': 'Warning'},
        },
        {
            'namespace': 'payments-dev',
            'quota_status': {'label': 'Missing'},
            'risk': {'label': 'Critical'},
        },
    ]

    assert filter_tenant_quota_rows(
        rows,
        selected_search='PROD',
        selected_quota_status='Configured',
        selected_risk='Warning',
    ) == [rows[0]]


def test_workload_filters_match_identity_and_operational_labels() -> None:
    rows = [
        {
            'workload': 'payments-api',
            'namespace': 'production',
            'type': 'Deployment',
            'resource_status': {'label': 'Configured'},
            'qos': {'label': 'Burstable'},
            'risk': {'label': 'Warning'},
        },
        {
            'workload': 'worker',
            'namespace': 'development',
            'type': 'StatefulSet',
            'resource_status': {'label': 'Missing'},
            'qos': {'label': 'BestEffort'},
            'risk': {'label': 'Critical'},
        },
    ]

    assert filter_workload_rows(
        rows,
        selected_search='PAYMENTS-API PROD',
        selected_type='Deployment',
        selected_resource_status='Configured',
        selected_qos='Burstable',
        selected_risk='Warning',
    ) == [rows[0]]
