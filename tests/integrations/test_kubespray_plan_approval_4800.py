"""Plan acknowledgement and currentness contract, not mutation admission."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes import plan_approval as service

_NOW = datetime(2026, 11, 28, 1, tzinfo=UTC)
_EXPIRY = _NOW + timedelta(minutes=15)
_WINDOW = service.PlanWindow(_NOW, _NOW + timedelta(hours=1), 'CHG-1234')
_SUMMARY = {
    'plan_fingerprint': 'a' * 64,
    'inventory_fingerprint': 'b' * 64,
    'host_registry_fingerprint': 'c' * 64,
    'host_access_fingerprint': 'd' * 64,
    'source_sha': 'e' * 40,
    'execution_environment_digest': 'sha256:' + 'f' * 64,
}


def _job():
    return SimpleNamespace(id=1, public_id='plan-fixture', requested_by_user_id=7, integration_instance_id=31)


def _record(window=_WINDOW, checker=9):
    return service._approval_record(
        _job(), _SUMMARY, checker_id=checker, window=window, now=_NOW, expiry=_EXPIRY
    )


def test_exact_window_and_independent_checker_record_never_authorizes_run():
    record = _record()
    assert record['requested_by'] == 7
    assert record['approved_by'] == 9
    assert record['approval_expires_at'] == _EXPIRY.isoformat()
    assert record['window_end'] == _WINDOW.ends_at.isoformat()
    assert record['execution_authorized'] is False
    assert record['mutation_authorized'] is False


@pytest.mark.parametrize('checker', [7, 0, True])
def test_self_approval_or_invalid_checker_denied(checker):
    with pytest.raises(service.PlanApprovalDenied):
        _record(checker=checker)


@pytest.mark.parametrize('window', [
    replace(_WINDOW, ends_at=_NOW),
    replace(_WINDOW, ends_at=_NOW + timedelta(hours=3)),
    replace(_WINDOW, starts_at=_EXPIRY),
    replace(_WINDOW, starts_at=_NOW.replace(tzinfo=None)),
    replace(_WINDOW, change_reference='bad\nreference'),
])
def test_unqualified_window_denied(window):
    with pytest.raises(service.PlanApprovalDenied):
        _record(window=window)


@pytest.fixture
def approval_store(monkeypatch):
    job = _job()
    record = _record()
    row = SimpleNamespace(action=service._ACK, actor_user_id=9, metadata_json=record)
    monkeypatch.setattr(service, 'local_security_review_enabled', lambda: True)
    monkeypatch.setattr(service, '_current_plan', lambda *args, **kwargs: (job, _SUMMARY, _EXPIRY))
    monkeypatch.setattr(service, '_latest_ack', lambda *args: row)
    monkeypatch.setattr(service, 'lock_explicit_permissions', lambda *args: True)
    return job, row


def _review(now=_NOW + timedelta(seconds=1)):
    return service.review_current_plan_acknowledgement(connection_id=31, plan_fingerprint='a' * 64, now=now)


def test_latest_ack_requalified_and_expiry_denies(approval_store):
    _, row = approval_store
    assert _review() == row.metadata_json
    assert _review(_EXPIRY) is None
    row.action = service._REVOKE
    assert _review() is None


@pytest.mark.parametrize('changes', [
    {'schema_version': True},
    {'plan_job_public_id': 'other'},
    {'plan_fingerprint': '9' * 64},
    {'inventory_fingerprint': '9' * 64},
    {'host_access_fingerprint': '9' * 64},
    {'approved_by': 7},
    {'execution_authorized': True},
    {'mutation_authorized': True},
    {'approval_expires_at': (_EXPIRY + timedelta(hours=1)).isoformat()},
    {'extra': 'not-in-contract'},
])
def test_latest_ack_drift_denies(approval_store, changes):
    _, row = approval_store
    row.metadata_json = {**row.metadata_json, **changes}
    assert _review() is None


def test_future_window_and_lost_permission_deny(approval_store, monkeypatch):
    _, row = approval_store
    row.metadata_json = _record(replace(_WINDOW, starts_at=_NOW + timedelta(minutes=2)))
    assert _review() is None
    assert _review(_NOW + timedelta(minutes=3)) is not None
    monkeypatch.setattr(service, 'lock_explicit_permissions', lambda *args: False)
    assert _review(_NOW + timedelta(minutes=3)) is None


def test_unavailable_current_plan_denies(approval_store, monkeypatch):
    def denied(*args, **kwargs):
        raise service.PlanApprovalDenied('fixture drift')

    monkeypatch.setattr(service, '_current_plan', denied)
    assert _review() is None
