"""Governed replacement keeps an active factor until committed verification (#5357)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.identity_provider.adapters.ldap.reauthentication import LdapReauthenticationProof
from app.access.authentication.mfa import service
from app.access.authentication.results import ExternalCredentialProof
from app.access.authentication.session import AuthSessionError
from app.access.authentication.session_lifecycle import SessionPolicy
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User


ReplacementFixture = tuple[User, AuthenticationMfaFactor, Mock, Mock]


@pytest.fixture
def replacement_fixture(monkeypatch: pytest.MonkeyPatch) -> ReplacementFixture:
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


def test_begin_preserves_active_factor_and_confirmation_rotates_generation(
    replacement_fixture: ReplacementFixture,
) -> None:
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
def test_confirmation_failures_do_not_commit(
    failure: str, replacement_fixture: ReplacementFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, factor, store, stage = replacement_fixture
    factor.replacement_totp_secret = 'new-test-seed'
    factor.replacement_generation = 8 if failure == 'stale' else 7
    factor.replacement_expires_at = datetime.now(UTC) + timedelta(seconds=-1 if failure == 'expired' else 60)
    if failure == 'invalid':
        monkeypatch.setattr(service, '_accepted_step', Mock(return_value=None))
    if failure == 'external':
        user.auth_source = 'ldap_directory'
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


def test_cancel_preserves_active_factor(replacement_fixture: ReplacementFixture) -> None:
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


@pytest.mark.parametrize('source,password', [('database', 'wrong'), ('ldap_directory', None), ('google', None), ('github', None)])
def test_begin_denies_unverified_primary(
    source: str, password: str | None, replacement_fixture: ReplacementFixture
) -> None:
    user, factor, store, _ = replacement_fixture
    user.auth_source = source
    with pytest.raises(service.MfaVerificationError):
        service.begin_mfa_replacement(user, '123456', expected_generation=7, current_password=password)
    assert factor.replacement_totp_secret is None
    assert factor.totp_secret == 'existing-test-seed'
    store.commit.assert_not_called()
    store.rollback.assert_called_once()


def test_recovery_proof_is_consumed_but_active_seed_stays(
    replacement_fixture: ReplacementFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, factor, store, _ = replacement_fixture
    factor.recovery_hashes = ['used-test-hash', 'remaining-test-hash']
    monkeypatch.setattr(service, '_accepted_step', Mock(return_value=None))
    monkeypatch.setattr(service, 'check_password_hash', lambda stored, _: stored == 'used-test-hash')
    service.begin_mfa_replacement(user, 'ABCDEF0123456789', expected_generation=7, current_password='fixture-password')
    assert factor.enabled
    assert factor.totp_secret == 'existing-test-seed'
    assert factor.recovery_hashes == ['remaining-test-hash']
    assert store.commit.call_count == 1


def test_recovery_rotation_invalidates_pending_replacement(replacement_fixture: ReplacementFixture) -> None:
    user, factor, store, stage = replacement_fixture
    factor.replacement_totp_secret = 'pending-test-seed'
    factor.replacement_generation = 7
    factor.replacement_expires_at = datetime.now(UTC) + timedelta(seconds=60)
    codes = service.regenerate_mfa_recovery_codes(
        user, '123456', expected_generation=7, current_password='fixture-password'
    )
    assert len(codes) == 8
    assert factor.totp_secret == 'existing-test-seed'
    assert factor.replacement_totp_secret is None
    assert [call.kwargs['action'] for call in stage.call_args_list] == [
        'mfa_challenge_verified',
        'mfa_replacement_cancelled',
        'mfa_recovery_regenerated',
    ]
    store.commit.assert_called_once()


def test_invalid_existing_factor_cannot_start_replacement(
    replacement_fixture: ReplacementFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, factor, store, stage = replacement_fixture
    monkeypatch.setattr(service, '_accepted_step', Mock(return_value=None))
    monkeypatch.setattr(service, 'check_password_hash', Mock(return_value=False))
    with pytest.raises(service.MfaVerificationError):
        service.begin_mfa_replacement(user, '123456', expected_generation=7, current_password='fixture-password')
    assert factor.replacement_totp_secret is None
    assert factor.totp_secret == 'existing-test-seed'
    stage.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()


def test_ldap_replacement_revalidates_bound_proof_and_rotates_generation(
    replacement_fixture: ReplacementFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, factor, store, stage = replacement_fixture
    user.auth_source = 'ldap_directory'
    user.external_id = 'stable'
    proof = LdapReauthenticationProof(ExternalCredentialProof(7, 3, 11), 'stable', 'a' * 64, datetime.now(UTC))
    bind = Mock(return_value=proof)
    fence = Mock()
    local = Mock(side_effect=AssertionError('LDAP must not compare a local password.'))
    monkeypatch.setattr(service, 'reauthenticate_ldap_account', bind)
    monkeypatch.setattr(service, 'lock_ldap_reauthentication_proof', fence)
    monkeypatch.setattr(User, 'check_password', local)

    seed = service.begin_mfa_replacement(user, '123456', expected_generation=7, current_password='directory-test')
    assert factor.totp_secret == 'existing-test-seed'
    assert factor.replacement_provider_proof == proof.to_record()
    assert 'directory-test' not in repr(factor.replacement_provider_proof)
    assert stage.call_args.kwargs['primary_assurance'] == 'ldap_linked_user_bind'
    bind.assert_called_once_with(user.id, 'directory-test', expected_subject='stable')
    fence.assert_called_once_with(user.id, proof)
    store.execute.return_value.scalar_one_or_none.return_value = factor.replacement_provider_proof
    codes, generation = service.confirm_mfa_replacement(user, '654321', expected_generation=7)
    assert generation == 8 and len(codes) == 8
    assert factor.totp_secret == seed and factor.replacement_provider_proof is None
    assert fence.call_count == 2
    assert store.commit.call_count == 2
    local.assert_not_called()


def test_stale_ldap_provider_fence_prevents_replacement_confirmation(
    replacement_fixture: ReplacementFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, factor, store, stage = replacement_fixture
    user.auth_source = 'ldap_directory'
    user.external_id = 'stable'
    proof = LdapReauthenticationProof(ExternalCredentialProof(7, 3, 11), 'stable', 'a' * 64, datetime.now(UTC))
    factor.replacement_totp_secret = 'new-test-seed'
    factor.replacement_generation = 7
    factor.replacement_expires_at = datetime.now(UTC) + timedelta(minutes=1)
    factor.replacement_provider_proof = proof.to_record()
    store.execute.return_value.scalar_one_or_none.return_value = proof.to_record()
    monkeypatch.setattr(service, 'lock_ldap_reauthentication_proof', Mock(side_effect=AuthSessionError('stale')))
    with pytest.raises(service.MfaVerificationError, match='Verified provider reauthentication'):
        service.confirm_mfa_replacement(user, '654321', expected_generation=7)
    assert user.auth_session_version == 7
    assert factor.totp_secret == 'existing-test-seed'
    stage.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()


@pytest.mark.parametrize('source', ('google', 'github', 'ldap', 'unsupported'))
@pytest.mark.parametrize('action', ('begin', 'confirm', 'cancel'))
def test_unsupported_replacement_cannot_use_fresh_admission_or_direct_post(
    source: str, action: str, replacement_fixture: ReplacementFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, factor, store, stage = replacement_fixture
    user.auth_source = source
    user.auth_session_issued_at = datetime.now(UTC)
    factor.replacement_totp_secret = 'pending-test-seed'
    factor.replacement_generation = 7
    factor.replacement_expires_at = datetime.now(UTC) + timedelta(minutes=1)
    account_lock = Mock()
    factor_lock = Mock()
    ldap_bind = Mock()
    local_check = Mock()
    monkeypatch.setattr(service, '_lock_mfa_user', account_lock)
    monkeypatch.setattr(service, '_locked_factor', factor_lock)
    monkeypatch.setattr(service, 'reauthenticate_ldap_account', ldap_bind)
    monkeypatch.setattr(User, 'check_password', local_check)
    with pytest.raises(service.MfaVerificationError, match='Verified provider reauthentication'):
        if action == 'begin':
            service.begin_mfa_replacement(user, '123456', expected_generation=7, current_password='forged-password')
        elif action == 'confirm':
            service.confirm_mfa_replacement(user, '123456', expected_generation=7)
        else:
            service.cancel_mfa_replacement(user, expected_generation=7)
    account_lock.assert_not_called()
    factor_lock.assert_not_called()
    ldap_bind.assert_not_called()
    local_check.assert_not_called()
    stage.assert_not_called()
    store.commit.assert_not_called()
    store.rollback.assert_called_once()
    assert factor.enabled
    assert factor.totp_secret == 'existing-test-seed'
    assert factor.recovery_hashes == ['old-test-hash']
    assert factor.replacement_totp_secret == 'pending-test-seed'
    assert user.auth_session_version == 7


def test_replacement_source_boundary_uses_canonical_catalog_keys() -> None:
    from app.access.authentication.identity_provider.catalog import provider_definitions

    supported = {
        definition.provider_key
        for definition in provider_definitions()
        if service.mfa_replacement_supports_source(definition.provider_key)
    }
    assert supported == {'database', 'ldap_directory'}
    assert not service.mfa_replacement_supports_source('ldap')
