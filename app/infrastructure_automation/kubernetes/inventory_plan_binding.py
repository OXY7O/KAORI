"""Fail-closed cross-evidence inventory/Plan binding preview (#5163).

A correlation proof is *not* an approved, executable or persisted Plan.
Only sanitized, canonical committed evidence belongs in this assessment.
No SSH, database mutation, arbitrary Ansible inventory or Kubernetes call.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

_HEX = re.compile(r'[a-f0-9]{64}\Z')
_SOURCE = re.compile(r'[a-f0-9]{40}\Z')
_EE = re.compile(r'sha256:[a-f0-9]{64}\Z')


@dataclass(frozen=True, slots=True)
class InventoryBoundPlanReview:
    """Redacted, non-executable result of cross-evidence comparison."""

    state: str
    reason_code: str
    fingerprint: str | None = None
    expires_at: str | None = None
    execution_authorized: bool = False

    def committed_summary(self) -> dict[str, Any]:
        return {
            'schema_version': 1,
            'state': self.state,
            'reason_code': self.reason_code,
            'fingerprint': self.fingerprint,
            'expires_at': self.expires_at,
            'execution_authorized': False,
        }


def _blocked(reason: str) -> InventoryBoundPlanReview:
    return InventoryBoundPlanReview('blocked', reason)


def _digest(value: object) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


def _datetime(value: object) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _qualified_inventory(inventory: Mapping[str, Any]) -> bool:
    return (
        type(inventory.get('schema_version')) is int
        and inventory.get('schema_version') == 1
        and type(inventory.get('control_plane_count')) is int
        and inventory.get('status') == 'review_only'
        and inventory.get('execution_authorized') is False
        and inventory.get('host_count') == 3
        and inventory.get('control_plane_count') == 1
        and inventory.get('worker_count') == 2
        and _digest(inventory.get('fingerprint'))
    )


def _qualified_access(access: Mapping[str, Any]) -> bool:
    return (
        type(access.get('schema_version')) is int
        and access.get('schema_version') == 1
        and access.get('credential_reference_recorded') is True
        and access.get('host_key_reference_recorded') is True
        and access.get('state') == 'references_recorded'
        and access.get('execution_authorized') is False
        and access.get('ssh_trust_verified') is False
        and access.get('privileged_identity_verified') is False
        and _digest(access.get('fingerprint'))
    )


def _qualified_plan(
    plan: Mapping[str, Any],
    inventory: Mapping[str, Any],
    access: Mapping[str, Any],
    connection_id: int,
    source_sha: str,
    execution_environment_digest: str,
) -> bool:
    return (
        type(plan.get('schema_version')) is int
        and plan.get('schema_version') == 1
        and type(plan.get('connection_id')) is int
        and plan.get('connection_id') == connection_id
        and plan.get('host_access_fingerprint') == access.get('fingerprint')
        and plan.get('status') == 'requires_independent_approval'
        and plan.get('approval_status') == 'not_requested'
        and plan.get('execution_status') == 'blocked'
        and plan.get('mutation_authorized') is False
        and _digest(plan.get('plan_fingerprint'))
        and plan.get('inventory_fingerprint') == inventory.get('fingerprint')
        and plan.get('source_sha') == source_sha
        and plan.get('execution_environment_digest') == execution_environment_digest
    )


def assess_inventory_bound_plan_review(
    *,
    connection_id: int,
    source_sha: str,
    execution_environment_digest: str,
    inventory_evidence: Mapping[str, Any] | None,
    access_evidence: Mapping[str, Any] | None,
    plan_evidence: Mapping[str, Any] | None,
    now: datetime,
) -> InventoryBoundPlanReview:
    """Match exact canonical evidence without claiming independent admission.

    Caller must fetch/authorize these snapshots from existing committed KAORI
    records, including exact JobExecution connection and access fingerprint
    binding. Current plan_dispatch does not supply this binding; missing fields
    must block rather than synthesize a review from unrelated evidence.
    Browser-provided JSON, secrets or raw host inventory are unsafe.
    This helper deliberately does not persist or enqueue a JobExecution.
    """
    if type(connection_id) is not int or connection_id <= 0:
        return _blocked('CONNECTION_ID_UNQUALIFIED')
    if type(source_sha) is not str or _SOURCE.fullmatch(source_sha) is None:
        return _blocked('SOURCE_REVISION_UNQUALIFIED')
    if type(execution_environment_digest) is not str or _EE.fullmatch(execution_environment_digest) is None:
        return _blocked('EXECUTION_ENVIRONMENT_UNQUALIFIED')
    if not isinstance(now, datetime) or now.tzinfo is None:
        return _blocked('CLOCK_UNQUALIFIED')
    if (
        not isinstance(inventory_evidence, Mapping)
        or not isinstance(access_evidence, Mapping)
        or not isinstance(plan_evidence, Mapping)
    ):
        return _blocked('COMMITTED_EVIDENCE_MISSING')

    inventory = inventory_evidence
    access = access_evidence
    plan = plan_evidence
    if not _qualified_inventory(inventory):
        return _blocked('INVENTORY_EVIDENCE_UNQUALIFIED')
    if not _qualified_access(access):
        return _blocked('HOST_ACCESS_EVIDENCE_UNQUALIFIED')
    if not _qualified_plan(plan, inventory, access, connection_id, source_sha, execution_environment_digest):
        return _blocked('PLAN_EVIDENCE_MISMATCH')
    expiry = _datetime(plan.get('expires_at'))
    if expiry is None or now >= expiry:
        return _blocked('PLAN_EVIDENCE_EXPIRED')
    # This source-independent SHA is intentionally only a correlation hint.
    # A worker/approval/mutation Run must recheck source identity, host access,
    # inventory generation and the authoritative latest JobExecution attempt.
    material = {
        'schema_version': 1,
        'connection_id': connection_id,
        'source_sha': source_sha,
        'execution_environment_digest': execution_environment_digest,
        'inventory_fingerprint': inventory['fingerprint'],
        'host_access_fingerprint': access['fingerprint'],
        'plan_fingerprint': plan['plan_fingerprint'],
        'expires_at': expiry.isoformat(),
    }
    fingerprint = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    return InventoryBoundPlanReview(
        'review_material_only',
        'INDEPENDENT_ADMISSION_REQUIRED',
        fingerprint,
        expiry.isoformat(),
    )
