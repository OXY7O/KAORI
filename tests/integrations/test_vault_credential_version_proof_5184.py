"""Offline signed exact-version type claims; no provider requests or material."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.integrations.secrets_management.secrets_pki.providers.vault.credential_version_proof import (
    CredentialVersionSelector,
    credential_version_statement,
    verify_credential_version_statement,
)

_NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)
_ISSUED = _NOW - timedelta(minutes=1)
_EXPIRES = _NOW + timedelta(hours=1)
_SELECTOR = CredentialVersionSelector(1, '', 'kv', 'a' * 64, 2, (_NOW - timedelta(days=1)).isoformat())


@pytest.fixture
def signed_claim():
    signer = Ed25519PrivateKey.generate()
    statement = credential_version_statement(_SELECTOR, issued_at=_ISSUED, expires_at=_EXPIRES)
    assert statement is not None
    return signer.public_key(), signer.sign(statement)


def _verify(selector, key, signature, *, issued=_ISSUED, expires=_EXPIRES, now=_NOW):
    return verify_credential_version_statement(
        selector,
        issued_at=issued,
        expires_at=expires,
        signature=signature,
        verification_key=key,
        now=now,
    )


def test_exact_signed_claim(signed_claim):
    key, signature = signed_claim
    assert _verify(_SELECTOR, key, signature)
    assert not _verify(_SELECTOR, Ed25519PrivateKey.generate().public_key(), signature)
    assert not _verify(_SELECTOR, key, bytes(64))
    assert not _verify(_SELECTOR, key, signature[:-1])


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('integration_instance_id', 2),
        ('provider_namespace', 'other'),
        ('mount', 'other'),
        ('path_sha256', 'b' * 64),
        ('version', 3),
        ('provider_created_time', (_NOW - timedelta(days=2)).isoformat()),
    ],
)
def test_signed_claim_cannot_be_transferred(signed_claim, field, value):
    key, signature = signed_claim
    assert not _verify(replace(_SELECTOR, **{field: value}), key, signature)


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('integration_instance_id', True),
        ('version', 0),
        ('version', True),
        ('mount', '*'),
        ('mount', ''),
        ('provider_namespace', '\n'),
        ('path_sha256', 'A' * 64),
        ('provider_created_time', ''),
        ('provider_created_time', '2026-11-23T12:00:00'),
        ('provider_created_time', (_NOW + timedelta(days=1)).isoformat()),
    ],
)
def test_invalid_selector_is_not_signable(field, value):
    selector = replace(_SELECTOR, **{field: value})
    assert credential_version_statement(selector, issued_at=_ISSUED, expires_at=_EXPIRES) is None


def test_window_cannot_be_changed_or_replayed(signed_claim):
    key, signature = signed_claim
    assert not _verify(_SELECTOR, key, signature, now=_EXPIRES)
    assert not _verify(_SELECTOR, key, signature, now=_ISSUED - timedelta(seconds=1))
    assert not _verify(_SELECTOR, key, signature, now=_NOW.replace(tzinfo=None))
    assert not _verify(_SELECTOR, key, signature, expires=_EXPIRES + timedelta(minutes=1))
    assert not _verify(_SELECTOR, key, signature, issued=_ISSUED - timedelta(minutes=1))


def test_unbounded_or_naive_window_not_signable():
    assert credential_version_statement(_SELECTOR, issued_at=_ISSUED, expires_at=_ISSUED) is None
    assert credential_version_statement(_SELECTOR, issued_at=_ISSUED, expires_at=_ISSUED + timedelta(days=2)) is None
    assert credential_version_statement(_SELECTOR, issued_at=_ISSUED.replace(tzinfo=None), expires_at=_EXPIRES) is None
