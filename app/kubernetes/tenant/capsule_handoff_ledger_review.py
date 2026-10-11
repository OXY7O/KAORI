"""Read-only integrity inspection for Capsule's dedicated SQL event ledger.

The schema/trigger migration must be separately installed and verified first.
This code cannot attest that triggers, WAL, backups or database permissions
are active. No insert/flush/commit, Kubernetes call, or Release is possible.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.kubernetes.tenant.capsule_handoff_attempt_state import (
    _MAX_HISTORY, _parse_time, project_capsule_attempt_history,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent

_COLUMNS = (
    'tenant_id', 'cluster_id', 'generation', 'plan_sha256',
    'handoff_fingerprint', 'worklist_sha256', 'attempt_id',
    'sequence', 'event_type', 'actor_user_id',
    'previous_event_sha256', 'event_sha256',
)


def _get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, Mapping) else getattr(value, key, None)


def _event_from_row(row: Any) -> dict[str, Any]:
    payload = _get(row, 'event_json')
    if not isinstance(payload, Mapping):
        raise ValueError('Capsule ledger row lacks canonical immutable event JSON.')
    event = dict(payload)
    if any(_get(row, field) != event.get(field) for field in _COLUMNS):
        raise ValueError('Capsule ledger indexed fields disagree with stored event payload.')
    recorded = _get(row, 'recorded_at')
    emitted = _get(row, 'event_at')
    if (
        type(_get(row, 'id')) is not int or _get(row, 'id') <= 0
        or not isinstance(recorded, datetime)
        or not isinstance(emitted, datetime)
    ):
        raise ValueError('Capsule ledger identity or timestamps are unavailable.')
    event_time = _parse_time(event.get('event_at'))
    # SQLite's SQLAlchemy DateTime storage may discard the timezone on round
    # trip; make the UTC storage convention explicit, not an authority claim.
    normalized = emitted if emitted.tzinfo is not None else emitted.replace(tzinfo=UTC)
    if normalized.astimezone(UTC) != event_time.astimezone(UTC):
        raise ValueError('Capsule ledger indexed provider event time differs from its payload.')
    return event


def inspect_capsule_ledger_rows(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    accepted_actor_user_id: int, rows: list[Any],
) -> dict[str, Any]:
    """Read-only validation of all supplied chronological rows, no trust grant."""
    if (
        not isinstance(plan, Mapping) or not isinstance(related, Mapping)
        or not isinstance(rows, list) or len(rows) > _MAX_HISTORY
    ):
        raise ValueError('Capsule ledger history is unbounded or malformed.')
    ids = [_get(row, 'id') for row in rows]
    if any(type(id_) is not int or id_ <= 0 for id_ in ids):
        raise ValueError('Capsule ledger contains invalid committed event IDs.')
    if any(ids[index] >= ids[index + 1] for index in range(len(ids) - 1)):
        raise ValueError('Capsule ledger append chronology is not strictly ordered.')
    events = [_event_from_row(row) for row in rows]
    projection = project_capsule_attempt_history(
        plan=plan, related=related,
        accepted_actor_user_id=accepted_actor_user_id, events=events,
    )
    if rows and events[0]['event_type'] != 'started':
        raise ValueError('Capsule ledger starts without the original START event.')
    return {
        **projection,
        'status': projection['status'],
        'ledger_record_count': len(rows),
        'ledger_record_anchor_sha256': _digest([
            {'id': id_, 'event_sha256': event['event_sha256']}
            for id_, event in zip(ids, events, strict=True)
        ]),
        'schema_source_reviewed': True,
        'database_schema_applied_verified': False,
        'db_write_once_triggers_verified': False,
        'database_role_permissions_verified': False,
        'ledger_history_completeness_verified': False,
        'transactional_start_commit_verified': False,
        'provider_readback_authoritative_verified': False,
        'provider_handoff_verified': False,
        'provider_execution_admitted': False,
        'append_authorized': False,
        'auto_retry_authorized': False,
        'resume_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }


def read_capsule_ledger_history(
    *, tenant_id: str, plan: Mapping[str, Any], related: Mapping[str, Any],
    accepted_actor_user_id: int,
) -> dict[str, Any]:
    """Bounded SELECT of all ledger rows for one Tenant; no app-side mutation.

    Excess rows or a missing prior event cannot be silently trimmed to the
    newest attempt. DB trigger installation and role hardening are NOT proved
    by the existence of this ORM reader.
    """
    if (
        not isinstance(tenant_id, str) or not tenant_id
        or not isinstance(plan, Mapping) or plan.get('tenant_id') != tenant_id
        or not isinstance(related, Mapping)
    ):
        raise ValueError('Capsule ledger reader requires the exact approved Tenant.')
    rows = (
        CapsuleHandoffLedgerEvent.query
        .filter_by(tenant_id=tenant_id)
        .order_by(CapsuleHandoffLedgerEvent.id.asc())
        .limit(_MAX_HISTORY + 1)
        .all()
    )
    if len(rows) > _MAX_HISTORY:
        raise ValueError('Multiple or overlong Capsule attempt ledgers require recovery.')
    return inspect_capsule_ledger_rows(
        plan=plan, related=related, accepted_actor_user_id=accepted_actor_user_id,
        rows=rows,
    )
