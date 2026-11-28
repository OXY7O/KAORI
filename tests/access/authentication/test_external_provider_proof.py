"""Exact provider instance and revision proof fence (#5365)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication import services
from app.access.authentication.identity_provider import proof
from app.access.authentication.mfa import service
from app.access.authentication.results import ExternalCredentialProof
from app.access.authentication.session import AuthSessionError
from app.models.user import User


@pytest.mark.parametrize('field', ('provider_id', 'provider_revision', 'provider_link_id'))
@pytest.mark.parametrize('invalid', (None, False, 0, -1, '1'))
def test_pending_external_proof_rejects_missing_or_malformed(field: str, invalid: object) -> None:
    pending: dict[str, object] = {'provider_id': 7, 'provider_revision': 3, 'provider_link_id': 11}
    pending[field] = invalid
    assert proof.parse_external_credential_proof(pending) is None


def test_pending_external_proof_preserves_exact_instance() -> None:
    pending = {'provider_id': 7, 'provider_revision': 3, 'provider_link_id': 11}
    assert proof.parse_external_credential_proof(pending) == ExternalCredentialProof(7, 3, 11)


@pytest.mark.parametrize('failure', ('none', 'provider', 'link', 'missing'))
def test_provider_revision_and_link_are_checked_before_admission(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Mock()
    provider = object()
    store.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: None if failure == 'provider' else provider),
        SimpleNamespace(scalar_one_or_none=lambda: None if failure == 'link' else 11),
    ]
    monkeypatch.setattr(proof, 'db', SimpleNamespace(session=store))
    credential = None if failure == 'missing' else ExternalCredentialProof(7, 3, 11)
    if failure == 'none':
        proof.lock_external_credential_proof(42, 'ldap', credential)
        assert store.execute.call_count == 2
    else:
        with pytest.raises(AuthSessionError):
            proof.lock_external_credential_proof(42, 'ldap', credential)
        assert store.execute.call_count == {'missing': 0, 'provider': 1, 'link': 2}[failure]
    if failure != 'missing':
        statement = store.execute.call_args_list[0].args[0]
        sql = str(statement).lower()
        assert 'for update' in sql
        assert 'identity_providers.authentication_revision =' in sql
        assert 'identity_providers.enabled is true' in sql
        assert {7, 3, 'ldap'} <= set(statement.compile().params.values())
    if failure in {'none', 'link'}:
        statement = store.execute.call_args_list[1].args[0]
        assert {7, 11, 42} <= set(statement.compile().params.values())
    store.commit.assert_not_called()


def test_stale_external_pending_proof_never_reaches_factor_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=42, auth_source='ldap', auth_session_version=7)
    store = Mock()
    lock = Mock(side_effect=AuthSessionError('stale provider revision'))
    user_lock = Mock()
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(service, 'lock_external_credential_proof', lock)
    monkeypatch.setattr(service, '_lock_mfa_user', user_lock)
    credential = ExternalCredentialProof(7, 3, 11)
    with pytest.raises(AuthSessionError):
        service.begin_mfa_enrollment(
            user, expected_generation=7, authenticated=False, external_credential_proof=credential
        )
    with pytest.raises(AuthSessionError):
        service.cancel_mfa_enrollment(
            user, expected_generation=7, authenticated=False, external_credential_proof=credential
        )
    user_lock.assert_not_called()
    store.commit.assert_not_called()
    assert store.rollback.call_count == 2


def test_stale_provider_proof_prevents_pending_admission_before_user_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=42, auth_source='ldap', auth_session_version=7)
    store = Mock()
    user_lock = Mock()
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(
        service, 'lock_external_credential_proof', Mock(side_effect=AuthSessionError('stale provider revision'))
    )
    monkeypatch.setattr(service, '_lock_mfa_user', user_lock)
    with pytest.raises(AuthSessionError):
        service.complete_pending_mfa_login(
            user,
            '123456',
            source='ldap',
            expected_generation=7,
            expires_at=(datetime.now(UTC) + timedelta(seconds=60)).timestamp(),
            enrollment=False,
            remember_requested=False,
            client_ip=None,
            external_credential_proof=ExternalCredentialProof(7, 3, 11),
        )
    user_lock.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()


def test_stale_provider_proof_prevents_primary_only_issuance(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=42, auth_source='github')
    store = Mock()
    monkeypatch.setattr(services, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(
        services, 'lock_external_credential_proof', Mock(side_effect=AuthSessionError('stale provider revision'))
    )
    with pytest.raises(AuthSessionError):
        services.record_successful_authentication(
            user, source='github', client_ip=None, external_credential_proof=ExternalCredentialProof(7, 3, 11)
        )
    store.execute.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()
