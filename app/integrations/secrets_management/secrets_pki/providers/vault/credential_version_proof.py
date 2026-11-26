"""Legacy Vault exact-version evidence contract (#5184).

The legacy schema and canonical bytes remain unchanged. A valid signature
does not confer provider authority or permission to retrieve material.
"""

from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    CredentialVersionSelector as CredentialVersionSelector,
    canonical_statement,
    credential_statement_payload,
    verify_statement,
)


def credential_version_statement(
    selector: CredentialVersionSelector, *, issued_at: datetime, expires_at: datetime
) -> bytes | None:
    """Preserve the existing Vault-only wire format."""
    payload = credential_statement_payload(selector, issued_at=issued_at, expires_at=expires_at)
    if payload is None:
        return None
    payload['schema'] = 'kaori.vault.kv2.ssh_private_key.v1'
    return canonical_statement(payload)


def verify_credential_version_statement(
    selector: CredentialVersionSelector,
    *,
    issued_at: datetime,
    expires_at: datetime,
    signature: bytes,
    verification_key: Ed25519PublicKey,
    now: datetime,
) -> bool:
    """Legacy signature check; no provider authority or execution admission."""
    return verify_statement(
        credential_version_statement(selector, issued_at=issued_at, expires_at=expires_at),
        issued_at=issued_at,
        expires_at=expires_at,
        signature=signature,
        verification_key=verification_key,
        now=now,
    )
