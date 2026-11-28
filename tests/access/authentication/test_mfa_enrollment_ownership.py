"""Generation and authentication-context ownership of pending MFA setup (#5346)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.mfa import service
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User

NOW = datetime(2026, 11, 28, tzinfo=UTC)


@pytest.mark.parametrize(
    ('generation', 'authenticated', 'expected'),
    [(7, True, 'pending'), (8, True, 'expired'), (7, False, 'expired'), (None, None, 'expired')],
)
def test_pending_setup_requires_original_owner(
    generation: int | None, authenticated: bool | None, expected: str
) -> None:
    factor = AuthenticationMfaFactor(
        enabled=False,
        enrollment_generation=generation,
        enrollment_authenticated=authenticated,
        enrollment_expires_at=NOW + timedelta(minutes=1),
    )
    assert service.mfa_enrollment_state(factor, now=NOW, expected_generation=7, authenticated=True) == expected


@pytest.mark.parametrize('condition', ('valid', 'stale', 'foreign_context', 'enabled', 'legacy', 'audit_failure'))
def test_cancellation_only_deletes_owned_inactive_setup(condition: str, monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=42, auth_session_version=7)
    factor = AuthenticationMfaFactor(
        enabled=condition == 'enabled',
        enrollment_generation=None if condition == 'legacy' else 8 if condition == 'stale' else 7,
        enrollment_authenticated=condition != 'foreign_context',
    )
    store = Mock()
    stage = Mock()
    if condition == 'audit_failure':
        stage.side_effect = SQLAlchemyError('audit failure')
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, '_lock_mfa_user', Mock(return_value=user))
    monkeypatch.setattr(service, '_locked_factor', Mock(return_value=factor))
    monkeypatch.setattr(service, 'stage_authentication_security_event', stage)
    if condition == 'valid':
        service.cancel_mfa_enrollment(user, expected_generation=7)
        store.delete.assert_called_once_with(factor)
        assert stage.call_args.kwargs['action'] == 'mfa_enrollment_cancelled'
        store.commit.assert_called_once()
        store.rollback.assert_not_called()
    else:
        with pytest.raises((service.MfaVerificationError, SQLAlchemyError)):
            service.cancel_mfa_enrollment(user, expected_generation=7)
        store.rollback.assert_called_once()
        store.commit.assert_not_called()
        if condition != 'audit_failure':
            store.delete.assert_not_called()
            stage.assert_not_called()


def test_confirmation_rejects_foreign_generation_before_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=42, auth_session_version=8)
    factor = AuthenticationMfaFactor(
        enabled=False,
        enrollment_generation=7,
        enrollment_authenticated=True,
        enrollment_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    store = Mock()
    verify = Mock()
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, '_lock_mfa_user', Mock(return_value=user))
    monkeypatch.setattr(service, '_locked_factor', Mock(return_value=factor))
    monkeypatch.setattr(service, '_accepted_step', verify)
    with pytest.raises(service.MfaVerificationError):
        service.confirm_mfa_enrollment(user, '123456', expected_generation=8)
    verify.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()
