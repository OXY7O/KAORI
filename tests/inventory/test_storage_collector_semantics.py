from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = ROOT / 'app/inventory/collectors/storage.py'
SEMANTICS_PATH = ROOT / 'app/inventory/resources/storage_semantics.py'


def _load_collector(monkeypatch: pytest.MonkeyPatch):
    app_module = ModuleType('app')
    inventory_module = ModuleType('app.inventory')
    collectors_module = ModuleType('app.inventory.collectors')

    common_spec = importlib.util.spec_from_file_location(
        'app.inventory.collectors.common',
        ROOT / 'app/inventory/collectors/common.py',
    )
    assert common_spec and common_spec.loader
    common_module = importlib.util.module_from_spec(common_spec)

    kubernetes_module = ModuleType('kubernetes')
    client_module = ModuleType('kubernetes.client')
    exceptions_module = ModuleType('kubernetes.client.exceptions')
    for name in (
        'CoreV1Api',
        'StorageV1Api',
        'V1PersistentVolumeClaimList',
        'V1PersistentVolumeList',
        'V1StorageClassList',
    ):
        setattr(client_module, name, type(name, (), {}))

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    exceptions_module.ApiException = ApiException
    for name, module in {
        'app': app_module,
        'app.inventory': inventory_module,
        'app.inventory.collectors': collectors_module,
        'app.inventory.collectors.common': common_module,
        'kubernetes': kubernetes_module,
        'kubernetes.client': client_module,
        'kubernetes.client.exceptions': exceptions_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    common_spec.loader.exec_module(common_module)

    spec = importlib.util.spec_from_file_location('storage_collector_under_test', COLLECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, ApiException


def _load_semantics(monkeypatch: pytest.MonkeyPatch):
    app_module = ModuleType('app')
    inventory_module = ModuleType('app.inventory')
    resources_module = ModuleType('app.inventory.resources')
    formatting_spec = importlib.util.spec_from_file_location(
        'app.inventory.formatting',
        ROOT / 'app/inventory/formatting.py',
    )
    assert formatting_spec and formatting_spec.loader
    formatting_module = importlib.util.module_from_spec(formatting_spec)
    for name, module in {
        'app': app_module,
        'app.inventory': inventory_module,
        'app.inventory.resources': resources_module,
        'app.inventory.formatting': formatting_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    formatting_spec.loader.exec_module(formatting_module)
    spec = importlib.util.spec_from_file_location('storage_semantics_under_test', SEMANTICS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(name: str | None, namespace: str | None = None, *, deleting: bool = False):
    return SimpleNamespace(
        name=name,
        namespace=namespace,
        uid=f'uid-{name}',
        labels={'app': name} if name else {},
        annotations={},
        finalizers=['kubernetes.io/pvc-protection'] if namespace else [],
        deletion_timestamp=datetime(2026, 8, 5, tzinfo=UTC) if deleting else None,
        creation_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
    )


def _storage_class(*, allow_expansion=False):
    return SimpleNamespace(
        metadata=_metadata('fast'),
        provisioner='csi.example.io',
        reclaim_policy='Delete',
        volume_binding_mode='WaitForFirstConsumer',
        allow_volume_expansion=allow_expansion,
        parameters={'tier': 'gold'},
        mount_options=[],
        allowed_topologies=[],
    )


def _pv(*, deleting=False):
    return SimpleNamespace(
        metadata=_metadata('pv-api', deleting=deleting),
        spec=SimpleNamespace(
            capacity={'storage': '10Gi'},
            claim_ref=SimpleNamespace(namespace='payments', name='api-data'),
            persistent_volume_reclaim_policy='Retain',
            access_modes=['ReadWriteOnce'],
            volume_mode='Filesystem',
            mount_options=['discard'],
            node_affinity=SimpleNamespace(),
            storage_class_name='fast',
            csi=SimpleNamespace(
                driver='csi.example.io',
                volume_handle='vol-1',
                read_only=False,
                fs_type='ext4',
            ),
        ),
        status=SimpleNamespace(phase='Bound'),
    )


def _pvc(*, status=None):
    return SimpleNamespace(
        metadata=_metadata('api-data', 'payments'),
        spec=SimpleNamespace(
            volume_name='pv-api',
            access_modes=['ReadWriteOnce'],
            volume_mode='Filesystem',
            storage_class_name='fast',
            resources=SimpleNamespace(requests={'storage': '10Gi'}),
            selector=None,
            data_source=None,
        ),
        status=status,
    )


def test_storage_collector_normalizes_data_source_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    pvc = _pvc(status=SimpleNamespace(phase='Pending', capacity=None, access_modes=[]))
    pvc.spec.data_source_ref = SimpleNamespace(
        kind='VolumeSnapshot',
        name='api-snapshot',
        api_group='snapshot.storage.k8s.io',
    )

    rows = collector.get_storage_inventory(
        SimpleNamespace(
            list_persistent_volume=lambda: SimpleNamespace(items=[]),
            list_persistent_volume_claim_for_all_namespaces=lambda: SimpleNamespace(items=[pvc]),
        ),
        SimpleNamespace(list_storage_class=lambda: SimpleNamespace(items=[])),
    )

    assert rows[0]['details']['data_source'] == {
        'kind': 'VolumeSnapshot',
        'name': 'api-snapshot',
        'api_group': 'snapshot.storage.k8s.io',
    }


def test_storage_collector_preserves_false_expansion_and_missing_pvc_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    rows = collector.get_storage_inventory(
        SimpleNamespace(
            list_persistent_volume=lambda: SimpleNamespace(items=[_pv()]),
            list_persistent_volume_claim_for_all_namespaces=lambda: SimpleNamespace(items=[_pvc()]),
        ),
        SimpleNamespace(list_storage_class=lambda: SimpleNamespace(items=[_storage_class()])),
    )

    storage_class = next(row for row in rows if row['storage_type'] == 'StorageClass')
    pvc = next(row for row in rows if row['storage_type'] == 'PersistentVolumeClaim')
    assert storage_class['status'] == 'Configured'
    assert storage_class['details']['allow_volume_expansion'] is False
    assert storage_class['details']['allow_volume_expansion_reported'] is True
    assert pvc['status'] is None
    assert pvc['capacity'] is None
    assert pvc['details']['status_evidence_reported'] is False
    assert pvc['details']['capacity_evidence_reported'] is False
    assert pvc['details']['requested_storage'] == '10Gi'


def test_storage_families_commit_independent_collection_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, ApiException = _load_collector(monkeypatch)

    def forbidden():
        raise ApiException(status=403)

    rows, evidence = collector.get_storage_inventory(
        SimpleNamespace(
            list_persistent_volume=lambda: SimpleNamespace(items=[_pv()]),
            list_persistent_volume_claim_for_all_namespaces=lambda: SimpleNamespace(items=[_pvc()]),
        ),
        SimpleNamespace(list_storage_class=forbidden),
        with_evidence=True,
    )

    assert {row['storage_type'] for row in rows} == {'PersistentVolume', 'PersistentVolumeClaim'}
    assert evidence['inventory.storageclasses'] == 'Permission Unavailable'
    assert evidence['inventory.persistentvolumes'] == 'Collected'
    assert evidence['inventory.persistentvolumeclaims'] == 'Collected'


def test_storage_collector_does_not_hide_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, ApiException = _load_collector(monkeypatch)

    def server_error():
        raise ApiException(status=500)

    with pytest.raises(ApiException):
        collector.get_storage_inventory(
            SimpleNamespace(
                list_persistent_volume=server_error,
                list_persistent_volume_claim_for_all_namespaces=lambda: SimpleNamespace(items=[]),
            ),
            SimpleNamespace(list_storage_class=lambda: SimpleNamespace(items=[])),
        )


def test_storage_collector_does_not_hide_unexpected_attribute_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)

    def broken_client_method():
        raise AttributeError('generated client failed internally')

    with pytest.raises(AttributeError, match='generated client failed internally'):
        collector.get_storage_inventory(
            SimpleNamespace(
                list_persistent_volume=broken_client_method,
                list_persistent_volume_claim_for_all_namespaces=lambda: SimpleNamespace(items=[]),
            ),
            SimpleNamespace(list_storage_class=lambda: SimpleNamespace(items=[])),
        )


def test_storage_collector_skips_invalid_identity_and_marks_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    invalid_pvc = _pvc()
    invalid_pvc.metadata.namespace = None
    rows = collector.get_storage_inventory(
        SimpleNamespace(
            list_persistent_volume=lambda: SimpleNamespace(items=[_pv(deleting=True)]),
            list_persistent_volume_claim_for_all_namespaces=lambda: SimpleNamespace(items=[invalid_pvc]),
        ),
        SimpleNamespace(list_storage_class=lambda: SimpleNamespace(items=[])),
    )

    assert len(rows) == 1
    assert rows[0]['status'] == 'Terminating'
    assert rows[0]['details']['kubernetes_phase'] == 'Bound'


def test_storage_semantics_distinguish_not_allowed_not_reported_and_not_applicable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantics = _load_semantics(monkeypatch)

    assert (
        semantics.expansion_presentation(
            'StorageClass',
            {'allow_volume_expansion_reported': True, 'allow_volume_expansion': False},
        )
        == 'Not Allowed'
    )
    assert semantics.expansion_presentation('StorageClass', {}) == 'Not Reported'
    assert semantics.expansion_presentation('PersistentVolume', {}) == 'Not Applicable'
    assert semantics.lifecycle_presentation('PersistentVolumeClaim', None, {}) == ('Not Reported', 'unknown')
    assert semantics.lifecycle_presentation(
        'PersistentVolume',
        'Bound',
        {'deletion_timestamp': '2026-08-05T00:00:00+00:00'},
    ) == ('Terminating', 'warning')


def test_storage_semantics_distinguish_classless_and_missing_specification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantics = _load_semantics(monkeypatch)

    assert semantics.provisioning_presentation(
        'PersistentVolumeClaim',
        None,
        {'specification_evidence_reported': True},
    ) == ('Not Configured', 'PersistentVolumeClaim')
    assert semantics.provisioning_presentation(
        'PersistentVolumeClaim',
        None,
        {'specification_evidence_reported': False},
    ) == ('Not Reported', 'PersistentVolumeClaim')
    assert (
        semantics.binding_reference(
            'PersistentVolumeClaim',
            {'specification_evidence_reported': False},
        )
        == 'Not Reported'
    )
    assert (
        semantics.binding_reference(
            'PersistentVolumeClaim',
            {'specification_evidence_reported': True, 'volume_name': None},
        )
        == 'Waiting for Volume'
    )
