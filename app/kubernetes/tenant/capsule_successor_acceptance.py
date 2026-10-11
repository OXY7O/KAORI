"""Independent, non-mutating Capsule successor acceptance under an exact Release plan.

Only the approved human consent is committed. Neither this action nor its
receipt executes Capsule ownership transfer, changes quotas or marks Released.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.capsule_platform_admin_authority import (
    _capsule_admin_scope, verify_capsule_provider_admin_authority,
)
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan, _checked_recently, _plan_hash,
    latest_release_handoff_approval, latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import review_tenant_release_preflight_committed
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_capsule_successor_acceptance'
_MODE = 'capsule_platform_admin_governed'


def latest_capsule_successor_acceptance(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def require_current_capsule_acceptance(
    *, tenant_id: str, plan: dict[str, Any], approval: dict[str, Any],
) -> dict[str, Any]:
    """Bind later executor consumers to only the current explicit Capsule receipt."""
    accepted = latest_capsule_successor_acceptance(tenant_id)
    if (
        not accepted or accepted.get('status') != 'platform_admin_handoff_accepted'
        or plan.get('provider') != 'capsule'
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('plan_sha256') != plan.get('plan_sha256')
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or type(approval.get('approved_by')) is not int
        or approval.get('approved_by') == plan.get('requested_by')
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
        or accepted.get('authority_mode') != _MODE
        or accepted.get('tenant_id') != tenant_id
        or accepted.get('cluster_id') != plan.get('cluster_id')
        or accepted.get('generation') != plan.get('generation')
        or accepted.get('plan_sha256') != plan.get('plan_sha256')
        or _plan_hash(plan) != plan.get('plan_sha256')
        or accepted.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or accepted.get('provider_identity') != plan.get('provider_identity')
        or accepted.get('successor_owner') != plan.get('successor_owner')
        or accepted.get('reviewed_by') != approval.get('approved_by')
        or type(accepted.get('accepted_by')) is not int
        or accepted.get('accepted_by') == plan.get('requested_by')
        or accepted.get('verified_provider_identity') is not True
        or accepted.get('resource_authority_verified') is not True
        or accepted.get('authenticated_provider') != 'kubernetes_self_subject_review'
        or accepted.get('authorization_source') != 'kubernetes_self_subject_access_review'
        or not str(accepted.get('provider_credential_id') or '').startswith('X509SHA256=')
        or len(str(accepted.get('provider_credential_id') or '')) <= len('X509SHA256=')
        or accepted.get('consent_verified') is not True
        or accepted.get('provider_mutation_performed') is not False
        or accepted.get('provider_handoff_verified') is not False
        or accepted.get('release_authorized') is not False
        or accepted.get('secret_material_persisted') is not False
        or not _checked_recently(accepted.get('accepted_at'))
    ):
        raise ValueError('Current independent Capsule successor acceptance is required.')
    scope = _capsule_admin_scope(plan.get('handoff_components'))
    if accepted.get('scoped_resources') != scope or accepted.get('scope_count') != len(scope):
        raise ValueError('Capsule successor provider scope changed.')
    return accepted


def _require_capsule_plan(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    plan: dict[str, Any] | None, approval: dict[str, Any] | None,
) -> None:
    if (
        not plan or not approval
        or not isinstance(plan_sha256, str) or len(plan_sha256) != 64
        or plan.get('tenant_id') != tenant_id
        or plan.get('provider') != 'capsule'
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('approved_by') == plan.get('requested_by')
        or type(approval.get('approved_by')) is not int
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or approval.get('provider_handoff_verified') is not False
        or approval.get('release_authorized') is not False
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
        or actor_user_id == plan.get('requested_by')
    ):
        raise ValueError('Current independently approved exact Capsule Release plan is required.')


def accept_capsule_successor_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Explicit Platform Admin acceptance using the registered X.509 provider connection."""
    if not confirmed:
        raise ValueError('Explicit Capsule Platform Admin acceptance is required.')
    require_platform_admin_actor(actor_user_id)
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    _require_capsule_plan(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
        plan_sha256=plan_sha256, plan=plan, approval=approval,
    )
    assert plan is not None and approval is not None
    scope = _capsule_admin_scope(plan.get('handoff_components'))
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.provider_key != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Capsule Tenant provider authority changed.')
    if not any(
        item['kind'] == 'CapsuleTenant' and item['name'] == tenant.provider_reference
        for item in scope
    ):
        raise ValueError('Capsule provider Tenant name is not in the exact approved scope.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Capsule Kubernetes connection is unavailable.')
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    _can_confirm_plan(fresh)
    if (
        fresh.get('tenant_id') != tenant_id
        or fresh.get('cluster_id') != plan.get('cluster_id')
        or fresh.get('generation') != plan.get('generation')
        or fresh.get('provider') != 'capsule'
        or fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
        or fresh.get('handoff_components') != plan.get('handoff_components')
    ):
        raise ValueError('Capsule provider scope changed after independent approval.')
    proof = verify_capsule_provider_admin_authority(
        cluster=cluster, components=plan['handoff_components'],
    )
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    current_plan = latest_release_handoff_plan(tenant_id)
    current_approval = latest_release_handoff_approval(tenant_id)
    previous = latest_capsule_successor_acceptance(tenant_id)
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.READY.value
        or locked.ownership_status != 'adopted'
        or locked.provider_key != 'capsule' or locked.provider_state != 'capsule'
        or locked.reconciliation_authority != 'capsule'
        or locked.cluster_id != plan.get('cluster_id')
        or locked.generation != plan.get('generation')
        or not current_plan or not current_approval
        or current_plan.get('handoff_components') != plan.get('handoff_components')
        or current_plan.get('provider_identity') != plan.get('provider_identity')
        or current_plan.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or _plan_hash(current_plan) != plan_sha256
        or not _checked_recently(current_plan.get('requested_at'))
        or current_approval.get('approved_by') != approval.get('approved_by')
        or not _checked_recently(current_approval.get('approved_at'))
        or (previous and previous.get('plan_sha256') == plan_sha256)
    ):
        raise ValueError('Capsule handoff was accepted, superseded or changed during verification.')
    _require_capsule_plan(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
        plan_sha256=plan_sha256, plan=current_plan, approval=current_approval,
    )
    accepted = {
        'status': 'platform_admin_handoff_accepted', 'authority_mode': _MODE,
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation, 'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_identity': plan['provider_identity'],
        'successor_owner': plan['successor_owner'],
        'reviewed_by': approval['approved_by'],
        'accepted_by': actor_user_id,
        'provider_username': proof['provider_username'],
        'provider_groups': proof['provider_groups'],
        'provider_credential_id': proof['provider_credential_id'],
        'scope_count': proof['scope_count'],
        'scoped_resources': proof['scoped_resources'],
        'authenticated_provider': proof['verification_source'],
        'authorization_source': proof['authorization_source'],
        'verified_provider_identity': True,
        'resource_authority_verified': True,
        'consent_verified': True,
        'accepted_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.release.capsule_platform_admin_handoff_accepted',
        summary=(
            'Approved exact Capsule scope after independent review and X.509 '
            'provider RBAC proof; no transfer performed.'
        ),
        metadata_json=accepted,
    ))
    db.session.commit()
    return accepted
