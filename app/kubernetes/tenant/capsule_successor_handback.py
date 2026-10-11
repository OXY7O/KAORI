"""Explicit Capsule successor metadata handback for fresh Re-Adopt (#1231).

Capsule CR and provider policy are never patched. A Released generation must
have a complete verified handoff receipt before a Platform Admin can remove
the exact successor ownership marker from transferred Namespace and related
resources. An immutable START audit record blocks every repeat attempt, even
after timeouts or partial provider changes. No automatic Adoption is performed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity, _labels, _successor, capsule_preservation_digest,
)
from app.kubernetes.tenant.capsule_handoff_live_patch import (
    _provider_methods, _provider_patch, _provider_read,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest, _get
from app.kubernetes.tenant.capsule_platform_admin_authority import (
    verify_capsule_provider_admin_authority, verify_capsule_related_admin_authority,
)
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import latest_release_handoff_plan
from app.kubernetes.tenant.release_preflight import _release_dependency_counts
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import (
    Tenant, TenantEnvironment, TenantNamespace,
    TenantLifecycleStatus, TenantNamespaceProvisioningStatus,
)

_TARGET = 'kubernetes_tenant_verified_capsule_successor_handback'
_KINDS = frozenset({'Namespace', 'ResourceQuota', 'LimitRange', 'RoleBinding'})


def latest_capsule_successor_handback(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def _capsule_handback_scope(
    *, release: dict[str, Any], tenant: Tenant,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Reject fabricated, missing or truncated provider preservation scope."""
    if (
        release.get('status') != 'released'
        or release.get('release_mode') != 'managed_handoff'
        or release.get('provider_handoff_verified') is not True
        or release.get('tenant_id') != tenant.id
        or release.get('cluster_id') != tenant.cluster_id
        or release.get('generation') != tenant.generation
        or release.get('provider') != 'capsule'
        or not isinstance(release.get('plan_sha256'), str)
        or not isinstance(release.get('handoff_fingerprint'), str)
    ):
        raise ValueError('Complete verified Capsule Released lineage is required.')
    owner = _successor(release.get('successor_owner'))
    rows = release.get('verified_components')
    if not isinstance(rows, list) or not 2 <= len(rows) <= 500:
        raise ValueError('Capsule handback requires complete bounded resource read-back.')
    cr = [r for r in rows if isinstance(r, dict) and r.get('kind') == 'CapsuleTenant']
    if len(cr) != 1 or cr[0].get('name') != tenant.provider_reference:
        raise ValueError('Capsule CR provider identity is not unique in Release evidence.')
    keys: set[tuple[str, str, str]] = set()
    targets: list[dict[str, Any]] = []
    observed_namespaces: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Capsule Release read-back contains a malformed object.')
        kind = row.get('kind')
        namespace = str(row.get('namespace') or '')
        name = row.get('name')
        uid, rv = row.get('uid'), row.get('resource_version')
        if (
            kind not in _KINDS | {'CapsuleTenant'}
            or not isinstance(name, str) or not name
            or not isinstance(uid, str) or not uid
            or not isinstance(rv, str) or not rv
            or (kind == 'Namespace' and namespace not in ('', name))
            or (kind in ('CapsuleTenant', 'Namespace') and namespace not in ('', name))
            or (kind not in ('CapsuleTenant', 'Namespace') and not namespace)
        ):
            raise ValueError('Capsule Released resource is missing exact scoped UID/RV.')
        key = (namespace if kind not in ('CapsuleTenant', 'Namespace') else '', kind, name)
        if key in keys:
            raise ValueError('Duplicate provider identity in Released Capsule handback scope.')
        keys.add(key)
        if kind == 'CapsuleTenant':
            if row.get('state') != 'preserved':
                raise ValueError('Capsule CR was not conclusively provider-preserved.')
        elif kind == 'Namespace':
            if row.get('state') != 'provider_markers_transferred':
                raise ValueError('Capsule Namespace does not have exact transferred ownership evidence.')
            observed_namespaces.add(name)
            targets.append({**row, 'namespace': name})
        elif row.get('state') == 'provider_markers_transferred':
            targets.append(row)
        elif row.get('state') != 'preserved':
            raise ValueError('Related Capsule provider resource has unknown ownership outcome.')
    if not targets or not observed_namespaces:
        raise ValueError('Capsule handback scope contains no verified Namespace to relinquish.')
    if any(
        row['namespace'] not in observed_namespaces
        for row in targets if row['kind'] != 'Namespace'
    ):
        raise ValueError('Related Capsule target belongs to a foreign Namespace.')
    targets.sort(key=lambda item: (
        item['namespace'],
        {'ResourceQuota': 0, 'LimitRange': 1, 'RoleBinding': 2, 'Namespace': 3}[item['kind']],
        item['name'],
    ))
    return cr[0], targets


