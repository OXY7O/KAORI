"""Time-bounded admission and authoritative local proof for MFA lifecycle (#5351)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication.mfa import service
from app.models.user import User

NOW = datetime(2026, 11, 28, tzinfo=UTC)


@pytest.mark.parametrize(
    ('age', 'expected'),
    [(None, False), (-1, False), (0, True), (299, True), (300, False), (301, False)],
)
def test_recent_admission_boundary(age: int | None, expected: bool) -> None:
    user = User(
        auth_source='ldap',
        auth_session_issued_at=NOW - timedelta(seconds=age) if age is not None else None,
        auth_session_activity_at=NOW,
    )
    assert service.has_recent_kaori_admission(user, now=NOW) is expected


@pytest.mark.parametrize('source', ('ldap', 'google', 'github'))
def test_external_recent_admission_is_not_strict_primary_assurance(source: str) -> None:
    user = User(auth_source=source, auth_session_issued_at=NOW)
    service.require_personal_factor_assurance(user, None, now=NOW)
    with pytest.raises(service.MfaVerificationError, match='Verified provider reauthentication'):
        service.require_personal_factor_assurance(user, None, now=NOW, strict_primary=True)


@pytest.mark.parametrize('source', ('ldap', 'google', 'github'))
def test_external_old_admission_is_not_refreshed_by_activity(source: str) -> None:
    user = User(
        auth_source=source,
        auth_session_issued_at=NOW - timedelta(minutes=5),
        auth_session_activity_at=NOW,
    )
    with pytest.raises(service.MfaVerificationError, match='Recent sign-in required'):
        service.require_personal_factor_assurance(user, None, now=NOW)


@pytest.mark.parametrize('password', (None, '', 'incorrect', 'x' * 1025))
def test_invalid_local_proof_rejected_under_lock_before_factor_access(
    password: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=42, auth_source='database', auth_session_version=7)
    locked = User(id=42, auth_source='database', auth_session_version=7)
    store = Mock()
    factor = Mock()
    check = Mock(return_value=False)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, '_lock_mfa_user', Mock(return_value=locked))
    monkeypatch.setattr(service, '_locked_factor', factor)
    monkeypatch.setattr(User, 'check_password', check)
    with pytest.raises(service.MfaVerificationError, match='current password'):
        service.begin_mfa_enrollment(user, expected_generation=7, current_password=password)
    factor.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()


def test_current_local_password_supports_strict_primary_assurance(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(auth_source='database')
    monkeypatch.setattr(User, 'check_password', lambda self, value: value == 'fixture-password')
    service.require_personal_factor_assurance(user, 'fixture-password', now=NOW, strict_primary=True)
