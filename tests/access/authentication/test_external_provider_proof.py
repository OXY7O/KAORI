"""Exact provider instance and revision proof fence (#5365)."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication.identity_provider import proof
from app.access.authentication.results import ExternalCredentialProof
from app.access.authentication.session import AuthSessionError


@pytest.mark.parametrize('field', ('provider_id', 'provider_revision', 'provider_link_id'))
@pytest.mark.parametrize('invalid', (None, False, 0, -1, '1'))
def test_pending_external_proof_rejects_missing_or_malformed(field: str, invalid: object) -> None:
    pending = {'provider_id': 7, 'provider_revision': 3, 'provider_link_id': 11}
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
