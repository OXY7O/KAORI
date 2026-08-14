from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[3]
PAYLOAD_PATH = ROOT / 'app/reports/export/payloads/inventory.py'


def _load_payload(monkeypatch: pytest.MonkeyPatch):
    module_names = (
        'app',
        'app.common',
        'app.common.inventory_generation',
        'app.extensions',
        'app.extensions.db',
        'app.inventory',
        'app.inventory.kubernetes.resources',
        'app.inventory.kubernetes.formatting',
        'app.inventory.kubernetes.resources.ingress_semantics',
        'app.inventory.kubernetes.resources.service_semantics',
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
        'app.inventory.kubernetes.resources',
        'app.models',
        'app.reports',
        'app.reports.export',
        'app.reports.export.payloads',
    ):
        modules[name].__path__ = []

    modules['app.common.inventory_generation'].filter_current_generation = lambda query, _model: query
    modules['app.extensions.db'].db = SimpleNamespace()
    modules['app.inventory.kubernetes.formatting'].format_kubernetes_size = lambda value: '-' if value is None else str(value)
    ingress_semantics = modules['app.inventory.kubernetes.resources.ingress_semantics']
    ingress_semantics.ingress_class_presentation = lambda value, source=None: (
        value or 'Not Explicitly Set',
        source or 'Not Explicitly Set',
    )
    ingress_semantics.host_presentation = lambda details: ('All Hosts', 'Host scope', 0)
    ingress_semantics.publication_presentation = lambda details: {
        'label': 'Not Reported',
        'tone': 'unknown',
        'address': 'Not Reported',
        'addresses': [],
        'supporting': 'Not Reported',
        'exception': True,
        'reported': False,
    }
    service_semantics = modules['app.inventory.kubernetes.resources.service_semantics']
    service_semantics.effective_service_type = lambda service_type, cluster_ip: (
        'Headless' if service_type == 'ClusterIP' and cluster_ip == 'None' else (service_type or 'Unknown')
    )
    service_semantics.access_model = lambda service_type: service_type
    service_semantics.backend_registration = lambda service_type, selector, endpoints: {
        'label': 'Registered',
        'ready': 0,
        'not_ready': 0,
        'reported': True,
        'source': 'EndpointSlice',
    }

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
    report_type = type('Report', (), {})
    modules['app.models.report'].Report = report_type
    modules['app.reports.catalog'].require_selected_cluster = lambda _report: 'cluster-id'
    modules['app.reports.export.payloads.common'].get_report_selected_cluster = lambda _report: None

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    storage_spec = importlib.util.spec_from_file_location(
        'app.inventory.kubernetes.resources.storage_semantics',
        ROOT / 'app/inventory/kubernetes/resources/storage_semantics.py',
    )
    assert storage_spec and storage_spec.loader
    storage_semantics = importlib.util.module_from_spec(storage_spec)
    monkeypatch.setitem(sys.modules, 'app.inventory.kubernetes.resources.storage_semantics', storage_semantics)
    storage_spec.loader.exec_module(storage_semantics)

    spec = importlib.util.spec_from_file_location('workload_export_payload_under_test', PAYLOAD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workload(details: dict):
    return SimpleNamespace(
        status='Stable',
        namespace='payments',
        name='api',
        workload_type='Deployment',
        ready='3/3',
        details=details,
        created_at=None,
        collected_at=None,
    )


def test_workload_export_prefers_canonical_flat_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._workload_row(
        _workload(
            {
                'update_strategy': 'RollingUpdate',
                'desired_replicas': 3,
                'available_replicas': 2,
                'updated_replicas': 2,
                'unavailable_replicas': 1,
            }
        ),
        'staging',
        'staging',
    )

    assert row['update_strategy'] == 'RollingUpdate'
    assert row['desired_replicas'] == 3
    assert row['available_replicas'] == 2
    assert row['updated_replicas'] == 2
    assert row['unavailable_replicas'] == 1


def test_workload_export_requires_canonical_flat_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._workload_row(
        _workload(
            {
                'state_rows': [{'label': 'Desired Replicas', 'value': '4'}],
                'delivery_rows': [{'label': 'Strategy', 'value': 'RollingUpdate'}],
            }
        ),
        'staging',
        'staging',
    )

    assert row['update_strategy'] == 'Not Available'
    assert row['desired_replicas'] is None
    assert row['available_replicas'] is None
    assert row['updated_replicas'] is None
    assert row['unavailable_replicas'] is None
