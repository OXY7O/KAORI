"""Governed replacement keeps an active factor until committed verification (#5357)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.mfa import service
from app.access.authentication.session_lifecycle import SessionPolicy
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User


@pytest.fixture
def replacement_fixture(monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(UTC)
    user = User(
        id=42,
        auth_source='database',
        auth_session_version=7,
        account_is_active=True,
        is_super_admin=True,
        auth_session_issued_at=now,
        auth_session_activity_at=now,
    )
    factor = AuthenticationMfaFactor(
        enabled=True, totp_secret='existing-test-seed', recovery_hashes=['old-test-hash'], last_accepted_step=1
    )
    store = Mock()
    stage = Mock(return_value=object())
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, '_lock_mfa_user', Mock(return_value=user))
    monkeypatch.setattr(service, '_locked_factor', Mock(return_value=factor))
    monkeypatch.setattr(service, 'stage_authentication_security_event', stage)
    monkeypatch.setattr(service, '_accepted_step', Mock(return_value=2))
    monkeypatch.setattr(service, 'read_session_policy', lambda: SessionPolicy())
    monkeypatch.setattr(service, 'generate_password_hash', lambda _: 'new-test-hash')
    monkeypatch.setattr(User, 'check_password', lambda self, value: value == 'fixture-password')
    return user, factor, store, stage


def test_begin_preserves_active_factor_and_confirmation_rotates_generation(replacement_fixture) -> None:
    user, factor, store, stage = replacement_fixture
    issued_at = user.auth_session_issued_at
    activity_at = user.auth_session_activity_at
    seed = service.begin_mfa_replacement(user, '123456', expected_generation=7, current_password='fixture-password')
    assert factor.totp_secret == 'existing-test-seed'
    assert factor.recovery_hashes == ['old-test-hash']
    assert factor.replacement_totp_secret == seed
    assert factor.replacement_generation == 7
    assert user.auth_session_version == 7
    assert store.commit.call_count == 1

    codes, issued_generation = service.confirm_mfa_replacement(user, '654321', expected_generation=7)
    assert len(codes) == 8
    assert factor.enabled
    assert factor.totp_secret == seed
    assert factor.recovery_hashes == ['new-test-hash'] * 8
    assert factor.replacement_totp_secret is None
    assert factor.replacement_generation is None
    assert factor.replacement_expires_at is None
    assert issued_generation == user.auth_session_version == 8
    assert user.auth_session_issued_at == issued_at
    assert user.auth_session_activity_at == activity_at
    assert stage.call_args.kwargs['action'] == 'mfa_replacement_confirmed'
    assert store.commit.call_count == 2


@pytest.mark.parametrize('failure', ('stale', 'expired', 'invalid', 'external', 'audit', 'commit'))
def test_confirmation_failures_do_not_commit(failure: str, replacement_fixture, monkeypatch) -> None:
    user, factor, store, stage = replacement_fixture
    factor.replacement_totp_secret = 'new-test-seed'
    factor.replacement_generation = 8 if failure == 'stale' else 7
    factor.replacement_expires_at = datetime.now(UTC) + timedelta(seconds=-1 if failure == 'expired' else 60)
    if failure == 'invalid':
        monkeypatch.setattr(service, '_accepted_step', Mock(return_value=None))
    if failure == 'external':
        user.auth_source = 'ldap'
    if failure == 'audit':
        stage.side_effect = SQLAlchemyError('simulated audit failure')
    if failure == 'commit':
        store.commit.side_effect = SQLAlchemyError('simulated commit failure')
    with pytest.raises((service.MfaVerificationError, SQLAlchemyError)):
        service.confirm_mfa_replacement(user, '654321', expected_generation=7)
    store.rollback.assert_called_once()
    if failure != 'commit':
        store.commit.assert_not_called()
    if failure not in {'audit', 'commit'}:
        assert factor.totp_secret == 'existing-test-seed'
        assert user.auth_session_version == 7


def test_cancel_preserves_active_factor(replacement_fixture) -> None:
    user, factor, store, stage = replacement_fixture
    factor.replacement_totp_secret = 'new-test-seed'
    factor.replacement_generation = 7
    service.cancel_mfa_replacement(user, expected_generation=7)
    assert factor.enabled and factor.totp_secret == 'existing-test-seed'
    assert factor.recovery_hashes == ['old-test-hash']
    assert factor.replacement_generation is None
    assert factor.replacement_totp_secret is None
    assert stage.call_args.kwargs['action'] == 'mfa_replacement_cancelled'
    store.commit.assert_called_once()


@pytest.mark.parametrize('source,password', [('database', 'wrong'), ('ldap', None), ('google', None), ('github', None)])
def test_begin_denies_unverified_primary(source, password, replacement_fixture) -> None:
    user, factor, store, _ = replacement_fixture
    user.auth_source = source
    with pytest.raises(service.MfaVerificationError):
        service.begin_mfa_replacement(user, '123456', expected_generation=7, current_password=password)
    assert factor.replacement_totp_secret is None
    assert factor.totp_secret == 'existing-test-seed'
    store.commit.assert_not_called()
    store.rollback.assert_called_once()
