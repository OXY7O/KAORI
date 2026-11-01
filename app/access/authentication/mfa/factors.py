"""Compatibility factor primitives built on KAORI's canonical cryptography TOTP.

Full enrollment, persistence, replay protection and admission remain governed
by mfa.service. Never introduce a second cryptographic OTP implementation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import quote

from app.access.authentication.mfa.service import _accepted_step
from app.security.credentials import decrypt_credential, encrypt_credential

RECOVERY_CODE_BYTES = 16
RECOVERY_CODE_COUNT = 10
TOTP_DIGITS = 6
RECOVERY_CODE_PREFIX = 'sha256:v1:'


@dataclass(frozen=True, slots=True)
class TotpEnrollment:
    encrypted_secret: str = field(repr=False)
    provisioning_uri: str = field(repr=False)


def totp_provisioning_uri(secret: str, *, account_label: str, issuer: str = 'KAORI') -> str:
    """Canonical RFC 6238 URI for an already-generated secret, never a remote QR request."""
    if not account_label or len(account_label) > 255 or not issuer or len(issuer) > 100:
        raise ValueError('Invalid TOTP enrollment identity.')
    label = quote(f'{issuer}:{account_label}', safe='')
    return (
        f'otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe="")}'
        f'&algorithm=SHA1&digits={TOTP_DIGITS}&period=30'
    )


def start_totp_enrollment(*, account_label: str, issuer: str = 'KAORI') -> TotpEnrollment:
    """Generate setup material with the same verifier as the active service."""
    if not account_label or len(account_label) > 255 or not issuer or len(issuer) > 100:
        raise ValueError('Invalid TOTP enrollment identity.')
    secret = base64.b32encode(secrets.token_bytes(20)).decode('ascii')
    encrypted = encrypt_credential(secret)
    if not encrypted:
        raise RuntimeError('TOTP factor encryption is unavailable.')
    return TotpEnrollment(
        encrypted_secret=encrypted,
        provisioning_uri=totp_provisioning_uri(secret, account_label=account_label, issuer=issuer),
    )


def verify_totp(encrypted_secret: str, value: str, *, at_time: int | None = None) -> bool:
    """Use canonical bounded verifier; browser-provided proof is never trusted."""
    secret = decrypt_credential(encrypted_secret)
    if not secret:
        return False
    timestamp = int(at_time) if at_time is not None else int(datetime.now(UTC).timestamp())
    return (
        _accepted_step(secret, value, last_accepted_step=None, now=datetime.fromtimestamp(timestamp, UTC)) is not None
    )


def generate_recovery_codes(*, count: int = RECOVERY_CODE_COUNT) -> tuple[str, ...]:
    if not 1 <= count <= RECOVERY_CODE_COUNT:
        raise ValueError('Invalid recovery code count.')
    return tuple(secrets.token_hex(RECOVERY_CODE_BYTES) for _ in range(count))


def hash_recovery_code(code: str) -> str:
    if not isinstance(code, str) or len(code) != RECOVERY_CODE_BYTES * 2:
        raise ValueError('Invalid recovery code format.')
    if not all(char in '0123456789abcdef' for char in code):
        raise ValueError('Invalid recovery code format.')
    return RECOVERY_CODE_PREFIX + hashlib.sha256(code.encode('ascii')).hexdigest()


def recovery_code_match(code: str, issued_hashes: Iterable[str]) -> str | None:
    try:
        digest = hash_recovery_code(code)
    except ValueError:
        return None
    for stored in issued_hashes:
        if isinstance(stored, str) and hmac.compare_digest(stored, digest):
            return stored
    return None
