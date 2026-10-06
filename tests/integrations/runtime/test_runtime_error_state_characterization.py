from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from app.integrations.validation import scheduling
from app.platform_operations.jobs import service as job_service

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_runtime_audit_keeps_provider_attention_states_distinct() -> None:
    service = read('app/integrations/service.py')

    for state in ('degraded', 'unhealthy', 'not_observed'):
        assert state in service
    assert 'validation_required' in service
    assert 'blocked' in service


def test_runtime_audit_has_executable_recovery_transition_evidence() -> None:
    recovery = read('app/integrations/runtime/recovery.py')

    assert 'def is_runtime_recovery(' in recovery
    assert 'previous not in _HEALTHY_STATES and current in _HEALTHY_STATES' in recovery
    assert "trigger_type='recovery'" in recovery
    assert 'Recovery dispatch is best-effort.' in recovery


def test_runtime_audit_keeps_report_storage_outage_degraded_not_successful() -> None:
    service = read('app/reports/generated/service.py')
    template = read('app/templates/reports/generated/index.html')

    assert 'Report records remain available' in service
    assert 'actions stay paused until connectivity returns.' in service
    assert 'data-generated-storage-degraded="true"' in template
    assert 'Artifact Storage Needs Review' in template


def test_runtime_audit_has_responsive_database_unavailable_evidence() -> None:
    browser_test = read('tests/ui/test_runtime_state_responsiveness.py')

    assert "'database_unavailable': 'PostgreSQL Unavailable'" in browser_test
    assert 'assert response.status == 503' in browser_test
    assert "heading', name='Database Setup Required'" in browser_test
    assert "layout['scrollWidth'] <= layout['clientWidth'] + 1" in browser_test


def test_runtime_refresh_dispatch_failure_releases_lock_and_terminalizes_job(monkeypatch) -> None:
    app = Flask(__name__)
    app.config['INTEGRATION_RUNTIME_CELERY_QUEUE'] = 'integration-runtime'
    job = SimpleNamespace(celery_task_id='task-dispatch', id=17, priority=5)
    dispatch_calls: list[dict[str, object]] = []
    release_calls: list[dict[str, object]] = []
    failed_calls: list[tuple[str, str, str]] = []

    class FailingTask:
        def apply_async(self, **kwargs):
            dispatch_calls.append(kwargs)
            raise RuntimeError('broker unavailable')

    monkeypatch.setattr(scheduling, 'get_active_validation_task_id', lambda **_kwargs: None)
    monkeypatch.setattr(scheduling, 'create_or_attach_job', lambda **_kwargs: (job, True))
    monkeypatch.setattr(scheduling, 'claim_validation_job', lambda **_kwargs: True)
    monkeypatch.setattr(scheduling, 'refresh_integration_runtime_instance', FailingTask())
    monkeypatch.setattr(scheduling, 'release_validation_job', lambda **kwargs: release_calls.append(kwargs))

    def mark_failed(task_id: str, *, error: Exception | str, error_code: str | None = None):
        failed_calls.append((task_id, str(error), str(error_code)))
        return job

    monkeypatch.setattr(scheduling, 'mark_job_failed', mark_failed)

    with app.app_context(), pytest.raises(RuntimeError, match='broker unavailable'):
        scheduling.enqueue_runtime_refresh(
            integration_type='metrics_source',
            integration_instance_id=23,
        )

    assert dispatch_calls == [
        {
            'kwargs': {
                'integration_type': 'metrics_source',
                'integration_instance_id': 23,
                'requested_by_user_id': None,
                'trigger_type': 'scheduled',
                'job_execution_id': 17,
            },
            'task_id': 'task-dispatch',
            'queue': 'integration-runtime',
            'priority': 5,
        }
    ]
    assert release_calls == [
        {
            'task_id': 'task-dispatch',
            'integration_type': 'metrics_source',
            'operation': 'runtime_refresh',
            'integration_instance_id': 23,
        }
    ]
    assert failed_calls == [('task-dispatch', 'broker unavailable', 'dispatch_failed')]


@pytest.mark.parametrize('status', ['running', 'retrying'])
def test_runtime_audit_expires_stale_worker_heartbeat(status: str, monkeypatch) -> None:
    fixed_now = datetime(2026, 9, 15, 1, 0, tzinfo=UTC)
    app = Flask(__name__)
    app.config['JOB_RUNNING_STALE_SECONDS'] = 300
    commits: list[bool] = []
    job = SimpleNamespace(
        status=status,
        heartbeat_at=fixed_now - timedelta(minutes=10),
        started_at=fixed_now - timedelta(minutes=11),
        queued_at=fixed_now - timedelta(minutes=12),
        cancel_requested_at=None,
        celery_task_id='task-stale-worker',
        expires_at=None,
        active_deduplication_key='dedupe-stale-worker',
        completed_at=None,
        error_code=None,
        error_message=None,
        progress_message='Running',
    )
    query = SimpleNamespace(filter=lambda *_args, **_kwargs: SimpleNamespace(all=lambda: [job]))
    status_field = SimpleNamespace(in_=lambda _values: object())

    monkeypatch.setattr(job_service, '_now', lambda: fixed_now)
    monkeypatch.setattr(job_service, 'JobExecution', SimpleNamespace(query=query, status=status_field))
    monkeypatch.setattr(job_service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    with app.app_context():
        result = job_service.recover_stale_jobs()

    assert job.status == 'expired'
    assert job.active_deduplication_key is None
    assert job.completed_at == fixed_now
    assert job.heartbeat_at == fixed_now
    assert job.error_code == 'stale_worker_heartbeat'
    assert job.error_message == 'KAORI marked the job expired because its worker heartbeat became stale.'
    assert job.progress_message == 'Expired after stale worker heartbeat'
    assert result == {'recovered': 1, 'expired': 1, 'canceled': 0}
    assert commits == [True]


def test_runtime_audit_records_retry_transition_semantics(monkeypatch) -> None:
    fixed_now = datetime(2026, 9, 15, 1, 30, tzinfo=UTC)
    commits: list[bool] = []
    job = SimpleNamespace(
        status='running',
        is_terminal=False,
        heartbeat_at=fixed_now - timedelta(minutes=5),
        progress_message='Running',
        payload_json={},
        error_code=None,
        error_message=None,
    )

    monkeypatch.setattr(job_service, '_now', lambda: fixed_now)
    monkeypatch.setattr(job_service, 'get_job_by_task_id', lambda _task_id: job)
    monkeypatch.setattr(job_service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    result = job_service.mark_job_retrying(
        'task-retry',
        message='Retry scheduled after provider timeout',
        error=RuntimeError('provider timeout'),
    )

    assert result is job
    assert job.status == 'retrying'
    assert job.heartbeat_at == fixed_now
    assert job.progress_message == 'Retry scheduled after provider timeout'
    assert job.error_code == 'RuntimeError'
    assert job.error_message == 'provider timeout'
    assert job.payload_json['_progress']['stage'] == 'Retrying'
    assert job.payload_json['_progress']['updated_at'] == fixed_now.isoformat()
    assert commits == [True]
