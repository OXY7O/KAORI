"""Generic Jobs & Executions must not reconcile an infrastructure mutation."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from app.common.job_execution_contract import KUBESPRAY_APPLY_OPERATION
from app.platform_operations.jobs import dispatcher, service


def _candidate(status='queued', operation=KUBESPRAY_APPLY_OPERATION):
    timestamp = datetime.now(UTC) - timedelta(hours=3)
    return SimpleNamespace(
        operation=operation, status=status, workload_class='analytics',
        public_id='fixture', celery_task_id='fixture-task',
        queued_at=timestamp, started_at=timestamp, heartbeat_at=timestamp,
        cancel_requested_at=timestamp, expires_at=None,
        active_deduplication_key='fixture-key', attempt_count=1,
        error_code=None, error_message=None, progress_message='Pending',
    )


@pytest.mark.parametrize('method,kwargs', [
    ('mark_job_running', {}),
    ('update_job_progress', {'current': 1, 'message': 'fixture'}),
    ('mark_job_succeeded', {'result_summary': {'runner_rc': 0}}),
    ('mark_job_failed', {'error': 'fixture'}),
    ('mark_job_retrying', {'message': 'fixture'}),
    ('mark_job_canceled', {}),
])
def test_mutation_refuses_generic_lifecycle_writes(monkeypatch, method, kwargs):
    job = _candidate()
    original = vars(job).copy()
    monkeypatch.setattr(service, '_lock_job_by_task_id', lambda task_id: job)
    with pytest.raises(service.JobDomainReconciliationRequired):
        getattr(service, method)('fixture-task', **kwargs)
    assert vars(job) == original


@pytest.mark.parametrize('status', ['queued', 'running', 'retrying', 'cancel_requested'])
def test_mutation_refuses_generic_cancellation(status):
    job = _candidate(status)
    original = vars(job).copy()
    assert service.job_can_cancel(job) is False
    with pytest.raises(service.JobCancellationNotAllowed):
        service.cancel_job_execution(job, terminate=True)
    with pytest.raises(service.JobCancellationNotAllowed):
        service.request_job_cancel(job)
    assert vars(job) == original


@pytest.mark.parametrize('status', ['queued', 'running', 'retrying', 'cancel_requested'])
def test_stale_recovery_preserves_mutation_and_recovers_normal_job(monkeypatch, status):
    app = Flask(__name__)
    app.config.update(JOB_QUEUED_STALE_SECONDS=300, JOB_RUNNING_STALE_SECONDS=300, JOB_CANCEL_GRACE_SECONDS=120)
    mutation = _candidate(status)
    original = vars(mutation).copy()
    normal = _candidate(operation='fixture_validation')
    normal.public_id = 'normal'
    normal.celery_task_id = 'normal-task'
    calls = []
    commits = []
    app.extensions['celery'] = SimpleNamespace(control=SimpleNamespace(
        revoke=lambda task_id, terminate: calls.append((task_id, terminate)),
    ))
    query = SimpleNamespace(filter=lambda *args: SimpleNamespace(all=lambda: [mutation, normal]))
    monkeypatch.setattr(service, 'JobExecution', SimpleNamespace(
        query=query, status=SimpleNamespace(in_=lambda *args: object()),
    ))
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    with app.app_context():
        assert service.recover_stale_jobs() == {'recovered': 1, 'expired': 1, 'canceled': 0}

    assert vars(mutation) == original
    assert normal.status == 'expired'
    assert normal.active_deduplication_key is None
    assert calls == [('normal-task', False)]
    assert commits == [True]


def test_generic_creation_rejects_apply_before_staging(monkeypatch):
    monkeypatch.setattr(service, 'stage_job_execution', lambda *args: pytest.fail('Unexpected staged job'))
    with pytest.raises(service.JobDomainReconciliationRequired):
        service.create_or_attach_job(
            job_type='infrastructure_automation',
            operation=KUBESPRAY_APPLY_OPERATION,
            queue_name='automation',
            workload_class='validation',
            requested_by_user_id=7,
        )


def test_generic_dispatch_rejects_apply_before_worker_or_job_creation(monkeypatch):
    monkeypatch.setattr(
        dispatcher, 'ensure_task_registered_for_queue', lambda **kwargs: pytest.fail('Unexpected worker inspection')
    )
    monkeypatch.setattr(dispatcher, 'create_or_attach_job', lambda **kwargs: pytest.fail('Unexpected job creation'))
    task = SimpleNamespace(apply_async=lambda **kwargs: pytest.fail('Unexpected broker dispatch'))
    with pytest.raises(service.JobDomainReconciliationRequired):
        dispatcher.enqueue_canonical_job(
            task=task,
            task_kwargs={},
            job_type='infrastructure_automation',
            operation=KUBESPRAY_APPLY_OPERATION,
            queue_name='automation',
            workload_class='validation',
            requested_by_user_id=7,
            resource_group='fixture',
            parameters={},
            dispatch_options=dispatcher.JobDispatchOptions(require_registered_worker=True),
        )
