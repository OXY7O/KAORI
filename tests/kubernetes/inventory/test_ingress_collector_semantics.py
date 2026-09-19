from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[3]
COLLECTOR_PATH = ROOT / 'app/kubernetes/inventory/collectors/ingresses.py'
SEMANTICS_PATH = ROOT / 'app/kubernetes/inventory/resources/ingress_semantics.py'


def _load_collector(monkeypatch: pytest.MonkeyPatch):
    app_module = ModuleType('app')
    inventory_module = ModuleType('app.inventory')
    collectors_module = ModuleType('app.kubernetes.inventory.collectors')

    common_spec = importlib.util.spec_from_file_location(
        'app.kubernetes.inventory.collectors.common',
        ROOT / 'app/kubernetes/inventory/collectors/common.py',
    )
    assert common_spec and common_spec.loader
    common_module = importlib.util.module_from_spec(common_spec)

    kubernetes_module = ModuleType('kubernetes')
    client_module = ModuleType('kubernetes.client')
    exceptions_module = ModuleType('kubernetes.client.exceptions')
    client_module.NetworkingV1Api = type('NetworkingV1Api', (), {})
    client_module.V1IngressList = type('V1IngressList', (), {})

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    exceptions_module.ApiException = ApiException
    for name, module in {
        'app': app_module,
        'app.inventory': inventory_module,
        'app.kubernetes.inventory.collectors': collectors_module,
        'app.kubernetes.inventory.collectors.common': common_module,
        'kubernetes': kubernetes_module,
        'kubernetes.client': client_module,
        'kubernetes.client.exceptions': exceptions_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    common_spec.loader.exec_module(common_module)

    spec = importlib.util.spec_from_file_location('ingress_collector_under_test', COLLECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, ApiException


def _load_semantics():
    spec = importlib.util.spec_from_file_location('ingress_semantics_under_test', SEMANTICS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(name='api', namespace='payments', annotations=None):
    return SimpleNamespace(
        name=name,
        namespace=namespace,
        uid=f'uid-{name}',
        labels={'app': name},
        annotations=annotations or {},
        finalizers=[],
        generation=4,
        creation_timestamp=datetime(2026, 8, 5, tzinfo=UTC),
    )


def _service_backend(name='api', port=443):
    return SimpleNamespace(
        service=SimpleNamespace(name=name, port=SimpleNamespace(name=None, number=port)),
        resource=None,
    )


def _resource_backend():
    return SimpleNamespace(
        service=None,
        resource=SimpleNamespace(api_group='storage.example.io', kind='Bucket', name='assets'),
    )


def _ingress(*, status=True, ingress_class='nginx'):
    rules = [
        SimpleNamespace(
            host='api.example.com',
            http=SimpleNamespace(paths=[SimpleNamespace(path='/api', path_type='Prefix', backend=_service_backend())]),
        ),
        SimpleNamespace(
            host=None,
            http=SimpleNamespace(
                paths=[SimpleNamespace(path='/assets', path_type='Prefix', backend=_resource_backend())]
            ),
        ),
    ]
    spec = SimpleNamespace(
        ingress_class_name=ingress_class,
        default_backend=None,
        rules=rules,
        tls=[SimpleNamespace(secret_name='api-tls', hosts=['api.example.com'])],
    )
    ingress_status = None
    if status is True:
        ingress_status = SimpleNamespace(
            load_balancer=SimpleNamespace(ingress=[SimpleNamespace(ip='203.0.113.10', hostname=None)])
        )
    elif status == 'pending':
        ingress_status = SimpleNamespace(load_balancer=SimpleNamespace(ingress=[]))
    return SimpleNamespace(metadata=_metadata(), spec=spec, status=ingress_status)


def test_collector_preserves_service_resource_and_hostless_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    rows, evidence = collector.get_ingresses(
        ingress_items=[_ingress()],
        with_evidence=True,
    )

    assert evidence == {'inventory.ingresses': 'Collected'}
    row = rows[0]
    assert row['ingress_class'] == 'nginx'
    assert row['details']['ingress_class_source'] == 'spec.ingressClassName'
    assert row['details']['hosts'] == ['api.example.com']
    assert row['details']['hostless_rule_count'] == 1
    assert row['details']['addresses'] == ['203.0.113.10']
    assert row['details']['publication_evidence_reported'] is True
    assert row['backend_paths'][0]['backend_type'] == 'Service'
    assert row['backend_paths'][0]['service_port'] == '443'
    assert row['backend_paths'][1]['backend_type'] == 'Resource'
    assert row['backend_paths'][1]['resource_kind'] == 'Bucket'
    assert 'host' not in row
    assert 'address' not in row


def test_pending_and_missing_publication_evidence_remain_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    semantics = _load_semantics()

    pending = collector.get_ingresses(ingress_items=[_ingress(status='pending')])[0]
    missing = collector.get_ingresses(ingress_items=[_ingress(status=False)])[0]

    assert semantics.publication_presentation(pending['details'])['label'] == 'Address Pending'
    assert semantics.publication_presentation(missing['details'])['label'] == 'Not Reported'


def test_legacy_annotation_and_provider_schema_normalize_to_canonical_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    legacy = {
        'metadata': {
            'name': 'legacy',
            'namespace': 'payments',
            'annotations': {'kubernetes.io/ingress.class': 'legacy-nginx'},
        },
        'spec': {
            'backend': {'serviceName': 'legacy-api', 'servicePort': 8080},
            'rules': [],
            'tls': [],
        },
        'status': {'loadBalancer': {'ingress': []}},
    }

    row = collector.get_ingresses(ingress_items=[legacy])[0]

    assert row['ingress_class'] == 'legacy-nginx'
    assert row['details']['ingress_class_source'] == 'kubernetes.io/ingress.class annotation'
    assert row['backend_paths'][0]['route_source'] == 'Default Backend'
    assert row['backend_paths'][0]['service_name'] == 'legacy-api'
    assert row['backend_paths'][0]['service_port'] == '8080'


def test_permission_and_api_unavailable_are_committed_without_hiding_server_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, ApiException = _load_collector(monkeypatch)

    def forbidden():
        raise ApiException(status=403)

    rows, evidence = collector.get_ingresses(
        SimpleNamespace(list_ingress_for_all_namespaces=forbidden),
        with_evidence=True,
    )
    assert rows == []
    assert evidence['inventory.ingresses'] == 'Permission Unavailable'

    def server_error():
        raise ApiException(status=500)

    with pytest.raises(ApiException):
        collector.get_ingresses(SimpleNamespace(list_ingress_for_all_namespaces=server_error))


def test_invalid_ingress_identity_or_missing_spec_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    invalid_name = _ingress()
    invalid_name.metadata.name = None
    invalid_spec = _ingress()
    invalid_spec.spec = None

    assert collector.get_ingresses(ingress_items=[invalid_name, invalid_spec]) == []
