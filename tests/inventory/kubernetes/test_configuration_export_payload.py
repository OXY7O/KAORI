from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[3]
PAYLOAD_PATH = ROOT / 'app/reports/export/payloads/inventory.py'


def _load_module_from_file(name: str, path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _load_payload(monkeypatch: pytest.MonkeyPatch):
    module_names = (
        'app',
        'app.common',
        'app.common.inventory_generation',
        'app.extensions',
        'app.extensions.db',
        'app.inventory',
        'app.inventory.kubernetes.resources',
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

    _load_module_from_file('app.inventory.kubernetes.formatting', ROOT / 'app/inventory/kubernetes/formatting.py', monkeypatch)
    _load_module_from_file(
        'app.inventory.kubernetes.resources.ingress_semantics',
        ROOT / 'app/inventory/kubernetes/resources/ingress_semantics.py',
        monkeypatch,
    )
    _load_module_from_file(
        'app.inventory.kubernetes.resources.service_semantics',
        ROOT / 'app/inventory/kubernetes/resources/service_semantics.py',
        monkeypatch,
    )
    _load_module_from_file(
        'app.inventory.kubernetes.resources.storage_semantics',
        ROOT / 'app/inventory/kubernetes/resources/storage_semantics.py',
        monkeypatch,
    )
    return _load_module_from_file('configuration_export_payload_under_test', PAYLOAD_PATH, monkeypatch)


def test_configuration_export_derives_key_count_and_declares_protected_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._configuration_row(
        SimpleNamespace(
            namespace='payments',
            name='api-secret',
            object_type='Secret',
            secret_type='kubernetes.io/tls',
            key_names=['tls.crt', 'tls.key'],
            immutable=True,
            created_at=None,
            collected_at=None,
        ),
        'staging',
        'staging',
    )

    assert row['key_count'] == 2
    assert row['key_names'] == ['tls.crt', 'tls.key']
    assert row['metadata_boundary'] == 'Key Names Only'
    assert row['value_persistence'] == 'None'
    assert 'payload_size_bytes' not in row


def test_configuration_export_marks_secret_type_not_applicable_for_configmap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._configuration_row(
        SimpleNamespace(
            namespace='payments',
            name='app-config',
            object_type='ConfigMap',
            secret_type=None,
            key_names=[],
            immutable=False,
            created_at=None,
            collected_at=None,
        ),
        'staging',
        'staging',
    )
    assert row['secret_type'] == 'Not Applicable'
    assert row['key_count'] == 0
