"""Platform Admin Native governance acceptance using the existing KAORI X.509 kubeconfig.

A KAORI administrator's explicit decision and the Kubernetes connection's
actual credentials are separate authorities. Neither relies on an external
successor token, a fabricated IdP mapping, or typed ownership labels.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.native_platform_admin_authority import (
    require_platform_admin_actor, verify_native_provider_admin_authority,
)
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan, _checked_recently, _plan_hash,
    latest_release_handoff_approval, latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import review_tenant_release_preflight_committed
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_verified_successor_acceptance'
_MODE = 'platform_admin_governed'


def latest_native_successor_acceptance(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def require_current_native_acceptance(
    *, tenant_id: str, plan: dict[str, Any], approval: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed on historical bearer-token receipts and stale plan generation."""
    accepted = latest_native_successor_acceptance(tenant_id)
    if (
        not accepted or accepted.get('status') != 'platform_admin_handoff_accepted'
        or accepted.get('authority_mode') != _MODE
        or accepted.get('tenant_id') != tenant_id
        or accepted.get('cluster_id') != plan.get('cluster_id')
        or accepted.get('generation') != plan.get('generation')
        or accepted.get('plan_sha256') != plan.get('plan_sha256')
        or accepted.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or accepted.get('provider_identity') != plan.get('provider_identity')
        or accepted.get('successor_owner') != plan.get('successor_owner')
        or accepted.get('reviewed_by') != approval.get('approved_by')
        or accepted.get('verified_provider_identity') is not True
        or accepted.get('resource_authority_verified') is not True
        or accepted.get('consent_verified') is not True
        or accepted.get('secret_material_persisted') is not False
        or not _checked_recently(accepted.get('accepted_at'))
    ):
        raise ValueError('Current Platform Admin acceptance and provider proof are required.')
    return accepted


def accept_native_successor_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Record explicit *human* Platform Admin acceptance after live kubeconfig proof."""
    if not confirmed:
        raise ValueError('Explicit Platform Admin governance acceptance is required.')
    require_platform_admin_actor(actor_user_id)
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approval
        or plan.get('plan_sha256') != plan_sha256 or _plan_hash(plan) != plan_sha256
        or plan.get('tenant_id') != tenant_id or plan.get('provider') != 'native_kubernetes'
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('approved_by') == plan.get('requested_by')
        or type(approval.get('approved_by')) is not int
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
        or actor_user_id == plan.get('requested_by')
    ):
        raise ValueError('A fresh independent Native handoff approval is required.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Native Tenant provider authority changed.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Native Kubernetes cluster is unavailable.')
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    _can_confirm_plan(fresh)
    if (
        fresh.get('tenant_id') != tenant_id
        or fresh.get('cluster_id') != plan.get('cluster_id')
        or fresh.get('generation') != plan.get('generation')
        or fresh.get('provider') != 'native_kubernetes'
        or fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
        or fresh.get('handoff_components') != plan.get('handoff_components')
    ):
        raise ValueError('Provider inventory changed after the independently approved plan.')
    components = [
        dict(item) for item in plan['handoff_components']
        if item.get('handoff') == 'external_acceptance_required'
    ]
    proof = verify_native_provider_admin_authority(cluster=cluster, components=components)
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    current = latest_release_handoff_plan(tenant_id)
    acknowledged = latest_release_handoff_approval(tenant_id)
    previous = latest_native_successor_acceptance(tenant_id)
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.READY.value
        or locked.generation != plan.get('generation')
        or not current or current.get('plan_sha256') != plan_sha256
        or not acknowledged or acknowledged.get('plan_sha256') != plan_sha256
        or not _checked_recently(current.get('requested_at'))
        or not _checked_recently(acknowledged.get('approved_at'))
        or previous and previous.get('plan_sha256') == plan_sha256
    ):
        raise ValueError('Platform Admin acceptance is stale, already committed or superseded.')
    accepted = {
        'status': 'platform_admin_handoff_accepted', 'authority_mode': _MODE,
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation, 'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_identity': plan['provider_identity'],
        'successor_owner': plan['successor_owner'],
        'reviewed_by': acknowledged['approved_by'],
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
        'provider_handoff_verified': False,
        'provider_mutation_performed': False,
        'release_authorized': False, 'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.release.platform_admin_handoff_accepted',
        summary='Authorized Platform Admin accepted exact Native governance handoff after kubeconfig identity and RBAC checks.',
        metadata_json=accepted,
    ))
    db.session.commit()
    return accepted
