"""Explicit read-only Capsule server dry-run entry point (#1229).

A Namespace metadata preview is *not* whole-scope handoff verification. The
Capsule CR, quota, limit, RBAC, and external consent remain authoritative;
nothing in this service authorizes live PATCH, Release or automatic retry.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_handoff_dry_run import preview_capsule_handoff_scope
from app.kubernetes.tenant.capsule_platform_admin_authority import (
    verify_capsule_provider_admin_authority,
)
from app.kubernetes.tenant.capsule_successor_acceptance import (
    require_current_capsule_acceptance,
)
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _checked_recently, _plan_hash, latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import (
    _release_dependency_counts, review_tenant_release_preflight_committed,
)
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_capsule_namespace_preview'


def preview_capsule_release_namespace_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Run real Kubernetes dryRun=All, never a live metadata transfer."""
    if not confirmed:
        raise ValueError('Explicit Capsule server-side preview confirmation is required.')
    require_platform_admin_actor(actor_user_id)
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approval or not isinstance(plan_sha256, str)
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or plan.get('tenant_id') != tenant_id
        or plan.get('provider') != 'capsule'
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
    ):
        raise ValueError('A fresh, independently reviewed Capsule plan is required.')
    accepted = require_current_capsule_acceptance(
        tenant_id=tenant_id, plan=plan, approval=approval,
    )
    if accepted.get('accepted_by') != actor_user_id:
        raise ValueError('Only the accepting Platform Admin may run this Capsule preview.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('The Capsule Tenant is no longer the approved Ready generation.')
    if any(type(count) is not int or count != 0 for count in _release_dependency_counts(tenant_id).values()):
        raise ValueError('Active Tenant dependencies block Capsule handoff preview.')

    # Provider GETs and the existing canonical Release inventory, not a
    # caller-supplied mapping, establish the scope used for dry-run.
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    if (
        fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
        or fresh.get('handoff_components') != plan.get('handoff_components')
        or fresh.get('dependency_counts') != plan.get('dependency_counts')
        or not isinstance(fresh.get('capsule_related_inventory'), dict)
        or fresh['capsule_related_inventory'].get('blockers')
        or fresh['capsule_related_inventory'].get('global_quota', {}).get('blockers')
        or fresh['capsule_related_inventory'].get('rbac_lineage', {}).get('blockers')
    ):
        raise ValueError('Capsule provider scope, dependencies or related-resource evidence changed; refresh the plan.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Approved Kubernetes cluster is unavailable.')
    authority = verify_capsule_provider_admin_authority(
        cluster=cluster, components=plan['handoff_components'],
    )
    if any(
        authority.get(key) != accepted.get(key)
        for key in ('provider_username', 'provider_groups', 'provider_credential_id', 'scope_count', 'scoped_resources')
    ):
        raise ValueError('Authenticated X.509 successor identity or scope changed.')
    provider = runtime_adapter.build_client(cluster)
    observed = preview_capsule_handoff_scope(
        custom=provider.custom_objects_api(), core=provider.core_api(),
        components=plan['handoff_components'], tenant_id=tenant_id,
        successor_owner=plan['successor_owner'],
    )
    # The helper is deliberately incomplete for quota/limit/RBAC. Never
    # promote a Namespace preview into executable handoff evidence.
    if (
        observed.get('status') != 'preview_observed_coverage_incomplete'
        or observed.get('dry_run_complete') is not False
        or observed.get('provider_handoff_verified') is not False
        or observed.get('provider_mutation_performed') is not False
        or observed.get('namespace_count') != len(plan['handoff_components']) - 1
    ):
        raise ValueError('Capsule preview did not return the expected fail-closed receipt.')
    receipt = {
        'status': 'namespace_server_dry_run_only',
        'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'actor_user_id': actor_user_id,
        'provider_credential_id': authority['provider_credential_id'],
        'namespace_count': observed['namespace_count'],
        'checked_at': datetime.now(UTC).isoformat(),
        'coverage': 'capsule_cr_and_namespaces_only',
        'quota_limit_rbac_dry_run_verified': False,
        'provider_execution_admitted': False,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.release.capsule_namespace_server_preview_observed',
        summary='Capsule Namespace server dry-run inspected; related-resource execution remains blocked.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
