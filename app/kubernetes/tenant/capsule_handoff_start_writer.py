"""STAGED, DISABLED Capsule handoff START writer (#1229).

This module has NO route, scheduler, service registration or provider client.
Hard-coded source gate plus the current fail-closed Capsule admission prevent
every SQL write. A future separately authorized PR must explicitly replace
both blockers and prove the installed database guards + authenticated provider
authority. Merely importing or calling this module cannot start a transfer.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text

from app.extensions.db import db
from app.kubernetes.tenant.capsule_handoff_admission import assess_capsule_handoff_admission
from app.kubernetes.tenant.capsule_handoff_attempt_state import (
    _event_checksum, project_capsule_attempt_history,
)
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _plan_hash, latest_release_handoff_approval, latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint
from app.kubernetes.tenant.capsule_successor_acceptance import (
    require_current_capsule_acceptance,
)
from app.models.audit import AuditEvent
from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

# This constant is deliberately NOT configurable via env, feature flag or
# caller parameter. Removing it requires a separately reviewed source change.
_CAPSULE_START_WRITER_ENABLED = False
_LEGACY_EXECUTION_TARGET = 'kubernetes_tenant_release_capsule_handoff_execution'
_TRANSFER_DECISIONS = frozenset({
    'candidate_kaori_metadata_handoff_review',
    'explicit_kaori_metadata_handoff_review',
})


def build_capsule_start_candidate(
    *, tenant_id: str, actor_user_id: int, plan: Mapping[str, Any],
    related: Mapping[str, Any], attempt_id: str, event_at: datetime,
) -> dict[str, Any]:
    """Build a safe, canonical START event; NEVER authorize its persistence."""
    if (
        not isinstance(tenant_id, str) or not tenant_id
        or type(actor_user_id) is not int or actor_user_id <= 0
        or not isinstance(plan, Mapping) or not isinstance(related, Mapping)
        or plan.get('tenant_id') != tenant_id or plan.get('provider') != 'capsule'
        or not isinstance(plan.get('plan_sha256'), str)
        or _plan_hash(dict(plan)) != plan['plan_sha256']
        or handoff_fingerprint(plan.get('handoff_components')) != plan.get('handoff_fingerprint')
        or not isinstance(attempt_id, str)
        or not isinstance(event_at, datetime)
        or event_at.tzinfo is None or event_at.utcoffset() is None
    ):
        raise ValueError('Capsule START candidate requires an exact plan, actor and timestamp.')
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    count = sum(item['decision'] in _TRANSFER_DECISIONS for item in worklist['items'])
    if count < 1:
        raise ValueError('Capsule START cannot claim an empty ownership-transfer scope.')
    event: dict[str, Any] = {
        'contract_version': 'capsule-handoff-attempt/v1',
        'event_type': 'started', 'attempt_id': attempt_id,
        'sequence': 1, 'event_at': event_at.isoformat(),
        'tenant_id': tenant_id,
        'cluster_id': plan.get('cluster_id'), 'generation': plan.get('generation'),
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan.get('handoff_fingerprint'),
        'worklist_sha256': worklist['inventory_sha256'],
        'actor_user_id': actor_user_id,
        'previous_event_sha256': None, 'event_sha256': None,
        'outcome': 'unknown', 'readback_sha256': None,
        'expected_count': count,
        'observed_count': 0, 'pending_count': 0, 'transferred_count': 0,
        'ambiguous_count': 0,
        'provider_handoff_verified': False, 'release_authorized': False,
        'resume_authorized': False, 'auto_retry_authorized': False,
        'secret_material_persisted': False,
    }
    event['event_sha256'] = _event_checksum(event)
    # Enforce all canonical UUID, plan, count, timestamp and no-secret fields,
    # not only a valid-looking checksum supplied by a caller.
    project_capsule_attempt_history(
        plan=plan, related=related,
        accepted_actor_user_id=actor_user_id, events=[event],
    )
    return event


def _require_postgres_ledger_write_once_guards(session: Any) -> None:
    """Fail closed unless the current non-owner DB role has immutable guards.

    Called only inside a locked START transaction after a future explicit
    source un-gating. A status check is not a substitute for privileged DDL
    audit or recovery/backup durability verification.
    """
    expected = {
        'tr_capsule_ledger_guard_insert',
        'tr_capsule_ledger_deny_update',
        'tr_capsule_ledger_deny_delete',
        'tr_capsule_ledger_deny_truncate',
    }
    triggers = session.execute(text("""
        SELECT t.tgname, t.tgenabled
        FROM pg_trigger AS t
        WHERE t.tgrelid = 'capsule_handoff_ledger_events'::regclass
          AND NOT t.tgisinternal
    """)).all()
    observed = {
        name: mode for name, mode in triggers
        if isinstance(name, str) and isinstance(mode, str)
    }
    if (
        not expected.issubset(observed)
        or any(observed[name] not in ('O', 'A') for name in expected)
    ):
        raise ValueError('PostgreSQL Capsule ledger write-once guards are missing or disabled.')
    state = session.execute(text("""
        SELECT current_setting('fsync') AS fsync_setting,
               current_setting('synchronous_commit') AS sync_commit,
               current_setting('session_replication_role') AS replication_role,
               (SELECT rolsuper OR rolcreatedb OR rolcreaterole
                FROM pg_roles WHERE rolname = current_user) AS elevated,
               pg_get_userbyid(c.relowner) = current_user AS is_owner,
               pg_has_role(current_user, c.relowner, 'MEMBER') AS member_of_owner,
               has_table_privilege(current_user, c.oid, 'INSERT') AS may_insert,
               has_table_privilege(current_user, c.oid, 'UPDATE') AS may_update,
               has_table_privilege(current_user, c.oid, 'DELETE') AS may_delete,
               has_table_privilege(current_user, c.oid, 'TRUNCATE') AS may_truncate
        FROM pg_class AS c
        WHERE c.oid = 'capsule_handoff_ledger_events'::regclass
    """)).mappings().one()
    if (
        state['fsync_setting'] != 'on'
        or state['sync_commit'] not in ('on', 'remote_write', 'remote_apply')
        or state['replication_role'] != 'origin'
        or state['elevated'] is not False
        or state['is_owner'] is not False
        or state['member_of_owner'] is not False
        or state['may_insert'] is not True
        or state['may_update'] is not False
        or state['may_delete'] is not False
        or state['may_truncate'] is not False
    ):
        raise ValueError('PostgreSQL Capsule ledger role, trigger or WAL durability is not admitted.')


def commit_capsule_start_staged(
    *, tenant_id: str, actor_user_id: int, expected_plan_sha256: str,
    preflight: Mapping[str, Any], provider_authority: Mapping[str, Any],
    explicit_operator_confirmation: bool = False,
) -> dict[str, Any]:
    """Unregistered transactional START implementation, statically disabled.

    The transaction is intentionally designed to lock the canonical Tenant,
    re-fetch committed plan/approval/acceptance and detect ANY preceding
    ledger/legacy execution record before inserting exactly one START event.
    No provider calls are performed here. An acknowledged commit could only
    ever be a *pre-write* barrier, not authority to patch Kubernetes.

    The static gate and existing Capsule admission *both* forbid reaching the
    write path in the current repository. No user input can switch them on.
    """
    if not _CAPSULE_START_WRITER_ENABLED:
        raise PermissionError(
            'Capsule START writer is source-staged only; explicit code-level '
            'admission and a separate operator authorization are required.'
        )
    if (
        not isinstance(tenant_id, str) or not tenant_id
        or type(actor_user_id) is not int or actor_user_id <= 0
        or not isinstance(expected_plan_sha256, str)
        or len(expected_plan_sha256) != 64
        or not isinstance(preflight, Mapping)
        or not isinstance(provider_authority, Mapping)
        or explicit_operator_confirmation is not True
    ):
        raise ValueError('A valid authenticated Capsule START request is required.')
    # PostgreSQL-only write path: SQLite is supported as an inspectable schema
    # but NOT as a proven distributed-concurrency/handoff execution backend.
    session = db.session()
    try:
        if session.in_transaction():
            raise ValueError('Capsule START requires an isolated, freshly begun transaction.')
        with session.begin():
            if session.get_bind().dialect.name != 'postgresql':
                raise ValueError('Capsule START requires the admitted PostgreSQL ledger.')
            require_platform_admin_actor(actor_user_id)
            tenant = session.execute(
                select(Tenant).where(Tenant.id == tenant_id).with_for_update()
            ).scalar_one_or_none()
            if (
                tenant is None
                or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
                or tenant.provider_key != 'capsule'
                or tenant.provider_state != 'capsule'
                or tenant.reconciliation_authority != 'capsule'
                or tenant.ownership_status != 'adopted'
            ):
                raise ValueError('Capsule Tenant is no longer an adopted, ready handoff candidate.')
            _require_postgres_ledger_write_once_guards(session)
            if session.execute(
                select(CapsuleHandoffLedgerEvent.id)
                .where(CapsuleHandoffLedgerEvent.tenant_id == tenant_id).limit(1)
            ).first():
                raise ValueError('Capsule START cannot reuse or reset existing immutable history.')
            if session.execute(
                select(AuditEvent.id)
                .where(
                    AuditEvent.target_type == _LEGACY_EXECUTION_TARGET,
                    AuditEvent.target_id == tenant_id,
                ).limit(1)
            ).first():
                raise ValueError('Legacy Capsule attempt evidence requires independent recovery.')
            plan = latest_release_handoff_plan(tenant_id)
            approval = latest_release_handoff_approval(tenant_id)
            if (
                not isinstance(plan, dict)
                or not isinstance(approval, dict)
                or plan.get('plan_sha256') != expected_plan_sha256
                or plan.get('generation') != tenant.generation
                or plan.get('cluster_id') != tenant.cluster_id
            ):
                raise ValueError('The approved Capsule plan changed under the Tenant lock.')
            acceptance = require_current_capsule_acceptance(
                tenant_id=tenant_id, plan=plan, approval=approval,
            )
            if acceptance.get('accepted_by') != actor_user_id:
                raise ValueError('Capsule START actor differs from accepted X.509 successor.')
            assessment = assess_capsule_handoff_admission(
                tenant_id=tenant_id, actor_user_id=actor_user_id,
                plan=plan, approval=approval, acceptance=acceptance,
                preflight=preflight, provider_authority=provider_authority,
            )
            if (
                assessment.get('provider_execution_admitted') is not True
                or assessment.get('dry_run_admitted') is not True
                or assessment.get('controller_origin_verified') is not True
                or assessment.get('blockers')
            ):
                raise ValueError(
                    'Capsule START remains unadmitted: controller origin, '
                    'per-resource transfer and fresh provider authority require independent proof.'
                )
            related = preflight.get('capsule_related_inventory')
            event = build_capsule_start_candidate(
                tenant_id=tenant_id, actor_user_id=actor_user_id,
                plan=plan, related=related,
                attempt_id=str(uuid4()), event_at=datetime.now(UTC),
            )
            session.add(CapsuleHandoffLedgerEvent(
                **{field: event[field] for field in (
                    'tenant_id', 'cluster_id', 'generation', 'plan_sha256',
                    'handoff_fingerprint', 'worklist_sha256', 'attempt_id',
                    'sequence', 'event_type', 'actor_user_id',
                    'previous_event_sha256', 'event_sha256',
                )},
                event_at=datetime.fromisoformat(event['event_at']),
                event_json=event,
            ))
            session.flush()  # constraints checked, but STILL no durability
        # Leaving session.begin() commits START before anything could consume
        # this receipt. Its outcome is checked by a separate read transaction.
        stored = session.execute(
            select(CapsuleHandoffLedgerEvent).where(
                CapsuleHandoffLedgerEvent.tenant_id == tenant_id,
                CapsuleHandoffLedgerEvent.sequence == 1,
            )
        ).scalar_one()
        if (
            stored.event_sha256 != event['event_sha256']
            or stored.attempt_id != event['attempt_id']
            or stored.event_json != event
        ):
            raise ValueError('Capsule START commit acknowledgment differs from ledger read-back.')
        # No provider capability or mutation authority is returned by START.
        return {
            'status': 'start_recorded_provider_execution_still_blocked',
            'attempt_id': event['attempt_id'],
            'plan_sha256': plan['plan_sha256'],
            'event_sha256': event['event_sha256'],
            'start_commit_acknowledged': True,
            'database_storage_durability_proven': False,
            'schema_triggers_verified': False,
            'authenticated_provider_readback_verified': False,
            'provider_execution_admitted': False,
            'provider_mutation_performed': False,
            'provider_handoff_verified': False,
            'auto_retry_authorized': False,
            'resume_authorized': False,
            'release_authorized': False,
            'secret_material_persisted': False,
        }
    finally:
        session.close()
