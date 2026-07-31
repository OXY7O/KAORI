from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_pagination_module() -> ModuleType:
    module_path = Path('app/analytics/storage/pagination.py')
    spec = importlib.util.spec_from_file_location('analytics_storage_pagination', module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_storage_pagination_keeps_filesystem_pvc_and_pv_independent() -> None:
    pagination = _load_pagination_module()

    state = pagination.resolve_storage_pagination(
        {
            'filesystem_page': '4',
            'filesystem_per_page': '5',
            'pvc_page': '3',
            'pvc_per_page': '10',
            'pv_page': '2',
            'pv_per_page': '25',
        }
    )

    assert state == {
        'filesystem': {'page': 4, 'per_page': 5},
        'pvc': {'page': 3, 'per_page': 10},
        'pv': {'page': 2, 'per_page': 25},
    }


def test_storage_pagination_rejects_invalid_or_shared_page_values() -> None:
    pagination = _load_pagination_module()

    state = pagination.resolve_storage_pagination(
        {
            'page': '9',
            'filesystem_page': 'invalid',
            'filesystem_per_page': '50',
            'pvc_page': '0',
            'pvc_per_page': '999',
            'pv_page': 'invalid',
        }
    )

    assert state['filesystem'] == {'page': 1, 'per_page': 50}
    assert state['pvc'] == {'page': 1, 'per_page': 5}
    assert state['pv'] == {'page': 1, 'per_page': 5}
