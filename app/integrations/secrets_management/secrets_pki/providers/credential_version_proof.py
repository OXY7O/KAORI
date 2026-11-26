"""Shared offline credential evidence primitives (#5184/#5204). No material or authority resolution."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import UUID
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_HEX_DIGEST = re.compile(r'[a-f0-9]{64}')
_MAX_VALIDITY = timedelta(hours=24)


@dataclass(frozen=True, slots=True, repr=False)
class CredentialVersionSelector:
    """Exact committed KV v2 representation and version identity, never material."""

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


def credential_statement_payload(
    selector: CredentialVersionSelector, *, issued_at: datetime, expires_at: datetime
) -> dict[str, object] | None:
    """Shared bounded selector and time validation; no provider identity inference."""
    if not _valid_selector(selector) or not _aware(issued_at) or not _aware(expires_at):
        return None
    issued, expires = issued_at.astimezone(UTC), expires_at.astimezone(UTC)
    if not timedelta(0) < expires - issued <= _MAX_VALIDITY:
        return None
    if datetime.fromisoformat(selector.provider_created_time) > issued:
        return None
    return {
        'selector': asdict(selector),
        'issued_at': issued.isoformat(),
        'expires_at': expires.isoformat(),
    }


def canonical_statement(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def verify_statement(
    statement: bytes | None,
    *,
    issued_at: datetime,
    expires_at: datetime,
    signature: bytes,
    verification_key: Ed25519PublicKey,
    now: datetime,
) -> bool:
    if (
        not isinstance(verification_key, Ed25519PublicKey)
        or type(signature) is not bytes
        or len(signature) != 64
        or not _aware(now)
        or statement is None
    ):
        return False
    if not issued_at.astimezone(UTC) <= now.astimezone(UTC) < expires_at.astimezone(UTC):
        return False
    try:
        verification_key.verify(signature, statement)
    except InvalidSignature:
        return False
    return True


@dataclass(frozen=True, slots=True, repr=False)
class ProviderCredentialVersionSelector:
    """Exact provider/deployment/issuer and committed secret representation."""

    provider_key: Literal['vault', 'openbao']
    deployment_ref: str
    issuer_revision: int
    secret_identity_id: str
    representation_id: int
    credential: CredentialVersionSelector


def _canonical_uuid(value: str) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _valid_provider_selector(selector: ProviderCredentialVersionSelector) -> bool:
    return (
        type(selector) is ProviderCredentialVersionSelector
        and type(selector.provider_key) is str
        and selector.provider_key in ('vault', 'openbao')
        and type(selector.deployment_ref) is str
        and _HEX_DIGEST.fullmatch(selector.deployment_ref) is not None
        and type(selector.issuer_revision) is int
        and selector.issuer_revision > 0
        and _canonical_uuid(selector.secret_identity_id)
        and type(selector.representation_id) is int
        and selector.representation_id > 0
        and _valid_selector(selector.credential)
        and '*' not in selector.credential.provider_namespace
        and '+' not in selector.credential.provider_namespace
        and '+' not in selector.credential.mount
    )


def provider_credential_version_statement(
    selector: ProviderCredentialVersionSelector, *, issued_at: datetime, expires_at: datetime
) -> bytes | None:
    """New provider-qualified schema; never reinterpret a legacy Vault statement."""
    if not _valid_provider_selector(selector):
        return None
    payload = credential_statement_payload(selector.credential, issued_at=issued_at, expires_at=expires_at)
    if payload is None:
        return None
    payload['schema'] = 'kaori.secrets.kv2.ssh_private_key.v1'
    payload['provider_key'] = selector.provider_key
    payload['deployment_ref'] = selector.deployment_ref
    payload['issuer_revision'] = selector.issuer_revision
    payload['secret_identity_id'] = selector.secret_identity_id
    payload['representation_id'] = selector.representation_id
    return canonical_statement(payload)


def verify_provider_credential_version_statement(
    selector: ProviderCredentialVersionSelector,
    *,
    issued_at: datetime,
    expires_at: datetime,
    signature: bytes,
    verification_key: Ed25519PublicKey,
    now: datetime,
) -> bool:
    """Signature and time only; independently resolve current issuer and grant before use."""
    return verify_statement(
        provider_credential_version_statement(selector, issued_at=issued_at, expires_at=expires_at),
        issued_at=issued_at,
        expires_at=expires_at,
        signature=signature,
        verification_key=verification_key,
        now=now,
    )