def _handback_snapshot(*, before: Any, item: dict[str, Any], owner: str) -> dict[str, Any]:
    meta = _get(before, 'metadata')
    labels = _labels(before)
    # Compare the complete baseline *again* after dry-run, not a caller flag.
    name, uid, rv = _identity(before)
    if (
        (name, uid, rv) != (item['name'], item['uid'], item['resource_version'])
        or labels.get('app.kubernetes.io/managed-by') != owner
        or any(key.startswith('kaori.io/') for key in labels)
        or _get(meta, 'deletion_timestamp') is not None
        or _get(meta, 'deletionTimestamp') is not None
    ):
        raise ValueError('Capsule successor ownership or provider UID/RV changed since Release.')
    if item['kind'] == 'Namespace':
        preserved = capsule_preservation_digest(before)
    else:
        spec = (
            {'role_ref': _get(before, 'role_ref') or _get(before, 'roleRef'),
             'subjects': _get(before, 'subjects')}
            if item['kind'] == 'RoleBinding'
            else _get(before, 'spec')
        )
        if spec is None:
            raise ValueError('Capsule related provider policy was not supplied.')
        preserved = _digest({
            'policy': spec,
            'annotations': _get(meta, 'annotations') or {},
            'owner_references': _get(meta, 'owner_references') or _get(meta, 'ownerReferences') or [],
            'finalizers': _get(meta, 'finalizers') or [],
        })
    return {'labels': labels, 'preserved': preserved}


