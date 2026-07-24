from __future__ import annotations

from app.inventory.formatting import (
    convert_storage_to_gib,
    format_gib,
    format_kubernetes_size,
    format_quota_value,
)
from app.inventory.resources.ingresses import _ingress_summary
from app.inventory.resources.workloads import _workload_pod_template


def test_inventory_kubernetes_quantities_have_stable_human_readable_units() -> None:
    assert format_kubernetes_size('1024Ki') == '1 MiB'
    assert format_kubernetes_size('1Gi') == '1 GiB'
    assert format_kubernetes_size('1G') == '953.7 MiB'
    assert format_kubernetes_size('-') == '-'
    assert format_kubernetes_size('invalid') == '-'


def test_inventory_storage_conversion_and_quota_formatting_are_consistent() -> None:
    assert convert_storage_to_gib('1048576Ki') == 1.0
    assert format_gib(1.5) == '1.5 GiB'
    assert format_gib(0) == '-'
    assert format_quota_value('requests.memory', '1024Mi') == '1 GiB'
    assert format_quota_value('pods', '25') == '25'


def test_workload_configuration_accepts_only_authoritative_schema_v2_templates() -> None:
    reported = {
        'reported': True,
        'container_count': 2,
        'containers': [{'name': 'api'}, {'name': 'sidecar'}],
    }

    assert _workload_pod_template({'pod_template': reported}) == reported
    assert _workload_pod_template({'pod_template': {'reported': False, 'container_count': 2}}) == {}
    assert _workload_pod_template({}) == {}


def test_ingress_summary_uses_the_active_filtered_rows() -> None:
    tls_enabled, hosts, classes, namespaces = _ingress_summary(
        [
            (True, 'fallback.example.com', 'nginx', 'team-a', {'hosts': ['api.example.com']}),
            (False, 'internal.example.com', 'nginx', 'team-b', {}),
        ]
    )

    assert tls_enabled == 1
    assert hosts == {'api.example.com', 'internal.example.com'}
    assert classes == {'nginx'}
    assert namespaces == {'team-a', 'team-b'}
