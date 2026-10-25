"""MFA factor primitives using vetted PyOTP; no credential/session issuance here.

Persistence, enrollment activation and login admission are owned by MFA-02
workflows. This module never accepts a browser assertion of prior verification.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Iterable
from dataclasses import dataclass

import pyotp

from app.security.credentials import decrypt_credential, encrypt_credential

RECOVERY_CODE_BYTES = 16
RECOVERY_CODE_COUNT = 10
TOTP_DIGITS = 6
RECOVERY_CODE_PREFIX = 'sha256:v1:'


@dataclass(frozen=True, slots=True)
class TotpEnrollment:
    encrypted_secret: str
    provisioning_uri: str


def start_totp_enrollment(*, account_label: str, issuer: str = 'KAORI') -> TotpEnrollment:
    """Return encrypted factor material; do not log or persist QR URI in audit."""
    if not account_label or len(account_label) > 255 or not issuer or len(issuer) > 100:
        raise ValueError('Invalid TOTP enrollment identity.')
    secret = pyotp.random_base32()
    encrypted = encrypt_credential(secret)
    if not encrypted:
        raise RuntimeError('TOTP factor encryption is unavailable.')
    uri = pyotp.TOTP(secret, digits=TOTP_DIGITS).provisioning_uri(name=account_label, issuer_name=issuer)
    return TotpEnrollment(encrypted_secret=encrypted, provisioning_uri=uri)


def verify_totp(encrypted_secret: str, value: str, *, at_time: int | None = None) -> bool:
    """Validate exactly six ASCII digits, with a bounded +/- one-step window."""
    if not isinstance(value, str) or len(value) != TOTP_DIGITS or not value.isascii() or not value.isdecimal():
        return False
    secret = decrypt_credential(encrypted_secret)
    if not secret:
        return False
    return bool(pyotp.TOTP(secret, digits=TOTP_DIGITS).verify(value, for_time=at_time, valid_window=1))


def generate_recovery_codes(*, count: int = RECOVERY_CODE_COUNT) -> tuple[str, ...]:
    """One-time display: persist only hashes, never raw recovery codes."""
    if not 1 <= count <= RECOVERY_CODE_COUNT:
        raise ValueError('Invalid recovery code count.')
    return tuple(secrets.token_hex(RECOVERY_CODE_BYTES) for _ in range(count))


def hash_recovery_code(code: str) -> str:
    """High-entropy random codes permit an SHA-256 digest; no username salt."""
    if not isinstance(code, str) or len(code) != RECOVERY_CODE_BYTES * 2:
        raise ValueError('Invalid recovery code format.')
    if not all(char in '0123456789abcdef' for char in code):
        raise ValueError('Invalid recovery code format.')
    return RECOVERY_CODE_PREFIX + hashlib.sha256(code.encode('ascii')).hexdigest()


def recovery_code_match(code: str, issued_hashes: Iterable[str]) -> str | None:
    """Return the digest to atomically consume, never a bearer recovery code."""
    try:
        digest = hash_recovery_code(code)
    except ValueError:
        return None
    for stored in issued_hashes:
        if isinstance(stored, str) and hmac.compare_digest(stored, digest):
            return stored
    return None
