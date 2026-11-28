"""AL-02 source and transaction boundary regressions."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from flask import Flask
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication import local_database, login_protection, services
from app.access.authentication.lockout_policy import LockoutGate, LockoutMode, LockoutState, inspect_state
from app.access.authentication.lockout_state import LockedAccountState
from app.access.authentication.login_protection import LoginProtectionUnavailable, LoginRequestProtection
from app.access.authentication.results import LocalCredentialProof
from app.access.authentication.session import AuthSessionError
from app.models import User

NOW = datetime(2026, 11, 28, tzinfo=UTC)


def _context(mode: LockoutMode, *, gated: bool = False) -> LockedAccountState:
    state = (
        LockoutState((NOW - timedelta(seconds=1),) * 3, cooldown_until=NOW + timedelta(seconds=4))
        if gated else LockoutState()
    )
    return LockedAccountState(1, 2, None, inspect_state(mode, state, now=NOW), NOW)


@pytest.mark.parametrize('mode', (LockoutMode.DISABLED, LockoutMode.MONITOR_ONLY, LockoutMode.ENFORCED))
def test_request_policy_and_monitor_budget(monkeypatch: pytest.MonkeyPatch, mode: LockoutMode) -> None:
    monkeypatch.setattr(login_protection, 'read_login_policy', lambda: (mode, 2))
    budget = Mock(return_value=True)
    monkeypatch.setattr(login_protection, 'shared_identity_budget', budget)
    app = Flask(__name__)
    with app.app_context():
        result = login_protection.check_login_request('fixture')
    assert result.revision == 2
    assert result.over_budget == (mode != LockoutMode.DISABLED)
    assert result.blocked == (mode == LockoutMode.ENFORCED)
    assert budget.call_count == int(mode != LockoutMode.DISABLED)


def test_bucket_is_private_normalized_namespaced_and_bounded() -> None:
    secret = 'fixture-secret-key-not-production'
    key = login_protection.identity_bucket('  ExampleUser ', secret)
    assert key == login_protection.identity_bucket('exampleuser', secret)
    assert key != login_protection.identity_bucket('exampleuser', secret + '-other')
    assert 'exampleuser' not in key.lower() and secret not in key
    assert 0 <= int(key.rsplit(':', 1)[1], 16) < login_protection.BUCKET_COUNT


def test_shared_budget_requires_redis_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='fixture-secret-key-not-production', RATELIMIT_ENABLED=True,
                      RATELIMIT_STORAGE_URI='memory://')
    client = Mock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    factory.return_value.__exit__.return_value = False
    monkeypatch.setattr(login_protection.Redis, 'from_url', factory)
    with app.app_context():
        with pytest.raises(LoginProtectionUnavailable):
            login_protection.shared_identity_budget('fixture')
        factory.assert_not_called()
        app.config['RATELIMIT_STORAGE_URI'] = 'redis://localhost:6379/0'
        client.eval.return_value = 30
        assert not login_protection.shared_identity_budget('fixture')
        client.eval.return_value = 31
        assert login_protection.shared_identity_budget('fixture')
        assert client.eval.call_args.args[-2:] == (60, 30)
        client.eval.side_effect = RedisError('fixture')
        with pytest.raises(LoginProtectionUnavailable):
            login_protection.shared_identity_budget('fixture')
        app.config['RATELIMIT_IN_MEMORY_FALLBACK_ENABLED'] = True
        with pytest.raises(LoginProtectionUnavailable):
            login_protection.shared_identity_budget('fixture')


@pytest.mark.parametrize('mode,gated,verified,commit_failure', (
    (LockoutMode.ENFORCED, True, True, False),
    (LockoutMode.ENFORCED, False, False, False),
    (LockoutMode.ENFORCED, False, True, False),
    (LockoutMode.MONITOR_ONLY, True, True, False),
    (LockoutMode.ENFORCED, False, True, True),
))
def test_local_gate_and_outcome_commit(
    monkeypatch: pytest.MonkeyPatch, mode: LockoutMode, gated: bool, verified: bool, commit_failure: bool
) -> None:
    user = User(id=1, username='fixture', auth_source='database', account_is_active=True,
                password_hash='fixture-hash', auth_session_version=7, is_super_admin=False)
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = user
    lookup = Mock()
    lookup.filter.return_value.first.return_value = user
    # Avoid Flask-SQLAlchemy's app-context query descriptor in the mock fixture.
    monkeypatch.setattr(local_database, 'User', SimpleNamespace(
        query=lookup, id=User.id, username=User.username, auth_source=User.auth_source, deleted_at=User.deleted_at
    ))
    monkeypatch.setattr(local_database, 'select', lambda *_args: Mock(
        **{'where.return_value.with_for_update.return_value.execution_options.return_value': object()}
    ))
    monkeypatch.setattr(local_database, 'db', SimpleNamespace(session=store))
    verify = Mock(return_value=verified)
    monkeypatch.setattr(User, 'check_password', verify)
    dummy = Mock()
    stage = Mock()
    monkeypatch.setattr(local_database, '_dummy_check', dummy)
    monkeypatch.setattr(local_database, 'lock_account_state', lambda _id: _context(mode, gated=gated))
    monkeypatch.setattr(local_database, 'stage_password_outcome', stage)
    if commit_failure:
        store.commit.side_effect = SQLAlchemyError('fixture')
    result = local_database.DatabaseAuthProvider().authenticate(
        'fixture', 'fixture-password', protection=LoginRequestProtection(mode, 2)
    )
    if gated and mode == LockoutMode.ENFORCED:
        assert not result.success and result.reason == 'account_gate_rejected'
        verify.assert_not_called()
        dummy.assert_called_once()
        assert stage.call_args.kwargs['password_valid'] is None
    else:
        verify.assert_called_once()
        assert stage.call_args.kwargs['password_valid'] is verified
        assert result.success == (verified and not commit_failure)
    store.commit.assert_called_once()
    if commit_failure:
        store.rollback.assert_called_once()
        assert result.reason == 'database_unavailable'
        assert result.local_credential_proof is None


@pytest.mark.parametrize('pending', (False, True))
def test_final_generation_rechecks_gate_before_update(monkeypatch: pytest.MonkeyPatch, pending: bool) -> None:
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = 'fixture-hash'
    store.execute.return_value.one_or_none.return_value = (False, 'fixture-hash')
    monkeypatch.setattr(services, 'db', SimpleNamespace(session=store))
    context = _context(LockoutMode.ENFORCED, gated=True)
    assert context.decision.gate == LockoutGate.COOLDOWN
    monkeypatch.setattr(services, 'lock_account_state', lambda _id: context)
    user = User(id=1, auth_source='database')
    with pytest.raises(AuthSessionError):
        services.stage_successful_authentication(
            user, source='database', client_ip=None,
            pending_generation=7 if pending else None,
            local_credential_proof=None if pending else LocalCredentialProof('fixture-hash', 7),
        )
    assert all(str(call.args[0]).lower().startswith('select') for call in store.execute.call_args_list)
    store.commit.assert_not_called()
