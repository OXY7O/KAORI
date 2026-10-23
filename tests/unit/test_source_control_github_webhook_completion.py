"""Signed delivery terminal evidence is owned by scoped canonical JobExecution."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import webhook_completion


def _job(*, status='succeeded', scope_key='installation:7'):
    return SimpleNamespace(
        id=91, job_type='source_control_repository_inventory',
        operation='sync_source_control_repositories',
        integration_type='source_control', scope_type='source_control_installation',
        scope_key=scope_key, status=status,
    )


class FakeSession:
    def __init__(self, job, *, state='queued', linked=91):
        self.delivery = SimpleNamespace(
            id=11, installation_id=7, dispatched_job_execution_id=linked,
            processing_state=state, completed_at=None,
        )
        self.installation = SimpleNamespace(id=7)
        self.job = job
        self.commits = 0

    def execute(self, _query):
        return SimpleNamespace(scalar_one_or_none=lambda: self.delivery)

    def get(self, model, identity):
        if model is webhook_completion.SourceInstallation:
            return self.installation
        return self.job if identity == 91 else None

    def commit(self):
        self.commits += 1


@pytest.mark.parametrize('job_status,expected', [
    ('succeeded', 'reconciled_success'),
    ('partially_succeeded', 'reconciled_partial'),
    ('failed', 'reconciled_failure'),
    ('canceled', 'reconciled_canceled'),
])
def test_exact_scoped_terminal_job_controls_delivery_state(job_status, expected):
    session = FakeSession(_job(status=job_status))
    result = webhook_completion.reconcile_delivery_completion(
        session, delivery_record_id=11, now=datetime.now(UTC),
    )
    assert result == expected
    assert session.delivery.completed_at is not None
    assert session.commits == 1


@pytest.mark.parametrize('job_status', [
    'queued', 'running', 'retrying', 'cancel_requested',
])
def test_active_job_does_not_create_terminal_evidence(job_status):
    session = FakeSession(_job(status=job_status))
    assert webhook_completion.reconcile_delivery_completion(
        session, delivery_record_id=11,
    ) == 'queued'
    assert session.delivery.completed_at is None
    assert session.commits == 0


def test_wrong_installation_is_never_considered_complete():
    session = FakeSession(_job(scope_key='installation:999'))
    assert webhook_completion.reconcile_delivery_completion(
        session, delivery_record_id=11,
    ) == 'requires_review'
    assert session.delivery.completed_at is None


def test_missing_link_is_review_not_success():
    session = FakeSession(_job(), linked=None)
    assert webhook_completion.reconcile_delivery_completion(
        session, delivery_record_id=11,
    ) == 'requires_review'


@pytest.mark.parametrize('state', [
    'dispatch_uncertain', 'received', 'retry_pending', 'reconciled_success',
])
def test_unlinked_or_terminal_delivery_never_fabricates_success(state):
    session = FakeSession(_job(), state=state)
    assert webhook_completion.reconcile_delivery_completion(
        session, delivery_record_id=11,
    ) == state
    assert session.commits == 0


def test_expired_job_demands_review():
    session = FakeSession(_job(status='expired'))
    assert webhook_completion.reconcile_delivery_completion(
        session, delivery_record_id=11,
    ) == 'requires_review'


@pytest.mark.parametrize('identity', [0, -1, None, True])
def test_unqualified_delivery_id_denied(identity):
    with pytest.raises(ValueError):
        webhook_completion.reconcile_delivery_completion(
            FakeSession(_job()), delivery_record_id=identity,
        )


def test_completion_never_calls_github_or_queues_again():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] /
        'app/integrations/source_control/source_control/providers/github/webhook_completion.py'
    ).read_text()
    assert 'enqueue_source_repository_sync(' not in src
    assert 'GitHubAppClient' not in src
    assert 'apply_async(' not in src
    assert 'reconciled_success' in src
