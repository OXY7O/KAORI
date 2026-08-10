from __future__ import annotations

import pytest

from app.kubernetes_operations.operation_flow import validate_then_apply


def test_validate_then_apply_runs_validation_before_mutation() -> None:
    events: list[str] = []

    result = validate_then_apply(
        validate=lambda: events.append('validate'),
        apply=lambda: events.append('apply') or 'updated',
    )

    assert result == 'updated'
    assert events == ['validate', 'apply']


def test_validate_then_apply_stops_before_prepare_and_apply_when_validation_fails() -> None:
    events: list[str] = []

    def fail_validation() -> None:
        events.append('validate')
        raise ValueError('validation failed')

    with pytest.raises(ValueError, match='validation failed'):
        validate_then_apply(
            validate=fail_validation,
            prepare_apply=lambda: events.append('prepare'),
            apply=lambda: events.append('apply'),
        )

    assert events == ['validate']


def test_validate_then_apply_runs_prepare_only_after_successful_validation() -> None:
    events: list[str] = []

    validate_then_apply(
        validate=lambda: events.append('validate'),
        prepare_apply=lambda: events.append('prepare'),
        apply=lambda: events.append('apply'),
    )

    assert events == ['validate', 'prepare', 'apply']
