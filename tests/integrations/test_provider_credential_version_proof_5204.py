"""Provider-qualified credential evidence; no secret material or provider request."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    CredentialVersionSelector,
    ProviderCredentialVersionSelector,
    provider_credential_version_statement,
    verify_provider_credential_version_statement,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.credential_version_proof import (
    credential_version_statement,
    verify_credential_version_statement,
)

_NOW = datetime(2026, 11, 26, 0, tzinfo=UTC)
_ISSUED = _NOW - timedelta(minutes=1)
_EXPIRES = _NOW + timedelta(hours=1)
_CREDENTIAL = CredentialVersionSelector(1, '', 'kv', 'a' * 64, 2, (_NOW - timedelta(days=1)).isoformat())
_SELECTOR = ProviderCredentialVersionSelector(
    'openbao', 'b' * 64, 1, '11111111-2222-4333-8444-555555555555', 3, _CREDENTIAL
)


def _statement(selector):
    return provider_credential_version_statement(selector, issued_at=_ISSUED, expires_at=_EXPIRES)


def _verify(selector, key, signature, *, now=_NOW):
    return verify_provider_credential_version_statement(
        selector,
        issued_at=_ISSUED,
        expires_at=_EXPIRES,
        signature=signature,
        verification_key=key,
        now=now,
    )


@pytest.mark.parametrize(
    'selector',
    [
        replace(_SELECTOR, provider_key='vault'),
        replace(_SELECTOR, deployment_ref='c' * 64),
        replace(_SELECTOR, issuer_revision=2),
        replace(_SELECTOR, secret_identity_id='11111111-2222-4333-8444-555555555556'),
        replace(_SELECTOR, representation_id=4),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, integration_instance_id=2)),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, provider_namespace='other')),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, mount='other')),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, path_sha256='d' * 64)),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, version=3)),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, provider_created_time='2026-11-24T00:00:00+00:00')),
    ],
)
def test_signed_provider_claim_cannot_transfer(selector):
    signer = Ed25519PrivateKey.generate()
    statement = _statement(_SELECTOR)
    assert statement is not None
    signature = signer.sign(statement)
    assert _verify(_SELECTOR, signer.public_key(), signature)
    assert not _verify(selector, signer.public_key(), signature)


@pytest.mark.parametrize(
    'selector',
    [
        replace(_SELECTOR, deployment_ref='invalid'),
        replace(_SELECTOR, issuer_revision=True),
        replace(_SELECTOR, issuer_revision=0),
        replace(_SELECTOR, secret_identity_id='invalid'),
        replace(_SELECTOR, representation_id=0),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, provider_namespace='*')),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, mount='+')),
        replace(_SELECTOR, credential=replace(_CREDENTIAL, version=0)),
    ],
)
def test_invalid_provider_claim_not_signable(selector):
    assert _statement(selector) is None


def test_legacy_wire_bytes_and_signature_domain_separation():
    signer = Ed25519PrivateKey.generate()
    legacy = credential_version_statement(_CREDENTIAL, issued_at=_ISSUED, expires_at=_EXPIRES)
    expected = {
        'schema': 'kaori.vault.kv2.ssh_private_key.v1',
        'selector': {
            'integration_instance_id': 1,
            'provider_namespace': '',
            'mount': 'kv',
            'path_sha256': 'a' * 64,
            'version': 2,
            'provider_created_time': _CREDENTIAL.provider_created_time,
        },
        'issued_at': _ISSUED.isoformat(),
        'expires_at': _EXPIRES.isoformat(),
    }
    assert legacy is not None
    assert legacy == json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    statement = _statement(replace(_SELECTOR, provider_key='vault'))
    assert statement is not None
    assert not _verify(replace(_SELECTOR, provider_key='vault'), signer.public_key(), signer.sign(legacy))
    assert not verify_credential_version_statement(
        _CREDENTIAL,
        issued_at=_ISSUED,
        expires_at=_EXPIRES,
        signature=signer.sign(statement),
        verification_key=signer.public_key(),
        now=_NOW,
    )
    active = _statement(_SELECTOR)
    assert active is not None
    signature = signer.sign(active)
    assert not _verify(_SELECTOR, signer.public_key(), signature, now=_EXPIRES)
    assert not _verify(_SELECTOR, Ed25519PrivateKey.generate().public_key(), signature)
