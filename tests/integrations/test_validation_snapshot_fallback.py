"""Canonical validation snapshot fallback for expected durable-job read failures."""

from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.validation import state
from app.platform_operations.jobs import service as job_service


def _app_with_celery_result(celery_state: str) -> Flask:
    app = Flask(__name__)
    result = SimpleNamespace(state=celery_state, info={}, result=None)
    app.extensions['celery'] = SimpleNamespace(AsyncResult=lambda _task_id: result)
    return app


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('database unavailable'),
        RuntimeError('missing Flask application context'),
        ValueError('invalid durable snapshot value'),
        TypeError('invalid durable snapshot type'),
    ],
)
def test_expected_canonical_read_error_falls_back_to_terminal_celery_state(monkeypatch, error: Exception) -> None:
    def unavailable(_task_id: str) -> None:
        raise error

    monkeypatch.setattr(job_service, 'get_job_by_task_id', unavailable)
    monkeypatch.setattr(state, 'get_validation_metadata', lambda _task_id: {'binding_id': '17'})
    monkeypatch.setattr(state, '_reconcile_terminal_job', lambda **_kwargs: {})

    with _app_with_celery_result('FAILURE').app_context():
        snapshot = state.build_validation_snapshot('validation-task')

    assert snapshot['task_id'] == 'validation-task'
    assert snapshot['binding_id'] == 17
    assert snapshot['celery_state'] == 'FAILURE'
    assert snapshot['status'] == 'error'
    assert snapshot['is_active'] is False
    assert snapshot['is_complete'] is True



@pytest.mark.parametrize('error', [TypeError('invalid snapshot field'), ValueError('invalid snapshot value')])
def test_expected_canonical_snapshot_serialization_error_uses_celery_state(monkeypatch, error: Exception) -> None:
    def broken_snapshot(_job: object) -> None:
        raise error

    monkeypatch.setattr(job_service, 'get_job_by_task_id', lambda _task_id: object())
    monkeypatch.setattr(job_service, 'job_snapshot', broken_snapshot)
    monkeypatch.setattr(state, 'get_validation_metadata', lambda _task_id: {})

    with _app_with_celery_result('PENDING').app_context():
        snapshot = state.build_validation_snapshot('validation-task')

    assert snapshot['celery_state'] == 'PENDING'
    assert snapshot['is_active'] is True
    assert snapshot['is_complete'] is False


def test_unexpected_canonical_read_defect_is_not_silently_hidden(monkeypatch) -> None:
    def unexpected(_task_id: str) -> None:
        raise LookupError('unexpected canonical job contract defect')

    monkeypatch.setattr(job_service, 'get_job_by_task_id', unexpected)
    monkeypatch.setattr(state, 'get_validation_metadata', lambda _task_id: {})

    with _app_with_celery_result('PENDING').app_context():
        with pytest.raises(LookupError, match='unexpected canonical job contract defect'):
            state.build_validation_snapshot('validation-task')


def test_canonical_snapshot_still_drives_active_polling_and_binding_identity(monkeypatch) -> None:
    canonical = {
        'status': 'running',
        'is_active': True,
        'is_complete': False,
        'scope_type': 'integration_binding',
        'scope_key': 'binding:21',
    }
    monkeypatch.setattr(job_service, 'get_job_by_task_id', lambda _task_id: object())
    monkeypatch.setattr(job_service, 'job_snapshot', lambda _job: canonical)
    monkeypatch.setattr(state, 'get_validation_metadata', lambda _task_id: {'message': 'worker evidence'})

    with _app_with_celery_result('PENDING').app_context():
        snapshot = state.build_validation_snapshot('validation-task')

    assert snapshot['status'] == 'running'
    assert snapshot['binding_id'] == 21
    assert snapshot['message'] == 'worker evidence'
    assert snapshot['is_active'] is True
    assert snapshot['is_complete'] is False
