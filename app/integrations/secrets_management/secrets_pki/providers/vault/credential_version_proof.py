"""Proposed offline exact-version SSH credential evidence contract (#5184).

No provider request, issuer discovery, material retrieval, policy approval or
execution authority is introduced. The future governed caller must resolve
the verification key independently from an admitted source-owner registry.
A signature from a caller-selected key is not provider authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_SCHEMA = 'kaori.vault.kv2.ssh_private_key.v1'
_HEX_DIGEST = re.compile(r'[a-f0-9]{64}')
_MAX_VALIDITY = timedelta(hours=24)


@dataclass(frozen=True, slots=True, repr=False)
class CredentialVersionSelector:
    """Exact committed Vault representation and version identity, never material."""

    integration_instance_id: int
    provider_namespace: str
    mount: str
    path_sha256: str
    version: int
    provider_created_time: str


def _safe_text(value: str, limit: int, *, allow_empty: bool = False) -> bool:
    return (
        type(value) is str
        and (allow_empty or bool(value))
        and len(value) <= limit
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
    )


def _valid_selector(selector: CredentialVersionSelector) -> bool:
    if (
        type(selector) is not CredentialVersionSelector
        or type(selector.integration_instance_id) is not int
        or selector.integration_instance_id <= 0
        or type(selector.version) is not int
        or not 1 <= selector.version <= 2_147_483_647
        or not _safe_text(selector.provider_namespace, 255, allow_empty=True)
        or not _safe_text(selector.mount, 160)
        or '*' in selector.mount
        or type(selector.path_sha256) is not str
        or _HEX_DIGEST.fullmatch(selector.path_sha256) is None
        or not _safe_text(selector.provider_created_time, 80)
    ):
        return False
    try:
        created = datetime.fromisoformat(selector.provider_created_time)
    except ValueError:
        return False
    return created.utcoffset() == timedelta(0) and created.isoformat() == selector.provider_created_time


def _aware(value: datetime) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def credential_version_statement(
    selector: CredentialVersionSelector, *, issued_at: datetime, expires_at: datetime
) -> bytes | None:
    """Canonical bounded signed bytes for the proposed single credential type."""
    if not _valid_selector(selector) or not _aware(issued_at) or not _aware(expires_at):
        return None
    issued, expires = issued_at.astimezone(UTC), expires_at.astimezone(UTC)
    if not timedelta(0) < expires - issued <= _MAX_VALIDITY:
        return None
    if datetime.fromisoformat(selector.provider_created_time) > issued:
        return None
    return json.dumps(
        {
            'schema': _SCHEMA,
            'selector': asdict(selector),
            'issued_at': issued.isoformat(),
            'expires_at': expires.isoformat(),
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    ).encode('ascii')


def verify_credential_version_statement(
    selector: CredentialVersionSelector,
    *,
    issued_at: datetime,
    expires_at: datetime,
    signature: bytes,
    verification_key: Ed25519PublicKey,
    now: datetime,
) -> bool:
    """Verify exact statement bytes with an independently supplied public key.

    A true result only verifies signature and time/selector shape. The caller
    must prove issuer authority, current provider generation, version state,
    approved policy and operation separately; this is not an access permit.
    """
    if (
        not isinstance(verification_key, Ed25519PublicKey)
        or type(signature) is not bytes
        or len(signature) != 64
        or not _aware(now)
    ):
        return False
    statement = credential_version_statement(selector, issued_at=issued_at, expires_at=expires_at)
    if statement is None:
        return False
    if not issued_at.astimezone(UTC) <= now.astimezone(UTC) < expires_at.astimezone(UTC):
        return False
    try:
        verification_key.verify(signature, statement)
    except InvalidSignature:
        return False
    return True
