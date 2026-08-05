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
        'app.inventory.resources',
        'app.inventory.formatting',
        'app.inventory.resources.service_semantics',
        'app.models',
        'app.models.report',
        'app.reports',
        'app.reports.catalog',
        'app.reports.export',
        'app.reports.export.payloads',
        'app.reports.export.payloads.common',
    )
    modules = {name: ModuleType(name) for name in module_names}
    package_names = (
        'app',
        'app.common',
        'app.extensions',
        'app.inventory',
        'app.inventory.resources',
        'app.models',
        'app.reports',
        'app.reports.export',
        'app.reports.export.payloads',
    )
    for name in package_names:
        modules[name].__path__ = []

    modules['app.common.inventory_generation'].filter_current_generation = lambda query, _model: query
    modules['app.extensions.db'].db = SimpleNamespace()
    modules['app.inventory.formatting'].format_kubernetes_size = lambda value: '-' if value is None else str(value)
    service_semantics = modules['app.inventory.resources.service_semantics']
    service_semantics.effective_service_type = lambda service_type, cluster_ip: ('Headless' if service_type == 'ClusterIP' and cluster_ip == 'None' else (service_type or 'Unknown'))
    service_semantics.access_model = lambda service_type: service_type
    service_semantics.backend_registration = lambda service_type, selector, endpoints: {
        'label': 'Registered', 'ready': 0, 'not_ready': 0, 'reported': True, 'source': 'EndpointSlice'
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
    modules['app.models.report'].Report = type('Report', (), {})
    modules['app.reports.catalog'].require_selected_cluster = lambda _report: 'cluster-id'
    modules['app.reports.export.payloads.common'].get_report_selected_cluster = lambda _report: None

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location('pod_export_payload_under_test', PAYLOAD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pod(details: dict, **overrides):
    values = {
        'phase': 'Running',
        'namespace': 'payments',
        'pod_name': 'api-7d9f',
        'workload_type': 'Deployment',
        'workload_name': 'api',
        'node_name': 'worker-1',
        'pod_ip': '10.0.0.10',
        'ready': '1/1',
        'restart_count': 2,
        'container_names': ['api'],
        'container_images': ['registry/api:1'],
        'image_count': 2,
        'configuration_references': [{'type': 'ConfigMap', 'name': 'api'}],
        'persistent_volume_claims': ['api-data'],
        'details': details,
        'created_at': None,
        'collected_at': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_pod_export_uses_canonical_specification_and_runtime_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._pod_row(
        _pod(
            {
                'runtime_evidence_reported': True,
                'specification_evidence_reported': True,
                'configuration': {'reported': True, 'container_count': 3},
                'qos_class': 'Burstable',
            }
        ),
        'staging',
        'staging',
    )

    assert row['restarts'] == 2
    assert row['container_count'] == 3
    assert row['image_count'] == 2
    assert row['configuration_references'] == 1
    assert row['persistent_volume_claims'] == 1
    assert row['qos_class'] == 'Burstable'


def test_pod_export_leaves_evidence_derived_numbers_blank_when_not_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._pod_row(
        _pod(
            {
                'runtime_evidence_reported': False,
                'specification_evidence_reported': False,
                'configuration': {'reported': False},
            },
            ready='Not Reported',
            restart_count=0,
            container_names=[],
            image_count=0,
            configuration_references=[],
            persistent_volume_claims=[],
            pod_ip=None,
            node_name=None,
        ),
        'staging',
        'staging',
    )

    assert row['restarts'] is None
    assert row['container_count'] is None
    assert row['image_count'] is None
    assert row['configuration_references'] is None
    assert row['persistent_volume_claims'] is None
    assert row['ready'] == 'Not Reported'
    assert row['node'] == 'Not Scheduled'
    assert row['pod_ip'] == 'Not Reported'


def test_pod_export_supports_legacy_snapshot_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload(monkeypatch)
    row = payload._pod_row(
        _pod(
            {'configuration': {'container_count': 2}, 'qos_class': 'Guaranteed'},
            container_names=[],
            ready='2/2',
        ),
        'staging',
        'staging',
    )

    assert row['restarts'] == 2
    assert row['container_count'] == 2
    assert row['image_count'] == 2
    assert row['qos_class'] == 'Guaranteed'
