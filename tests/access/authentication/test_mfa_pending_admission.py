"""One transaction for pending MFA proof, generation and audit (#5361)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.mfa import service
from app.access.authentication.session import AuthSessionError
from app.access.authentication.session_lifecycle import SessionPolicy
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User


@pytest.mark.parametrize('enrollment', (False, True))
@pytest.mark.parametrize('failure', ('none', 'issuance', 'audit', 'commit', 'expired', 'policy'))
def test_pending_proof_and_generation_share_commit(
    enrollment: bool, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    user = User(id=42, username='fixture', auth_source='database', auth_session_version=7, is_super_admin=True)
    factor = AuthenticationMfaFactor(
        enabled=not enrollment,
        totp_secret='test-seed',
        recovery_hashes=['old-test-hash'],
        enrollment_expires_at=now + timedelta(minutes=1),
        enrollment_generation=7,
        enrollment_authenticated=False,
    )
    store = Mock()
    store.get.return_value = SimpleNamespace(mfa_mode='disabled' if failure == 'policy' else 'required_all')
    events = Mock()
    events.attach_mock(store.commit, 'commit')
    events.attach_mock(store.rollback, 'rollback')
    proof = Mock(return_value=['one-time-test-code'] if enrollment else 'totp')
    issue = Mock(return_value=8)
    audit = Mock()
    events.attach_mock(proof, 'proof')
    events.attach_mock(issue, 'issue')
    events.attach_mock(audit, 'audit')
    if failure == 'issuance':
        issue.side_effect = AuthSessionError('fixture denial')
    if failure == 'audit':
        audit.side_effect = SQLAlchemyError('fixture audit failure')
    if failure == 'commit':
        store.commit.side_effect = SQLAlchemyError('fixture commit failure')
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, '_lock_mfa_user', Mock(return_value=user))
    monkeypatch.setattr(service, '_locked_factor', Mock(return_value=factor))
    monkeypatch.setattr(service, '_stage_enrollment_confirmation' if enrollment else '_consume_factor_proof', proof)
    monkeypatch.setattr(service, 'stage_successful_authentication', issue)
    monkeypatch.setattr(service, 'record_authentication_activity', audit)
    monkeypatch.setattr(service, 'read_session_policy', lambda: SessionPolicy())
    kwargs = {
        'source': 'database',
        'expected_generation': 7,
        'expires_at': (now + timedelta(seconds=-1 if failure == 'expired' else 60)).timestamp(),
        'enrollment': enrollment,
        'remember_requested': True,
        'client_ip': None,
    }
    if failure == 'none':
        result = service.complete_pending_mfa_login(user, '123456', **kwargs)
        assert result.generation == 8
        assert not result.remember_requested
        assert result.recovery_codes == (['one-time-test-code'] if enrollment else None)
        assert 'one-time-test-code' not in repr(result)
        assert issue.call_args.kwargs['pending_generation'] == 7
        assert audit.call_args.kwargs['commit'] is False
        assert audit.call_args.kwargs['issued_session_reference'] == result.session_reference
        assert [call[0] for call in events.mock_calls] == ['proof', 'issue', 'audit', 'commit']
    else:
        with pytest.raises((service.MfaVerificationError, AuthSessionError, SQLAlchemyError)):
            service.complete_pending_mfa_login(user, '123456', **kwargs)
        store.rollback.assert_called_once()
        if failure != 'commit':
            store.commit.assert_not_called()
        if failure in {'expired', 'policy'}:
            proof.assert_not_called()
            issue.assert_not_called()
            audit.assert_not_called()


@pytest.mark.parametrize('expires_at', (float('nan'), float('inf'), float('-inf'), 0))
def test_pending_deadline_rejects_invalid_or_expired_value(expires_at: float) -> None:
    assert not service._pending_deadline_valid(expires_at)
