"""MFA proof and recovery rotation share one transaction (#5342)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.mfa import service
from app.access.authentication.session_lifecycle import SessionPolicy
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User


def _user() -> User:
    now = datetime.now(UTC)
    return User(
        id=42,
        auth_source='database',
        auth_session_version=8,
        is_super_admin=True,
        account_is_active=True,
        auth_session_issued_at=now,
        auth_session_activity_at=now,
    )


@pytest.mark.parametrize('failure', ('none', 'stale', 'audit', 'commit', 'invalid_proof'))
def test_recovery_proof_and_rotation_commit_together(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    factor = AuthenticationMfaFactor(
        enabled=True, totp_secret='test-only-seed', recovery_hashes=['old-hash'], last_accepted_step=1
    )
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = None if failure == 'stale' else user
    if failure == 'commit':
        store.commit.side_effect = SQLAlchemyError('simulated commit failure')
    query = Mock()
    query.filter_by.return_value.with_for_update.return_value.populate_existing.return_value.first.return_value = factor
    stage = Mock(side_effect=[object(), SQLAlchemyError('simulated audit failure')] if failure == 'audit' else None)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, 'AuthenticationMfaFactor', SimpleNamespace(query=query))
    monkeypatch.setattr(service, 'read_session_policy', lambda: SessionPolicy())
    monkeypatch.setattr(User, 'check_password', lambda self, password: password == 'fixture-password')
    monkeypatch.setattr(service, 'stage_authentication_security_event', stage)
    monkeypatch.setattr(service, '_accepted_step', Mock(return_value=None if failure == 'invalid_proof' else 2))
    monkeypatch.setattr(service, 'check_password_hash', Mock(return_value=False))
    monkeypatch.setattr(service, 'generate_password_hash', lambda value: 'replacement-test-hash')
    timeline = Mock()
    timeline.attach_mock(store.add, 'stage')
    timeline.attach_mock(store.commit, 'commit')
    if failure == 'none':
        codes = service.regenerate_mfa_recovery_codes(
            user, '123456', expected_generation=8, current_password='fixture-password'
        )
        assert len(codes) == 8
        assert factor.last_accepted_step == 2
        assert factor.recovery_hashes == ['replacement-test-hash'] * 8
        assert [call[0] for call in timeline.mock_calls] == ['stage', 'stage', 'commit']
        assert [call.kwargs['action'] for call in stage.call_args_list] == [
            'mfa_challenge_verified',
            'mfa_recovery_regenerated',
        ]
        store.rollback.assert_not_called()
    else:
        with pytest.raises((service.MfaVerificationError, SQLAlchemyError)):
            service.regenerate_mfa_recovery_codes(
                user, '123456', expected_generation=8, current_password='fixture-password'
            )
        store.rollback.assert_called_once()
        if failure != 'commit':
            store.commit.assert_not_called()
        if failure == 'stale':
            query.filter_by.assert_not_called()
            stage.assert_not_called()
