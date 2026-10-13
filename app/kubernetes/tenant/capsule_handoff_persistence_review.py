"""Read-only Capsule AuditEvent persistence boundary and pre-append review (#1229).

The shared AuditEvent table is NOT an immutable ledger. Until DB-level
write-once/uniqueness guarantees, authenticated history completeness and a
transactional actor/plan authority gate exist, these helpers grant NO append,
provider PATCH, recovery retry, or Released transition.

There is deliberately no INSERT/UPDATE/DELETE/commit, route or background job.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_attempt_state import (
    project_capsule_attempt_history,
)
from app.kubernetes.tenant.capsule_handoff_audit_envelope import (
    _MAX_ROWS,
    _TARGET,
    inspect_capsule_audit_event_envelopes,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.models.audit import AuditEvent


def _metadata(row: Any) -> dict[str, Any]:
    value = getattr(row, 'metadata_json', None)
    if isinstance(row, Mapping):
        value = row.get('metadata_json')
    if not isinstance(value, dict):
        raise ValueError('Capsule AuditEvent metadata is missing or malformed.')
    return dict(value)


def inspect_capsule_persistence_snapshot(
    *,
    tenant_id: str,
    plan: Mapping[str, Any],
    related: Mapping[str, Any],
    accepted_actor_user_id: int,
    rows: list[Any],
) -> dict[str, Any]:
    """Validate a complete caller-supplied history *shape*, not DB integrity.

    Historical records from other plan hashes MUST NOT be filtered out.
    A snapshot cannot prove there are no concurrently committed rows or
    records previously deleted from the shared AuditEvent table.
    """
    if (
        not isinstance(tenant_id, str)
        or not tenant_id
        or not isinstance(plan, Mapping)
        or plan.get('tenant_id') != tenant_id
        or not isinstance(related, Mapping)
        or not isinstance(rows, list)
        or len(rows) > _MAX_ROWS
    ):
        raise ValueError('Capsule persistence snapshot has incomplete canonical scope.')
    projection = inspect_capsule_audit_event_envelopes(
        plan=plan,
        related=related,
        accepted_actor_user_id=accepted_actor_user_id,
        rows=rows,
    )
    status = projection['status']
    blocked = status not in ('no_attempt_observed_not_authorized',)
    return {
        **projection,
        'persistence_status': (
            'existing_attempt_requires_independent_recovery_review'
            if blocked
            else 'no_attempt_observed_storage_guarantees_missing'
        ),
        'recorded_attempt_count': 1 if rows else 0,
        'new_attempt_blocked_by_history': blocked,
        'historical_attempts_exhaustively_proven': False,
        'transactional_single_attempt_guaranteed': False,
        'database_write_once_enforced': False,
        'prewrite_audit_commit_barrier_proven': False,
        'storage_durability_proven': False,
        'append_authorized': False,
        'provider_mutation_performed': False,
        'provider_execution_admitted': False,
        'provider_handoff_verified': False,
        'auto_retry_authorized': False,
        'resume_authorized': False,
        'release_authorized': False,
    }


def read_capsule_committed_audit_history(
    *,
    tenant_id: str,
    plan: Mapping[str, Any],
    related: Mapping[str, Any],
    accepted_actor_user_id: int,
) -> dict[str, Any]:
    """Read the unfiltered Capsule execution rows from SQL; NEVER write.

    A fixed upper bound catches historical/replayed attempts rather than
    truncating them to the newest three. A second writer or DB tampering
    remains possible until the future locked, unique, write-once ledger exists.
    """
    if (
        not isinstance(tenant_id, str)
        or not tenant_id
        or not isinstance(plan, Mapping)
        or plan.get('tenant_id') != tenant_id
        or not isinstance(related, Mapping)
        or type(accepted_actor_user_id) is not int
        or accepted_actor_user_id <= 0
    ):
        raise ValueError('Canonical Capsule Tenant and accepted actor are required.')
    rows = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.asc())
        .limit(_MAX_ROWS + 1)
        .all()
    )
    if len(rows) > _MAX_ROWS:
        raise ValueError('Multiple, truncated or replayed Capsule attempt histories require independent recovery.')
    return inspect_capsule_persistence_snapshot(
        tenant_id=tenant_id,
        plan=plan,
        related=related,
        accepted_actor_user_id=accepted_actor_user_id,
        rows=rows,
    )


def review_capsule_audit_append_candidate(
    *,
    tenant_id: str,
    plan: Mapping[str, Any],
    related: Mapping[str, Any],
    accepted_actor_user_id: int,
    committed_rows: list[Any],
    candidate_event: Mapping[str, Any],
) -> dict[str, Any]:
    """Check proposed event sequence, not whether an append is permitted.

    The future trusted service MUST hold a Tenant-scoped transactional lock,
    reload all committed rows, enforce a unique-attempt DB constraint, commit
    START before any Kubernetes write, then independently validate provider
    outcome. This pure review cannot replace those atomic guarantees.
    """
    snapshot = inspect_capsule_persistence_snapshot(
        tenant_id=tenant_id,
        plan=plan,
        related=related,
        accepted_actor_user_id=accepted_actor_user_id,
        rows=committed_rows,
    )
    if (
        not isinstance(candidate_event, Mapping)
        or not isinstance(candidate_event.get('event_sha256'), str)
        or len(committed_rows) >= _MAX_ROWS
    ):
        raise ValueError('Capsule append candidate is malformed or its attempt is terminal.')
    events = [_metadata(row) for row in committed_rows]
    events.append(dict(candidate_event))
    projected = project_capsule_attempt_history(
        plan=plan,
        related=related,
        accepted_actor_user_id=accepted_actor_user_id,
        events=events,
    )
    return {
        'status': 'candidate_event_schema_validated_storage_admission_blocked',
        'tenant_id': tenant_id,
        'plan_sha256': plan.get('plan_sha256'),
        'attempt_id': projected['attempt_id'],
        'history_sha256': projected['history_sha256'],
        'prior_audit_anchor_sha256': snapshot['audit_record_anchor_sha256'],
        'candidate_event_sha256': candidate_event['event_sha256'],
        'expected_event_count': len(events),
        'candidate_receipt_sha256': _digest(
            {
                'plan_sha256': plan.get('plan_sha256'),
                'history_sha256': projected['history_sha256'],
                'event_count': len(events),
            }
        ),
        'append_authorized': False,
        'trusted_audit_persistence_verified': False,
        'database_write_once_enforced': False,
        'prewrite_audit_commit_barrier_proven': False,
        'provider_handoff_verified': False,
        'provider_execution_admitted': False,
        'auto_retry_authorized': False,
        'resume_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
