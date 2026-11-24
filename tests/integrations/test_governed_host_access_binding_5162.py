"""Governed metadata binding must be atomic, non-executable and default-deny."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure_automation import host_access_binding as service
from app.infrastructure_automation.host_access_reference import HostAccessReferenceReview
from app.models.automation import AutomationHostAccessBinding


@pytest.fixture
def transaction(monkeypatch):
    intent = service.HostAccessBindingIntent(
        connection_id=7,
        host_id=str(uuid4()),
        expected_host_revision='a' * 64,
        scope_ref=str(uuid4()),
        secret_identity_id=str(uuid4()),
        expected_secret_version=2,
        host_key_digest='sha256:' + 'b' * 64,
    )
    events = []
    connection = SimpleNamespace(id=7)
    assignment = SimpleNamespace(id=17)
    policy = SimpleNamespace(id=intent.scope_ref, integration_instance_id=31, current_revision=3)
    representation = SimpleNamespace(id=41, secret_identity_id=intent.secret_identity_id)
    review = HostAccessReferenceReview('references_recorded', 'REVIEW_ONLY', 'c' * 64, True, True)

    def get(model, key, **kwargs):
        if model is service.IntegrationInstance:
            return connection if key == 7 else SimpleNamespace(id=31)
        if model is service.SecretIdentity:
            return SimpleNamespace(id=key)
        return None

    monkeypatch.setattr(service, '_require_actor', lambda actor_id: None)
    monkeypatch.setattr(service, '_require_scope', lambda *args: policy)
    monkeypatch.setattr(service, 'get_scoped_host_assignment', lambda *args, **kwargs: assignment)
    monkeypatch.setattr(service, 'host_revision', lambda item: intent.expected_host_revision)
    monkeypatch.setattr(service, '_locked_collection', lambda item: object())
    monkeypatch.setattr(service, '_selected_representation', lambda *args: representation)
    monkeypatch.setattr(service, '_selected_version', lambda *args: SimpleNamespace(version=2))
    monkeypatch.setattr(service, 'assess_scoped_host_access_references', lambda **kwargs: review)
    monkeypatch.setattr(service.db.session, 'get', get)
    monkeypatch.setattr(service.db.session, 'add', lambda row: events.append(('add', row)))
    monkeypatch.setattr(service.db.session, 'commit', lambda: events.append(('commit', None)))
    monkeypatch.setattr(service.db.session, 'rollback', lambda: events.append(('rollback', None)))
    monkeypatch.setattr(service, 'stage_operational_activity', lambda **kwargs: events.append(('audit', kwargs)))
    return intent, events, get


def test_candidate_and_mandatory_audit_share_one_transaction(transaction):
    intent, events, _ = transaction
    result = service.record_host_access_reference(actor_id=11, intent=intent)
    assert [event[0] for event in events] == ['add', 'audit', 'commit']
    binding = events[0][1]
    assert isinstance(binding, AutomationHostAccessBinding)
    assert binding.assignment_id == 17
    assert binding.secret_representation_id == 41
    assert binding.secret_version == 2
    assert binding.recorded_by_user_id == 11
    audit = events[1][1]['metadata']
    assert audit['policy_ref'] == intent.scope_ref
    assert audit['policy_revision'] == 3
    assert audit['execution_authorized'] is False
    assert intent.host_key_digest not in str(audit)
    assert intent.secret_identity_id not in str(audit)
    assert result.execution_authorized is False


@pytest.mark.parametrize(
    'changes',
    [
        {'connection_id': 0},
        {'host_id': '../host'},
        {'scope_ref': 'guessed'},
        {'secret_identity_id': 'raw/path'},
        {'expected_secret_version': True},
        {'expected_host_revision': 'old'},
        {'host_key_digest': 'raw-key'},
    ],
)
def test_bad_intent_never_stages_reference_or_audit(transaction, changes):
    intent, events, _ = transaction
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=11, intent=replace(intent, **changes))
    assert events == [('rollback', None)]


def test_existing_candidate_cannot_be_overwritten(transaction, monkeypatch):
    intent, events, get = transaction

    def existing(model, key, **kwargs):
        if model is AutomationHostAccessBinding:
            return object()
        return get(model, key, **kwargs)

    monkeypatch.setattr(service.db.session, 'get', existing)
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=11, intent=intent)
    assert events == [('rollback', None)]


def test_audit_failure_rolls_back_reference_without_commit(transaction, monkeypatch):
    intent, events, _ = transaction

    def fail(**kwargs):
        raise RuntimeError('sensitive provider detail')

    monkeypatch.setattr(service, 'stage_operational_activity', fail)
    with pytest.raises(service.HostAccessBindingDenied) as caught:
        service.record_host_access_reference(actor_id=11, intent=intent)
    assert [event[0] for event in events] == ['add', 'rollback']
    assert 'sensitive provider detail' not in str(caught.value)


def test_stale_revision_rolls_back_before_write(transaction, monkeypatch):
    intent, events, _ = transaction
    monkeypatch.setattr(service, 'host_revision', lambda item: 'd' * 64)
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=11, intent=intent)
    assert events == [('rollback', None)]


def test_scope_evaluator_requires_exact_policy_revision(monkeypatch):
    now = datetime.now(UTC)
    policy = SimpleNamespace(
        id=str(uuid4()),
        principal_user_id=11,
        permission_key='secrets_pki.view',
        scope_level='vault_mount',
        integration_instance_id=31,
        provider_namespace='',
        mount='fixture',
        current_revision=2,
    )
    monkeypatch.setattr(service.db.session, 'get', lambda *args: policy)

    def evaluate(**kwargs):
        assert kwargs['lock_for_read'] is True
        return SimpleNamespace(allowed=True, policy_ref=policy.id, revision=1, expires_at=now + timedelta(minutes=5))

    monkeypatch.setattr(service, 'evaluate_exact_vault_scope', evaluate)
    with pytest.raises(service.HostAccessBindingDenied):
        service._require_scope(11, policy.id, now)
