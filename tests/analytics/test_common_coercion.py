from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'app' / 'analytics' / 'common' / 'coercion.py'


def _load_module():
    spec = importlib.util.spec_from_file_location('kaori_analytics_coercion', MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collection_coercion_preserves_only_canonical_types() -> None:
    module = _load_module()
    mapping = {'cluster': 'production'}
    values = ['node-a']

    assert module.as_dict(mapping) is mapping
    assert module.as_dict(values) == {}
    assert module.as_list(values) is values
    assert module.as_list(mapping) == []


def test_numeric_coercion_is_deterministic_and_fail_closed() -> None:
    module = _load_module()

    assert module.safe_float('12.5') == 12.5
    assert module.safe_float(True) == 1.0
    assert module.safe_float('not-a-number') == 0.0
    assert module.safe_float(None) == 0.0
    assert module.safe_int(2.6) == 3
    assert module.safe_int('not-a-number') == 0
