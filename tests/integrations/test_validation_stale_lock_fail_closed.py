"""Fail-closed stale validation lock reclamation under the canonical job read boundary."""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.validation import state
from app.platform_operations.jobs import service as job_service


class _LockClient:
    def __init__(self) -> None:
        self.eval_calls: list[tuple[object, ...]] = []

    def get(self, _key: str) -> str:
        return 'owner-task'

    def eval(self, *args: object) -> int:
        self.eval_calls.append(args)
        return 1


@pytest.mark.parametrize('error', [SQLAlchemyError('database unavailable'), RuntimeError('missing app context')])
def test_canonical_owner_read_error_never_reclaims_lock(monkeypatch, error: Exception) -> None:
    client = _LockClient()

    def unavailable(_task_id: str) -> None:
        raise error

    monkeypatch.setattr(job_service, 'get_job_by_task_id', unavailable)

    assert state._release_stale_validation_lock(client, 'validation-lock') is False
    assert client.eval_calls == []


def test_unexpected_owner_failure_propagates_without_deleting_lock(monkeypatch) -> None:
    client = _LockClient()

    def unexpected(_task_id: str) -> None:
        raise ValueError('unexpected job contract')

    monkeypatch.setattr(job_service, 'get_job_by_task_id', unexpected)

    with pytest.raises(ValueError, match='unexpected job contract'):
        state._release_stale_validation_lock(client, 'validation-lock')
    assert client.eval_calls == []


def test_active_canonical_job_never_reclaims_lock(monkeypatch) -> None:
    client = _LockClient()
    monkeypatch.setattr(job_service, 'get_job_by_task_id', lambda _task_id: SimpleNamespace(status='running'))

    assert state._release_stale_validation_lock(client, 'validation-lock') is False
    assert client.eval_calls == []


@pytest.mark.parametrize('job', [None, SimpleNamespace(status='succeeded')])
def test_terminal_or_missing_job_reclaims_only_by_compare_delete(monkeypatch, job) -> None:
    client = _LockClient()
    monkeypatch.setattr(job_service, 'get_job_by_task_id', lambda _task_id: job)

    assert state._release_stale_validation_lock(client, 'validation-lock') is True
    assert client.eval_calls == [(state._COMPARE_DELETE_SCRIPT, 1, 'validation-lock', 'owner-task')]
