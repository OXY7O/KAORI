from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.platform_operations.jobs import notifications, tasks

ROOT = Path(__file__).resolve().parents[3]


def _failed_job() -> SimpleNamespace:
    return SimpleNamespace(
        id=14,
        public_id='JOB-UAT-14',
        job_type='inventory.sync',
        status='failed',
        error_message='secret-token-this-must-not-be-sent',
        payload_json={'password': 'hidden-payload'},
    )


def test_committed_job_failure_event_is_redacted_and_has_stable_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notifications, 'current_app', SimpleNamespace(config={}))
    monkeypatch.setattr(notifications, 'url_for', lambda name: '/jobs/executions')
    job = _failed_job()
    event = notifications.build_failed_job_event(job)
    assert event.domain == 'platform_operations'
    assert event.event_type == 'jobs.execution_failed'
    assert event.event_key == 'jobs.execution_failed:JOB-UAT-14'
    assert event.asset_type == 'job_execution'
    assert event.message.severity == 'warning'
    assert event.message.action_url == '/jobs/executions'
    assert job.error_message not in event.message.body
    assert 'password' not in str(event.payload)
    assert 'secret-token' not in str(event.payload)


def test_uncommitted_or_nonfailure_cannot_be_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, 'current_app', SimpleNamespace(config={}))
    monkeypatch.setattr(notifications, 'url_for', lambda name: '/jobs/executions')
    job = _failed_job()
    for status in ('queued', 'running', 'succeeded', 'retrying'):
        job.status = status
        with pytest.raises(ValueError, match='Only committed failed'):
            notifications.build_failed_job_event(job)


def test_delivery_task_reloads_committed_failure_and_skips_nonfailed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.job import JobExecution

    job = _failed_job()
    calls: list[int] = []

    def get_job(model, identifier: int):
        assert model is JobExecution
        assert identifier == 14
        calls.append(identifier)
        return job

    monkeypatch.setattr(tasks, 'db', SimpleNamespace(session=SimpleNamespace(get=get_job)))
    monkeypatch.setattr(tasks, 'dispatch_failed_job_event', lambda _job: {'successful': 1})
    assert tasks.dispatch_failed_job_notification.run(14) == {'status': 'completed', 'successful': 1}
    job.status = 'succeeded'
    assert tasks.dispatch_failed_job_notification.run(14)['status'] == 'skipped'
    assert calls == [14, 14]


def test_canonical_terminal_commit_precedes_outbound_enqueue() -> None:
    source = (ROOT / 'app/platform_operations/jobs/service.py').read_text()
    block = source.split('def mark_job_failed(', 1)[1].split('def request_job_cancel(', 1)[0]
    assert block.index('db.session.commit()\n    # This is an outbound side effect') < block.index(
        'dispatch_failed_job_notification.apply_async('
    )
    config = (ROOT / 'app/config/default.py').read_text()
    assert "'app.platform_operations.jobs.tasks.dispatch_failed_job_notification'" in config
