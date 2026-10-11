"""Staged Capsule audit collector receipt verification, not Kubernetes authority.

A MAC can authenticate *who supplied a normalized claim batch* IF its key
came independently from an operator-controlled trust store. It cannot prove
that the Kubernetes apiserver emitted those claims, that the controller
originated the mutation, or that an unrecorded/replayed batch never existed.

No key is stored, logged, returned, read from user input, or wired into a
runtime endpoint. Caller must supply server-owned key material out-of-band.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.kubernetes.tenant.capsule_handoff_related_inventory import _canonical, _digest

_SHA = re.compile(r'[a-f0-9]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{2,119}\Z')
_MAX_AGE_SECONDS = 300
_FIELDS = frozenset({
    'contract_version', 'collector_id', 'key_id', 'batch_id',
    'tenant_id', 'cluster_id', 'plan_sha256', 'worklist_sha256',
    'resource_review_sha256', 'claims_sha256', 'captured_at',
    'auth_tag_sha256',
})
_VERSION = 'capsule-apiserver-collector-receipt/v1'


def _utc_recent(value: Any, *, now: datetime) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return False
    seconds = (now - parsed).total_seconds()
    return 0 <= seconds <= _MAX_AGE_SECONDS


def inspect_capsule_collector_receipt(
    *, resource_report: Mapping[str, Any],
    claims: list[Mapping[str, Any]],
    receipt: Mapping[str, Any],
    trusted_collector_id: str,
    trusted_key_id: str,
    trusted_hmac_key: bytes | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify exact batch MAC using a separately provisioned backend trust key.

    This deliberately never labels the audit source/controller authenticated:
    a MAC proves only receipt origin under the supplied key, not that the
    upstream audit pipeline captured genuine, complete apiserver records.
    """
    if (
        not isinstance(resource_report, Mapping)
        or not isinstance(receipt, Mapping)
        or set(receipt) != _FIELDS
        or not isinstance(claims, list)
        or len(claims) > 300
        or not isinstance(trusted_collector_id, str)
        or not _ID.fullmatch(trusted_collector_id)
        or not isinstance(trusted_key_id, str)
        or not _ID.fullmatch(trusted_key_id)
        or type(trusted_hmac_key) is not bytes
        or len(trusted_hmac_key) < 32
    ):
        raise ValueError('Capsule collector receipt requires exact fields and a backend-pinned trust key.')
    now = datetime.now(UTC) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Capsule collector verification requires timezone-aware current time.')
    try:
        batch_uuid = UUID(str(receipt['batch_id']))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Capsule collector receipt batch identity is invalid.') from exc
    if (
        receipt['contract_version'] != _VERSION
        or receipt['collector_id'] != trusted_collector_id
        or receipt['key_id'] != trusted_key_id
        or receipt['batch_id'] != str(batch_uuid)
        or receipt['tenant_id'] != resource_report.get('tenant_id')
        or receipt['cluster_id'] != resource_report.get('cluster_id')
        or receipt['plan_sha256'] != resource_report.get('plan_sha256')
        or receipt['worklist_sha256'] != resource_report.get('worklist_sha256')
        or receipt['resource_review_sha256'] != resource_report.get('resource_review_sha256')
        or any(
            not isinstance(receipt[field], str)
            or not _SHA.fullmatch(receipt[field])
            for field in ('claims_sha256', 'auth_tag_sha256')
        )
        or receipt['claims_sha256'] != _digest(claims)
        or not _utc_recent(receipt['captured_at'], now=now)
    ):
        raise ValueError('Capsule collector receipt is stale or not SHA-bound to this exact plan.')
    payload = {key: receipt[key] for key in sorted(_FIELDS - {'auth_tag_sha256'})}
    calculated = hmac.new(trusted_hmac_key, _canonical(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, receipt['auth_tag_sha256']):
        raise ValueError('Capsule collector receipt authentication failed.')
    # This digest deliberately excludes secret trust key and source actor data.
    return {
        'status': 'collector_mac_valid_upstream_apiserver_origin_unverified',
        'tenant_id': resource_report['tenant_id'],
        'plan_sha256': resource_report['plan_sha256'],
        'worklist_sha256': resource_report['worklist_sha256'],
        'resource_review_sha256': resource_report['resource_review_sha256'],
        'collector_id': trusted_collector_id, 'key_id': trusted_key_id,
        'batch_id': receipt['batch_id'], 'claims_sha256': receipt['claims_sha256'],
        'collector_receipt_sha256': _digest(dict(receipt)),
        'collector_mac_verified': True,
        'collector_key_source_independently_attested': False,
        'audit_batch_replay_prevention_verified': False,
        'apiserver_audit_integrity_verified': False,
        'kubernetes_controller_identity_authenticated': False,
        'controller_origin_attested': False,
        'resource_specific_handoff_admitted': False,
        'provider_execution_admitted': False, 'release_authorized': False,
        'secret_material_persisted': False,
    }
