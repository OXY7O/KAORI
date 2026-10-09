"""Non-authoritative external successor reference intake for Release handoff.

A supplied ticket/reference is a CLAIM, not external approval. This boundary
never authorizes transfer or Release and performs no provider mutation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan,
    _plan_hash,
    _valid_reference,
    latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import (
    review_tenant_release_preflight_committed,
)
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_successor_claim'


def latest_release_successor_claim(tenant_id: str) -> dict[str, Any] | None:
    row = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(row.metadata_json or {}) if row else None


def _require_matching_approval(
    *, tenant_id: str, plan_sha256: str,
    plan: dict[str, Any] | None, approval: dict[str, Any] | None,
) -> None:
    """A local second-operator acknowledgement is NOT successor acceptance."""
    if (
        not plan or not approval
        or len(plan_sha256) != 64
        or plan.get('tenant_id') != tenant_id
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('approved_by') == plan.get('requested_by')
        or not isinstance(approval.get('approved_by'), int)
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or approval.get('provider_handoff_verified') is not False
        or approval.get('release_authorized') is not False
    ):
        raise ValueError('The latest independently acknowledged handoff plan is required.')


def record_release_successor_claim_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    successor_reference: str,
) -> dict[str, Any]:
    """Commit an *unverified* external reference; never claim verified acceptance.

    No caller may use this receipt as permission for a live transfer or a
    Released lifecycle transition. A future trusted verification integration
    must be separately admitted and must compare current provider read-back.
    """
    reference = _valid_reference(successor_reference, name='External successor reference')
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    _require_matching_approval(
        tenant_id=tenant_id, plan_sha256=plan_sha256, plan=plan, approval=approval
    )
    assert plan is not None
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
        or tenant.provider_key != plan.get('provider')
    ):
        raise ValueError('Tenant lifecycle, generation or provider differs from the handoff plan.')

    # Explicit authorized provider observation; normal UI continues reading
    # only committed AuditEvent evidence. No Kubernetes write is performed.
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id
    )
    _can_confirm_plan(fresh)
    if (
        fresh.get('tenant_id') != tenant_id
        or fresh.get('cluster_id') != plan.get('cluster_id')
        or fresh.get('generation') != plan.get('generation')
        or fresh.get('provider') != plan.get('provider')
        or fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
    ):
        raise ValueError('Provider changed; refresh and independently reapprove handoff.')

    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.READY.value
        or locked.ownership_status != 'adopted'
        or locked.cluster_id != plan.get('cluster_id')
        or locked.generation != plan.get('generation')
        or locked.provider_key != plan.get('provider')
    ):
        raise ValueError('Tenant authority changed during successor reference review.')
    _require_matching_approval(
        tenant_id=tenant_id, plan_sha256=plan_sha256,
        plan=latest_release_handoff_plan(tenant_id),
        approval=latest_release_handoff_approval(tenant_id),
    )
    previous = latest_release_successor_claim(tenant_id)
    if previous and previous.get('plan_sha256') == plan_sha256:
        raise ValueError('A successor reference is already recorded for this plan.')

    receipt = {
        'tenant_id': tenant_id,
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'provider': plan['provider'],
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'successor_owner': plan['successor_owner'],
        'change_reference': plan['change_reference'],
        'successor_reference': reference,
        'recorded_by': actor_user_id,
        'recorded_at': datetime.now(UTC).isoformat(),
        'status': 'external_reference_unverified',
        'external_successor_verified': False,
        'provider_handoff_verified': False,
        'provider_mutation_performed': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.release.successor_reference_recorded',
        summary='Recorded unverified external successor reference; ownership unchanged.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
