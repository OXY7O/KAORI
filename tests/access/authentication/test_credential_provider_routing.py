"""Credential dispatch: projected LDAP identity must reach its linked adapter (#2957)."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication import services
from app.access.authentication.results import AuthResult


def _account(
    auth_source: str = 'ldap',
    *,
    active: bool = True,
    role_active: bool = True,
    is_super_admin: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        auth_source=auth_source,
        is_active=active,
        is_super_admin=is_super_admin,
        role_record=SimpleNamespace(is_active=role_active),
    )


def _providers(
    monkeypatch: pytest.MonkeyPatch,
    local_result: AuthResult,
    ldap_result: AuthResult,
) -> tuple[Mock, Mock]:
    local = Mock()
    ldap = Mock()
    local.authenticate.return_value = local_result
    ldap.authenticate.return_value = ldap_result
    monkeypatch.setattr(
        services,
        'build_credential_provider_registry',
        lambda: SimpleNamespace(local=local, external=(ldap,)),
    )
    return local, ldap


def test_provisioned_ldap_user_reaches_user_bind_and_viewer_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projected = _account('ldap')
    local, ldap = _providers(
        monkeypatch,
        AuthResult(False, 'invalid_credentials', source='database', user=projected),
        AuthResult(True, 'success', source='ldap', user=projected),
    )

    result = services.authenticate('kaori-uat-user', 'directory-test-password')

    assert result.success is True
    assert result.reason == 'success'
    assert result.source == 'ldap'
    assert result.user is projected
    local.authenticate.assert_called_once_with(username='kaori-uat-user', password='directory-test-password')
    ldap.authenticate.assert_called_once_with(username='kaori-uat-user', password='directory-test-password')


@pytest.mark.parametrize('password_hash_present', [True, False])
def test_existing_local_identity_never_falls_through_to_external_provider(
    monkeypatch: pytest.MonkeyPatch,
    password_hash_present: bool,
) -> None:
    # The orchestrator uses credential authority, not password-hash truthiness:
    # even a misconfigured Local Database account cannot fall through to LDAP.
    local_user = _account('database')
    local_user.password_hash = 'local-hash' if password_hash_present else ''
    _, ldap = _providers(
        monkeypatch,
        AuthResult(False, 'invalid_credentials', source='database', user=local_user),
        AuthResult(True, 'success', source='ldap', user=local_user),
    )

    result = services.authenticate('local-operator', 'wrong-password')

    assert result.success is False
    assert result.source == 'database'
    assert result.user is local_user
    ldap.authenticate.assert_not_called()


def test_valid_local_credentials_remain_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _account('database')
    _, ldap = _providers(
        monkeypatch,
        AuthResult(True, 'success', source='database', user=user),
        AuthResult(True, 'success', source='ldap', user=user),
    )

    result = services.authenticate('local-operator', 'local-password')

    assert result.success is True
    assert result.source == 'database'
    ldap.authenticate.assert_not_called()


@pytest.mark.parametrize('reason', ['database_unavailable', 'user_inactive'])
def test_local_fail_closed_conditions_never_attempt_ldap(
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    local_user = _account('database') if reason == 'user_inactive' else None
    _, ldap = _providers(
        monkeypatch,
        AuthResult(False, reason, source='database', user=local_user),
        AuthResult(True, 'success', source='ldap', user=_account()),
    )

    result = services.authenticate('local-operator', 'password')

    assert result.success is False
    assert result.reason == reason
    ldap.authenticate.assert_not_called()


def test_wrong_ldap_password_fails_without_session_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    projected = _account()
    _, ldap = _providers(
        monkeypatch,
        AuthResult(False, 'invalid_credentials', source='database', user=projected),
        AuthResult(False, 'invalid_credentials', source='ldap', user=projected),
    )

    result = services.authenticate('kaori-uat-user', 'wrong-password')

    assert result.success is False
    assert result.reason == 'invalid_credentials'
    assert services.credential_failure_message(result) == 'Invalid username or password.'
    ldap.authenticate.assert_called_once()


@pytest.mark.parametrize('reason', ['invalid_credentials', 'provider_unavailable'])
def test_unlinked_or_unavailable_directory_identity_does_not_sign_in(
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    projected = _account()
    _, ldap = _providers(
        monkeypatch,
        AuthResult(False, 'invalid_credentials', source='database', user=projected),
        AuthResult(False, reason, source='ldap'),
    )

    result = services.authenticate('kaori-uat-user', 'password')

    assert result.success is False
    assert result.reason == reason
    assert services.credential_failure_message(result) == 'Invalid username or password.'
    ldap.authenticate.assert_called_once()


@pytest.mark.parametrize(
    ('projected', 'expected_reason'),
    [
        (_account(active=False), 'user_inactive'),
        (_account(role_active=False), 'access_not_permitted'),
        (_account(is_super_admin=True), 'access_not_permitted'),
    ],
)
def test_external_bind_does_not_bypass_kaori_lifecycle_or_role(
    monkeypatch: pytest.MonkeyPatch,
    projected: SimpleNamespace,
    expected_reason: str,
) -> None:
    _, ldap = _providers(
        monkeypatch,
        AuthResult(False, 'invalid_credentials', source='database', user=projected),
        AuthResult(True, 'success', source='ldap', user=projected),
    )

    result = services.authenticate('kaori-uat-user', 'password')

    assert result.success is False
    assert result.reason == expected_reason
    assert services.credential_failure_message(result) == 'Invalid username or password.'
    ldap.authenticate.assert_called_once()
