from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IDENTITY_MODULE = ROOT / 'app/analytics/materialization/identity.py'

spec = importlib.util.spec_from_file_location('kaori_analytics_materialization_identity', IDENTITY_MODULE)
assert spec is not None and spec.loader is not None
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)

normalize_parameters = identity.normalize_parameters
parameter_fingerprint = identity.parameter_fingerprint


def test_normalize_parameters_is_ordered_and_omits_empty_values() -> None:
    assert normalize_parameters({'time_range': '24h', 'namespace': '', 'cluster': 'prod'}) == {
        'cluster': 'prod',
        'time_range': '24h',
    }


def test_parameter_fingerprint_is_stable_for_equivalent_parameter_order() -> None:
    left = parameter_fingerprint({'time_range': '24h', 'namespace': 'payments'})
    right = parameter_fingerprint({'namespace': 'payments', 'time_range': '24h'})
    assert left == right


def test_parameter_fingerprint_changes_when_snapshot_identity_changes() -> None:
    assert parameter_fingerprint({'time_range': '24h'}) != parameter_fingerprint({'time_range': '7d'})
