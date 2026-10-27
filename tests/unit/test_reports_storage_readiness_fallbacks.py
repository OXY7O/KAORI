"""Fail-closed Reports storage presentation on expected, typed failures."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from app.reports.generate import service as generate_service
from app.reports.generated import service as generated_service
from app.reports.schedules import service as schedules_service


def _raises(error: Exception) -> Callable[..., None]:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise error

    return unavailable


@pytest.mark.parametrize('module', [generate_service, schedules_service])
@pytest.mark.parametrize(
    'error',
    [
        RuntimeError('no Flask context'),
        OSError('local path unavailable'),
        TypeError('invalid storage status type'),
        ValueError('invalid storage setting'),
    ],
)
def test_expected_storage_status_error_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    error: Exception,
) -> None:
    monkeypatch.setattr(module, 'get_configured_storage_backend_name', _raises(error))

    context = (
        generate_service._get_storage_generation_context()
        if module is generate_service
        else schedules_service._get_storage_context()
    )

    assert context['ready'] is False
    assert context['status'] == 'Needs Review'
    assert context['state'] == 'unknown'
    assert context['source'] == 'fallback'


@pytest.mark.parametrize('module', [generate_service, schedules_service])
def test_unexpected_storage_contract_defect_is_not_masked(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
) -> None:
    monkeypatch.setattr(module, 'get_configured_storage_backend_name', _raises(LookupError('unexpected defect')))

    with pytest.raises(LookupError, match='unexpected defect'):
        if module is generate_service:
            generate_service._get_storage_generation_context()
        else:
            schedules_service._get_storage_context()


@pytest.mark.parametrize('module', [generate_service, schedules_service])
def test_healthy_storage_still_enables_expected_presentation(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
) -> None:
    monkeypatch.setattr(module, 'get_configured_storage_backend_name', lambda: 's3')
    monkeypatch.setattr(
        module,
        'get_report_storage_backend_status',
        lambda _backend: {
            'write_available': True,
            'status': 'Connected',
            'state': 'ready',
            'source': 'direct',
        },
    )

    context = (
        generate_service._get_storage_generation_context()
        if module is generate_service
        else schedules_service._get_storage_context()
    )

    assert context['backend'] == 's3'
    assert context['ready'] is True
    assert context['state'] == 'ready'
    assert context['source'] == 'direct'


def test_missing_flask_context_preserves_generated_report_display_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        generated_service,
        'get_configured_storage_backend_name',
        _raises(RuntimeError('no Flask application context')),
    )

    assert generated_service._get_active_storage_backend_name() == 'local'


def test_unexpected_generated_report_storage_defect_is_not_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        generated_service,
        'get_configured_storage_backend_name',
        _raises(LookupError('unexpected defect')),
    )

    with pytest.raises(LookupError, match='unexpected defect'):
        generated_service._get_active_storage_backend_name()


def test_generated_reports_keep_configured_storage_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generated_service, 'get_configured_storage_backend_name', lambda: 's3')

    assert generated_service._get_active_storage_backend_name() == 's3'
