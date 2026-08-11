from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from flask import Flask

from app.jobs import service


class _JobStub(SimpleNamespace):
    @property
    def is_active(self) -> bool:
        return self.status in {'queued', 'running', 'retrying', 'cancel_requested'}

    @property
    def is_terminal(self) -> bool:
        return self.status in {'succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired'}


def _job(**overrides):
    values = {
        'status': 'running',
        'workload_class': 'analytics',
        'heartbeat_at': datetime.now(UTC) - timedelta(minutes=10),
        'started_at': datetime.now(UTC) - timedelta(minutes=10),
        'queued_at': datetime.now(UTC) - timedelta(minutes=11),
        'cancel_requested_at': None,
        'celery_task_id': 'task-1',
        'expires_at': None,
        'active_deduplication_key': 'dedupe-1',
        'completed_at': None,
        'error_code': None,
        'error_message': None,
        'progress_message': 'Running',
    }
    values.update(overrides)
    return _JobStub(**values)


def test_request_cancel_preserves_worker_heartbeat(monkeypatch) -> None:
    heartbeat = datetime.now(UTC) - timedelta(minutes=5)
    job = _job(heartbeat_at=heartbeat)
    commits: list[bool] = []
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    service.request_job_cancel(job)

    assert job.status == 'cancel_requested'
    assert job.cancel_requested_at is not None
    assert job.heartbeat_at == heartbeat
    assert commits == [True]


def test_cancel_requested_job_cannot_be_canceled_again() -> None:
    job = _job(status='cancel_requested')

    assert service.job_can_cancel(job) is False


def test_stale_recovery_force_cancels_after_grace_period(monkeypatch) -> None:
    app = Flask(__name__)
    app.config['JOB_CANCEL_GRACE_SECONDS'] = 120
    revoke_calls: list[tuple[str, bool, str]] = []
    commits: list[bool] = []
    celery = SimpleNamespace(
        control=SimpleNamespace(
            revoke=lambda task_id, terminate, signal: revoke_calls.append((task_id, terminate, signal))
        )
    )
    app.extensions['celery'] = celery
    job = _job(
        status='cancel_requested',
        cancel_requested_at=datetime.now(UTC) - timedelta(minutes=3),
    )
    query = SimpleNamespace(filter=lambda *_args, **_kwargs: SimpleNamespace(all=lambda: [job]))
    status_field = SimpleNamespace(in_=lambda _values: object())
    monkeypatch.setattr(service, 'JobExecution', SimpleNamespace(query=query, status=status_field))
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))
    monkeypatch.setattr(service, '_append_automatic_terminal_audit', lambda _job: None)

    with app.app_context():
        result = service.recover_stale_jobs()

    assert revoke_calls == [('task-1', True, 'SIGTERM')]
    assert job.status == 'canceled'
    assert job.active_deduplication_key is None
    assert job.progress_message == 'Force canceled after cooperative cancellation timeout'
    assert result == {'recovered': 1, 'expired': 0, 'canceled': 1}
    assert commits == [True]
