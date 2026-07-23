from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.jobs import service


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def _job(status: str):
    terminal = {'succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired'}
    return SimpleNamespace(
        status=status,
        active_deduplication_key='active-key',
        completed_at=None,
        heartbeat_at=None,
        progress_total=0,
        progress_current=0,
        progress_message=None,
        result_summary_json=None,
        result_type=None,
        result_reference=None,
        error_code=None,
        error_message=None,
        is_terminal=status in terminal,
    )


@pytest.mark.parametrize('terminal_status', ['succeeded', 'failed', 'canceled', 'expired'])
def test_late_success_cannot_overwrite_terminal_job(monkeypatch, terminal_status: str) -> None:
    job = _job(terminal_status)
    session = FakeSession()
    monkeypatch.setattr(service, 'get_job_by_task_id', lambda task_id: job)
    monkeypatch.setattr(service.db, 'session', session)

    result = service.mark_job_succeeded('task-1', result_summary={'late': True})

    assert result is job
    assert job.status == terminal_status
    assert session.commits == 0


def test_cancel_request_wins_completion_race(monkeypatch) -> None:
    job = _job('cancel_requested')
    session = FakeSession()
    monkeypatch.setattr(service, 'get_job_by_task_id', lambda task_id: job)
    monkeypatch.setattr(service.db, 'session', session)

    service.mark_job_succeeded('task-1', result_summary={'completed': True})

    assert job.status == 'canceled'
    assert job.active_deduplication_key is None
    assert job.completed_at is not None
    assert session.commits == 1


def test_retry_callback_cannot_revive_terminal_or_cancel_requested_job(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(service.db, 'session', session)
    for status in ('failed', 'expired', 'canceled', 'cancel_requested'):
        job = _job(status)
        monkeypatch.setattr(service, 'get_job_by_task_id', lambda task_id, job=job: job)
        service.mark_job_retrying('task-1', message='Retrying')
        assert job.status == status
    assert session.commits == 0
