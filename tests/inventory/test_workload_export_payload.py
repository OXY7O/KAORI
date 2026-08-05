from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_PATH = ROOT / 'app/reports/export/payloads/inventory.py'


def _load_payload(monkeypatch: pytest.MonkeyPatch):
    module_names = (
        'app',
        'app.common',
        'app.common.inventory_generation',
        'app.extensions',
        'app.extensions.db',
        'app.inventory',
        'app.inventory.formatting',
        'app.models',
        'app.models.report',
        'app.reports',
        'app.reports.catalog',
        'app.reports.export',
        'app.reports.export.payloads',
        'app.reports.export.payloads.common',
    )
    modules = {name: ModuleType(name) for name in module_names}
    for name in ('app', 'app.common', 'app.extensions', 'app.inventory', 'app.models', 'app.reports', 'app.reports.export', 'app.reports.export.payloads'):
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
    report_type = type('Report', (), {})
    modules['app.models.report'].Report = report_type
    modules['app.reports.catalog'].require_selected_cluster = lambda _report: 'cluster-id'
    modules['app.reports.export.payloads.common'].get_report_selected_cluster = lambda _report: None

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

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


def test_workload_export_supports_legacy_nested_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._workload_row(
        _workload(
            {
                'state_rows': [
                    {'label': 'Desired Replicas', 'value': '4'},
                    {'label': 'Available Replicas', 'value': '3'},
                    {'label': 'Updated Replicas', 'value': '3'},
                    {'label': 'Unavailable Replicas', 'value': '1'},
                ],
                'delivery_rows': [{'label': 'Strategy', 'value': 'RollingUpdate'}],
            }
        ),
        'staging',
        'staging',
    )

    assert row['update_strategy'] == 'RollingUpdate'
    assert row['desired_replicas'] == 4
    assert row['available_replicas'] == 3
    assert row['updated_replicas'] == 3
    assert row['unavailable_replicas'] == 1
