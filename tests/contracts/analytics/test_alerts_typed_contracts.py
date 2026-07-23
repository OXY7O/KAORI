from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app' / 'analytics' / 'alerts'
CONTRACTS = ALERTS / 'contracts.py'
SOURCES = ALERTS / 'sources.py'
SNAPSHOTS = ALERTS / 'snapshots.py'
SERVICE = ALERTS / 'service.py'

TYPED_CONTRACTS = {
    'NormalizedAlert',
    'AlertSourceStatus',
    'AlertsSnapshot',
}

TYPED_CONSUMERS = {
    'health.py',
    'inhibition.py',
    'ownership.py',
    'routing.py',
    'signals.py',
    'silences.py',
    'snapshots.py',
    'sources.py',
}


def _function_return_annotations(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))

    return {
        node.name: ast.unparse(node.returns)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.returns is not None
    }


def _typed_dict_keys(class_name: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(CONTRACTS.read_text(encoding='utf-8'))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    required: set[str] = set()
    optional: set[str] = set()

    for node in class_node.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue

        annotation = ast.unparse(node.annotation)
        if annotation.startswith('NotRequired['):
            optional.add(node.target.id)
        else:
            required.add(node.target.id)

    return required, optional


def _return_dictionary_keys(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
            continue

        keys = {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if keys:
            return keys

    raise AssertionError(f'No literal dictionary return found for {function_name}')


def test_alert_contracts_are_explicit_typed_dictionaries() -> None:
    tree = ast.parse(CONTRACTS.read_text(encoding='utf-8'))
    typed_dicts = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(ast.unparse(base) == 'TypedDict' for base in node.bases)
    }
    aliases = {
        node.name.id
        for node in tree.body
        if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name)
    }

    assert TYPED_CONTRACTS <= typed_dicts
    assert 'AlertLoadResult' in aliases


def test_source_boundary_returns_canonical_alert_contracts() -> None:
    annotations = _function_return_annotations(SOURCES)
    source = SOURCES.read_text(encoding='utf-8')

    assert annotations['build_empty_source_status'] == 'AlertSourceStatus'
    assert annotations['normalize_alertmanager_item'] == 'NormalizedAlert'
    assert annotations['normalize_prometheus_alert'] == 'NormalizedAlert'
    assert annotations['load_alertmanager_alerts'] == 'AlertLoadResult'
    assert annotations['load_prometheus_alerts'] == 'AlertLoadResult'
    assert annotations['load_alerts_by_source'] == 'AlertLoadResult'
    assert 'tuple[list[dict[str, Any]], dict[str, Any]]' not in source


def test_snapshot_boundary_has_an_explicit_contract() -> None:
    annotations = _function_return_annotations(SNAPSHOTS)

    assert annotations['get_alerts_snapshot'] == 'AlertsSnapshot'
    assert annotations['_empty_alerts_snapshot'] == 'AlertsSnapshot'


def test_alert_consumers_use_the_canonical_types() -> None:
    offenders: list[str] = []

    for filename in sorted(TYPED_CONSUMERS):
        source = (ALERTS / filename).read_text(encoding='utf-8')
        if filename != 'snapshots.py' and 'NormalizedAlert' not in source:
            offenders.append(f'{filename}: missing NormalizedAlert')
        if filename not in {'snapshots.py'} and 'AlertSourceStatus' not in source:
            offenders.append(f'{filename}: missing AlertSourceStatus')

    assert offenders == []


def test_compatibility_facade_reexports_typed_contracts() -> None:
    source = SERVICE.read_text(encoding='utf-8')

    for contract_name in sorted(TYPED_CONTRACTS | {'AlertLoadResult'}):
        assert contract_name in source
        assert f"'{contract_name}'" in source


def test_runtime_dictionary_keys_match_the_typed_contracts() -> None:
    required_alert_keys, _ = _typed_dict_keys('NormalizedAlert')
    source_status_keys, _ = _typed_dict_keys('AlertSourceStatus')
    snapshot_keys, _ = _typed_dict_keys('AlertsSnapshot')

    alertmanager_keys = _return_dictionary_keys(SOURCES, 'normalize_alertmanager_item')
    prometheus_keys = _return_dictionary_keys(SOURCES, 'normalize_prometheus_alert')
    empty_source_keys = _return_dictionary_keys(SOURCES, 'build_empty_source_status')
    empty_snapshot_keys = _return_dictionary_keys(SNAPSHOTS, '_empty_alerts_snapshot')

    assert required_alert_keys <= alertmanager_keys
    assert required_alert_keys <= prometheus_keys
    assert source_status_keys == empty_source_keys
    assert snapshot_keys == empty_snapshot_keys
