from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_PATH = ROOT / 'app/reports/export/payloads/inventory.py'
INGRESS_SEMANTICS_PATH = ROOT / 'app/inventory/resources/ingress_semantics.py'
SEMANTICS_PATH = ROOT / 'app/inventory/resources/service_semantics.py'


def _load_payload(monkeypatch: pytest.MonkeyPatch):
    module_names = (
        'app',
        'app.common',
        'app.common.inventory_generation',
        'app.extensions',
        'app.extensions.db',
        'app.inventory',
        'app.inventory.formatting',
        'app.inventory.resources',
        'app.models',
        'app.models.report',
        'app.reports',
        'app.reports.catalog',
        'app.reports.export',
        'app.reports.export.payloads',
        'app.reports.export.payloads.common',
    )
    modules = {name: ModuleType(name) for name in module_names}
    for name in (
        'app',
        'app.common',
        'app.extensions',
        'app.inventory',
        'app.inventory.resources',
        'app.models',
        'app.reports',
        'app.reports.export',
        'app.reports.export.payloads',
    ):
        modules[name].__path__ = []

    modules['app.common.inventory_generation'].filter_current_generation = lambda query, _model: query
    modules['app.extensions.db'].db = SimpleNamespace()
    modules['app.inventory.formatting'].format_kubernetes_size = lambda value: '-' if value is None else str(value)

    model_names = (
        'Cluster',
        'ClusterInventory',
        'ConfigurationInventory',
        'IngressInventory',
        'NamespaceInventory',
        'NodeInventory',
        'PodInventory',
        'ServiceInventory',
        'StorageInventory',
        'WorkloadInventory',
    )
    for name in model_names:
        setattr(modules['app.models'], name, type(name, (), {}))
    modules['app.models.report'].Report = type('Report', (), {})
    modules['app.reports.catalog'].require_selected_cluster = lambda _report: 'cluster-id'
    modules['app.reports.export.payloads.common'].get_report_selected_cluster = lambda _report: None

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    ingress_spec = importlib.util.spec_from_file_location(
        'app.inventory.resources.ingress_semantics',
        INGRESS_SEMANTICS_PATH,
    )
    assert ingress_spec and ingress_spec.loader
    ingress_semantics = importlib.util.module_from_spec(ingress_spec)
    monkeypatch.setitem(sys.modules, 'app.inventory.resources.ingress_semantics', ingress_semantics)
    ingress_spec.loader.exec_module(ingress_semantics)

    semantics_spec = importlib.util.spec_from_file_location(
        'app.inventory.resources.service_semantics',
        SEMANTICS_PATH,
    )
    assert semantics_spec and semantics_spec.loader
    semantics = importlib.util.module_from_spec(semantics_spec)
    monkeypatch.setitem(sys.modules, 'app.inventory.resources.service_semantics', semantics)
    semantics_spec.loader.exec_module(semantics)

    spec = importlib.util.spec_from_file_location('service_export_payload_under_test', PAYLOAD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _service(details: dict, **overrides):
    values = {
        'service_type': 'LoadBalancer',
        'cluster_ip': '10.96.0.10',
        'selector': {'app': 'api'},
        'namespace': 'payments',
        'service_name': 'api',
        'details': details,
        'created_at': None,
        'collected_at': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_service_export_uses_canonical_backend_and_load_balancer_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._service_row(
        _service(
            {
                'external_addresses': ['203.0.113.10'],
                'load_balancer_ingress': ['203.0.113.10'],
                'external_name': None,
                'ports': [
                    {
                        'name': 'https',
                        'port': 443,
                        'target_port': '8443',
                        'protocol': 'TCP',
                        'node_port': 30443,
                    }
                ],
                'endpoints': {
                    'reported': True,
                    'source': 'EndpointSlice',
                    'ready_addresses': [{'ip': '10.0.0.10'}],
                    'not_ready_addresses': [],
                },
                'internal_traffic_policy': 'Cluster',
                'external_traffic_policy': 'Local',
                'publish_not_ready_addresses': False,
            }
        ),
        'staging',
        'staging',
    )

    assert row['status'] == 'Registered'
    assert row['access_model'] == 'Load Balancer Publication'
    assert row['load_balancer'] == '203.0.113.10'
    assert row['external_ip'] == '203.0.113.10'
    assert row['ports'] == '443/TCP -> 8443 (NodePort 30443)'
    assert row['port_count'] == 1
    assert row['ready_endpoints'] == 1
    assert row['not_ready_endpoints'] == 0
    assert row['endpoint_source'] == 'EndpointSlice'


def test_service_export_leaves_backend_counts_blank_when_evidence_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._service_row(
        _service(
            {
                'ports': [],
                'endpoints': {
                    'reported': False,
                    'source': 'Endpoints',
                    'ready_addresses': [],
                    'not_ready_addresses': [],
                },
            },
            service_type='ClusterIP',
        ),
        'staging',
        'staging',
    )

    assert row['status'] == 'Not Reported'
    assert row['ready_endpoints'] is None
    assert row['not_ready_endpoints'] is None
    assert row['ports'] == 'Not Configured'
    assert row['external_ip'] == 'Not Configured'


def test_headless_service_export_preserves_effective_type(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._service_row(
        _service(
            {
                'ports': [],
                'endpoints': {
                    'reported': True,
                    'source': 'EndpointSlice',
                    'ready_addresses': [],
                    'not_ready_addresses': [],
                },
            },
            service_type='ClusterIP',
            cluster_ip='None',
        ),
        'staging',
        'staging',
    )

    assert row['resource_type'] == 'Headless'
    assert row['cluster_ip'] == 'None (Headless)'
