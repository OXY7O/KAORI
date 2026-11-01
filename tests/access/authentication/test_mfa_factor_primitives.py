"""Compatibility primitives use the same tested RFC 6238 core as MFA service."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest
from flask import Flask

from app.access.authentication.mfa.factors import (
    generate_recovery_codes,
    hash_recovery_code,
    recovery_code_match,
    start_totp_enrollment,
    verify_totp,
)
from app.access.authentication.mfa.service import _totp
from app.security.credentials import decrypt_credential


def test_enrollment_secret_is_encrypted_and_compatible_with_authenticator() -> None:
    app = Flask(__name__)
    app.config['INTEGRATION_CREDENTIAL_KEY'] = base64.urlsafe_b64encode(b'm' * 32).decode()
    with app.app_context():
        enrollment = start_totp_enrollment(account_label='kaori-uat')
        assert enrollment.encrypted_secret.startswith('enc:v1:')
        assert 'otpauth://totp/' in enrollment.provisioning_uri
        secret = decrypt_credential(enrollment.encrypted_secret)
        assert secret and secret not in repr(enrollment)
        assert enrollment.provisioning_uri not in repr(enrollment)
        assert 'otpauth://' not in repr(enrollment)
        assert 'encrypted_secret=' not in repr(enrollment)
        assert 'provisioning_uri=' not in repr(enrollment)
        assert secret in enrollment.provisioning_uri  # Authorized manual setup still works.
        timestamp = int(datetime(2026, 10, 25, tzinfo=UTC).timestamp())
        code = _totp(secret).generate(timestamp).decode('ascii')
        assert verify_totp(enrollment.encrypted_secret, code, at_time=timestamp)
        assert not verify_totp(enrollment.encrypted_secret, 'invalid', at_time=timestamp)
        assert not verify_totp(enrollment.encrypted_secret, '1234567', at_time=timestamp)
        assert not verify_totp(enrollment.encrypted_secret, '１２３４５６', at_time=timestamp)


def test_recovery_hash_is_nonreversible_and_constant_time_match() -> None:
    codes = generate_recovery_codes()
    assert len(codes) == 10 and len(set(codes)) == 10
    hashes = tuple(hash_recovery_code(value) for value in codes)
    assert all(raw not in digest for raw, digest in zip(codes, hashes, strict=True))
    assert recovery_code_match(codes[0], hashes) == hashes[0]
    assert recovery_code_match('0' * 32, hashes) is None
    assert recovery_code_match('not-a-code', hashes) is None
    assert recovery_code_match(codes[0], hashes[1:]) is None


@pytest.mark.parametrize('count', [0, 11, -1])
def test_recovery_code_generation_rejects_invalid_counts(count: int) -> None:
    with pytest.raises(ValueError):
        generate_recovery_codes(count=count)
