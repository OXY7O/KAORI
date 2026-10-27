"""Fail-closed admission for future scoped Vault Secret registry projections.

This is NOT a grant database or replacement for canonical #724 policy.
Only a separately authorized caller may supply exact committed source IDs.
No raw path, mount, Secret name, provider namespace, or value crosses output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

ResultStatus = Literal['scope_denied', 'source_unknown', 'qualified']


@dataclass(frozen=True, slots=True)
class SecretRegistryAdmission:
    status: ResultStatus
    eligible_record_count: int | None = None
    permitted_for_detail: bool = False


@dataclass(frozen=True, slots=True)
class SecretRegistryCollectionState:
    source_ready: bool
    generation_complete: bool


def admit_secret_registry_scope(
    *,
    has_view_permission: bool,
    scope_policy_enforced: bool,
    approved_instance_ids: frozenset[int] | None,
    requested_instance_id: int,
    observed_record_instance_ids: tuple[int, ...],
    collection_state: SecretRegistryCollectionState,
    committed_at: datetime | None,
    now: datetime,
) -> SecretRegistryAdmission:
    """Return only count/status; never accept caller-provided source names.

    Source IDs are canonical IntegrationInstance keys, not Vault-issued IDs.
    The request must be constrained to one **explicitly authorized** source.
    No grant or outdated/no collection evidence results in non-count status.
    """
    denied = SecretRegistryAdmission('scope_denied')
    unknown = SecretRegistryAdmission('source_unknown')
    if (
        has_view_permission is not True
        or scope_policy_enforced is not True
        or approved_instance_ids is None
        or not isinstance(approved_instance_ids, frozenset)
        or not isinstance(requested_instance_id, int)
        or isinstance(requested_instance_id, bool)
        or requested_instance_id < 1
        or not approved_instance_ids
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in approved_instance_ids)
        or requested_instance_id not in approved_instance_ids
    ):
        return denied
    if (
        not isinstance(collection_state, SecretRegistryCollectionState)
        or collection_state.source_ready is not True
        or collection_state.generation_complete is not True
        or not isinstance(now, datetime)
        or now.tzinfo is None
        or committed_at is None
        or not isinstance(committed_at, datetime)
        or committed_at.tzinfo is None
        or now.utcoffset() is None
        or committed_at.utcoffset() is None
    ):
        return unknown
    elapsed = now.astimezone(UTC) - committed_at.astimezone(UTC)
    if not timedelta(0) <= elapsed <= timedelta(hours=24):
        return unknown
    if (
        not isinstance(observed_record_instance_ids, tuple)
        or len(observed_record_instance_ids) > 200
        or any(
            not isinstance(item, int) or isinstance(item, bool) or item != requested_instance_id
            for item in observed_record_instance_ids
        )
    ):
        return unknown
    return SecretRegistryAdmission('qualified', len(observed_record_instance_ids))