def _handback_patch(*, before: Any, item: dict[str, Any], owner: str) -> list[dict[str, Any]]:
    labels = _handback_snapshot(before=before, item=item, owner=owner)['labels']
    return [
        {'op': 'test', 'path': '/metadata/uid', 'value': item['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': item['resource_version']},
        {'op': 'test', 'path': '/metadata/labels', 'value': labels},
        {'op': 'remove', 'path': '/metadata/labels/app.kubernetes.io~1managed-by'},
    ]


def _verify_handback(
    *, before: Any, after: Any, item: dict[str, Any], owner: str,
    preview: bool,
) -> str:
    first = _handback_snapshot(before=before, item=item, owner=owner)
    _, uid, rv = _identity(after)
    if uid != item['uid'] or not rv or _identity(after)[0] != item['name']:
        raise ValueError('Capsule handback changed provider resource identity.')
    actual = _labels(after)
    if actual != {
        key: val for key, val in first['labels'].items()
        if key != 'app.kubernetes.io/managed-by'
    }:
        raise ValueError('Capsule handback would alter foreign or Capsule ownership labels.')
    if item['kind'] == 'Namespace':
        preserved = capsule_preservation_digest(after)
    else:
        meta = _get(after, 'metadata')
        spec = (
            {'role_ref': _get(after, 'role_ref') or _get(after, 'roleRef'),
             'subjects': _get(after, 'subjects')}
            if item['kind'] == 'RoleBinding'
            else _get(after, 'spec')
        )
        preserved = _digest({
            'policy': spec,
            'annotations': _get(meta, 'annotations') or {},
            'owner_references': _get(meta, 'owner_references') or _get(meta, 'ownerReferences') or [],
            'finalizers': _get(meta, 'finalizers') or [],
        })
    if preserved != first['preserved'] or (not preview and rv == item['resource_version']):
        raise ValueError('Capsule handback changed provider policy or did not commit metadata.')
    return rv


def handback_capsule_successor_governance_committed(
    *, tenant_id: str, actor_user_id: int, release_plan_sha256: str,
    confirmed: bool,
) -> dict[str, Any]:
    """One explicit, recovery-fenced successor handback; never auto-Re-Adopt."""
    if not confirmed:
        raise ValueError('Explicit Capsule successor handback confirmation is required.')
    require_platform_admin_actor(actor_user_id)
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or tenant.provider_key != 'capsule' or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.ownership_status != 'adopted'
    ):
        raise ValueError('Only a verified Released Capsule generation is eligible for handback.')
    evidence = tenant.provider_evidence_json or {}
    release = evidence.get('release_governance') or {}
    cr, targets = _capsule_handback_scope(release=release, tenant=tenant)
    if release['plan_sha256'] != release_plan_sha256 or latest_capsule_successor_handback(tenant_id):
        raise ValueError('Capsule handback plan changed or a previous attempt requires recovery.')
    if any(type(v) is not int or v != 0 for v in _release_dependency_counts(tenant_id).values()):
        raise ValueError('Released Tenant still has active governance dependencies.')
    previous = latest_release_handoff_plan(tenant_id)
    if (
        not previous or previous.get('plan_sha256') != release_plan_sha256
        or previous.get('handoff_fingerprint') != release['handoff_fingerprint']
    ):
        raise ValueError('Original independently accepted Capsule handoff plan is missing.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Capsule Kubernetes provider cluster is unavailable.')
    # The released CR is *never* rewritten. Require a current X.509 identity
    # and exact get/patch SAR for each released target before any mutation.
    current_components = [
        {**obj, 'authority': 'capsule', 'handoff': 'external_acceptance_required',
         'capsule_spec_sha256': next(
             (x.get('capsule_spec_sha256') for x in previous['handoff_components']
              if x.get('kind') == 'CapsuleTenant'), None
         )} if obj['kind'] == 'CapsuleTenant' else {
            **obj, 'namespace': obj['name'], 'authority': 'capsule',
            'handoff': 'external_acceptance_required',
        }
        for obj in [cr] + [
            row for row in targets if row['kind'] == 'Namespace'
        ]
    ]
    authority = verify_capsule_provider_admin_authority(
        cluster=cluster, components=current_components,
    )
    if (
        release.get('authority_mode') != 'platform_admin_governed'
        or authority.get('provider_username') != release.get('provider_username')
        or authority.get('provider_credential_id') != release.get('provider_credential_id')
    ):
        raise ValueError('Released Capsule X.509 successor identity has changed.')
    provider = runtime_adapter.build_client(cluster)
    related = [dict(row, decision='explicit_kaori_metadata_handoff_review')
               for row in targets if row['kind'] != 'Namespace']
    verify_capsule_related_admin_authority(provider=provider, candidates=related)
    custom = provider.custom_objects_api()
    live_cr = custom.get_cluster_custom_object(
        'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'],
        _request_timeout=5,
    )
    if _identity(live_cr) != (cr['name'], cr['uid'], cr['resource_version']):
        raise ValueError('Capsule CR changed before successor handback.')
    # Verify ALL selected sources before starting, not just the first patch.
    core, rbac = provider.core_api(), provider.rbac_authorization_api()
    source: list[tuple[dict[str, Any], Any]] = []
    for row in targets:
        read, _ = _provider_methods(core=core, rbac=rbac, kind=row['kind'])
        before = _provider_read(
            read, kind=row['kind'], name=row['name'], namespace=row['namespace'],
        )
        _handback_patch(before=before, item=row, owner=release['successor_owner'])
        source.append((row, before))
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or locked.generation != release['generation']
        or latest_capsule_successor_handback(tenant_id)
    ):
        raise ValueError('Capsule predecessor or handback attempt changed concurrently.')
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.release.capsule_successor_handback_started',
        summary='Capsule successor handback START; unknown outcomes require manual recovery.',
        metadata_json={
            'status': 'in_progress', 'tenant_id': tenant_id,
            'release_plan_sha256': release_plan_sha256,
            'provider_credential_id': authority['provider_credential_id'],
            'expected_component_count': len(targets),
            'provider_handoff_verified': False, 're_adopt_admitted': False,
            'auto_retry_authorized': False,
        },
    ))
    db.session.commit()  # START before any provider mutation.
    completed: list[dict[str, Any]] = []
    errors: list[str] = []
    for row, before in source:
        try:
            read, patch = _provider_methods(core=core, rbac=rbac, kind=row['kind'])
            patch_body = _handback_patch(
                before=before, item=row, owner=release['successor_owner'],
            )
            draft = _provider_patch(
                patch, kind=row['kind'], name=row['name'], namespace=row['namespace'],
                body=patch_body, dry_run=True,
            )
            _verify_handback(
                before=before, after=draft, item=row,
                owner=release['successor_owner'], preview=True,
            )
            fresh = _provider_read(
                read, kind=row['kind'], name=row['name'], namespace=row['namespace'],
            )
            if _identity(fresh) != _identity(before) or _labels(fresh) != _labels(before):
                raise ValueError('Capsule successor source changed between dry-run and live patch.')
            _provider_patch(
                patch, kind=row['kind'], name=row['name'], namespace=row['namespace'],
                body=patch_body, dry_run=False,
            )
            after = _provider_read(
                read, kind=row['kind'], name=row['name'], namespace=row['namespace'],
            )
            rv = _verify_handback(
                before=before, after=after, item=row,
                owner=release['successor_owner'], preview=False,
            )
            completed.append({
                'kind': row['kind'], 'namespace': row['namespace'],
                'name': row['name'], 'uid': row['uid'], 'resource_version': rv,
            })
        except Exception as exc:
            errors.append(f"{row['kind']}/{row['namespace']}/{row['name']}: {type(exc).__name__}")
            break  # NEVER automatic retry or continuation on uncertainty.
    success = not errors and len(completed) == len(targets)
    receipt = {
        'status': 'verified' if success else 'partial_handback_recovery_required',
        'tenant_id': tenant_id, 'release_plan_sha256': release_plan_sha256,
        'successor_owner': release['successor_owner'],
        'provider_username': authority['provider_username'],
        'provider_credential_id': authority['provider_credential_id'],
        'provider_specs_preserved': success,
        'verified_components': completed,
        'expected_component_count': len(targets),
        'verified_count': len(completed), 'errors': errors,
        'successor_handback_verified': success,
        'adoption_automatic': False,
        're_adopt_admitted': False,
        'auto_retry_authorized': False,
        'secret_material_persisted': False,
        'checked_at': datetime.now(UTC).isoformat(),
    }
    if success:
        locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
        latest = latest_capsule_successor_handback(tenant_id)
        if (
            locked is None or locked.lifecycle_status != TenantLifecycleStatus.RELEASED.value
            or locked.generation != release['generation']
            or not latest or latest.get('status') != 'in_progress'
            or latest.get('release_plan_sha256') != release_plan_sha256
        ):
            raise ValueError('Capsule handback finalization changed; recovery required.')
        rows = (
            TenantNamespace.query.join(
                TenantEnvironment, TenantNamespace.tenant_environment_id == TenantEnvironment.id,
            ).filter(TenantEnvironment.tenant_id == tenant_id)
            .order_by(TenantNamespace.id.asc()).with_for_update().all()
        )
        ns = {row['name']: row for row in completed if row['kind'] == 'Namespace'}
        if len(rows) != len(ns):
            raise ValueError('Capsule released Namespace history coverage is incomplete.')
        for item in rows:
            current = ns.get(item.namespace)
            if (
                item.provisioning_status != TenantNamespaceProvisioningStatus.RELEASED.value
                or not current or item.provider_reference != current['uid']
            ):
                raise ValueError('Capsule Released Namespace lineage changed during handback.')
            row_evidence = dict(item.provisioning_evidence_json or {})
            row_evidence['handback_governance'] = {
                'status': 'verified', 'release_plan_sha256': release_plan_sha256,
                'provider_uid': current['uid'],
                'resource_version': current['resource_version'],
                'successor_owner': release['successor_owner'],
            }
            item.provisioning_evidence_json = row_evidence
        tenant_evidence = dict(locked.provider_evidence_json or {})
        tenant_evidence['handback_governance'] = {
            'status': 'verified', 'release_plan_sha256': release_plan_sha256,
            'provider_uid': cr['uid'], 'resource_version': cr['resource_version'],
            'provider_resource_versions': {
                row['name']: row['resource_version']
                for row in completed if row['kind'] == 'Namespace'
            },
            'successor_owner': release['successor_owner'],
        }
        locked.provider_evidence_json = tenant_evidence
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action=(
            'tenant.release.capsule_successor_handback_verified'
            if success else 'tenant.release.capsule_successor_handback_recovery_required'
        ),
        summary=(
            'Capsule successor metadata handback verified; explicit fresh Discovery is required.'
            if success else 'Capsule provider handback partial or unknown; operator recovery required.'
        ),
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
