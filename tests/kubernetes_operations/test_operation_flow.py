from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app' / 'kubernetes_operations' / 'operation_flow.py'
SPEC = importlib.util.spec_from_file_location('kaori_operation_flow', MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_then_apply = MODULE.validate_then_apply


def test_validate_then_apply_preserves_order() -> None:
    calls: list[str] = []

    result = validate_then_apply(
        validate=lambda: calls.append('validate'),
        prepare_apply=lambda: calls.append('prepare'),
        apply=lambda: calls.append('apply') or 'completed',
    )

    assert result == 'completed'
    assert calls == ['validate', 'prepare', 'apply']


def test_validate_then_apply_blocks_mutation_when_validation_fails() -> None:
    calls: list[str] = []

    def fail_validation() -> None:
        calls.append('validate')
        raise ValueError('invalid payload')

    with pytest.raises(ValueError, match='invalid payload'):
        validate_then_apply(
            validate=fail_validation,
            apply=lambda: calls.append('apply'),
        )

    assert calls == ['validate']
