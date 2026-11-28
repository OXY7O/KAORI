"""Effective pending enrollment and locked factor protection (#5340)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication.mfa import service
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User

NOW = datetime(2026, 11, 28, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ('enabled', 'expires', 'expected'),
    [
        (True, None, 'enrolled'),
        (False, None, 'expired'),
        (False, NOW + timedelta(seconds=1), 'pending'),
        (False, NOW, 'expired'),
        (False, NOW - timedelta(seconds=1), 'expired'),
        (False, NOW.replace(tzinfo=None), 'expired'),
    ],
)
def test_mfa_effective_pending_state(enabled: bool, expires: datetime | None, expected: str) -> None:
    factor = AuthenticationMfaFactor(enabled=enabled, enrollment_expires_at=expires)
    assert service.mfa_enrollment_state(factor, now=NOW) == expected


def test_no_mfa_factor_is_not_enrolled() -> None:
    assert service.mfa_enrollment_state(None, now=NOW) == 'not_enrolled'


@pytest.mark.parametrize('admitted', (True, False))
def test_stale_or_concurrently_enabled_enrollment_is_rejected(
    admitted: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=42, auth_source='database', auth_session_version=7, account_is_active=True, is_super_admin=True)
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = user if admitted else None
    factor = AuthenticationMfaFactor(enabled=True)
    query = Mock()
    query.filter_by.return_value.with_for_update.return_value.populate_existing.return_value.first.return_value = factor
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, 'AuthenticationMfaFactor', SimpleNamespace(query=query))
    with pytest.raises(service.MfaVerificationError):
        service.begin_mfa_enrollment(user, expected_generation=7, authenticated=False)
    assert factor.enabled
    store.add.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()
    if admitted:
        query.filter_by.return_value.with_for_update.return_value.populate_existing.assert_called_once()
    else:
        query.filter_by.assert_not_called()
