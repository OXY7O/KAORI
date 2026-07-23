from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.resolver import orchestration
from app.resolver.orchestration import FailureClass, OrchestrationError


def journal(**overrides):
    base = dict(
        id=10,
        public_id='journal-10',
        orchestration_status='queued',
        next_retry_at=None,
        lease_expires_at=None,
        lease_owner=None,
        lease_acquired_at=None,
        last_heartbeat_at=None,
        attempt_count=0,
        max_attempts=3,
        completed_at=None,
        error_message=None,
        last_error_code=None,
        requested_by_user_id=7,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_second_worker_cannot_acquire_live_lease(monkeypatch) -> None:
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    record = journal(orchestration_status='running', lease_owner='worker-a', lease_expires_at=now + timedelta(minutes=1))
    monkeypatch.setattr(orchestration.db.session, 'get', lambda *args, **kwargs: record)
    monkeypatch.setattr(orchestration.db.session, 'flush', lambda: None)

    with pytest.raises(OrchestrationError, match='leased by another worker'):
        orchestration.acquire_execution_lease(record.id, owner='worker-b', now=now)


def test_retry_backoff_and_budget_are_persisted(monkeypatch) -> None:
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    record = journal(orchestration_status='running', lease_owner='worker-a', attempt_count=1)
    monkeypatch.setattr(orchestration.db.session, 'flush', lambda: None)

    retry = orchestration.record_execution_failure(
        record,
        owner='worker-a',
        failure_class=FailureClass.TIMEOUT,
        message='provider timeout',
        now=now,
    )

    assert retry is True
    assert record.orchestration_status == 'retry_wait'
    assert record.next_retry_at == now + timedelta(seconds=30)
    assert record.last_error_code == 'timeout'
    assert record.lease_owner is None


def test_terminal_failure_enters_dead_letter(monkeypatch) -> None:
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    record = journal(orchestration_status='running', lease_owner='worker-a', attempt_count=1)
    monkeypatch.setattr(orchestration.db.session, 'flush', lambda: None)

    retry = orchestration.record_execution_failure(
        record,
        owner='worker-a',
        failure_class=FailureClass.TERMINAL,
        message='validation rejected',
        now=now,
    )

    assert retry is False
    assert record.orchestration_status == 'dead_letter'
    assert record.completed_at == now
