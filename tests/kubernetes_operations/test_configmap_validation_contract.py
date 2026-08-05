from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = ROOT / 'app/kubernetes_operations/configmaps/contracts.py'
VALIDATION_PATH = ROOT / 'app/kubernetes_operations/configmaps/validation.py'


class FormData(dict):
    def __init__(self, *, keys: list[str], values: list[str], kinds: list[str]):
        super().__init__()
        self._lists = {
            'entry_key': keys,
            'entry_value': values,
            'entry_kind': kinds,
        }

    def getlist(self, name: str) -> list[str]:
        return list(self._lists.get(name, []))


def load_validation(monkeypatch: pytest.MonkeyPatch):
    app_module = ModuleType('app')
    operations_module = ModuleType('app.kubernetes_operations')
    configmaps_module = ModuleType('app.kubernetes_operations.configmaps')
    monkeypatch.setitem(sys.modules, 'app', app_module)
    monkeypatch.setitem(sys.modules, 'app.kubernetes_operations', operations_module)
    monkeypatch.setitem(sys.modules, 'app.kubernetes_operations.configmaps', configmaps_module)

    contract_spec = importlib.util.spec_from_file_location(
        'app.kubernetes_operations.configmaps.contracts',
        CONTRACTS_PATH,
    )
    assert contract_spec and contract_spec.loader
    contracts = importlib.util.module_from_spec(contract_spec)
    monkeypatch.setitem(
        sys.modules,
        'app.kubernetes_operations.configmaps.contracts',
        contracts,
    )
    contract_spec.loader.exec_module(contracts)

    validation_spec = importlib.util.spec_from_file_location(
        'configmap_validation_under_test',
        VALIDATION_PATH,
    )
    assert validation_spec and validation_spec.loader
    validation = importlib.util.module_from_spec(validation_spec)
    validation_spec.loader.exec_module(validation)
    return validation


def test_binary_entries_remain_canonical_base64_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    validation = load_validation(monkeypatch)
    entries = validation.parse_entries(
        FormData(keys=['binary.bin'], values=['aGVsbG8='], kinds=['binary'])
    )

    assert entries.binary_data == {'binary.bin': 'aGVsbG8='}
    assert entries.payload_size_bytes == len('binary.bin'.encode()) + len(b'hello')


def test_blank_key_with_value_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    validation = load_validation(monkeypatch)

    with pytest.raises(ValueError, match='value but no key'):
        validation.parse_entries(FormData(keys=[''], values=['value'], kinds=['text']))


def test_unsupported_entry_kind_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    validation = load_validation(monkeypatch)

    with pytest.raises(ValueError, match='unsupported content type'):
        validation.parse_entries(FormData(keys=['mode'], values=['value'], kinds=['secret']))


def test_merge_recalculates_complete_payload_size(monkeypatch: pytest.MonkeyPatch) -> None:
    validation = load_validation(monkeypatch)
    submitted = validation.parse_entries(
        FormData(keys=['new'], values=['two'], kinds=['text'])
    )

    merged = validation.merge_entries(
        {'data': {'existing': 'one'}, 'binary_data': {}},
        submitted,
        'merge',
    )

    assert merged.data == {'existing': 'one', 'new': 'two'}
    assert merged.payload_size_bytes == len(b'existingone') + len(b'newtwo')


def test_replace_diff_reports_removed_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    validation = load_validation(monkeypatch)
    submitted = validation.parse_entries(
        FormData(keys=['new'], values=['two'], kinds=['text'])
    )

    diff = validation.diff_entries(
        {'data': {'existing': 'one'}, 'binary_data': {}},
        submitted,
    )

    assert diff == {
        'added': ['new'],
        'changed': [],
        'removed': ['existing'],
        'unchanged': [],
    }


def test_configmap_name_rejects_empty_or_oversized_dns_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_validation(monkeypatch)

    with pytest.raises(ValueError, match='DNS subdomain'):
        module.validate_name('api..config', 'ConfigMap name')
    with pytest.raises(ValueError, match='DNS subdomain'):
        module.validate_name(f"{'a' * 64}.config", 'ConfigMap name')


def test_configmap_name_accepts_valid_multi_label_dns_subdomain(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_validation(monkeypatch)
    assert module.validate_name('api.v2-config', 'ConfigMap name') == 'api.v2-config'
