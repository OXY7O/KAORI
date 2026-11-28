"""Runtime activation request is canonical audit intent, never approval (#5466)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation import remote_activation_request as service
from app.infrastructure_automation.kubernetes.source_policy import SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_target import SourceOnlyActivationIntent

_NOW = datetime(2026, 11, 28, 1, tzinfo=UTC)
_EXPIRY = _NOW + timedelta(minutes=5)


@pytest.fixture
def store(monkeypatch):
    intent = SourceOnlyActivationIntent(
        31, 7, SOURCE_CANDIDATE_SHA, 'sha256:' + 'a' * 64,
        'b' * 64, 'c' * 64, 'd' * 64, _EXPIRY,
    )
    state = SimpleNamespace(intent=intent, row=None, permitted=True, events=[])
    monkeypatch.setattr(service, 'review_enabled', lambda: True)
    monkeypatch.setattr(service, 'begin_security_review_transaction', lambda: state.events.append('begin'))
    monkeypatch.setattr(service, 'lock_explicit_permissions', lambda *args: state.permitted)
    monkeypatch.setattr(service, 'review_source_only_activation_intent', lambda **kwargs: state.intent)
    monkeypatch.setattr(service, '_latest_request', lambda *args: state.row)
    monkeypatch.setattr(service, 'AuditEvent', SimpleNamespace)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        add=lambda row: (setattr(state, 'row', row), state.events.append('add')),
        commit=lambda: state.events.append('commit'),
        rollback=lambda: state.events.append('rollback'),
    )))
    # The writer uses the actual UTC clock. Freeze the evidence relative to
    # that clock so this regression remains independent of calendar date.
    state.intent = replace(intent, expires_at=datetime.now(UTC) + timedelta(minutes=5))
    return state


def _request():
    return service.request_remote_runtime_activation(connection_id=31, actor_id=7)


def _review(now=None):
    return service.review_current_activation_request(connection_id=31, actor_id=7, now=now or datetime.now(UTC))


def test_request_commits_audit_without_any_activation_or_execution(store):
    record = _request()
    assert store.events == ['begin', 'add', 'commit']
    assert store.row.action == service._ACTION
    assert store.row.actor_user_id == 7
    assert record['status'] == 'pending_independent_admission'
    assert record['runtime_activation_authorized'] is False
    assert record['execution_authorized'] is False
    assert record['mutation_authorized'] is False
    assert _review() == record
    with pytest.raises(service.RemoteActivationRequestDenied):
        _request()
    assert store.events[-2:] == ['begin', 'rollback']


@pytest.mark.parametrize('failure', ['permission', 'missing', 'actor', 'expired', 'execution', 'wrong_source'])
def test_invalid_prerequisites_roll_back_without_audit(store, failure):
    if failure == 'permission':
        store.permitted = False
    elif failure == 'missing':
        store.intent = None
    elif failure == 'actor':
        store.intent = replace(store.intent, actor_id=8)
    elif failure == 'expired':
        store.intent = replace(store.intent, expires_at=_NOW)
    elif failure == 'execution':
        store.intent = replace(store.intent, execution_authorized=True)
    else:
        store.intent = replace(store.intent, source_sha='0' * 40)
    with pytest.raises(service.RemoteActivationRequestDenied):
        _request()
    assert store.events == ['begin', 'rollback']
    assert store.row is None


def test_drift_during_request_denies_before_audit(store, monkeypatch):
    intents = iter((store.intent, replace(store.intent, access_fingerprint='9' * 64)))
    monkeypatch.setattr(service, 'review_source_only_activation_intent', lambda **kwargs: next(intents))
    with pytest.raises(service.RemoteActivationRequestDenied):
        _request()
    assert store.events == ['begin', 'rollback']
    assert store.row is None


@pytest.mark.parametrize('field,value', [
    ('schema_version', True), ('runtime_activation_authorized', True),
    ('execution_authorized', True), ('mutation_authorized', True),
    ('inventory_fingerprint', '9' * 64), ('remote_candidate_sha', '9' * 40),
    ('request_fingerprint', '9' * 64), ('extra', 'unexpected'),
])
def test_request_record_tamper_is_not_current(store, field, value):
    record = _request()
    store.row.metadata_json = {**record, field: value}
    assert _review() is None


def test_expiry_access_drift_and_permission_loss_block_readback(store):
    _request()
    assert _review(store.intent.expires_at) is None
    original = store.intent
    store.intent = replace(original, access_fingerprint='9' * 64)
    assert _review() is None
    store.intent = original
    store.permitted = False
    assert _review() is None


def test_audit_commit_error_rolls_back(store, monkeypatch):
    def fail():
        raise RuntimeError('fixture database failure')

    monkeypatch.setattr(service.db.session, 'commit', fail)
    with pytest.raises(RuntimeError, match='fixture database failure'):
        _request()
    assert store.events == ['begin', 'add', 'rollback']
