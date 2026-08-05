from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = ROOT / 'app/inventory/collectors/configuration.py'


def _load_collector(monkeypatch: pytest.MonkeyPatch):
    kubernetes_module = ModuleType('kubernetes')
    client_module = ModuleType('kubernetes.client')
    exceptions_module = ModuleType('kubernetes.client.exceptions')
    for name in ('CoreV1Api', 'V1ConfigMapList', 'V1ResourceQuotaList', 'V1SecretList'):
        setattr(client_module, name, type(name, (), {}))

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    exceptions_module.ApiException = ApiException
    for name, module in {
        'kubernetes': kubernetes_module,
        'kubernetes.client': client_module,
        'kubernetes.client.exceptions': exceptions_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location('configuration_collector_under_test', COLLECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, ApiException


def _metadata(name: str | None, namespace: str | None = 'payments'):
    return SimpleNamespace(
        name=name,
        namespace=namespace,
        creation_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
    )


def test_configuration_collector_indexes_names_without_persisting_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    api = SimpleNamespace(
        list_config_map_for_all_namespaces=lambda: SimpleNamespace(
            items=[
                SimpleNamespace(
                    metadata=_metadata('app-config'),
                    data={'LOG_LEVEL': 'debug'},
                    binary_data={'bundle.pem': 'opaque-value'},
                    immutable=False,
                )
            ]
        ),
        list_secret_for_all_namespaces=lambda: SimpleNamespace(
            items=[
                SimpleNamespace(
                    metadata=_metadata('api-secret'),
                    data={'token': 'base64-content'},
                    string_data={'username': 'admin'},
                    immutable=True,
                    type='Opaque',
                )
            ]
        ),
    )

    rows, evidence = collector.get_configuration_inventory(api, with_evidence=True)

    config_map = next(row for row in rows if row['object_type'] == 'ConfigMap')
    secret = next(row for row in rows if row['object_type'] == 'Secret')
    assert config_map['key_names'] == ['LOG_LEVEL', 'bundle.pem']
    assert secret['key_names'] == ['token', 'username']
    assert config_map['immutable'] is False
    assert secret['immutable'] is True
    assert 'key_count' not in config_map
    assert 'payload_size_bytes' not in config_map
    assert 'debug' not in repr(rows)
    assert 'base64-content' not in repr(rows)
    assert evidence == {
        'inventory.configmaps': 'Collected',
        'inventory.secrets': 'Collected',
    }


def test_configuration_families_commit_independent_collection_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, ApiException = _load_collector(monkeypatch)

    def forbidden():
        raise ApiException(status=403)

    rows, evidence = collector.get_configuration_inventory(
        SimpleNamespace(
            list_config_map_for_all_namespaces=lambda: SimpleNamespace(
                items=[SimpleNamespace(metadata=_metadata('app-config'), data={}, binary_data={}, immutable=None)]
            ),
            list_secret_for_all_namespaces=forbidden,
        ),
        with_evidence=True,
    )

    assert [row['name'] for row in rows] == ['app-config']
    assert evidence['inventory.configmaps'] == 'Collected'
    assert evidence['inventory.secrets'] == 'Permission Unavailable'


def test_configuration_collector_does_not_hide_unexpected_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, ApiException = _load_collector(monkeypatch)

    def server_error():
        raise ApiException(status=500)

    with pytest.raises(ApiException):
        collector.get_configuration_inventory(
            SimpleNamespace(
                list_config_map_for_all_namespaces=server_error,
                list_secret_for_all_namespaces=lambda: SimpleNamespace(items=[]),
            )
        )


def test_configuration_collector_skips_objects_without_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    rows = collector.get_configuration_inventory(
        SimpleNamespace(
            list_config_map_for_all_namespaces=lambda: SimpleNamespace(
                items=[
                    SimpleNamespace(metadata=_metadata(None), data={'a': 'b'}, binary_data={}, immutable=False),
                    SimpleNamespace(metadata=_metadata('valid'), data={}, binary_data={}, immutable=False),
                ]
            ),
            list_secret_for_all_namespaces=lambda: SimpleNamespace(items=[]),
        )
    )
    assert [row['name'] for row in rows] == ['valid']
