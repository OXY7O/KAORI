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
from app.kubernetes.tenant.capsule_handoff_dry_run import (
    preview_capsule_handoff_scope, preview_capsule_related_handoff_with_provider,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _get, _strings, classify_capsule_related_resource,
)
from app.kubernetes.tenant.capsule_handoff_contract import _RELATED_TRANSFER_LABELS
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.capsule_platform_admin_authority import (
    verify_capsule_provider_admin_authority, verify_capsule_related_admin_authority,
)
from app.kubernetes.tenant.capsule_successor_acceptance import (
    require_current_capsule_acceptance,
)
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _capsule_g1_only_origin_obligation, _checked_recently, _plan_hash,
    latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import (
    _release_dependency_counts, review_tenant_release_preflight_committed,
)
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_capsule_namespace_preview'


def _preview_related_provider_scope(
    *, provider: Any, plan: dict[str, Any], related: dict[str, Any],
) -> dict[str, int]:
    """Read every related object; dry-run only exact KAORI-correlated candidates.

    Approved label keys are *proposed from current provider state for preview*,
    NOT independently authenticated per-object transfer consent. No executor
    may treat these preview-derived keys as a mutation authorization.
    """
    work = build_capsule_handoff_worklist(plan=plan, related=related)
    if any(
        item['decision'] in ('operator_origin_investigation', 'operator_selector_investigation')
        for item in work['items']
    ):
        raise ValueError('Capsule scope contains ambiguous origin or shared quota selectors.')
    cr = next(item for item in plan['handoff_components'] if item['kind'] == 'CapsuleTenant')
    observations = {
        (item['namespace'], item['kind'], item['name']): item
        for item in related['resources']
    }
    approved_candidates = [
        item for item in work['items']
        if item['kind'] in ('ResourceQuota', 'LimitRange', 'RoleBinding')
        and item['decision'] == 'explicit_kaori_metadata_handoff_review'
    ]
    # Actor's current Kubernetes SAR, not an application checkbox or label,
    # must allow both exact-resource GET and dry-run PATCH.
    verify_capsule_related_admin_authority(
        provider=provider, candidates=approved_candidates,
    )
    core, rbac = provider.core_api(), provider.rbac_authorization_api()
    api_methods = {
        'ResourceQuota': (core.read_namespaced_resource_quota, core),
        'LimitRange': (core.read_namespaced_limit_range, core),
        'RoleBinding': (rbac.read_namespaced_role_binding, rbac),
    }
    previews = 0
    preserved = 0
    for item in work['items']:
        kind = item['kind']
        if kind not in api_methods:
            continue
        key = (item['namespace'], kind, item['name'])
        observed = observations[key]
        read, _ = api_methods[kind]
        before = read(name=item['name'], namespace=item['namespace'], _request_timeout=5)
        row, problems = classify_capsule_related_resource(
            resource=before, kind=kind, namespace=item['namespace'],
            tenant_id=plan['tenant_id'], capsule_name=cr['name'], capsule_uid=cr['uid'],
        )
        if row != observed:
            raise ValueError('Capsule related resource differs from committed source LIST.')
        if item['decision'] == 'explicit_kaori_metadata_handoff_review':
            allowed = {
                f"Capsule {kind}/{item['namespace']}/{item['name']} "
                "retains KAORI provider controls requiring separately admitted handoff."
            }
            if set(problems) != allowed:
                raise ValueError('Capsule resource has unexpected ownership or RBAC problems.')
            meta = _get(before, 'metadata')
            labels = _strings(_get(meta, 'labels'), label='labels')
            proposed_keys = sorted(key for key in labels if key in _RELATED_TRANSFER_LABELS)
            response = preview_capsule_related_handoff_with_provider(
                core=core, rbac=rbac, record=observed, namespace=item['namespace'],
                tenant_id=plan['tenant_id'], capsule_name=cr['name'], capsule_uid=cr['uid'],
                successor_owner=plan['successor_owner'], approved_label_keys=proposed_keys,
            )
            if (
                response.get('status') != 'server_dry_run_shape_observed_not_execution_admitted'
                or response.get('live_resource_unchanged') is not True
                or response.get('provider_mutation_performed') is not False
                or response.get('provider_execution_admitted') is not False
            ):
                raise ValueError('Capsule related dry-run returned a noncanonical receipt.')
            previews += 1
        elif item['decision'] == 'preserve_foreign_provider_control' and not problems:
            preserved += 1
        else:
            raise ValueError('Capsule related object cannot be preserved or previewed.')
    if previews != len(approved_candidates) or preserved + previews != len(observations):
        raise ValueError('Capsule related dry-run omitted a source object.')
    return {'related_preview_count': previews, 'related_preserved_count': preserved}


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
        or not isinstance(fresh['capsule_related_inventory'].get('blockers'), list)
        or any(
            not _capsule_g1_only_origin_obligation(fresh, warning)
            for warning in fresh['capsule_related_inventory']['blockers']
        )
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
    # Prove the source covers every namespaced quota, limit and RoleBinding.
    # These are previews only; consent/provenance for *live* PATCH is missing.
    related_counts = _preview_related_provider_scope(
        provider=provider, plan=plan,
        related=fresh['capsule_related_inventory'],
    )
    # Provider-owned CR, foreign objects and cluster-scoped GlobalResourceQuota
    # are preserved by a second complete authoritative preflight. Any changed
    # LIST, RBAC lineage, UID/RV or scope fails closed, not a partial PASS.
    after = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    if any(after.get(field) != fresh.get(field) for field in (
        'live_provider_identity', 'handoff_fingerprint',
        'handoff_components', 'capsule_related_inventory', 'dependency_counts',
    )):
        raise ValueError('Capsule provider changed during complete-scope dry-run; refresh Release preflight.')
    complete_worklist = build_capsule_handoff_worklist(
        plan=plan, related=fresh['capsule_related_inventory'],
    )
    transfer_items = [
        {
            'kind': item['kind'], 'namespace': item['namespace'],
            'name': item['name'], 'uid': item['uid'],
            'resource_version': item['resource_version'],
        }
        for item in complete_worklist['items']
        if item['decision'] in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        )
    ]
    receipt = {
        'status': 'complete_scope_server_dry_run_only',
        'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'source_worklist_sha256': complete_worklist['inventory_sha256'],
        'transfer_items': transfer_items,
        'actor_user_id': actor_user_id,
        'provider_credential_id': authority['provider_credential_id'],
        'namespace_count': observed['namespace_count'],
        **related_counts,
        'whole_scope_source_unchanged': True,
        'checked_at': datetime.now(UTC).isoformat(),
        'coverage': 'capsule_cr_namespaces_related_controls_shared_quota_readback',
        'related_server_dry_run_preview_completed': True,
        'related_mutation_consent_verified': False,
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
        action='tenant.release.capsule_complete_scope_server_preview_observed',
        summary='Capsule complete-scope metadata dry-run observed; live provider handoff remains blocked.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
