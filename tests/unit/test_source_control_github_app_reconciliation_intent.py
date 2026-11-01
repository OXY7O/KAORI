"""SC-02 only resolves verified delivery hints against committed grants."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import reconciliation_intent
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError


def _source(event_type='workflow_run', repository_id='501'):
    return SimpleNamespace(
        id=9,
        installation_id=7,
        processing_state='received',
        event_type=event_type,
        repository_native_id_hint=repository_id,
    )


def _installation():
    return SimpleNamespace(
        id=7,
        integration_instance_id=13,
        provider_key='github',
        host_key='github.com',
    )


class StubSession:
    def __init__(self, delivery, repository=None):
        self.delivery = delivery
        self.repository = repository
        self.executions = 0

    def get(self, _model, _id):
        return self.delivery

    def execute(self, _query):
        self.executions += 1
        return SimpleNamespace(scalar_one_or_none=lambda: self.repository)


def _admit(monkeypatch):
    monkeypatch.setattr(
        reconciliation_intent,
        '_eligible_installation',
        lambda _: 'never-return-raw-secret-in-intent',
    )


def test_current_grant_yields_repository_record_identity(monkeypatch):
    _admit(monkeypatch)
    session = StubSession(_source(), SimpleNamespace(id=501))
    intent = reconciliation_intent.resolve_reconciliation_intent(
        session=session,
        installation=_installation(),
        delivery_record_id=9,
    )
    assert intent.scope == 'repository'
    assert intent.repository_record_id == 501
    assert intent.integration_instance_id == 13
    assert intent.installation_record_id == 7
    assert session.executions == 1
    assert not hasattr(intent, 'repository_native_id_hint')
    assert 'secret' not in repr(intent)


def test_unknown_or_revoked_grant_cannot_target_payload_repository(monkeypatch):
    _admit(monkeypatch)
    session = StubSession(_source(repository_id='999'), repository=None)
    intent = reconciliation_intent.resolve_reconciliation_intent(
        session=session,
        installation=_installation(),
        delivery_record_id=9,
    )
    assert intent.scope == 'installation'
    assert intent.repository_record_id is None


@pytest.mark.parametrize('event', ['installation', 'installation_repositories'])
def test_installation_changes_require_grant_reconciliation(monkeypatch, event):
    _admit(monkeypatch)
    session = StubSession(_source(event_type=event), repository=SimpleNamespace(id=501))
    intent = reconciliation_intent.resolve_reconciliation_intent(
        session=session,
        installation=_installation(),
        delivery_record_id=9,
    )
    assert intent.scope == 'installation'
    assert session.executions == 0


def test_delivery_from_other_installation_is_denied(monkeypatch):
    _admit(monkeypatch)
    delivery = _source()
    delivery.installation_id = 88
    with pytest.raises(GitHubWebhookError, match='does not belong'):
        reconciliation_intent.resolve_reconciliation_intent(
            session=StubSession(delivery),
            installation=_installation(),
            delivery_record_id=9,
        )


def test_unadmitted_provider_denies_even_committed_delivery(monkeypatch):
    monkeypatch.setattr(
        reconciliation_intent,
        '_eligible_installation',
        lambda _: (_ for _ in ()).throw(GitHubWebhookError('not admitted')),
    )
    with pytest.raises(GitHubWebhookError, match='not admitted'):
        reconciliation_intent.resolve_reconciliation_intent(
            session=StubSession(_source()),
            installation=_installation(),
            delivery_record_id=9,
        )


@pytest.mark.parametrize('status', ['completed', 'processing', 'failed'])
def test_terminal_or_reserved_delivery_is_not_replayed(monkeypatch, status):
    _admit(monkeypatch)
    delivery = _source()
    delivery.processing_state = status
    with pytest.raises(GitHubWebhookError, match='not awaiting'):
        reconciliation_intent.resolve_reconciliation_intent(
            session=StubSession(delivery),
            installation=_installation(),
            delivery_record_id=9,
        )


def test_integration_intent_does_not_dispatch_or_publish_source_events():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = (
        root / 'app/integrations/source_control/source_control/providers/github/reconciliation_intent.py'
    ).read_text()
    assert 'apply_async(' not in source
    assert 'enqueue_canonical_job(' not in source
    assert 'db.session.commit(' not in source
    assert 'notify(' not in source
    assert 'event_payload' not in source
