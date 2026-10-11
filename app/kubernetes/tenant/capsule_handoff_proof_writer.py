"""Source-staged Capsule audit + per-resource consent transactional writer (#1229).

NO endpoint, queue, reconciliation callback or executable provider operation.
Two independent source gates remain False and raise before a DB session,
key handling, human lookup, SQL INSERT or Kubernetes work can occur.

The unreachable SQL path documents one future serializable/fenced transaction
that inserts BOTH proof rows together, then checks committed read-back. A
successful SQL COMMIT is not proof of authenticated collector origin, human
consent, database backups or authority to patch/release Kubernetes resources.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text

from app.extensions.db import db
from app.kubernetes.tenant.capsule_handoff_collector_receipt import (
    inspect_capsule_collector_receipt,
)
from app.kubernetes.tenant.capsule_handoff_origin_consent_docket import (
    review_capsule_origin_consent_docket,
)
from app.kubernetes.tenant.capsule_handoff_resource_admission import (
    assess_capsule_resource_handoff_scope,
)
from app.kubernetes.tenant.capsule_handoff_resource_consent import (
    inspect_capsule_resource_consent,
)
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _checked_recently, _plan_hash, latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import latest_tenant_release_preflight
from app.kubernetes.tenant.capsule_successor_acceptance import (
    require_current_capsule_acceptance,
)
from app.models.audit import AuditEvent
from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent
from app.models.capsule_handoff_proof import (
    CapsuleHandoffAuditBatch, CapsuleHandoffResourceConsentRecord,
)
from app.models.tenant import Tenant, TenantLifecycleStatus

_CAPSULE_PROOF_WRITER_ENABLED = False
_AUTHENTICATED_PROVENANCE_AND_CONSENT_WRITER_ENABLED = False
_SHA = re.compile(r'[a-f0-9]{64}\Z')
_TABLE_GUARDS = {
    'capsule_handoff_audit_batches': frozenset({
        'tr_capsule_batch_deny_update', 'tr_capsule_batch_deny_delete',
        'tr_capsule_batch_deny_truncate',
    }),
    'capsule_handoff_resource_consent_records': frozenset({
        'tr_capsule_consent_deny_update', 'tr_capsule_consent_deny_delete',
        'tr_capsule_consent_deny_truncate',
    }),
}
_REQUIRED_CONSTRAINTS = frozenset({
    'uq_capsule_audit_batch_global_id',
    'uq_capsule_audit_batch_tenant_once',
    'uq_capsule_audit_batch_plan_once',
    'uq_capsule_audit_batch_full_scope',
    'ck_capsule_audit_batch_generation',
    'ck_capsule_audit_batch_digest_shape',
    'uq_capsule_resource_consent_tenant_once',
    'uq_capsule_resource_consent_plan_once',
    'uq_capsule_resource_consent_manifest',
    'fk_capsule_resource_consent_exact_audit_batch',
    'ck_capsule_resource_consent_target_count',
    'ck_capsule_resource_consent_independent_actors',
    'ck_capsule_resource_consent_digest_shape',
})


def _aware_iso(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Capsule proof evidence timestamp is missing.')
    try:
        date = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Capsule proof evidence timestamp is malformed.') from exc
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError('Capsule proof evidence must use timezone-aware timestamps.')
    return date.astimezone(UTC)


def build_capsule_proof_pair_candidate(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    approval: Mapping[str, Any], acceptance: Mapping[str, Any],
    claims: list[Mapping[str, Any]], collector_receipt: Mapping[str, Any],
    consent_manifest: Mapping[str, Any],
    trusted_collector_id: str, trusted_key_id: str,
    trusted_hmac_key: bytes | None,
) -> dict[str, Any]:
    """Pure normalized INSERT candidates; no trust promotion or persistence."""
    resource_report = assess_capsule_resource_handoff_scope(
        plan=plan, related=related,
    )
    docket = review_capsule_origin_consent_docket(
        plan=plan, related=related, approval=approval, acceptance=acceptance,
        claims=claims, collector_receipt=collector_receipt,
        consent_manifest=consent_manifest,
        trusted_collector_id=trusted_collector_id,
        trusted_key_id=trusted_key_id, trusted_hmac_key=trusted_hmac_key,
    )
    collector = inspect_capsule_collector_receipt(
        resource_report=resource_report, claims=claims, receipt=collector_receipt,
        trusted_collector_id=trusted_collector_id,
        trusted_key_id=trusted_key_id, trusted_hmac_key=trusted_hmac_key,
    )
    consent = inspect_capsule_resource_consent(
        plan=plan, resource_report=resource_report, approval=approval,
        acceptance=acceptance, manifest=consent_manifest,
    )
    if (
        docket['collector_receipt_sha256'] != collector['collector_receipt_sha256']
        or docket['resource_consent_manifest_sha256'] != consent['resource_consent_manifest_sha256']
        or consent['resource_count'] != resource_report['source_candidate_count']
        or consent['resource_count'] != docket['candidate_count']
        or not 1 <= consent['resource_count'] <= 330
        or plan.get('generation') != resource_report.get('generation')
        or type(plan.get('generation')) is not int
        or plan['generation'] <= 0
    ):
        raise ValueError('Capsule audit/consent source evidence is incomplete or changed.')
    batch = {
        'batch_id': collector['batch_id'],
        'tenant_id': resource_report['tenant_id'],
        'cluster_id': resource_report['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': resource_report['plan_sha256'],
        'worklist_sha256': resource_report['worklist_sha256'],
        'resource_review_sha256': resource_report['resource_review_sha256'],
        'claims_sha256': collector['claims_sha256'],
        'receipt_sha256': collector['collector_receipt_sha256'],
        'collector_id': collector['collector_id'],
        'key_id': collector['key_id'],
        'captured_at': _aware_iso(collector_receipt['captured_at']),
    }
    consent_row = {
        'tenant_id': resource_report['tenant_id'],
        'batch_id': collector['batch_id'],
        'plan_sha256': resource_report['plan_sha256'],
        'worklist_sha256': resource_report['worklist_sha256'],
        'resource_review_sha256': resource_report['resource_review_sha256'],
        'consent_manifest_sha256': consent['resource_consent_manifest_sha256'],
        'resource_scope_sha256': consent['resource_scope_sha256'],
        'target_count': consent['resource_count'],
        'requester_user_id': plan['requested_by'],
        'reviewer_user_id': approval['approved_by'],
        'successor_user_id': acceptance['accepted_by'],
        'accepted_at': _aware_iso(consent_manifest['accepted_at']),
    }
    if (
        any(type(consent_row[k]) is not int or consent_row[k] <= 0
            for k in ('requester_user_id', 'reviewer_user_id', 'successor_user_id'))
        or len({
            consent_row['requester_user_id'], consent_row['reviewer_user_id'],
            consent_row['successor_user_id'],
        }) != 3
    ):
        raise ValueError('Capsule proof requires exact, distinct current human actors.')
    return {
        'status': 'proof_insert_pair_candidate_unadmitted',
        'batch_values': batch,
        'consent_values': consent_row,
        'review_docket_sha256': docket['review_docket_sha256'],
        'append_authorized': False,
        'collector_source_authenticated': False,
        'human_consent_authenticated': False,
        'resource_specific_handoff_admitted': False,
        'provider_execution_admitted': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }


def _require_postgres_proof_storage_guards(session: Any) -> None:
    """Future PostgreSQL-only transactional fencing and least-privilege probe.

    A catalog SELECT cannot prove DBA-level protection or backup durability.
    """
    triggers = session.execute(text("""
        SELECT c.relname AS table_name, t.tgname AS trigger_name, t.tgenabled AS trigger_state
        FROM pg_trigger AS t
        JOIN pg_class AS c ON c.oid = t.tgrelid
        WHERE c.oid IN (
            'capsule_handoff_audit_batches'::regclass,
            'capsule_handoff_resource_consent_records'::regclass
        ) AND NOT t.tgisinternal
    """)).all()
    observed: dict[str, dict[str, str]] = {table: {} for table in _TABLE_GUARDS}
    for table, name, state in triggers:
        if table in observed and isinstance(name, str) and isinstance(state, str):
            observed[table][name] = state
    if any(
        not required.issubset(observed[table])
        or any(observed[table][name] not in ('O', 'A') for name in required)
        for table, required in _TABLE_GUARDS.items()
    ):
        raise ValueError('Capsule proof write-once trigger is missing or disabled.')
    constraints = session.execute(text("""
        SELECT con.conname
        FROM pg_constraint AS con
        WHERE con.conrelid IN (
            'capsule_handoff_audit_batches'::regclass,
            'capsule_handoff_resource_consent_records'::regclass
        )
    """)).scalars().all()
    if not _REQUIRED_CONSTRAINTS.issubset(set(constraints)):
        raise ValueError('Capsule proof uniqueness, actor or composite scope constraints are absent.')
    permissions = session.execute(text("""
        SELECT c.relname AS table_name,
               has_table_privilege(current_user, c.oid, 'SELECT') AS may_select,
               has_table_privilege(current_user, c.oid, 'INSERT') AS may_insert,
               has_table_privilege(current_user, c.oid, 'UPDATE') AS may_update,
               has_table_privilege(current_user, c.oid, 'DELETE') AS may_delete,
               has_table_privilege(current_user, c.oid, 'TRUNCATE') AS may_truncate,
               pg_get_userbyid(c.relowner) = current_user AS is_owner,
               pg_has_role(
                   (SELECT oid FROM pg_roles WHERE rolname = current_user),
                   c.relowner, 'MEMBER'
               ) AS member_of_owner,
               has_schema_privilege(current_user, c.relnamespace, 'CREATE') AS may_create
        FROM pg_class AS c
        WHERE c.oid IN (
            'capsule_handoff_audit_batches'::regclass,
            'capsule_handoff_resource_consent_records'::regclass
        )
    """)).mappings().all()
    if (
        len(permissions) != len(_TABLE_GUARDS)
        or {row['table_name'] for row in permissions} != set(_TABLE_GUARDS)
        or any(
            row['may_select'] is not True
            or row['may_insert'] is not True
            or any(row[key] is not False for key in (
                'may_update', 'may_delete', 'may_truncate',
                'is_owner', 'member_of_owner', 'may_create',
            ))
            for row in permissions
        )
    ):
        raise ValueError('Capsule proof writer requires restricted INSERT-only database role.')
    settings = session.execute(text("""
        SELECT current_setting('fsync') AS fsync,
               current_setting('synchronous_commit') AS synchronous_commit,
               current_setting('session_replication_role') AS replication_role,
               (SELECT rolsuper OR rolcreaterole OR rolcreatedb
                FROM pg_roles WHERE rolname = current_user) AS elevated
    """)).mappings().one()
    if (
        settings['fsync'] != 'on'
        or settings['synchronous_commit'] not in ('on', 'remote_write', 'remote_apply')
        or settings['replication_role'] != 'origin'
        or settings['elevated'] is not False
    ):
        raise ValueError('Capsule proof writer WAL, replication or role safety is unverified.')


def _stored_matches(stored: Any, expected: Mapping[str, Any]) -> bool:
    return stored is not None and all(getattr(stored, key, None) == value for key, value in expected.items())


def commit_capsule_proof_pair_staged(
    *, tenant_id: str, actor_user_id: int, expected_plan_sha256: str,
    claims: list[Mapping[str, Any]], collector_receipt: Mapping[str, Any],
    consent_manifest: Mapping[str, Any],
    trusted_collector_id: str, trusted_key_id: str,
    trusted_hmac_key: bytes | None,
    explicit_operator_confirmation: bool = False,
) -> dict[str, Any]:
    """Unregistered, statically disabled one-transaction batch+consent writer.

    CRITICAL: no caller argument, env flag or forged proof can activate this
    code. A future admission PR must also establish a trusted audit collector,
    durable anti-replay and independently authenticated human consent BEFORE
    lifting either hardcoded source gate. A commit is not provider authority.
    """
    if not _CAPSULE_PROOF_WRITER_ENABLED or not _AUTHENTICATED_PROVENANCE_AND_CONSENT_WRITER_ENABLED:
        raise PermissionError(
            'Capsule audit/consent proof writer is source-staged only; trusted '
            'collector and authenticated human admission remain blocked.'
        )
    if (
        not isinstance(tenant_id, str) or not tenant_id
        or type(actor_user_id) is not int or actor_user_id <= 0
        or not isinstance(expected_plan_sha256, str)
        or not _SHA.fullmatch(expected_plan_sha256)
        or explicit_operator_confirmation is not True
        or not isinstance(claims, list)
        or not isinstance(collector_receipt, Mapping)
        or not isinstance(consent_manifest, Mapping)
    ):
        raise ValueError('Capsule proof write requires exact confirmation, plan and scoped evidence.')
    session = db.session()
    try:
        if session.in_transaction():
            raise ValueError('Capsule proof write requires a clean, isolated database transaction.')
        with session.begin():
            if session.get_bind().dialect.name != 'postgresql':
                raise ValueError('Capsule proof writes require a separately admitted PostgreSQL engine.')
            require_platform_admin_actor(actor_user_id)
            tenant = session.execute(
                select(Tenant).where(Tenant.id == tenant_id).with_for_update()
            ).scalar_one_or_none()
            if (
                tenant is None
                or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
                or tenant.ownership_status != 'adopted'
                or tenant.provider_key != 'capsule'
                or tenant.provider_state != 'capsule'
                or tenant.reconciliation_authority != 'capsule'
            ):
                raise ValueError('Capsule proof Tenant changed or is no longer adopted/Ready.')
            _require_postgres_proof_storage_guards(session)
            # Never restrict history checks to the newest plan: one previous
            # Tenant record, even partial, requires separate human recovery.
            if session.execute(
                select(CapsuleHandoffAuditBatch.id)
                .where(CapsuleHandoffAuditBatch.tenant_id == tenant_id).limit(1)
            ).first() or session.execute(
                select(CapsuleHandoffResourceConsentRecord.id)
                .where(CapsuleHandoffResourceConsentRecord.tenant_id == tenant_id).limit(1)
            ).first():
                raise ValueError('Capsule proof history already exists: no replay, reset or auto-retry.')
            if session.execute(
                select(CapsuleHandoffLedgerEvent.id)
                .where(CapsuleHandoffLedgerEvent.tenant_id == tenant_id).limit(1)
            ).first() or session.execute(
                select(AuditEvent.id).where(
                    AuditEvent.target_type == 'kubernetes_tenant_release_capsule_handoff_execution',
                    AuditEvent.target_id == tenant_id,
                ).limit(1)
            ).first():
                raise ValueError('Prior Capsule START/legacy execution evidence forbids retroactive consent.')
            plan = latest_release_handoff_plan(tenant_id)
            approval = latest_release_handoff_approval(tenant_id)
            preflight = latest_tenant_release_preflight(tenant_id)
            if (
                not isinstance(plan, dict)
                or not isinstance(approval, dict)
                or not isinstance(preflight, dict)
                or plan.get('plan_sha256') != expected_plan_sha256
                or _plan_hash(plan) != expected_plan_sha256
                or plan.get('tenant_id') != tenant_id
                or plan.get('cluster_id') != tenant.cluster_id
                or plan.get('generation') != tenant.generation
                or preflight.get('tenant_id') != tenant_id
                or preflight.get('cluster_id') != tenant.cluster_id
                or preflight.get('generation') != tenant.generation
                or preflight.get('provider') != 'capsule'
                or preflight.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
                or preflight.get('handoff_components') != plan.get('handoff_components')
                or preflight.get('live_provider_identity') != plan.get('provider_identity')
                or not _checked_recently(preflight.get('checked_at'))
            ):
                raise ValueError('Capsule approved plan or preflight scope changed under the Tenant lock.')
            acceptance = require_current_capsule_acceptance(
                tenant_id=tenant_id, plan=plan, approval=approval,
            )
            if acceptance.get('accepted_by') != actor_user_id:
                raise ValueError('Capsule proof actor must equal the accepted X.509 successor.')
            related = preflight.get('capsule_related_inventory')
            pair = build_capsule_proof_pair_candidate(
                plan=plan, related=related, approval=approval,
                acceptance=acceptance, claims=claims,
                collector_receipt=collector_receipt,
                consent_manifest=consent_manifest,
                trusted_collector_id=trusted_collector_id,
                trusted_key_id=trusted_key_id, trusted_hmac_key=trusted_hmac_key,
            )
            session.add(CapsuleHandoffAuditBatch(**pair['batch_values']))
            session.flush()  # parent FK exists, but flush is NOT durability.
            session.add(CapsuleHandoffResourceConsentRecord(**pair['consent_values']))
            session.flush()
        # Context manager COMMIT is a single all-or-none database write.
        # A lost COMMIT acknowledgement is an UNKNOWN result: never retry.
        batch = session.execute(
            select(CapsuleHandoffAuditBatch)
            .where(CapsuleHandoffAuditBatch.tenant_id == tenant_id)
        ).scalar_one()
        consent = session.execute(
            select(CapsuleHandoffResourceConsentRecord)
            .where(CapsuleHandoffResourceConsentRecord.tenant_id == tenant_id)
        ).scalar_one()
        if (
            not _stored_matches(batch, pair['batch_values'])
            or not _stored_matches(consent, pair['consent_values'])
        ):
            raise ValueError('Committed Capsule proof differs from canonical batch/consent read-back.')
        return {
            'status': 'proof_pair_commit_acknowledged_origin_and_provider_still_unverified',
            'tenant_id': tenant_id,
            'plan_sha256': expected_plan_sha256,
            'batch_id': pair['batch_values']['batch_id'],
            'audit_batch_receipt_sha256': pair['batch_values']['receipt_sha256'],
            'consent_manifest_sha256': pair['consent_values']['consent_manifest_sha256'],
            'transaction_commit_acknowledged': True,
            'database_durability_independently_verified': False,
            'db_write_once_triggers_operationally_verified': False,
            'apiserver_audit_integrity_verified': False,
            'controller_origin_attested': False,
            'authenticated_human_consent_proven': False,
            'provider_execution_admitted': False,
            'provider_mutation_performed': False,
            'auto_retry_authorized': False,
            'resume_authorized': False,
            'release_authorized': False,
            'secret_material_persisted': False,
        }
    finally:
        session.close()
