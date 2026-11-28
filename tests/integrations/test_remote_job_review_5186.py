"""Canonical review-only job regressions; no live provider or host."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation import remote_job_review as service
from app.infrastructure_automation import remote_review_dispatch as dispatch
from app.infrastructure_automation import remote_review_posture as posture
from app.infrastructure_automation.kubernetes.source_policy import SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA, RemoteSourceReview
from app.infrastructure_automation.remote_preflight_target import RemoteTargetReview
from app.infrastructure_automation.remote_worker_review import WorkerReviewEvidence
from app.platform_operations.jobs.fingerprint import payload_fingerprint


def _target(now):
    return RemoteTargetReview(
        31, 7, SOURCE_CANDIDATE_SHA, 'sha256:' + 'a' * 64, 'b' * 64, 'c' * 64,
        'd' * 64, (), now + timedelta(minutes=10),
    )


def _job(now):
    parameters = service.review_parameters(_target(now))
    return SimpleNamespace(
        id=51, celery_task_id='task-51', integration_instance_id=31,
        integration_type='configuration_automation', job_type='infrastructure_automation',
        operation=service.REVIEW_OPERATION, queue_name='automation', workload_class='validation',
        scope_type='ansible_source_connection', scope_key='31',
        resource_group='kubespray:remote-preflight-review:31', requested_by_user_id=7,
        max_attempts=1, status='queued', attempt_count=0, cancel_requested_at=None,
        completed_at=None, queued_at=now - timedelta(seconds=1), expires_at=None,
        payload_json=parameters, parameter_fingerprint=payload_fingerprint(parameters),
    )


@pytest.mark.parametrize('change', [
    {'status': 'running'}, {'attempt_count': 1}, {'queue_name': 'default'},
    {'operation': 'automation_kubespray_host_preflight'}, {'requested_by_user_id': None},
    {'resource_group': 'other'}, {'celery_task_id': 'wrong'}, {'max_attempts': 2},
    {'integration_instance_id': 32},
])
def test_wrong_job_or_replay_cannot_claim(change):
    now = datetime.now(UTC)
    job = _job(now)
    vars(job).update(change)
    assert not service.matches_review_job(job, task_id='task-51', connection_id=31, now=now, running=False)


@pytest.fixture
def reviewed(monkeypatch):
    now = datetime.now(UTC)
    job, target = _job(now), _target(now)
    source = RemoteSourceReview(REMOTE_CANDIDATE_SHA, 'e' * 64)
    evidence = WorkerReviewEvidence('f' * 64, now + timedelta(minutes=5))
    events = []
    monkeypatch.setattr(service, 'review_enabled', lambda: True)
    monkeypatch.setenv('KAORI_LOCAL_REMOTE_REVIEW_WORKER', 'automation@fixture')
    monkeypatch.setenv('KAORI_LOCAL_REMOTE_REVIEW_SOURCE', '/fixture/source')
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(rollback=lambda: None)))
    monkeypatch.setattr(service, '_job', lambda identifier: job if identifier == job.id else None)
    monkeypatch.setattr(service, 'review_remote_preflight_target', lambda **kwargs: target)
    monkeypatch.setattr(service, 'review_remote_source_candidate', lambda path: source)
    monkeypatch.setattr(service, 'resolve_remote_worker_review', lambda *args, **kwargs: evidence)

    def start(*args, **kwargs):
        events.append('claim')
        job.status, job.attempt_count = 'running', 1
        job.payload_json = {**job.payload_json, '_progress': {}}
        return job

    def success(*args, **kwargs):
        events.append(kwargs)
        job.status = 'succeeded'
        return job

    def failure(*args, **kwargs):
        events.append('fail')
        job.status = 'failed'

    monkeypatch.setattr(service, 'mark_job_running', start)
    monkeypatch.setattr(service, 'stage_operational_activity', lambda **kwargs: events.append('audit'))
    monkeypatch.setattr(service, 'mark_job_succeeded', success)
    monkeypatch.setattr(service, 'mark_job_failed', failure)
    return job, target, source, evidence, events


def _run(worker='automation@fixture'):
    return service.run_remote_preflight_review(
        job_id=51, task_id='task-51', connection_id=31, worker_identity=worker
    )


def test_review_commit_distinct_from_full_preflight_and_no_replay(reviewed):
    job, _, _, _, events = reviewed
    assert _run() == {'status': 'succeeded'}
    assert events[:2] == ['claim', 'audit']
    committed = events[-1]
    assert committed['result_type'] == service.REVIEW_RESULT_TYPE
    summary = committed['result_summary']
    for field in (
        'execution_authorized', 'mutation_authorized', 'ssh_executed',
        'credential_material_accessed', 'runtime_attestation_verified', 'full_preflight_verified',
    ):
        assert summary[field] is False
    assert 'fixture/source' not in str(summary)
    assert _run() == {'status': 'blocked'}
    assert job.attempt_count == 1


def test_wrong_worker_never_claims(reviewed):
    assert _run('other@fixture') == {'status': 'blocked'}
    assert reviewed[-1] == []


@pytest.mark.parametrize('drift', ['payload', 'actor', 'source', 'receipt', 'audit'])
def test_drift_or_audit_failure_denies_before_success(reviewed, monkeypatch, drift):
    job, target, source, evidence, events = reviewed
    if drift == 'payload':
        job.payload_json = {**job.payload_json, 'schema_version': True}
    elif drift == 'actor':
        job.requested_by_user_id = 8
        monkeypatch.setattr(
            service, 'review_remote_preflight_target', lambda **kwargs: replace(target, actor_id=8)
        )
    elif drift == 'source':
        values = iter((source, replace(source, fingerprint='9' * 64)))
        monkeypatch.setattr(service, 'review_remote_source_candidate', lambda path: next(values))
    elif drift == 'receipt':
        values = iter((evidence, None))
        monkeypatch.setattr(service, 'resolve_remote_worker_review', lambda *args, **kwargs: next(values))
    else:
        def unavailable(**kwargs):
            raise RuntimeError('synthetic audit unavailable')

        monkeypatch.setattr(service, 'stage_operational_activity', unavailable)
    assert _run() == {'status': 'blocked'}
    assert events[-1] == 'fail'
    assert not any(isinstance(event, dict) for event in events)


def test_dispatch_only_passes_opaque_connection_and_canonical_actor(monkeypatch):
    target = _target(datetime.now(UTC))
    monkeypatch.setattr(dispatch, 'review_enabled', lambda: True)
    monkeypatch.setattr(dispatch, 'review_remote_preflight_target', lambda **kwargs: target)
    monkeypatch.setattr(dispatch, 'db', SimpleNamespace(session=SimpleNamespace(rollback=lambda: None)))

    def enqueue(**kwargs):
        assert kwargs['task_kwargs'] == {'connection_id': 31}
        assert kwargs['requested_by_user_id'] == 7
        assert kwargs['parameters'] == service.review_parameters(target)
        assert kwargs['max_attempts'] == 1
        assert kwargs['dispatch_options'].require_registered_worker is True
        return SimpleNamespace(id=51), True

    monkeypatch.setattr(dispatch, 'enqueue_canonical_job', enqueue)
    job, created = dispatch.dispatch_remote_preflight_review(actor_id=7, connection_id=31)
    assert job.id == 51 and created


def test_review_worker_result_projects_historical_not_execution_readiness(reviewed, monkeypatch):
    job, target, _, _, events = reviewed
    assert _run() == {'status': 'succeeded'}
    committed = events[-1]
    job.result_type = committed['result_type']
    job.result_summary_json = committed['result_summary']
    job.completed_at = datetime.now(UTC)
    connection = SimpleNamespace(
        id=31, integration_type='configuration_automation', provider_key='ansible', enabled=True,
        metadata_json={'source_sha': target.source_sha, 'execution_environment_digest': target.ee_digest},
    )
    monkeypatch.setattr(posture, 'committed_source_state', lambda metadata: 'checked')
    projected = posture.review_remote_job_posture(connection, job, now=datetime.now(UTC))
    assert projected.state == 'historical'
    assert projected.execution_authorized is False
    job.status = 'failed'
    assert posture.review_remote_job_posture(connection, job, now=datetime.now(UTC)).state == 'blocked'
