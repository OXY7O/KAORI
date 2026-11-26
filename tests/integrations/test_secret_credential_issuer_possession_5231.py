"""Synthetic offline possession verification, not custody or trust (#5231)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.secrets_pki.credential_issuer_resolution import (
    IssuerPossessionChallenge,
    IssuerResolutionTarget,
    issuer_possession_statement,
    verify_issuer_possession,
)

_NOW = datetime(2026, 11, 26, 12, tzinfo=UTC)
_TARGET = IssuerResolutionTarget(1, 'openbao', '', 'kv', 'a' * 64, 2)
# Public deterministic synthetic test seed; never an operational key.
_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
_PUBLIC = _KEY.public_key()
_CHALLENGE = IssuerPossessionChallenge(
    _TARGET,
    sha256(_PUBLIC.public_bytes_raw()).hexdigest(),
    'b' * 64,
    1,
    _NOW - timedelta(minutes=5),
    _NOW + timedelta(minutes=5),
)


def _signature(challenge):
    statement = issuer_possession_statement(challenge)
    assert statement is not None
    return _KEY.sign(statement)


def test_possession_only_and_repeated_verification_not_consumption():
    signature = _signature(_CHALLENGE)
    assert verify_issuer_possession(_CHALLENGE, signature=signature, verification_key=_PUBLIC, now=_NOW)
    assert verify_issuer_possession(_CHALLENGE, signature=signature, verification_key=_PUBLIC, now=_NOW)
    vault = replace(_CHALLENGE, target=replace(_TARGET, provider_key='vault'))
    assert verify_issuer_possession(vault, signature=_signature(vault), verification_key=_PUBLIC, now=_NOW)


@pytest.mark.parametrize(
    'changes',
    [
        {'provider_key': 'vault'},
        {'integration_instance_id': 2},
        {'provider_namespace': 'other'},
        {'mount': 'other'},
        {'deployment_ref': 'c' * 64},
        {'revision_number': 3},
    ],
)
def test_target_substitution_denied(changes):
    expected = replace(_CHALLENGE, target=replace(_TARGET, **changes))
    assert not verify_issuer_possession(expected, signature=_signature(_CHALLENGE), verification_key=_PUBLIC, now=_NOW)


@pytest.mark.parametrize(
    'changes',
    [
        {'source_owner_id': 2},
        {'challenge_sha256': 'c' * 64},
        {'key_sha256': 'd' * 64},
        {'issued_at': _NOW - timedelta(minutes=4)},
        {'expires_at': _NOW + timedelta(minutes=4)},
        {'expires_at': _NOW},
        {'issued_at': _NOW + timedelta(seconds=1)},
        {'expires_at': _NOW + timedelta(hours=24)},
        {'issued_at': _NOW.replace(tzinfo=None)},
        {'challenge_sha256': ''},
        {'source_owner_id': 0},
    ],
)
def test_challenge_substitution_or_invalid_window_denied(changes):
    assert not verify_issuer_possession(
        replace(_CHALLENGE, **changes), signature=_signature(_CHALLENGE), verification_key=_PUBLIC, now=_NOW
    )


def test_wrong_domain_key_and_signature_denied():
    statement = issuer_possession_statement(_CHALLENGE)
    assert statement is not None
    assert b'"schema":"kaori.secrets.issuer_possession.v1"' in statement
    wrong_domain = statement.replace(b'kaori.secrets.issuer_possession.v1', b'kaori.secrets.kv2.ssh_private_key.v1')
    other = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32)))).public_key()
    assert not verify_issuer_possession(
        _CHALLENGE, signature=_KEY.sign(wrong_domain), verification_key=_PUBLIC, now=_NOW
    )
    assert not verify_issuer_possession(_CHALLENGE, signature=_signature(_CHALLENGE), verification_key=other, now=_NOW)
    assert not verify_issuer_possession(_CHALLENGE, signature=b'invalid', verification_key=_PUBLIC, now=_NOW)


def test_valid_signature_outside_window_denied():
    signature = _signature(_CHALLENGE)
    assert not verify_issuer_possession(
        _CHALLENGE, signature=signature, verification_key=_PUBLIC, now=_CHALLENGE.expires_at
    )
    assert not verify_issuer_possession(
        _CHALLENGE, signature=signature, verification_key=_PUBLIC, now=_CHALLENGE.issued_at - timedelta(seconds=1)
    )
