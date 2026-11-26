"""Provider-native read-only issuer metadata and versioned signature decoding (#5245).

No signing API, export, key creation, rotation or fallback. A successful
observation is not deployment/custody authority; compare independently pinned
enrollment evidence before using the public key.
"""

from __future__ import annotations

import base64
import os
import re
from binascii import Error as Base64Error
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import (
    KV2HTTPTransport,
    SecretProviderError,
)
from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient

_SEGMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,159}')
_DIGEST = re.compile(r'[a-f0-9]{64}')
_CLUSTER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')


@dataclass(frozen=True, slots=True, repr=False)
class TransitIssuerBinding:
    provider_key: str
    endpoint: str
    cluster_id: str
    namespace: str
    transit_mount: str
    key_name: str
    key_version: int
    key_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class TransitIssuerObservation:
    binding: TransitIssuerBinding
    public_key_hex: str
    observed_at: datetime


def _segment(value: object) -> bool:
    return isinstance(value, str) and _SEGMENT.fullmatch(value) is not None


def valid_transit_binding(binding: TransitIssuerBinding) -> bool:
    return (
        isinstance(binding, TransitIssuerBinding)
        and binding.provider_key in ('vault', 'openbao')
        and isinstance(binding.endpoint, str)
        and 0 < len(binding.endpoint) <= 512
        and isinstance(binding.cluster_id, str)
        and _CLUSTER.fullmatch(binding.cluster_id) is not None
        and isinstance(binding.namespace, str)
        and len(binding.namespace) <= 255
        and all(_segment(part) for part in binding.namespace.split('/') if binding.namespace)
        and _segment(binding.transit_mount)
        and _segment(binding.key_name)
        and type(binding.key_version) is int
        and 1 <= binding.key_version <= 2_147_483_647
        and isinstance(binding.key_sha256, str)
        and _DIGEST.fullmatch(binding.key_sha256) is not None
    )


def _decode_canonical(value: object, size: int) -> bytes | None:
    if not isinstance(value, str) or len(value) != 4 * ((size + 2) // 3) or not value.isascii():
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, Base64Error):
        return None
    if len(raw) != size or base64.b64encode(raw).decode('ascii') != value:
        return None
    return raw


def decode_transit_signature(value: object, *, key_version: int) -> bytes | None:
    """Only the explicitly enrolled native signature version, never latest fallback."""
    if (
        not isinstance(value, str)
        or type(key_version) is not int
        or not 1 <= key_version <= 2_147_483_647
        or len(value) > 112
    ):
        return None
    prefix = f'vault:v{key_version}:'
    return _decode_canonical(value[len(prefix) :], 64) if value.startswith(prefix) else None


def _transport(binding: TransitIssuerBinding, *, root: bool = False) -> KV2HTTPTransport:
    provider = OpenBaoClient if binding.provider_key == 'openbao' else VaultClient
    if not os.getenv(provider.ca_bundle_env, '').strip():
        raise SecretProviderError('Explicit provider CA is required for issuer enrollment.')
    transport = KV2HTTPTransport(
        endpoint=binding.endpoint,
        provider_label=provider.provider_label,
        allowed_origins_env=provider.allowed_origins_env,
        ca_bundle_env=provider.ca_bundle_env,
        namespace='' if root else binding.namespace,
    )
    if transport.endpoint != binding.endpoint or transport.namespace != ('' if root else binding.namespace):
        raise SecretProviderError('Issuer endpoint or namespace is not canonical.')
    return transport


def _active_cluster(transport: KV2HTTPTransport, binding: TransitIssuerBinding) -> None:
    status, health = transport._request('/v1/sys/health')
    if (
        status != 200
        or health.get('initialized') is not True
        or health.get('sealed') is not False
        or health.get('standby') is not False
        or health.get('performance_standby', False) is not False
        or health.get('cluster_id') != binding.cluster_id
    ):
        raise SecretProviderError('Issuer deployment is not currently qualified.')


def _require_inspection_token(transport: KV2HTTPTransport, token: str) -> None:
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= 4096
        or not token.isascii()
        or any(ord(char) < 33 or ord(char) > 126 for char in token)
    ):
        raise SecretProviderError('Issuer inspection requires a transient operator token.')
    status, response = transport._request('/v1/auth/token/lookup-self', token=token)
    data = response.get('data')
    if status != 200 or not isinstance(data, dict):
        raise SecretProviderError('Issuer inspection token could not be qualified.')
    policies, ttl = data.get('policies'), data.get('ttl')
    if (
        not isinstance(policies, list)
        or not policies
        or not all(isinstance(policy, str) for policy in policies)
        or 'root' in policies
        or type(ttl) is not int
        or not 0 < ttl <= 3600
    ):
        raise SecretProviderError('Issuer inspection requires a bounded non-root token.')


def qualify_transit_public_key(data: object, binding: TransitIssuerBinding) -> bytes | None:
    """Strictly interpret native metadata; absence, drift or unsafe flags deny."""
    if not valid_transit_binding(binding) or not isinstance(data, dict):
        return None
    if (
        data.get('name') != binding.key_name
        or data.get('type') != 'ed25519'
        or data.get('supports_signing') is not True
        or any(
            data.get(flag) is not False for flag in ('derived', 'exportable', 'allow_plaintext_backup', 'deletion_allowed')
        )
        or data.get('imported_key', False) is not False
        or type(data.get('auto_rotate_period')) is not int
        or data['auto_rotate_period'] != 0
        or type(data.get('latest_version')) is not int
        or data['latest_version'] != binding.key_version
    ):
        return None
    minimum = data.get('min_decryption_version')
    signing_minimum = data.get('min_encryption_version')
    if (
        type(minimum) is not int
        or not 1 <= minimum <= binding.key_version
        or type(signing_minimum) is not int
        or not 0 <= signing_minimum <= binding.key_version
    ):
        return None
    versions = data.get('keys')
    version = versions.get(str(binding.key_version)) if isinstance(versions, dict) else None
    raw = _decode_canonical(version.get('public_key'), 32) if isinstance(version, dict) else None
    if raw is None or sha256(raw).hexdigest() != binding.key_sha256:
        return None
    return raw


def observe_transit_issuer(binding: TransitIssuerBinding, *, token: str) -> TransitIssuerObservation:
    """Read only exact enrolled native metadata over the provider's HTTPS policy.

    Intended for a separately authorized operator inspection outside DB locks.
    Token scope and native audit configuration need independent deployment UAT.
    Do not expose this as a generic HTTP action or store the token/response.
    """
    if not valid_transit_binding(binding):
        raise SecretProviderError('Issuer binding is invalid.')
    root = _transport(binding, root=True)
    _active_cluster(root, binding)
    transport = _transport(binding)
    _require_inspection_token(transport, token)
    status, response = transport._request(f'/v1/{binding.transit_mount}/keys/{binding.key_name}', token=token)
    key = qualify_transit_public_key(response.get('data'), binding) if status == 200 else None
    if key is None:
        raise SecretProviderError('Issuer public key or native key policy is unqualified.')
    _active_cluster(root, binding)
    return TransitIssuerObservation(binding, key.hex(), datetime.now(UTC))
