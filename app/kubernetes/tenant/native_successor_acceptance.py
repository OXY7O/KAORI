"""Explicit provider-verified Native Tenant successor consent (#1047).

A Kubernetes bearer is transient and never stored. TokenReview authenticates
the token against the same cluster; SAR checks exact provider object scope.
The signed application request explicitly accepts that plan. KAORI SSO
identity is deliberately NOT assumed to equal the Kubernetes subject.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.native_successor_identity import verify_native_successor_resource_authority
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan,
    _checked_recently,
    _plan_hash,
    latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import review_tenant_release_preflight_committed
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_verified_successor_acceptance'


def latest_native_successor_acceptance(tenant_id: str) -> dict[str, Any] | None:
    row = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(row.metadata_json or {}) if row else None


def require_current_native_acceptance(
    *, tenant_id: str, plan: dict[str, Any], approval: dict[str, Any],
) -> dict[str, Any]:
    """Latest committed acceptance must match the one currently approved plan."""
    accepted = latest_native_successor_acceptance(tenant_id)
    if (
        not accepted
        or accepted.get('status') != 'verified_explicit_successor_acceptance'
        or accepted.get('tenant_id') != tenant_id
        or accepted.get('cluster_id') != plan.get('cluster_id')
        or accepted.get('generation') != plan.get('generation')
        or accepted.get('plan_sha256') != plan.get('plan_sha256')
        or accepted.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or accepted.get('provider_identity') != plan.get('provider_identity')
        or accepted.get('successor_owner') != plan.get('successor_owner')
        or accepted.get('reviewed_by') != approval.get('approved_by')
        or accepted.get('authenticated_provider') != 'kubernetes_token_review'
        or accepted.get('resource_authority_verified') is not True
        or accepted.get('consent_verified') is not True
        or accepted.get('secret_material_persisted') is not False
        or not _checked_recently(accepted.get('accepted_at'))
    ):
        raise ValueError('Fresh verified successor consent is required for this exact Native plan.')
    return accepted


def accept_native_successor_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    provider_token: str, confirmed: bool,
) -> dict[str, Any]:
    """Explicit acceptance from provider-authenticated successor token owner."""
    if not confirmed:
        raise ValueError('Successor must explicitly accept ownership of the exact provider inventory.')
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approval
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or plan.get('provider') != 'native_kubernetes'
        or plan.get('tenant_id') != tenant_id
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
        raise ValueError('A current independently reviewed Native plan is required before successor acceptance.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Native Tenant generation or provider authority changed.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Native Kubernetes cluster is unavailable.')
    # Verify immutable provider scope in the same call; preflight is the only
    # source of current UID/resourceVersion/fingerprint, not a typed label.
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    _can_confirm_plan(fresh)
    if (
        fresh.get('cluster_id') != plan.get('cluster_id')
        or fresh.get('generation') != plan.get('generation')
        or fresh.get('provider') != 'native_kubernetes'
        or fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
        or fresh.get('handoff_components') != plan.get('handoff_components')
    ):
        raise ValueError('Native provider inventory changed since approval; restart review.')
    result = verify_native_successor_resource_authority(
        cluster=cluster, plan=plan, provider_token=provider_token,
    )
    # Lock after provider reads/TokenReview/SAR, then recheck current plan and
    # commit once; another acceptance for this SHA is never overwritten.
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    current = latest_release_handoff_plan(tenant_id)
    acknowledged = latest_release_handoff_approval(tenant_id)
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.READY.value
        or locked.generation != plan.get('generation')
        or not current or current.get('plan_sha256') != plan_sha256
        or not acknowledged or acknowledged.get('plan_sha256') != plan_sha256
        or not _checked_recently(current.get('requested_at'))
        or not _checked_recently(acknowledged.get('approved_at'))
        or latest_native_successor_acceptance(tenant_id)
        and latest_native_successor_acceptance(tenant_id).get('plan_sha256') == plan_sha256
    ):
        raise ValueError('Native handoff acceptance was replaced, expired or already committed.')
    accepted = {
        'status': 'verified_explicit_successor_acceptance',
        'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_identity': plan['provider_identity'],
        'successor_owner': plan['successor_owner'],
        'reviewed_by': approval['approved_by'],
        'accepted_by': actor_user_id,
        'provider_username': result['provider_username'],
        'provider_principal_uid': result['provider_principal_uid'],
        'provider_groups_include_successor': True,
        'scope_count': result['scope_count'],
        'scoped_resources': result['scoped_resources'],
        'authenticated_provider': 'kubernetes_token_review',
        'authorization_source': 'kubernetes_subject_access_review',
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
        action='tenant.release.successor_identity_and_consent_verified',
        summary='External Kubernetes principal explicitly accepted exact Native handoff plan.',
        metadata_json=accepted,
    ))
    db.session.commit()
    return accepted
