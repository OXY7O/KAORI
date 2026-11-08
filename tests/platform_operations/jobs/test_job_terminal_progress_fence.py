from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.platform_operations.jobs import execution, service


class _LockedQuery:
    def __init__(self, job):
        self.job = job
        self.locked = False

    def filter_by(self, **_kwargs):
        return self

    def with_for_update(self):
        self.locked = True
        return self

    def first(self):
        assert self.locked
        return self.job


@pytest.mark.parametrize('status', ['succeeded', 'failed', 'expired', 'canceled', 'cancel_requested'])
def test_progress_does_not_mutate_inactive_job(monkeypatch, status):
    job = SimpleNamespace(
        status=status,
        is_terminal=status != 'cancel_requested',
        progress_current=3,
        progress_total=10,
        progress_message='Frozen',
        heartbeat_at=datetime(2026, 10, 12, tzinfo=UTC),
        payload_json={'_progress': {'percent': 30}},
    )
    query = _LockedQuery(job)
    commits = []
    monkeypatch.setattr(service, 'JobExecution', SimpleNamespace(query=query))
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    result = service.update_job_progress('task-1', current=9, percent=90, message='late update')

    assert result is job
    assert query.locked is True
    assert job.progress_current == 3
    assert job.progress_message == 'Frozen'
    assert job.payload_json['_progress']['percent'] == 30
    assert not commits


def test_checkpoint_rejects_terminal_worker_without_progress(monkeypatch):
    job = SimpleNamespace(status='expired', is_terminal=True, public_id='expired-1')
    monkeypatch.setattr(execution, 'is_cancel_requested', lambda _: False)
    monkeypatch.setattr(execution, 'update_job_progress', lambda *_args, **_kwargs: job)

    with pytest.raises(execution.JobExecutionUnavailable):
        execution.JobExecutionContext(task_id='task-1').checkpoint(current=9)


def test_checkpoint_rejects_cancellation_after_first_check(monkeypatch):
    job = SimpleNamespace(status='cancel_requested', is_terminal=False)
    monkeypatch.setattr(execution, 'is_cancel_requested', lambda _: False)
    monkeypatch.setattr(execution, 'update_job_progress', lambda *_args, **_kwargs: job)

    with pytest.raises(execution.JobCancellationRequested):
        execution.JobExecutionContext(task_id='task-1').checkpoint(current=9)
