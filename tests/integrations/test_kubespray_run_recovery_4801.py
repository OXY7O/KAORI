"""Recovery hold tests: no worker, provider operation or claim release."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask

from app.infrastructure_automation.kubernetes import run_recovery as service
from app.models.audit import AuditEvent


def _run(status='running'):
    old = datetime.now(UTC) - timedelta(hours=3)
    return SimpleNamespace(
        public_id='run-fixture', status=status, queued_at=old,
        heartbeat_at=old, started_at=old, cancel_requested_at=old,
        expires_at=None, result_summary_json=None, progress_message='Running',
        active_deduplication_key='fixture-slot', payload_json={'fixture': 'immutable'},
    )


@pytest.mark.parametrize(('status', 'reason'), [
    ('queued', 'queued_start_unconfirmed'),
    ('running', 'worker_heartbeat_stale'),
    ('retrying', 'worker_heartbeat_stale'),
    ('cancel_requested', 'cancellation_outcome_unconfirmed'),
])
def test_stale_reason_is_not_terminal_outcome(status, reason):
    with Flask(__name__).app_context():
        assert service._stale_reason(_run(status), datetime.now(UTC)) == reason


@pytest.mark.parametrize('status', ['succeeded', 'failed', 'expired', 'canceled', 'partially_succeeded'])
def test_terminal_status_not_admitted_to_active_hold(status):
    with Flask(__name__).app_context(), pytest.raises(service.RunRecoveryDenied):
        service._stale_reason(_run(status), datetime.now(UTC))


@pytest.mark.parametrize('status', ['queued', 'running', 'cancel_requested'])
def test_fresh_active_job_not_admitted_to_hold(status):
    run = _run(status)
    now = datetime.now(UTC)
    run.queued_at = run.started_at = run.heartbeat_at = run.cancel_requested_at = now
    with Flask(__name__).app_context(), pytest.raises(service.RunRecoveryDenied):
        service._stale_reason(run, now)


@pytest.mark.parametrize('failure', [None, 'permissions', 'duplicate', 'identity'])
def test_hold_commits_audit_without_changing_execution_or_claims(monkeypatch, failure):
    run = _run()
    plan = SimpleNamespace(public_id='plan-fixture')
    reservation = str(uuid4())
    if failure == 'duplicate':
        run.result_summary_json = {'recovery_hold': {'status': 'recovery_required'}}
    before = vars(run).copy()
    events = []
    audits = []
    monkeypatch.setattr(service, 'begin_security_review_transaction', lambda: None)
    monkeypatch.setattr(service, 'lock_explicit_permissions', lambda *args: failure != 'permissions')

    def lock(*args):
        if failure == 'identity':
            raise service.RunRecoveryDenied('fixture')
        return plan, run, 'a' * 64

    monkeypatch.setattr(service, '_lock_adopted_run', lock)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        add=audits.append, commit=lambda: events.append('commit'), rollback=lambda: events.append('rollback'),
    )))
    with Flask(__name__).app_context():
        if failure is not None:
            with pytest.raises(service.RunRecoveryDenied):
                service.record_run_recovery_hold(reservation_id=reservation, owner_id=9)
            assert vars(run) == before
            assert events == ['rollback']
            assert audits == []
            return
        evidence = service.record_run_recovery_hold(reservation_id=reservation, owner_id=9)
    assert evidence['recovery_owner_user_id'] == 9
    assert evidence['status'] == 'recovery_required'
    assert evidence['worker_stopped_verified'] is False
    assert evidence['provisioning_verified'] is False
    assert evidence['reservation_released'] is False
    assert evidence['execution_authorized'] is False
    assert run.result_summary_json == {'recovery_hold': evidence}
    assert {key: value for key, value in vars(run).items()
            if key not in ('result_summary_json', 'progress_message')} == {
        key: value for key, value in before.items() if key not in ('result_summary_json', 'progress_message')
    }
    assert len(audits) == 1 and isinstance(audits[0], AuditEvent)
    assert audits[0].metadata_json == evidence
    assert events == ['commit']


def test_recovery_actor_must_differ_from_adopter(monkeypatch):
    adoption = SimpleNamespace(adopted_by_user_id=7)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        execute=lambda statement: SimpleNamespace(scalar_one_or_none=lambda: adoption),
    )))
    with pytest.raises(service.RunRecoveryDenied):
        service._lock_adopted_run(str(uuid4()), 7)


@pytest.mark.parametrize('failure', [None, 'missing', 'released', 'wrong_fingerprint', 'wrong_reservation'])
def test_historical_claim_group_requires_exact_seven_active_resources(failure):
    reservation = str(uuid4())
    adoption = SimpleNamespace(reservation_id=reservation, plan_job_id=1, adopted_by_user_id=7)
    keys = ['kubespray:connection:31']
    keys.extend(f'kubespray:host:{uuid4()}' for _ in range(3))
    keys.extend(f'kubespray:endpoint:{i:064x}' for i in range(3))
    rows = [
        SimpleNamespace(
            reservation_id=reservation, plan_job_id=1, reserved_by_user_id=7, plan_fingerprint='a' * 64,
            resource_key=key, active_resource_key=key, released_at=None,
        )
        for key in keys
    ]
    if failure == 'missing':
        rows.pop()
    elif failure == 'released':
        rows[0].released_at = datetime.now(UTC)
    elif failure == 'wrong_fingerprint':
        rows[0].plan_fingerprint = 'b' * 64
    elif failure == 'wrong_reservation':
        rows[0].reservation_id = str(uuid4())
    if failure is None:
        service._require_claims(rows, adoption, 'a' * 64, 31)
    else:
        with pytest.raises(service.RunRecoveryDenied):
            service._require_claims(rows, adoption, 'a' * 64, 31)
