"""Explicit KAORI-controlled Native ownership transfer (#1048).

Only trusted #1047 successor consent authorizes entry. The Kubernetes API
remains authoritative; all patches are metadata-only UID/RV compare-and-swap.
No Released DB transition or provider spec change occurs here.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.native_handoff_dry_run import (
    _CONTENT_TYPE, _MARKER_KEYS, _dry_run_patch, _immutable_metadata,
    _read_resource, _resource_metadata, _retained_provider_metadata,
    _spec, _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_readback import (
    _latest_native_dry_run, verify_external_native_component,
)
from app.kubernetes.tenant.native_handoff_recovery import classify_native_handoff_component
from app.kubernetes.tenant.native_handoff_transfer_patch import build_native_successor_handoff_patch
from app.kubernetes.tenant.native_successor_acceptance import require_current_native_acceptance
from app.kubernetes.tenant.native_successor_identity import verify_native_successor_resource_authority
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan, _checked_recently, _plan_hash,
    latest_release_handoff_approval, latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import (
    _release_dependency_counts, review_tenant_release_preflight_committed,
)
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_native_handoff_execution'
_MAX_COMPONENTS = 100


def latest_native_handoff_execution(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def _component_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get('namespace') or ''), str(item.get('kind') or ''),
        str(item.get('name') or ''), str(item.get('uid') or ''),
    )


def _patch_native_live(core: Any, component: dict[str, Any], patch: list[dict[str, str]]) -> Any:
    """Dispatch ONLY approved JSON Patch; never replace/delete/create resource."""
    params = {'body': patch, '_content_type': _CONTENT_TYPE, '_request_timeout': 5}
    kind, name = component['kind'], component['name']
    namespace = component.get('namespace') or name
    if kind == 'Namespace':
        return core.patch_namespace(name=name, **params)
    if kind == 'ResourceQuota':
        return core.patch_namespaced_resource_quota(name=name, namespace=namespace, **params)
    if kind == 'LimitRange':
        return core.patch_namespaced_limit_range(name=name, namespace=namespace, **params)
    raise ValueError('Only canonical Native ownership components can be transferred.')


def _verify_patch_preview(*, before: Any, preview: Any, successor_owner: str) -> None:
    before_name, before_uid, _, before_labels = _resource_metadata(before)
    after_name, after_uid, _, after_labels = _resource_metadata(preview)
    if (
        (before_name, before_uid) != (after_name, after_uid)
        or after_labels.get('app.kubernetes.io/managed-by') != successor_owner
        or any(key in after_labels for key in _MARKER_KEYS if key != 'app.kubernetes.io/managed-by')
        or after_labels != {
            **{k: v for k, v in before_labels.items() if k not in _MARKER_KEYS},
            'app.kubernetes.io/managed-by': successor_owner,
        }
        or _spec(before) != _spec(preview)
        or _retained_provider_metadata(before) != _retained_provider_metadata(preview)
        or _immutable_metadata(before) != _immutable_metadata(preview)
    ):
        raise ValueError('Kubernetes admission dry-run would alter nonownership provider state.')


def _verify_current_plan(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Tenant, Cluster, list[dict[str, Any]]]:
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approval or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or plan.get('tenant_id') != tenant_id
        or plan.get('provider') != 'native_kubernetes'
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('approved_by') == plan.get('requested_by')
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
    ):
        raise ValueError('A current independently approved exact Native handoff plan is required.')
    accepted = require_current_native_acceptance(tenant_id=tenant_id, plan=plan, approval=approval)
    if accepted['accepted_by'] != actor_user_id:
        raise ValueError('The same authenticated successor actor must execute the accepted transfer.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Native Tenant authority differs from accepted transfer.')
    if any(type(v) is not int or v != 0 for v in _release_dependency_counts(tenant_id).values()):
        raise ValueError('Active Tenant access, credential or governance dependencies block handoff.')
    dry_run = _latest_native_dry_run(tenant_id)
    if (
        not dry_run or dry_run.get('plan_sha256') != plan_sha256
        or dry_run.get('status') != 'dry_run_passed'
        or not _checked_recently(dry_run.get('checked_at'))
        or dry_run.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or dry_run.get('provider_mutation_performed') is not False
        or dry_run.get('release_authorized') is not False
    ):
        raise ValueError('Current complete Native provider dry-run is required.')
    selected = [
        item for item in plan.get('handoff_components', [])
        if item.get('handoff') == 'external_acceptance_required'
    ]
    snapshots = dry_run.get('previewed_components')
    if (
        not isinstance(snapshots, list) or not 0 < len(snapshots) <= _MAX_COMPONENTS
        or dry_run.get('expected_component_count') != len(snapshots)
        or len(snapshots) != len(selected)
        or len({_component_key(i) for i in selected}) != len(selected)
        or len({_component_key(i) for i in snapshots}) != len(snapshots)
        or {_component_key(i) for i in snapshots} != {_component_key(i) for i in selected}
    ):
        raise ValueError('Native handoff dry-run and exact authorized inventory differ.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Canonical Native provider cluster is unavailable.')
    return plan, approval, accepted, tenant, cluster, snapshots


def execute_native_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    provider_token: str, confirmed: bool,
) -> dict[str, Any]:
    """Perform explicit guarded provider handoff; commit partial recovery evidence.

    Atomic database+Kubernetes transactions do not exist. Every component is
    re-read after its conditional patch and every failure blocks governance
    Release. A second call can resume within fresh plan/consent time only
    against the exact original dry-run inventory.
    """
    if not confirmed:
        raise ValueError('Explicit successor-authorized Native transfer confirmation is required.')
    plan, approval, accepted, tenant, cluster, snapshots = _verify_current_plan(
        tenant_id=tenant_id, actor_user_id=actor_user_id, plan_sha256=plan_sha256,
    )
    identity = verify_native_successor_resource_authority(
        cluster=cluster, plan=plan, provider_token=provider_token,
    )
    if (
        identity['provider_principal_uid'] != accepted['provider_principal_uid']
        or identity['provider_username'] != accepted['provider_username']
        or identity['successor_owner'] != accepted['successor_owner']
        or identity['scope_count'] != accepted['scope_count']
    ):
        raise ValueError('Successor Kubernetes identity/authorization changed after consent.')
    # The first provider transfer must be performed against a new exact preflight.
    # On a partial retry this will no longer match the original fingerprint;
    # recovery instead proves each component against the immutable dry-run.
    previous = latest_native_handoff_execution(tenant_id)
    if previous and previous.get('plan_sha256') == plan_sha256:
        if previous.get('status') == 'provider_handoff_verified':
            raise ValueError('Native provider handoff has already been verified.')
        if previous.get('status') not in ('partial_handoff_recovery_required',):
            raise ValueError('Previous handoff attempt needs operator recovery review.')
    else:
        fresh = review_tenant_release_preflight_committed(
            tenant_id=tenant_id, actor_user_id=actor_user_id,
        )
        _can_confirm_plan(fresh)
        if (
            fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
            or fresh.get('live_provider_identity') != plan.get('provider_identity')
            or fresh.get('handoff_components') != plan.get('handoff_components')
        ):
            raise ValueError('Provider resource inventory changed; restart handoff approval.')
    # Process Namespace last: quota/limits must be preserved before Namespace
    # management marker passes to the successor.
    order = {'ResourceQuota': 0, 'LimitRange': 1, 'Namespace': 2}
    components = sorted(snapshots, key=lambda item: (
        str(item.get('namespace') or ''), order.get(item['kind'], 99), item['name'],
    ))
    core = runtime_adapter.build_client(cluster).core_api()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for component in components:
        try:
            live = _read_resource(core, component)
            observation = classify_native_handoff_component(
                before=component, current=live,
                tenant_id=tenant_id, successor_owner=plan['successor_owner'],
            )
            if observation['state'] == 'pending_provider_transfer':
                patch = build_native_successor_handoff_patch(
                    component, live, tenant_id=tenant_id,
                    verified_successor_owner=plan['successor_owner'],
                )
                preview = _dry_run_patch(core, component, patch)
                _verify_patch_preview(
                    before=live, preview=preview, successor_owner=plan['successor_owner'],
                )
                _patch_native_live(core, component, patch)
                live = _read_resource(core, component)
            verified = verify_external_native_component(
                before=component, current=live, successor_owner=plan['successor_owner'],
            )
            results.append({**verified, 'scope_namespace': component.get('namespace')})
        except Exception as exc:
            # Provider exception content may contain credentials; record only
            # exception class and public resource kind/name.
            errors.append(f"{component.get('kind')}/{component.get('name')}: {type(exc).__name__}")
            break
    complete = not errors and len(results) == len(components)
    receipt = {
        'status': 'provider_handoff_verified' if complete else 'partial_handoff_recovery_required',
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'successor_owner': plan['successor_owner'],
        'provider_principal_uid': accepted['provider_principal_uid'],
        'verified_components': results,
        'expected_component_count': len(components),
        'verified_count': len(results),
        'errors': errors, 'checked_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': True,
        'provider_handoff_verified': complete,
        'external_successor_verified': True,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action=(
            'tenant.release.native_handoff_verified'
            if complete else 'tenant.release.native_handoff_recovery_required'
        ),
        summary=(
            'Verified metadata-only Native ownership transfer; governance finalization pending.'
            if complete else 'Incomplete Native handoff; explicit provider recovery required before Release.'
        ),
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
