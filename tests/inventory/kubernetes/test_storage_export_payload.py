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

    _load_module_from_file(
        'app.inventory.kubernetes.formatting',
        ROOT / 'app/inventory/kubernetes/formatting.py',
        monkeypatch,
    )
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
    return _load_module_from_file('storage_export_payload_under_test', PAYLOAD_PATH, monkeypatch)


def _item(storage_type: str, details: dict, **overrides):
    values = {
        'namespace': None,
        'name': 'storage-object',
        'storage_type': storage_type,
        'storage_class': 'fast',
        'capacity': None,
        'status': None,
        'details': details,
        'created_at': None,
        'collected_at': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_storage_export_preserves_pvc_requested_and_reported_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._storage_row(
        _item(
            'PersistentVolumeClaim',
            {
                'specification_evidence_reported': True,
                'status_evidence_reported': True,
                'capacity_evidence_reported': True,
                'requested_storage': '8Gi',
                'requested_access_modes': ['ReadWriteOnce'],
                'reported_access_modes': ['ReadWriteOnce'],
                'volume_name': 'pv-api',
                'volume_mode': 'Filesystem',
            },
            namespace='payments',
            capacity='10Gi',
            status='Bound',
        ),
        'staging',
        'staging',
    )

    assert row['status'] == 'Bound'
    assert row['requested_capacity'] == '8 GiB'
    assert row['reported_capacity'] == '10 GiB'
    assert row['requested_access_modes'] == 'ReadWriteOnce'
    assert row['reported_access_modes'] == 'ReadWriteOnce'
    assert row['binding_reference'] == 'pv-api'
    assert row['volume_expansion'] == 'Not Applicable'
    assert row['specification_evidence'] == 'Reported'
    assert row['status_evidence'] == 'Reported'


def test_storage_export_does_not_convert_missing_status_to_unknown_or_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._storage_row(
        _item(
            'PersistentVolumeClaim',
            {
                'specification_evidence_reported': True,
                'status_evidence_reported': False,
                'capacity_evidence_reported': False,
                'requested_storage': '5Gi',
                'requested_access_modes': ['ReadWriteOnce'],
            },
            namespace='payments',
        ),
        'staging',
        'staging',
    )

    assert row['status'] == 'Not Reported'
    assert row['requested_capacity'] == '5 GiB'
    assert row['reported_capacity'] is None
    assert row['reported_access_modes'] == 'Not Reported'
    assert row['status_evidence'] == 'Not Reported'


def test_storage_class_export_distinguishes_false_expansion_from_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._storage_row(
        _item(
            'StorageClass',
            {
                'specification_evidence_reported': True,
                'allow_volume_expansion_reported': True,
                'allow_volume_expansion': False,
                'provisioner': 'csi.example.io',
                'volume_binding_mode': 'WaitForFirstConsumer',
                'reclaim_policy': 'Delete',
            },
            status='Configured',
        ),
        'staging',
        'staging',
    )

    assert row['status'] == 'Configured'
    assert row['volume_expansion'] == 'Not Allowed'
    assert row['status_evidence'] == 'Not Applicable'
    assert row['provisioner'] == 'csi.example.io'


def test_storage_export_distinguishes_classless_configuration_from_missing_specification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    classless = payload._storage_row(
        _item(
            'PersistentVolumeClaim',
            {
                'specification_evidence_reported': True,
                'status_evidence_reported': True,
                'requested_access_modes': [],
                'reported_access_modes': [],
            },
            namespace='payments',
            storage_class=None,
            status='Pending',
        ),
        'staging',
        'staging',
    )
    missing_spec = payload._storage_row(
        _item(
            'PersistentVolumeClaim',
            {
                'specification_evidence_reported': False,
                'status_evidence_reported': False,
            },
            namespace='payments',
            storage_class=None,
        ),
        'staging',
        'staging',
    )

    assert classless['storage_class'] == 'Not Configured'
    assert classless['requested_access_modes'] == 'Not Configured'
    assert classless['reclaim_policy'] == 'Not Applicable'
    assert classless['provisioner'] == 'Not Applicable'
    assert missing_spec['storage_class'] == 'Not Reported'
    assert missing_spec['requested_access_modes'] == 'Not Reported'
