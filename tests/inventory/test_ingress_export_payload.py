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
SERVICE_SEMANTICS_PATH = ROOT / 'app/inventory/resources/service_semantics.py'


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
    for name in (
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
    ):
        setattr(modules['app.models'], name, type(name, (), {}))
    modules['app.models.report'].Report = type('Report', (), {})
    modules['app.reports.catalog'].require_selected_cluster = lambda _report: 'cluster-id'
    modules['app.reports.export.payloads.common'].get_report_selected_cluster = lambda _report: None
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    for module_name, path in (
        ('app.inventory.resources.ingress_semantics', INGRESS_SEMANTICS_PATH),
        ('app.inventory.resources.service_semantics', SERVICE_SEMANTICS_PATH),
    ):
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)

    spec = importlib.util.spec_from_file_location('ingress_export_payload_under_test', PAYLOAD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ingress(details: dict, backend_paths: list[dict], *, ingress_class=None, tls_enabled=True):
    return SimpleNamespace(
        ingress_class=ingress_class,
        namespace='payments',
        ingress_name='api',
        tls_enabled=tls_enabled,
        backend_paths=backend_paths,
        details=details,
        created_at=None,
        collected_at=None,
    )


def test_ingress_export_uses_canonical_json_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._ingress_row(
        _ingress(
            {
                'ingress_class_source': 'Not Explicitly Set',
                'specification_evidence_reported': True,
                'publication_evidence_reported': True,
                'hosts': ['api.example.com'],
                'hostless_rule_count': 1,
                'addresses': ['203.0.113.10'],
                'tls': [{'secret_name': 'api-tls', 'hosts': ['api.example.com']}],
            },
            [
                {'backend_type': 'Service', 'service_name': 'api', 'service_port': '443'},
                {'backend_type': 'Resource', 'resource_kind': 'Bucket', 'resource_name': 'assets'},
            ],
        ),
        'staging',
        'staging',
    )

    assert row['ingress_class'] == 'Not Explicitly Set'
    assert row['host_scope'] == 'api.example.com'
    assert row['hosts'] == 'api.example.com'
    assert row['all_host_rule_count'] == 1
    assert row['publication_status'] == 'Published'
    assert row['addresses'] == '203.0.113.10'
    assert row['address_count'] == 1
    assert row['tls_status'] == 'TLS Referenced'
    assert row['tls_secret_count'] == 1
    assert row['backend_count'] == 2
    assert row['service_backend_count'] == 1
    assert row['resource_backend_count'] == 1


def test_ingress_export_keeps_unreported_publication_blank_for_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._ingress_row(
        _ingress(
            {
                'ingress_class_source': 'spec.ingressClassName',
                'specification_evidence_reported': True,
                'publication_evidence_reported': False,
                'hosts': [],
                'hostless_rule_count': 1,
                'addresses': [],
                'tls': [],
            },
            [],
            ingress_class='nginx',
            tls_enabled=False,
        ),
        'staging',
        'staging',
    )

    assert row['status'] == 'Not Reported'
    assert row['host_scope'] == 'All Hosts'
    assert row['hosts'] == 'Not Configured'
    assert row['addresses'] == 'Not Reported'
    assert row['address_count'] is None
    assert row['tls_status'] == 'No TLS Declaration'


def test_ingress_export_does_not_infer_all_hosts_when_specification_is_unreported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._ingress_row(
        _ingress(
            {
                'specification_evidence_reported': False,
                'publication_evidence_reported': False,
                'hosts': [],
                'hostless_rule_count': 0,
                'addresses': [],
                'tls': [],
            },
            [],
            ingress_class=None,
            tls_enabled=False,
        ),
        'staging',
        'staging',
    )

    assert row['host_scope'] == 'Not Reported'
    assert row['hosts'] == 'Not Reported'
