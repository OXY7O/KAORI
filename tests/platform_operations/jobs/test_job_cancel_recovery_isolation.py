from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from flask import Flask

from app.platform_operations.jobs import service


class _Job(SimpleNamespace):
    @property
    def is_terminal(self):
        return self.status in {'succeeded', 'failed', 'expired', 'canceled', 'partially_succeeded'}

    @property
    def is_active(self):
        return not self.is_terminal


def _candidate(*, status, task_id, minutes):
    return _Job(
        status=status,
        public_id=task_id,
        celery_task_id=task_id,
        cancel_requested_at=datetime.now(UTC) - timedelta(minutes=minutes),
        queued_at=datetime.now(UTC) - timedelta(minutes=minutes),
        heartbeat_at=None,
        started_at=None,
        expires_at=None,
        active_deduplication_key='dedupe-' + task_id,
        error_code=None,
        error_message=None,
        progress_message='Pending',
    )


def test_revoke_failure_keeps_pending_cancel_and_recovers_other_jobs(monkeypatch):
    app = Flask(__name__)
    app.config.update(JOB_CANCEL_GRACE_SECONDS=120, JOB_QUEUED_STALE_SECONDS=300)
    calls = []

    def revoke(task_id, terminate, signal=None):
        calls.append((task_id, terminate, signal))
        if task_id == 'cancel-job':
            raise OSError('broker unavailable for one task')

    app.extensions['celery'] = SimpleNamespace(control=SimpleNamespace(revoke=revoke))
    canceling = _candidate(status='cancel_requested', task_id='cancel-job', minutes=10)
    queued = _candidate(status='queued', task_id='queued-job', minutes=12)
    query = SimpleNamespace(filter=lambda *_a, **_kw: SimpleNamespace(all=lambda: [canceling, queued]))
    monkeypatch.setattr(service, 'JobExecution', SimpleNamespace(
        query=query, status=SimpleNamespace(in_=lambda *_args: object())
    ))
    commits = []
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    with app.app_context():
        result = service.recover_stale_jobs()

    assert canceling.status == 'cancel_requested'
    assert canceling.active_deduplication_key == 'dedupe-cancel-job'
    assert queued.status == 'expired'
    assert result == {'recovered': 1, 'expired': 1, 'canceled': 0}
    assert commits == [True]
    assert calls == [('cancel-job', True, 'SIGTERM'), ('queued-job', False, None)]


def test_interactive_cancel_fails_closed_without_changing_state(monkeypatch):
    app = Flask(__name__)
    app.extensions['celery'] = SimpleNamespace(
        control=SimpleNamespace(revoke=lambda *_a, **_kw: (_ for _ in ()).throw(OSError('offline')))
    )
    job = _candidate(status='queued', task_id='pending-job', minutes=1)
    job.workload_class = 'standard'

    with app.app_context():
        try:
            service.cancel_job_execution(job)
        except service.JobCancellationNotAllowed:
            pass
        else:
            raise AssertionError('Expected graceful refusal on Celery revoke failure')

    assert job.status == 'queued'
