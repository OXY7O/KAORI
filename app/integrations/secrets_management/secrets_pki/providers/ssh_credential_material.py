"""Candidate exact KV v2 SSH material schema, shared by OpenBao and Vault.

Pure validation only: no provider request, login, credential grant or material
retrieval. An independently admitted worker must own the response and selector.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    ProviderCredentialVersionSelector,
    provider_credential_version_statement,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import _safe_metadata, _safe_timestamp

SCHEMA = 'kaori.secrets.kv2.ssh_private_key.v1'
_USERNAME = re.compile(r'[a-z_][a-z0-9_-]{0,30}')
_MAX_KEY_BYTES = 16384


@dataclass(frozen=True, slots=True, repr=False)
class SSHCredentialMaterial:
    """Worker-memory-only value. Never serialize, log or persist this object."""

    username: str
    private_key: Ed25519PrivateKey = field(repr=False)


def _deny() -> SecretProviderError:
    return SecretProviderError('Exact SSH credential material could not be qualified.')


def qualify_ssh_credential_payload(payload: object) -> SSHCredentialMaterial:
    """Validate one narrow candidate schema; reject passwords, extra fields and encrypted keys.

    Schema validation is not issuer proof, provider ownership or a use permit.
    """
    if not isinstance(payload, dict) or set(payload) != {'schema', 'username', 'private_key'}:
        raise _deny()
    username, private_key = payload.get('username'), payload.get('private_key')
    if (
        payload.get('schema') != SCHEMA
        or type(username) is not str
        or _USERNAME.fullmatch(username) is None
        or username == 'root'
        or type(private_key) is not str
        or not private_key.isascii()
        or not 1 <= len(private_key) <= _MAX_KEY_BYTES
        or not private_key.startswith('-----BEGIN OPENSSH PRIVATE KEY-----\n')
        or not private_key.endswith('-----END OPENSSH PRIVATE KEY-----\n')
        or private_key.count('-----BEGIN OPENSSH PRIVATE KEY-----') != 1
        or private_key.count('-----END OPENSSH PRIVATE KEY-----') != 1
    ):
        raise _deny()
    try:
        key = serialization.load_ssh_private_key(private_key.encode('ascii'), password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm):
        # Never propagate parser errors or material into ordinary error paths.
        raise _deny() from None
    if not isinstance(key, Ed25519PrivateKey):
        raise _deny()
    return SSHCredentialMaterial(username, key)


def qualify_exact_ssh_version(
    selector: ProviderCredentialVersionSelector,
    *,
    metadata_before: dict[str, Any],
    data_response: dict[str, Any],
    metadata_after: dict[str, Any],
    now: datetime,
) -> SSHCredentialMaterial:
    """Check exact current native metadata on both sides of a versioned data read.

    The future worker must separately authenticate provider/endpoint/cluster,
    obtain a least-privileged short-lived token and fetch the exact canonical
    path/version. This function deliberately performs no request.
    """
    if (
        not isinstance(now, datetime)
        or now.utcoffset() is None
        or provider_credential_version_statement(
            selector, issued_at=now, expires_at=now + timedelta(seconds=1)
        ) is None
        or not isinstance(metadata_before, dict)
        or not isinstance(metadata_after, dict)
        or not isinstance(data_response, dict)
    ):
        raise _deny()
    selected = selector.credential
    try:
        # The shared inventory parser permits absent optional timestamps.
        # Material use requires explicit native fields for the selected version.
        for response in (metadata_before, metadata_after):
            data = response.get('data')
            if not isinstance(data, dict) or type(data.get('current_version')) is not int:
                raise _deny()
            rows = data.get('versions')
            native_row = rows.get(str(selected.version)) if isinstance(rows, dict) else None
            if (
                not isinstance(native_row, dict)
                or not {'created_time', 'deletion_time', 'destroyed'}.issubset(native_row)
                or native_row['destroyed'] is not False
            ):
                raise _deny()
        before = _safe_metadata(mount=selected.mount, path='', body=metadata_before)
        after = _safe_metadata(mount=selected.mount, path='', body=metadata_after)
        if before != after or before.current_version != selected.version:
            raise _deny()
        versions = [version for version in before.versions if version.version == selected.version]
        if (
            len(versions) != 1
            or versions[0].created_time != selected.provider_created_time
            or versions[0].deletion_time is not None
            or versions[0].destroyed
        ):
            raise _deny()
        envelope = data_response.get('data')
        if not isinstance(envelope, dict):
            raise _deny()
        native = envelope.get('metadata')
        if (
            not isinstance(native, dict)
            or type(native.get('version')) is not int
            or native['version'] != selected.version
            or native.get('destroyed') is not False
            or 'deletion_time' not in native
            or _safe_timestamp(native['deletion_time']) is not None
            or _safe_timestamp(native.get('created_time')) != selected.provider_created_time
        ):
            raise _deny()
        return qualify_ssh_credential_payload(envelope.get('data'))
    except (ValueError, TypeError, KeyError, OverflowError):
        raise _deny() from None
