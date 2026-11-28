"""Strict LDAP assurance requires a stable linked identity and verified transport (#5374)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication.identity_provider.adapters.ldap import reauthentication as ldap
from app.access.authentication.identity_provider.adapters.ldap.client import (
    ExternalProviderError,
    LdapDirectoryClient,
    LdapTransport,
)
from app.access.authentication.results import ExternalCredentialProof
from app.models.identity import ExternalIdentityLink, IdentityProvider


@pytest.mark.parametrize('matching', (True, False))
def test_strict_bind_reads_stable_subject_on_same_connection(matching: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    client = object.__new__(LdapDirectoryClient)
    client.config = {'stable_id_attribute': 'entryUUID'}
    client.transport = LdapTransport('fixture.invalid', 636, True, False)
    connection = Mock()
    connection.bind.return_value = True
    connection.search.return_value = True
    connection.entries = [SimpleNamespace(entryUUID=SimpleNamespace(value='stable' if matching else 'different'))]
    monkeypatch.setattr(client, '_new_connection', Mock(return_value=connection))
    monkeypatch.setattr(client, '_open_and_secure', Mock())
    assert client.reauthenticate_linked_identity('cn=fixture', 'test-only', 'stable') is matching
    assert connection.auto_referrals is False
    assert connection.search.call_args.kwargs['search_base'] == 'cn=fixture'
    connection.unbind.assert_called_once()


def test_plaintext_strict_reauthentication_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object.__new__(LdapDirectoryClient)
    client.transport = LdapTransport('fixture.invalid', 389, False, False)
    connect = Mock()
    monkeypatch.setattr(client, '_new_connection', connect)
    with pytest.raises(ExternalProviderError):
        client.reauthenticate_linked_identity('cn=fixture', 'test-only', 'stable')
    connect.assert_not_called()


@pytest.mark.parametrize('count', (0, 2))
def test_ambiguous_or_missing_binding_rejected(count: int, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Mock()
    store.execute.return_value.all.return_value = [(object(), object())] * count
    monkeypatch.setattr(ldap, 'db', SimpleNamespace(session=store))
    with pytest.raises(ldap.LdapReauthenticationError):
        ldap._linked_directory(42)


def test_proof_contains_no_password_and_revalidates_exact_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    link = ExternalIdentityLink(id=11, provider_id=7, user_id=42, subject='stable', distinguished_name='cn=fixture')
    provider = IdentityProvider(id=7, provider_key='ldap', adapter_key='ldap', enabled=True, authentication_revision=3)
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = link
    monkeypatch.setattr(ldap, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(ldap, '_linked_directory', Mock(return_value=(link, provider)))
    bind = Mock(return_value=True)
    monkeypatch.setattr(ldap, 'LdapDirectoryClient', Mock(return_value=SimpleNamespace(reauthenticate_linked_identity=bind)))
    lock = Mock(return_value=provider)
    monkeypatch.setattr(ldap, 'lock_provider_revision', lock)
    proof = ldap.reauthenticate_ldap_account(42, 'test-only-password', expected_subject='stable')
    assert proof.credential == ExternalCredentialProof(7, 3, 11)
    assert 'test-only-password' not in repr(proof.to_record())
    assert ldap.LdapReauthenticationProof.from_record(proof.to_record()) == proof
    store.rollback.assert_called_once()
    ldap.lock_ldap_reauthentication_proof(42, proof)
    lock.assert_called_once_with(7, 3, source='ldap')
    link.distinguished_name = 'cn=changed'
    with pytest.raises(ldap.LdapReauthenticationError):
        ldap.lock_ldap_reauthentication_proof(42, proof)


def test_missing_provider_record_is_rejected() -> None:
    assert ldap.LdapReauthenticationProof.from_record(None) is None
    proof = ldap.LdapReauthenticationProof(ExternalCredentialProof(7, 3, 11), 'stable', 'a' * 64, datetime.now(UTC))
    record = proof.to_record()
    record['verified_at'] = '2026-11-28'
    assert ldap.LdapReauthenticationProof.from_record(record) is None


def test_directory_subject_mismatch_is_rejected_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    link = ExternalIdentityLink(id=11, provider_id=7, user_id=42, subject='other', distinguished_name='cn=fixture')
    provider = IdentityProvider(id=7, provider_key='ldap', adapter_key='ldap', enabled=True, authentication_revision=3)
    monkeypatch.setattr(ldap, '_linked_directory', Mock(return_value=(link, provider)))
    client = Mock()
    monkeypatch.setattr(ldap, 'LdapDirectoryClient', client)
    with pytest.raises(ldap.LdapReauthenticationError):
        ldap.reauthenticate_ldap_account(42, 'test-only-password', expected_subject='stable')
    client.assert_not_called()


def test_invalid_directory_password_never_creates_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    link = ExternalIdentityLink(id=11, provider_id=7, user_id=42, subject='stable', distinguished_name='cn=fixture')
    provider = IdentityProvider(id=7, provider_key='ldap', adapter_key='ldap', enabled=True, authentication_revision=3)
    store = Mock()
    monkeypatch.setattr(ldap, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(ldap, '_linked_directory', Mock(return_value=(link, provider)))
    bind = Mock(return_value=False)
    monkeypatch.setattr(ldap, 'LdapDirectoryClient', Mock(return_value=SimpleNamespace(reauthenticate_linked_identity=bind)))
    with pytest.raises(ldap.LdapReauthenticationError):
        ldap.reauthenticate_ldap_account(42, 'wrong', expected_subject='stable')
    store.rollback.assert_called_once()
