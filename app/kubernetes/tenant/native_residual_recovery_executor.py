"""Provider-authoritative, two-actor legacy Native profile-residue executor (#1128).

Not wired to a route or background job. No provider mutation is authorized by
source integration; enabling a trusted, permission-gated request entry point
requires separate human acceptance and lifting the Kubernetes mutation HOLD.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import (
    runtime_adapter,
)
from app.kubernetes.tenant.native_handoff_dry_run import (
    _CONTENT_TYPE,
    _dry_run_patch,
    _immutable_metadata,
    _metadata,
    _read,
    _read_resource,
    _resource_metadata,
    _spec,
    _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_executor import _patch_native_live
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.native_residual_recovery_assessment import (
    _RESIDUAL_LABEL,
    assess_legacy_native_profile_residue_readonly,
)
from app.kubernetes.tenant.native_residual_recovery_governance import (
    _EXECUTION_TARGET, _candidate_digest, _require_plan,
    latest_native_residual_cleanup_approval,
    latest_native_residual_cleanup_execution,
    require_authenticated_recovery_actor,
)
from app.kubernetes.tenant.release_handoff_approval import _checked_recently
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import (
    Tenant, TenantEnvironment, TenantLifecycleStatus, TenantNamespace,
    TenantNamespaceProvisioningStatus,
)


def build_legacy_profile_residue_patch(
    *, component: dict[str, Any], resource: Any,
    exact_profile_id: str,
) -> list[dict[str, str]]:
    """Pure UID/RV CAS patch for exactly one verified owned profile label."""
    name, uid, rv, labels = _resource_metadata(resource)
    if (
        name != component.get('name') or uid != component.get('uid')
        or rv != component.get('resource_version')
        or component.get('residual_label') != _RESIDUAL_LABEL
        or not exact_profile_id
        or labels.get(_RESIDUAL_LABEL) != exact_profile_id
        or any(key in labels for key in (
            'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
            'kaori.io/environment', 'kaori.io/profile-id',
            'kaori.io/tenant-generation',
        ))
    ):
        raise ValueError('Current provider identity/residual ownership differs from approved scope.')
    return [
        {'op': 'test', 'path': '/metadata/uid', 'value': uid},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': rv},
        {'op': 'test', 'path': '/metadata/labels/kaori.io~1resource-profile',
         'value': exact_profile_id},
        {'op': 'remove', 'path': '/metadata/labels/kaori.io~1resource-profile'},
    ]


def _nonprofile_metadata(resource: Any) -> dict[str, Any]:
    labels = _resource_metadata(resource)[3]
    return {
        'labels': {key: value for key, value in labels.items()
                   if key != _RESIDUAL_LABEL},
        'annotations': _read(_metadata(resource), 'annotations') or {},
        'immutable_metadata': _immutable_metadata(resource),
    }


def _unchanged_except_profile(*, before: Any, after: Any) -> bool:
    before_name, before_uid, _, before_labels = _resource_metadata(before)
    after_name, after_uid, _, after_labels = _resource_metadata(after)
    return bool(
        (before_name, before_uid) == (after_name, after_uid)
        and after_labels == {
            k: v for k, v in before_labels.items() if k != _RESIDUAL_LABEL
        }
        and _spec(after) == _spec(before)
        and _immutable_metadata(after) == _immutable_metadata(before)
        and (_read(_metadata(after), 'annotations') or {})
        == (_read(_metadata(before), 'annotations') or {})
    )


def _assert_live_request_actor(actor_user_id: int) -> None:
    """Never let a shell-passed arbitrary user ID serve as human approval."""
    require_authenticated_recovery_actor(actor_user_id)


def execute_native_residual_cleanup_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Execute approved CAS-only provider cleanup, append-only recovery ledger.

    A failed or partial attempt is deliberately not retried. Independent
    recovery adjudication is necessary before any new provider write.
    """
    if not confirmed:
        raise ValueError('Explicit provider metadata cleanup confirmation is required.')
    _assert_live_request_actor(actor_user_id)
    require_platform_admin_actor(actor_user_id)
    plan = _require_plan(tenant_id, plan_sha256)
    approval = latest_native_residual_cleanup_approval(tenant_id)
    if (
        not approval or approval.get('status') != 'approved_for_exact_metadata_cleanup'
        or approval.get('tenant_id') != tenant_id
        or approval.get('cluster_id') != plan.get('cluster_id')
        or approval.get('generation') != plan.get('generation')
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('candidate_digest_sha256') != plan.get('candidate_digest_sha256')
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('approved_by') != actor_user_id
        or actor_user_id == plan.get('requested_by')
        or not _checked_recently(approval.get('approved_at'))
        or latest_native_residual_cleanup_execution(tenant_id)
    ):
        raise ValueError('Fresh independent approved recovery scope is required.')

    assessed = assess_legacy_native_profile_residue_readonly(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    if (
        _candidate_digest(assessed) != plan.get('candidate_digest_sha256')
        or assessed.get('cluster_id') != plan.get('cluster_id')
        or assessed.get('release_plan_sha256') != plan.get('release_plan_sha256')
        or assessed.get('historical_handback_plan_sha256') != plan.get('handback_plan_sha256')
        or assessed.get('generation') != plan.get('generation')
    ):
        raise ValueError('Approved residual provider evidence changed before execution.')

    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or tenant.generation != plan['generation']
        or tenant.cluster_id != plan['cluster_id']
        or _require_plan(tenant_id, plan_sha256) != plan
        or latest_native_residual_cleanup_approval(tenant_id) != approval
        or latest_native_residual_cleanup_execution(tenant_id)
    ):
        raise ValueError('Concurrent recovery or Released generation changed before start.')
    started = {
        'status': 'in_progress', 'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id, 'generation': tenant.generation,
        'plan_sha256': plan_sha256,
        'candidate_digest_sha256': plan['candidate_digest_sha256'],
        'requested_by': plan['requested_by'],
        'approved_by': actor_user_id,
        'started_at': datetime.now(UTC).isoformat(),
        'expected_component_count': len(assessed['components']),
        'provider_mutation_performed': False,
        're_adopt_admitted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_EXECUTION_TARGET,
        target_id=tenant_id,
        action='tenant.release.native_residual_cleanup_started',
        summary='Authorized exact profile-label cleanup started; never auto Re-adopt.',
        metadata_json=started,
    ))
    db.session.commit()

    cluster = db.session.get(Cluster, plan['cluster_id'])
    components = sorted(
        assessed['components'],
        key=lambda x: (
            x['namespace'],
            {'ResourceQuota': 0, 'LimitRange': 1, 'Namespace': 2}[x['kind']],
            x['name'],
        ),
    )
    rows = (
        TenantNamespace.query.join(TenantEnvironment)
        .filter(TenantEnvironment.tenant_id == tenant_id).all()
    )
    profiles = {
        row.namespace: str(row.resource_profile.public_id)
        for row in rows
        if row.provisioning_status == TenantNamespaceProvisioningStatus.RELEASED.value
        and row.resource_profile is not None
    }
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    if cluster is None or len(profiles) != len(rows):
        errors.append('Missing Released cluster or Namespace Resource Profile lineage.')
    else:
        # Building the client may raise due to provider availability. A
        # started attempt must remain auditable and non-retryable even then.
        try:
            core = runtime_adapter.build_client(cluster).core_api()
        except Exception as exc:
            errors.append(f'provider_connection: {type(exc).__name__}')
        for component in (components if not errors else []):
            try:
                profile_id = profiles.get(component['namespace'])
                if not profile_id:
                    raise ValueError('Missing committed Namespace Resource Profile for cleanup.')
                before = _read_resource(core, component)
                _, _, old_rv, labels = _resource_metadata(before)
                if (
                    old_rv != component['resource_version']
                    or (labels.get(_RESIDUAL_LABEL) != profile_id
            if component['residual_label'] == _RESIDUAL_LABEL
            else _RESIDUAL_LABEL in labels)
                ):
                    raise ValueError('Provider resource changed since approved assessment.')
                changed = component['residual_label'] == _RESIDUAL_LABEL
                if changed:
                    patch = build_legacy_profile_residue_patch(
                        component=component, resource=before,
                        exact_profile_id=profile_id,
                    )
                    preview = _dry_run_patch(core, component, patch)
                    if not _unchanged_except_profile(before=before, after=preview):
                        raise ValueError('Provider dry-run would change nonowned metadata/spec.')
                    current = _read_resource(core, component)
                    if (
                        _resource_metadata(current) != _resource_metadata(before)
                        or _spec(current) != _spec(before)
                        or _immutable_metadata(current) != _immutable_metadata(before)
                        or (_read(_metadata(current), 'annotations') or {})
                        != (_read(_metadata(before), 'annotations') or {})
                    ):
                        raise ValueError('Provider drift before UID/RV conditional PATCH.')
                    _patch_native_live(core, component, patch)
                after = _read_resource(core, component)
                _, _, new_rv, _ = _resource_metadata(after)
                if not _unchanged_except_profile(before=before, after=after):
                    raise ValueError('Provider recovery read-back drifted.')
                if not changed and (
                    _resource_metadata(after) != _resource_metadata(before)
                ):
                    raise ValueError('Untouched resource changed unexpectedly.')
                if changed and new_rv == old_rv:
                    raise ValueError('Provider did not advance resourceVersion after patch.')
                results.append({
                    'kind': component['kind'], 'namespace': component['namespace'],
                    'name': component['name'], 'uid': component['uid'],
                    'previous_resource_version': old_rv, 'resource_version': new_rv,
                    'removed_label': _RESIDUAL_LABEL if changed else None,
                    'provider_spec_preserved': True,
                    'foreign_metadata_preserved': True,
                    'nonprofile_metadata_sha256': _stable_sha256(
                        _nonprofile_metadata(before)
                    ),
                    'provider_mutation_performed': changed,
                })
            except Exception as exc:
                errors.append(
                    f"{component['kind']}/{component['name']}: {type(exc).__name__}"
                )
                break

    # Recheck the entire complete resource scope before committing a success
    # receipt; provider writes do not imply a verified recovery.
    if not errors and len(results) == len(components):
        try:
            core = runtime_adapter.build_client(cluster).core_api()
            indexed = {
                (item['kind'], item['namespace'], item['name']): item
                for item in results
            }
            for component in components:
                item = indexed[
                    component['kind'], component['namespace'], component['name']
                ]
                current = _read_resource(core, component)
                _, uid, rv, labels = _resource_metadata(current)
                if (
                    uid != item['uid'] or rv != item['resource_version']
                    or any(key in labels for key in (
                        'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
                        'kaori.io/environment', 'kaori.io/profile-id',
                        'kaori.io/tenant-generation', _RESIDUAL_LABEL,
                    ))
                    or _stable_sha256(_spec(current))
                    != component['legacy_spec_sha256']
                    or _stable_sha256(_nonprofile_metadata(current))
                    != item['nonprofile_metadata_sha256']
                ):
                    raise ValueError('Final provider identity/spec/ownership differs.')
        except Exception as exc:
            errors.append(f'final_provider_readback: {type(exc).__name__}')

    complete = not errors and len(results) == len(components)
    receipt = {
        'status': 'verified' if complete else 'partial_recovery_required',
        'tenant_id': tenant_id, 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan_sha256,
        'release_plan_sha256': plan['release_plan_sha256'],
        'handback_plan_sha256': plan['handback_plan_sha256'],
        'successor_owner': plan['successor_owner'],
        'candidate_digest_sha256': plan['candidate_digest_sha256'],
        'requested_by': plan['requested_by'],
        'approved_by': actor_user_id,
        'verified_components': results,
        'verified_count': len(results),
        'expected_component_count': len(components),
        'errors': errors, 'completed_at': datetime.now(UTC).isoformat(),
        # On an unverified failure a write may have reached Kubernetes
        # even when no successful read-back exists; never assert False.
        'provider_mutation_performed': (
            True if any(item['provider_mutation_performed'] for item in results)
            else None if errors else False
        ),
        'provider_specs_preserved': complete,
        'historical_release_handback_unchanged': True,
        're_adopt_admitted': False,
    }
    receipt['receipt_sha256'] = _stable_sha256(receipt)

    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    latest = latest_native_residual_cleanup_execution(tenant_id)
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or locked.generation != plan['generation']
        or not latest or latest.get('status') != 'in_progress'
        or latest.get('plan_sha256') != plan_sha256
    ):
        raise ValueError('Concurrent recovery changed: in-progress receipt requires incident review.')

    if complete:
        namespaces = {
            result['name']: result for result in results if result['kind'] == 'Namespace'
        }
        if (
            len(namespaces) != len(rows)
            or any(
                row.namespace not in namespaces
                or row.provider_reference != namespaces[row.namespace]['uid']
                or row.provisioning_status != TenantNamespaceProvisioningStatus.RELEASED.value
                for row in rows
            )
        ):
            raise ValueError('Released Namespace lineage changed before recovery commit.')
        new_versions = {
            item['name']: item['resource_version']
            for item in results if item['kind'] == 'Namespace'
        }
        for row in rows:
            current = dict(row.provisioning_evidence_json or {})
            current['residual_recovery_governance'] = {
                'status': 'verified', 'release_plan_sha256': plan['release_plan_sha256'],
                'handback_plan_sha256': plan['handback_plan_sha256'],
                'provider_uid': row.provider_reference,
                'resource_version': new_versions[row.namespace],
                'receipt_sha256': receipt['receipt_sha256'],
                'provider_metadata_only_verified': True,
            }
            row.provisioning_evidence_json = current
        new_evidence = dict(locked.provider_evidence_json or {})
        original = new_evidence.get('handback_governance') or {}
        new_evidence['residual_recovery_governance'] = {
            'status': 'verified',
            'release_plan_sha256': plan['release_plan_sha256'],
            'handback_plan_sha256': plan['handback_plan_sha256'],
            'successor_owner': plan['successor_owner'],
            'provider_uid': original.get('provider_uid'),
            'provider_resource_versions': new_versions,
            'receipt_sha256': receipt['receipt_sha256'],
            'provider_metadata_only_verified': True,
        }
        locked.provider_evidence_json = new_evidence

    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_EXECUTION_TARGET,
        target_id=tenant_id,
        action=(
            'tenant.release.native_residual_cleanup_verified' if complete
            else 'tenant.release.native_residual_cleanup_recovery_required'
        ),
        summary=(
            'Verified exact Native profile-label cleanup with preserved provider specs.'
            if complete else 'Native residual cleanup incomplete; manual provider review required.'
        ),
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
