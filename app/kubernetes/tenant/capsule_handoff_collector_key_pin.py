"""Review-only collector key pin/rotation contract for Capsule audit evidence.

A pin description is NOT the trust store. The caller cannot earn
independent provenance by supplying a matching self-asserted key hash.
A future Vault/KMS-backed credential broker must supply operator-pinned
key identity, actual key/verify handle and an authenticated origin.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest

_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{2,119}\Z')
_FIELDS = frozenset(
    {
        'contract_version',
        'cluster_id',
        'collector_id',
        'key_id',
        'key_fingerprint_sha256',
        'issued_at',
        'expires_at',
        'state',
    }
)


def _at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Capsule key pin timestamp is missing.')
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Capsule key pin timestamp is malformed.') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('Capsule key pin timestamp requires a timezone.')
    return dt.astimezone(UTC)


def inspect_capsule_collector_key_pin(
    *,
    descriptor: Mapping[str, Any],
    cluster_id: str,
    collector_id: str,
    key_id: str,
    backend_key_material: bytes | None,
    pinned_fingerprint_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Match exact expected key/collector scope, grant no source authority.

    The fingerprint MUST come from independent backend configuration.
    This pure function cannot prove it did, or prove a revoked key has
    been removed from Vault/KMS or all backend nodes.
    """
    if (
        not isinstance(descriptor, Mapping)
        or set(descriptor) != _FIELDS
        or any(not isinstance(x, str) or not _ID.fullmatch(x) for x in (cluster_id, collector_id, key_id))
        or type(backend_key_material) is not bytes
        or len(backend_key_material) < 32
        or not isinstance(pinned_fingerprint_sha256, str)
        or not _SHA.fullmatch(pinned_fingerprint_sha256)
    ):
        raise ValueError('Collector pin requires bounded identity and an independently supplied strong key.')
    instant = datetime.now(UTC) if now is None else now
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Collector key pin review requires timezone-aware now.')
    if (
        descriptor['contract_version'] != 'capsule-collector-key-pin/v1'
        or descriptor['state'] != 'active'
        or descriptor['cluster_id'] != cluster_id
        or descriptor['collector_id'] != collector_id
        or descriptor['key_id'] != key_id
        or descriptor['key_fingerprint_sha256'] != pinned_fingerprint_sha256
    ):
        raise ValueError('Collector pin is revoked, rotated or outside exact trusted scope.')
    start = _at(descriptor['issued_at'])
    end = _at(descriptor['expires_at'])
    instant = instant.astimezone(UTC)
    if not start <= instant < end:
        raise ValueError('Collector key pin is not inside its active key-rotation window.')
    material_fingerprint = hashlib.sha256(backend_key_material).hexdigest()
    if not hmac.compare_digest(material_fingerprint, pinned_fingerprint_sha256):
        raise ValueError('Backend collector key material differs from pinned key identity.')
    return {
        'status': 'collector_key_pin_shape_correlated_unattested',
        'cluster_id': cluster_id,
        'collector_id': collector_id,
        'key_id': key_id,
        'pin_record_sha256': _digest(dict(descriptor)),
        'key_material_matches_pin': True,
        'backend_trust_store_source_attested': False,
        'key_rotation_revocation_enforced': False,
        'collector_principal_authenticated': False,
        'apiserver_audit_integrity_verified': False,
        'controller_origin_attested': False,
        'provider_execution_admitted': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
