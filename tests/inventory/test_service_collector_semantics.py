from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = ROOT / 'app/inventory/collectors/services.py'
SEMANTICS_PATH = ROOT / 'app/inventory/resources/service_semantics.py'


def _load_collector(monkeypatch: pytest.MonkeyPatch):
    app_module = ModuleType('app')
    inventory_module = ModuleType('app.inventory')
    collectors_module = ModuleType('app.inventory.collectors')
    common_module = ModuleType('app.inventory.collectors.common')

    common_module._string_value = lambda value, default='-': default if value in (None, '') else str(value)
    common_module._metadata_details = lambda metadata: {
        'uid': getattr(metadata, 'uid', None),
        'labels': dict(getattr(metadata, 'labels', None) or {}),
        'annotations': dict(getattr(metadata, 'annotations', None) or {}),
    }

    kubernetes_module = ModuleType('kubernetes')
    client_module = ModuleType('kubernetes.client')
    exceptions_module = ModuleType('kubernetes.client.exceptions')
    for name in (
        'CoreV1Api',
        'DiscoveryV1Api',
        'V1EndpointSliceList',
        'V1EndpointsList',
        'V1ServiceList',
    ):
        setattr(client_module, name, type(name, (), {}))

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    exceptions_module.ApiException = ApiException
    modules = {
        'app': app_module,
        'app.inventory': inventory_module,
        'app.inventory.collectors': collectors_module,
        'app.inventory.collectors.common': common_module,
        'kubernetes': kubernetes_module,
        'kubernetes.client': client_module,
        'kubernetes.client.exceptions': exceptions_module,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location('service_collector_under_test', COLLECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, ApiException


def _load_semantics():
    spec = importlib.util.spec_from_file_location('service_semantics_under_test', SEMANTICS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(name='api', namespace='payments'):
    return SimpleNamespace(
        name=name,
        namespace=namespace,
        uid=f'uid-{name}',
        labels={'app': name},
        annotations={},
        generation=3,
        creation_timestamp=datetime(2026, 8, 5, tzinfo=UTC),
    )


def _port(value=443, target='8443', node_port=30443):
    return SimpleNamespace(
        name='https',
        protocol='TCP',
        port=value,
        target_port=target,
        node_port=node_port,
        app_protocol='https',
    )


def _service(*, name='api', namespace='payments', service_type='LoadBalancer', ports=None, external_ips=None):
    spec = SimpleNamespace(
        type=service_type,
        cluster_ip='10.96.0.10',
        cluster_ips=['10.96.0.10'],
        ip_families=['IPv4'],
        ip_family_policy='SingleStack',
        external_name=None,
        external_ips=external_ips or [],
        selector={'app': 'api'},
        ports=ports or [_port()],
        session_affinity='None',
        internal_traffic_policy='Cluster',
        external_traffic_policy='Local',
        publish_not_ready_addresses=False,
        health_check_node_port=32000,
        load_balancer_class=None,
        allocate_load_balancer_node_ports=True,
    )
    status = SimpleNamespace(
        load_balancer=SimpleNamespace(
            ingress=[SimpleNamespace(ip='203.0.113.10', hostname=None)]
        )
    )
    return SimpleNamespace(metadata=_metadata(name, namespace), spec=spec, status=status)


def _endpoint_slice(*, duplicate=False):
    endpoint = SimpleNamespace(
        addresses=['10.0.0.10', '10.0.0.10'] if duplicate else ['10.0.0.10'],
        hostname=None,
        node_name='worker-1',
        target_ref=SimpleNamespace(kind='Pod', name='api-7d9f'),
        conditions=SimpleNamespace(ready=True, serving=True, terminating=False),
    )
    port = SimpleNamespace(name='https', port=8443, protocol='TCP', app_protocol='https')
    return SimpleNamespace(
        metadata=SimpleNamespace(
            namespace='payments',
            labels={'kubernetes.io/service-name': 'api'},
        ),
        endpoints=[endpoint],
        ports=[port, port] if duplicate else [port],
    )


def test_endpoint_slice_collection_deduplicates_backend_and_port_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    core_api = SimpleNamespace(
        list_service_for_all_namespaces=lambda: SimpleNamespace(items=[_service()]),
        list_endpoints_for_all_namespaces=lambda: SimpleNamespace(items=[]),
    )
    discovery_api = SimpleNamespace(
        list_endpoint_slice_for_all_namespaces=lambda: SimpleNamespace(items=[_endpoint_slice(duplicate=True)])
    )

    rows, evidence = collector.get_services(core_api, discovery_api, with_evidence=True)

    assert evidence['inventory.services.backend-registration'] == 'Collected'
    assert rows[0]['details']['endpoints']['source'] == 'EndpointSlice'
    assert len(rows[0]['details']['endpoints']['ready_addresses']) == 1
    assert len(rows[0]['details']['endpoints']['ports']) == 1
    assert rows[0]['details']['endpoints']['ready_addresses'][0]['serving'] is True


def test_endpoint_slice_permission_failure_uses_endpoints_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, ApiException = _load_collector(monkeypatch)
    endpoint_record = SimpleNamespace(
        metadata=SimpleNamespace(namespace='payments', name='api'),
        subsets=[
            SimpleNamespace(
                addresses=[SimpleNamespace(ip='10.0.0.11', hostname=None, node_name='worker-2', target_ref=None)],
                not_ready_addresses=[],
                ports=[SimpleNamespace(name='https', port=8443, protocol='TCP', app_protocol=None)],
            )
        ],
    )
    core_api = SimpleNamespace(
        list_service_for_all_namespaces=lambda: SimpleNamespace(items=[_service()]),
        list_endpoints_for_all_namespaces=lambda: SimpleNamespace(items=[endpoint_record]),
    )

    def forbidden():
        raise ApiException(status=403)

    rows, evidence = collector.get_services(
        core_api,
        SimpleNamespace(list_endpoint_slice_for_all_namespaces=forbidden),
        with_evidence=True,
    )

    assert evidence['inventory.services.backend-registration'] == 'Collected'
    assert rows[0]['details']['endpoints']['source'] == 'Endpoints'
    assert rows[0]['details']['endpoints']['ready_addresses'][0]['ip'] == '10.0.0.11'


def test_unexpected_endpoint_slice_error_is_not_hidden_by_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, ApiException = _load_collector(monkeypatch)
    core_api = SimpleNamespace(
        list_service_for_all_namespaces=lambda: SimpleNamespace(items=[_service()]),
        list_endpoints_for_all_namespaces=lambda: SimpleNamespace(items=[]),
    )

    def server_error():
        raise ApiException(status=500)

    with pytest.raises(ApiException):
        collector.get_services(
            core_api,
            SimpleNamespace(list_endpoint_slice_for_all_namespaces=server_error),
        )


def test_missing_backend_permissions_are_committed_as_missing_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, ApiException = _load_collector(monkeypatch)

    def forbidden():
        raise ApiException(status=403)

    core_api = SimpleNamespace(
        list_service_for_all_namespaces=lambda: SimpleNamespace(items=[_service()]),
        list_endpoints_for_all_namespaces=forbidden,
    )
    rows, evidence = collector.get_services(
        core_api,
        SimpleNamespace(list_endpoint_slice_for_all_namespaces=forbidden),
        with_evidence=True,
    )

    assert evidence['inventory.services.backend-registration'] == 'Permission Unavailable'
    assert rows[0]['details']['endpoints']['reported'] is False


def test_invalid_service_identity_is_skipped_and_canonical_details_are_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    many_ports = [_port(value=10000 + index, target=str(20000 + index), node_port=30000 + index) for index in range(60)]
    many_ips = [f'203.0.113.{index}' for index in range(1, 40)]
    invalid = _service(name=None)
    valid = _service(ports=many_ports, external_ips=many_ips)
    core_api = SimpleNamespace(
        list_service_for_all_namespaces=lambda: SimpleNamespace(items=[invalid, valid]),
        list_endpoints_for_all_namespaces=lambda: SimpleNamespace(items=[]),
    )

    rows = collector.get_services(core_api)

    assert len(rows) == 1
    assert 'ports' not in rows[0]
    assert 'external_ip' not in rows[0]
    assert len(rows[0]['details']['ports']) == 60
    assert len(rows[0]['details']['external_addresses']) >= len(many_ips)


def test_selectorless_service_does_not_hide_missing_endpoint_evidence() -> None:
    semantics = _load_semantics()
    missing = semantics.backend_registration('ClusterIP', {}, {'reported': False, 'source': 'Endpoints'})
    empty_manual = semantics.backend_registration(
        'ClusterIP',
        {},
        {'reported': True, 'source': 'EndpointSlice', 'ready_addresses': [], 'not_ready_addresses': []},
    )

    assert missing['label'] == 'Not Reported'
    assert missing['exception'] is True
    assert empty_manual['label'] == 'Manually Managed'
    assert empty_manual['exception'] is True
    assert empty_manual['tone'] == 'warning'
