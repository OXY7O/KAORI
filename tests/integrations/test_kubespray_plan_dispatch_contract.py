"""Canonical Plan materialization dispatch contracts (issue #4800).

This only tests approved job arguments and fail-closed admission; never
dispatches a real Celery job or contacts an infrastructure provider.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes import plan_dispatch
from app.infrastructure_automation.kubernetes.plan_review import PLAN_OPERATION


def _connection() -> SimpleNamespace:
    return SimpleNamespace(
        id=31,
        integration_type='configuration_automation',
        provider_key='ansible',
        enabled=True,
        lifecycle_status='active',
    )


def _stub_qualified(monkeypatch: pytest.MonkeyPatch, *, outcome: str = 'qualified') -> list:
    recorded: list = []
    preflight = SimpleNamespace(
        state='ready_for_review' if outcome != 'blocked' else 'blocked',
        facts_job_public_id='job-55',
        host_registry_fingerprint='b' * 64,
        host_access_fingerprint='c' * 64,
    )
    host_job = SimpleNamespace(id=55, public_id='job-55', integration_instance_id=31)

    class FakeQuery:
        def filter_by(self, **kwargs):
            assert kwargs == {'public_id': 'job-55'}
            return self

        def first(self):
            return None if outcome == 'missing_job' else host_job

    fake_plan = SimpleNamespace(
        status='requires_independent_approval' if outcome != 'invalid_plan' else 'blocked',
        plan_fingerprint='a' * 64 if outcome != 'invalid_plan' else None,
        source_sha='1' * 40,
        host_registry_fingerprint='b' * 64,
        host_access_fingerprint='d' * 64 if outcome == 'access_drift' else 'c' * 64,
        dispatch_parameters=lambda: {
            'plan_fingerprint': 'a' * 64,
            'host_preflight_job_public_id': 'job-55',
            'source_sha': '1' * 40,
            'host_registry_fingerprint': 'b' * 64,
            'host_access_fingerprint': 'c' * 64,
        },
    )
    monkeypatch.setattr(plan_dispatch, 'committed_kubespray_preflight', lambda connection: preflight)
    monkeypatch.setattr(plan_dispatch, 'JobExecution', SimpleNamespace(query=FakeQuery()))
    monkeypatch.setattr(plan_dispatch, 'build_kubespray_plan_review', lambda conn, job: fake_plan)

    def fake_enqueue(**kwargs):
        recorded.append(kwargs)
        return SimpleNamespace(id=98), True

    monkeypatch.setattr(plan_dispatch, 'enqueue_canonical_job', fake_enqueue)
    return recorded


def test_review_only_dispatch_uses_existing_job_worker_and_secret_safe_ids(monkeypatch) -> None:
    calls = _stub_qualified(monkeypatch)
    job, created = plan_dispatch.dispatch_kubespray_plan_review(_connection(), user_id=42)
    assert created is True
    assert job.id == 98
    assert len(calls) == 1
    params = calls[0]
    assert params['operation'] == PLAN_OPERATION
    assert params['job_type'] == 'infrastructure_automation'
    assert params['queue_name'] == 'automation'
    assert params['integration_type'] == 'configuration_automation'
    assert params['integration_instance_id'] == 31
    assert params['task_kwargs'] == {'connection_id': 31, 'host_preflight_job_id': 55}
    assert params['parameters'] == {
        'plan_fingerprint': 'a' * 64,
        'host_preflight_job_public_id': 'job-55',
        'source_sha': '1' * 40,
        'host_registry_fingerprint': 'b' * 64,
        'host_access_fingerprint': 'c' * 64,
    }
    assert params['resource_group'] == 'kubespray:plan-review:31'
    assert params['requested_by_user_id'] == 42
    assert params['max_attempts'] == 1
    assert params['dispatch_options'].require_registered_worker is True
    assert 'ssh' not in repr(params).lower()
    assert 'password' not in repr(params).lower()
    assert 'inventory_path' not in repr(params).lower()


@pytest.mark.parametrize(
    'bad_change',
    [
        {'integration_type': 'registry'},
        {'provider_key': 'harbor'},
        {'enabled': False},
        {'lifecycle_status': 'deleted'},
    ],
)
def test_unqualified_connection_never_creates_plan_job(monkeypatch, bad_change) -> None:
    calls = _stub_qualified(monkeypatch)
    connection = _connection()
    for field, value in bad_change.items():
        setattr(connection, field, value)
    with pytest.raises(plan_dispatch.KubesprayPlanNotQualified):
        plan_dispatch.dispatch_kubespray_plan_review(connection, user_id=42)
    assert calls == []


@pytest.mark.parametrize('outcome', ['blocked', 'missing_job', 'invalid_plan', 'access_drift'])
def test_missing_host_evidence_or_invalid_plan_fails_before_enqueue(monkeypatch, outcome) -> None:
    calls = _stub_qualified(monkeypatch, outcome=outcome)
    with pytest.raises(plan_dispatch.KubesprayPlanNotQualified):
        plan_dispatch.dispatch_kubespray_plan_review(_connection(), user_id=42)
    assert calls == []


def test_actor_id_cannot_be_boolean(monkeypatch) -> None:
    calls = _stub_qualified(monkeypatch)
    with pytest.raises(plan_dispatch.KubesprayPlanNotQualified):
        plan_dispatch.dispatch_kubespray_plan_review(_connection(), user_id=True)
    assert calls == []
