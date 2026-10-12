"""Explicit safe restart of an *expired* acknowledged Capsule G1 plan (#1228).

No Kubernetes mutation, plan auto-renewal, approval inheritance, or executor
replay. Never restart if any Capsule handoff attempt/START exists. The
PostgreSQL write-once ledger role/trigger posture is verified before trusting
the absence of an attempt: an absent ledger is NOT evidence of no execution.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.capsule_handoff_start_writer import (
    _require_postgres_ledger_write_once_guards,
)
from app.kubernetes.tenant.release_handoff_approval import (
    _PLAN_HASH_FIELDS, _PLAN_TARGET, _can_confirm_plan, _checked_recently,
    _complete_provider_snapshot, _plan_hash, latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import review_tenant_release_preflight_committed
from app.models.audit import AuditEvent
from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_ATTEMPT_TARGETS = (
    'kubernetes_tenant_release_capsule_handoff_execution',
    'kubernetes_tenant_release',
    'kubernetes_tenant_verified_capsule_successor_handback',
)


def _ensure_capsule_no_execution_history(tenant_id: str) -> None:
    """Require guarded, complete DB evidence of *zero* prior provider attempts.

    Both the dedicated immutable START ledger and legacy executor audit rows
    must be empty. Any loss of the ledger table, disabled triggers, elevated DB
    role or unreadable history aborts; a partial/unknown attempt cannot replay.
    """
    try:
        if db.session.get_bind().dialect.name != 'postgresql':
            raise ValueError('Capsule restart requires protected PostgreSQL START history.')
        _require_postgres_ledger_write_once_guards(db.session)
        started = (
            CapsuleHandoffLedgerEvent.query
            .filter_by(tenant_id=tenant_id).limit(1).first()
        )
        if started is not None:
            raise ValueError(
                'Capsule START/attempt history exists; independent recovery is '
                'required and G1 may not be restarted.'
            )
        for target in _ATTEMPT_TARGETS:
            if AuditEvent.query.filter_by(
                target_type=target, target_id=tenant_id,
            ).limit(1).first() is not None:
                raise ValueError(
                    'Capsule provider execution or Released history exists; '
                    'independent recovery is required.'
                )
    except SQLAlchemyError as exc:
        raise ValueError(
            'Capsule immutable START ledger could not be verified; '
            'install/verify database guards before restart.'
        ) from exc


def _assert_expired_acknowledged_capsule(
    *, tenant_id: str, actor_user_id: int,
    plan_sha256: str, plan: dict[str, Any] | None,
    approval: dict[str, Any] | None,
) -> None:
    if (
        not plan or not approval
        or plan.get('provider') != 'capsule'
        or plan.get('status') != 'pending_independent_approval'
        or plan.get('tenant_id') != tenant_id
        or not isinstance(plan_sha256, str) or len(plan_sha256) != 64
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or plan.get('requested_by') != actor_user_id
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('requested_by') != actor_user_id
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or type(approval.get('approved_by')) is not int
        or approval.get('approved_by') == actor_user_id
        or approval.get('provider_handoff_verified') is not False
        or approval.get('release_authorized') is not False
    ):
        raise ValueError(
            'Only the original requester may restart the exact independently '
            'acknowledged Capsule plan.'
        )
    for value in (plan.get('requested_at'), approval.get('approved_at')):
        try:
            timestamp = datetime.fromisoformat(str(value or ''))
        except ValueError as exc:
            raise ValueError('Capsule approval timestamp is malformed; recovery required.') from exc
        if timestamp.tzinfo is None or timestamp > datetime.now(UTC):
            raise ValueError('Capsule approval timestamp is not trustworthy.')
    if _checked_recently(plan['requested_at']) and _checked_recently(approval['approved_at']):
        raise ValueError('Capsule plan and independent approval are still current.')


def restart_expired_capsule_handoff_plan_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Prepare a fresh SHA only after expiration, a protected empty ledger,
    and an exact fresh authoritative provider scope and governance review.
    """
    if not confirmed:
        raise ValueError('Explicit Capsule expired-plan restart confirmation is required.')
    if type(actor_user_id) is not int or actor_user_id <= 0:
        raise ValueError('Authenticated original requester is required.')
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    _assert_expired_acknowledged_capsule(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
        plan_sha256=plan_sha256, plan=plan, approval=approval,
    )
    _ensure_capsule_no_execution_history(tenant_id)
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    _complete_provider_snapshot(fresh)
    _can_confirm_plan(fresh)
    assert plan is not None
    if (
        fresh.get('tenant_id') != tenant_id
        or fresh.get('cluster_id') != plan.get('cluster_id')
        or fresh.get('generation') != plan.get('generation')
        or fresh.get('provider') != 'capsule'
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
    ):
        raise ValueError(
            'Capsule provider object identity changed; separate authoritative '
            'scope/recovery review is required before restarting.'
        )
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.READY.value
        or locked.ownership_status != 'adopted'
        or locked.provider_key != 'capsule' or locked.provider_state != 'capsule'
        or locked.reconciliation_authority != 'capsule'
        or locked.cluster_id != plan.get('cluster_id')
        or locked.generation != plan.get('generation')
    ):
        raise ValueError('Capsule Tenant identity or lifecycle changed during restart.')
    current = latest_release_handoff_plan(tenant_id)
    decision = latest_release_handoff_approval(tenant_id)
    _assert_expired_acknowledged_capsule(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
        plan_sha256=plan_sha256, plan=current, approval=decision,
    )
    _ensure_capsule_no_execution_history(tenant_id)

    now = datetime.now(UTC).isoformat()
    contract = {
        'tenant_id': tenant_id,
        'cluster_id': fresh['cluster_id'],
        'generation': fresh['generation'],
        'provider': fresh['provider'],
        'handoff_fingerprint': fresh['handoff_fingerprint'],
        'provider_identity': fresh['live_provider_identity'],
        'successor_owner': plan['successor_owner'],
        'change_reference': plan['change_reference'],
        'requested_by': actor_user_id,
        'requested_at': now,
    }
    if set(contract) != set(_PLAN_HASH_FIELDS):
        raise ValueError('Capsule restart plan hash contract changed.')
    new_sha = _plan_hash(contract)
    if new_sha == plan_sha256:
        raise ValueError('Capsule restart requires a different immutable Plan SHA.')
    receipt = {
        **contract,
        'plan_sha256': new_sha,
        'status': 'pending_independent_approval',
        'handoff_components': fresh['handoff_components'],
        'dependency_counts': fresh['dependency_counts'],
        'blockers': fresh['blockers'],
        'supersedes_plan_sha256': plan_sha256,
        'restart_reason': 'approved_evidence_expired_without_provider_start',
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_PLAN_TARGET, target_id=tenant_id,
        action='tenant.release.capsule_expired_plan_restarted',
        summary='Restarted expired approved Capsule plan after protected zero-attempt proof and fresh provider preflight.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
