"""Non-mutating Plan worker must use canonical evidence and cancel correctly."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from app.infrastructure_automation import tasks
from app.platform_operations.jobs.fingerprint import payload_fingerprint


class _Context:
    instances: list[_Context] = []

    def __init__(self, **kwargs):
        self.events: list[tuple[str, dict]] = []
        self.instances.append(self)

    def start(self, **kwargs):
        self.events.append(('start', kwargs))

    def checkpoint(self, **kwargs):
        self.events.append(('checkpoint', kwargs))

    def succeed(self, **kwargs):
        self.events.append(('succeed', kwargs))

    def fail(self, message, **kwargs):
        self.events.append(('fail', {'message': message, **kwargs}))

    def canceled(self, **kwargs):
        self.events.append(('canceled', kwargs))


def _setup(monkeypatch: pytest.MonkeyPatch, *, state: str = 'ready_for_review', drift: bool = False) -> None:
    connection = SimpleNamespace(
        id=31,
        integration_type='configuration_automation',
        provider_key='ansible',
        enabled=True,
        lifecycle_status='active',
    )
    source_job = SimpleNamespace(id=55, public_id='preflight-55', integration_instance_id=31)
    parameters = {'plan_fingerprint': 'f' * 64}
    request_job = SimpleNamespace(
        celery_task_id=str(tasks.materialize_kubespray_plan_review.request.id),
        integration_instance_id=31,
        integration_type='configuration_automation',
        job_type='infrastructure_automation',
        operation=tasks.PLAN_OPERATION,
        queue_name='automation',
        scope_type='ansible_source_connection',
        scope_key='31',
        parameter_fingerprint='0' * 64 if drift else payload_fingerprint(parameters),
    )

    class _Session:
        def get(self, model, identifier):
            if model is tasks.IntegrationInstance:
                return connection if identifier == 31 else None
            if model is tasks.JobExecution:
                return {55: source_job, 71: request_job}.get(identifier)
            return None

    _Context.instances.clear()
    monkeypatch.setattr(tasks, 'db', SimpleNamespace(session=_Session()))
    monkeypatch.setattr(tasks, 'JobExecutionContext', _Context)
    monkeypatch.setattr(
        tasks,
        'committed_kubespray_preflight',
        lambda conn: SimpleNamespace(
            state=state,
            facts_job_public_id=source_job.public_id,
            host_registry_fingerprint='a' * 64,
            host_access_fingerprint='b' * 64,
        ),
    )
    monkeypatch.setattr(
        tasks,
        'build_kubespray_plan_review',
        lambda conn, job: SimpleNamespace(
            status='requires_independent_approval',
            plan_fingerprint='f' * 64,
            host_registry_fingerprint='a' * 64,
            host_access_fingerprint='b' * 64,
            dispatch_parameters=lambda: parameters,
            committed_summary=lambda: {
                'plan_fingerprint': 'f' * 64,
                'approval_status': 'not_requested',
                'execution_status': 'blocked',
                'mutation_authorized': False,
            },
        ),
    )


def _run_plan(**kwargs):
    app = Flask(__name__)
    with app.app_context():
        return tasks.materialize_kubespray_plan_review.run(
            connection_id=kwargs.get('connection_id', 31),
            host_preflight_job_id=kwargs.get('host_preflight_job_id', 55),
            job_execution_id=71,
        )


def test_worker_commits_only_review_plan_via_job_execution(monkeypatch) -> None:
    _setup(monkeypatch)
    outcome = _run_plan()
    assert outcome == {'status': 'succeeded', 'plan_fingerprint': 'f' * 64}
    events = _Context.instances[-1].events
    assert [name for name, _ in events] == ['start', 'checkpoint', 'succeed']
    committed = events[-1][1]
    assert committed['result_type'] == 'automation_kubespray_plan_review_v1'
    assert committed['result_summary']['mutation_authorized'] is False
    assert committed['result_summary']['approval_status'] == 'not_requested'


@pytest.mark.parametrize('state', ['blocked', 'unknown', 'stale'])
def test_worker_cannot_commit_when_remote_evidence_not_qualified(monkeypatch, state) -> None:
    _setup(monkeypatch, state=state)
    outcome = _run_plan()
    assert outcome == {'status': 'blocked'}
    events = _Context.instances[-1].events
    assert 'succeed' not in [name for name, _ in events]
    assert events[-1][0] == 'fail'


def test_worker_rejects_missing_canonical_source_job(monkeypatch) -> None:
    _setup(monkeypatch)
    outcome = _run_plan(host_preflight_job_id=56)
    assert outcome == {'status': 'blocked'}
    assert _Context.instances[-1].events[-1][0] == 'fail'


def test_worker_rejects_plan_that_differs_from_queued_fingerprint(monkeypatch):
    _setup(monkeypatch, drift=True)
    assert _run_plan() == {'status': 'blocked'}
    assert [name for name, _ in _Context.instances[-1].events] == ['start', 'fail']
