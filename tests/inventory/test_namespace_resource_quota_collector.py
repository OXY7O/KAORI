from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'app' / 'inventory' / 'collectors' / 'configuration.py'


class FakeApiException(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f'API status {status}')
        self.status = status


class FakeResourceQuotaList:
    def __init__(self, items: list[Any] | None = None) -> None:
        self.items = items or []


def load_collector():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            selected.append(node)
        elif isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & {
                'COLLECTED',
                'PERMISSION_UNAVAILABLE',
                'API_UNAVAILABLE',
            }:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {
            '_collection_error_state',
            'get_resource_quotas',
        }:
            selected.append(node)

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        'Any': Any,
        'ApiException': FakeApiException,
        'CoreV1Api': object,
        'V1ResourceQuotaList': FakeResourceQuotaList,
        'cast': lambda _type, value: value,
        'overload': lambda function: function,
    }
    exec(compile(module, str(SOURCE), 'exec'), namespace)
    return namespace['get_resource_quotas']


def test_resource_quota_uses_configured_spec_hard_limits() -> None:
    quota = SimpleNamespace(
        metadata=SimpleNamespace(
            namespace='payments',
            name='compute-budget',
            creation_timestamp=None,
        ),
        spec=SimpleNamespace(hard={'requests.cpu': '4', 'requests.memory': '8Gi'}),
        status=SimpleNamespace(
            hard={'requests.cpu': '2'},
            used={'requests.cpu': '1500m', 'requests.memory': '4Gi'},
        ),
    )
    api = SimpleNamespace(
        list_resource_quota_for_all_namespaces=lambda: FakeResourceQuotaList([quota])
    )

    get_resource_quotas = load_collector()
    rows, evidence = get_resource_quotas(api, with_evidence=True)

    assert evidence == 'Collected'
    assert rows[0]['hard'] == {
        'requests.cpu': '4',
        'requests.memory': '8Gi',
    }
    assert rows[0]['used'] == {
        'requests.cpu': '1500m',
        'requests.memory': '4Gi',
    }


def test_resource_quota_permission_failure_is_committed_as_evidence() -> None:
    def denied():
        raise FakeApiException(403)

    get_resource_quotas = load_collector()
    rows, evidence = get_resource_quotas(
        SimpleNamespace(list_resource_quota_for_all_namespaces=denied),
        with_evidence=True,
    )

    assert rows == []
    assert evidence == 'Permission Unavailable'


def test_resource_quota_unexpected_failure_is_not_suppressed() -> None:
    def unavailable():
        raise FakeApiException(500)

    get_resource_quotas = load_collector()

    try:
        get_resource_quotas(
            SimpleNamespace(list_resource_quota_for_all_namespaces=unavailable),
            with_evidence=True,
        )
    except FakeApiException as exc:
        assert exc.status == 500
    else:
        raise AssertionError('Unexpected ResourceQuota API failures must be re-raised.')
