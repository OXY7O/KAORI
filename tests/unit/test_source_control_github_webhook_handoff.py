"""Signed webhook outbox is committed BEFORE canonical job dispatch (#2742).

These are deterministic admission/claim tests; they do not expose a public
webhook route and do not run a live GitHub provider.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import webhook_handoff
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError
from app.platform_operations.jobs.dispatcher import JobWorkerUnavailable


class FakeSession:
    def __init__(self, *, state='received', attempts=0, last_attempt_at=None):
        self.row = SimpleNamespace(
            id=11, installation_id=7, processing_state=state,
            attempt_count=attempts, last_attempt_at=last_attempt_at,
            dispatched_job_execution_id=None,
        )
        self.inst = SimpleNamespace(id=7)
        self.commits = []
        self.rollbacks = 0

    def execute(self, _query):
        return SimpleNamespace(scalar_one_or_none=lambda: self.row)

    def get(self, _model, _identity):
        return self.inst

    def commit(self):
        self.commits.append(self.row.processing_state)

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def valid_committed_scope(monkeypatch):
    monkeypatch.setattr(
        webhook_handoff, 'resolve_reconciliation_intent',
        lambda **_: SimpleNamespace(scope='installation', installation_record_id=7),
    )


def test_commit_precedes_canonical_queue_and_linking(monkeypatch):
    session = FakeSession()
    events = []
    original = session.commit

    def commit():
        events.append(('commit', session.row.processing_state))
        original()
    session.commit = commit

    def enqueue(**kwargs):
        events.append(('enqueue', session.row.processing_state))
        assert kwargs == {
            'requested_by_user_id': None, 'trigger_type': 'on_demand',
            'installation_record_id': 7,
        }
        return SimpleNamespace(id=91), True
    monkeypatch.setattr(webhook_handoff, 'enqueue_source_repository_sync', enqueue)

    result = webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert result.state == 'queued'
    assert result.job_execution_id == 91
    assert result.created_job
    assert events == [
        ('commit', 'dispatching'), ('enqueue', 'dispatching'), ('commit', 'queued'),
    ]
    assert session.row.dispatched_job_execution_id == 91


def test_queued_delivery_is_idempotent(monkeypatch):
    session = FakeSession(state='queued', attempts=1)
    session.row.dispatched_job_execution_id = 89
    monkeypatch.setattr(
        webhook_handoff, 'enqueue_source_repository_sync',
        lambda **_: pytest.fail('a queued delivery must not re-dispatch'),
    )
    result = webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert not result.created_job
    assert result.job_execution_id == 89
    assert session.commits == []


def test_recent_retry_has_bounded_backoff(monkeypatch):
    now = datetime.now(UTC)
    session = FakeSession(state='retry_pending', attempts=1, last_attempt_at=now)
    monkeypatch.setattr(
        webhook_handoff, 'enqueue_source_repository_sync',
        lambda **_: pytest.fail('bounded retry cannot enqueue early'),
    )
    result = webhook_handoff.dispatch_committed_delivery(
        session, delivery_record_id=11, now=now + timedelta(seconds=30),
    )
    assert result.state == 'retry_pending'
    assert session.commits == []


def test_failure_before_job_creation_allows_bounded_retry(monkeypatch):
    session = FakeSession()

    def fail(**_kwargs):
        raise JobWorkerUnavailable('queue unavailable')

    monkeypatch.setattr(webhook_handoff, 'enqueue_source_repository_sync', fail)
    with pytest.raises(JobWorkerUnavailable, match='queue unavailable'):
        webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert session.commits == ['dispatching', 'retry_pending']
    assert session.rollbacks == 1
    assert session.row.dispatched_job_execution_id is None


def test_ambiguous_failure_after_worker_acceptance_must_not_auto_retry(monkeypatch):
    session = FakeSession()
    # Simulate a canonical dispatcher returning an unusable JobExecution ID
    # AFTER queue admission. The status must be operator review, not retry.
    monkeypatch.setattr(
        webhook_handoff, 'enqueue_source_repository_sync',
        lambda **_: (SimpleNamespace(id='malformed'), True),
    )
    with pytest.raises(ValueError):
        webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert session.commits == ['dispatching', 'dispatch_uncertain']
    assert session.row.processing_state == 'dispatch_uncertain'


def test_exhausted_attempts_never_enqueue(monkeypatch):
    session = FakeSession(state='retry_pending', attempts=3)
    monkeypatch.setattr(
        webhook_handoff, 'enqueue_source_repository_sync',
        lambda **_: pytest.fail('attempt limit must not be bypassed'),
    )
    result = webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert result.state == 'requires_review'
    assert session.commits == ['requires_review']


def test_scope_failure_happens_before_committing_or_dispatch(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(
        webhook_handoff, 'resolve_reconciliation_intent',
        lambda **_: (_ for _ in ()).throw(GitHubWebhookError('cross-installation')),
    )
    monkeypatch.setattr(
        webhook_handoff, 'enqueue_source_repository_sync',
        lambda **_: pytest.fail('cross-installation cannot create JobExecution'),
    )
    with pytest.raises(GitHubWebhookError):
        webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert session.commits == []


def test_abandoned_claim_becomes_uncertain_not_automatically_retried():
    now = datetime.now(UTC)
    session = FakeSession(state='dispatching', attempts=1,
                          last_attempt_at=now - timedelta(minutes=30))
    assert webhook_handoff.flag_abandoned_dispatch(
        session, delivery_record_id=11, now=now,
    )
    assert session.row.processing_state == 'dispatch_uncertain'
    assert session.commits == ['dispatch_uncertain']


def test_invalid_delivery_id_does_not_broaden_scope():
    with pytest.raises(GitHubWebhookError):
        webhook_handoff.dispatch_committed_delivery(FakeSession(), delivery_record_id=0)



def test_unknown_dispatch_failure_is_held_for_review_not_reenqueued(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(
        webhook_handoff, 'enqueue_source_repository_sync',
        lambda **_: (_ for _ in ()).throw(RuntimeError('broker acknowledgment unknown')),
    )
    with pytest.raises(RuntimeError):
        webhook_handoff.dispatch_committed_delivery(session, delivery_record_id=11)
    assert session.row.processing_state == 'dispatch_uncertain'
    assert session.commits == ['dispatching', 'dispatch_uncertain']
