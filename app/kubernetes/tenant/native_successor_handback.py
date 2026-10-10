"""Provider-authoritative explicit Native successor relinquishment (#1049).

No automatic Re-adoption: the successor first consents using TokenReview/SAR;
only exact successor ownership labels are removed with UID/RV conditional PATCH.
The canonical Discovery workflow then creates a NEW adopted generation.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.native_handoff_dry_run import (
    _CONTENT_TYPE, _MARKER_KEYS, _dry_run_patch, _label_path, _read_resource,
    _resource_metadata, _retained_provider_metadata, _spec, _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_readback import _latest_native_dry_run
from app.kubernetes.tenant.native_successor_identity import verify_native_successor_resource_authority
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_preflight import _release_dependency_counts
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import (
    Tenant, TenantEnvironment, TenantLifecycleStatus,
    TenantNamespace, TenantNamespaceProvisioningStatus,
)

_TARGET = 'kubernetes_tenant_verified_native_successor_handback'


def latest_native_successor_handback(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def _validate_released_component(
    *, item: dict[str, Any], live: Any, successor_owner: str,
) -> None:
    name, uid, _, labels = _resource_metadata(live)
    if (
        name != item.get('name') or uid != item.get('uid')
        or labels.get('app.kubernetes.io/managed-by') != successor_owner
        or any(key in labels for key in _MARKER_KEYS if key != 'app.kubernetes.io/managed-by')
        or item.get('spec_sha256') != _stable_sha256(_spec(live))
        or item.get('retained_metadata_sha256')
        != _stable_sha256(_retained_provider_metadata(live))
    ):
        raise ValueError('Released provider resource is no longer owned and preserved by the verified successor.')


def handback_native_successor_governance_committed(
    *, tenant_id: str, actor_user_id: int, release_plan_sha256: str,
    provider_token: str, confirmed: bool,
) -> dict[str, Any]:
    """Relinquish a verified successor-owned Native generation for future Discovery."""
    if not confirmed:
        raise ValueError('External successor must explicitly authorize governance handback.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or tenant.provider_key != 'native_kubernetes'
        or tenant.reconciliation_authority != 'native_kubernetes'
    ):
        raise ValueError('Only an existing Released Native Tenant may be handed back.')
    release = (tenant.provider_evidence_json or {}).get('release_governance') or {}
    if (
        release.get('status') != 'released'
        or release.get('release_mode') != 'managed_handoff'
        or release.get('provider_handoff_verified') is not True
        or release.get('tenant_id') != tenant_id
        or release.get('cluster_id') != tenant.cluster_id
        or release.get('generation') != tenant.generation
        or release.get('plan_sha256') != release_plan_sha256
        or not release.get('successor_owner')
    ):
        raise ValueError('Exact verified managed Native Release lineage is required.')
    if latest_native_successor_handback(tenant_id):
        raise ValueError('A handback attempt already exists; review provider recovery before retrying.')
    if any(type(v) is not int or v != 0 for v in _release_dependency_counts(tenant_id).values()):
        raise ValueError('Former KAORI dependencies unexpectedly remain active.')
    previous = _latest_native_dry_run(tenant_id)
    if (
        not previous or previous.get('plan_sha256') != release_plan_sha256
        or previous.get('handoff_fingerprint') != release.get('handoff_fingerprint')
        or previous.get('status') != 'dry_run_passed'
    ):
        raise ValueError('Original immutable Native handoff inventory is missing.')
    items = previous.get('previewed_components')
    if not isinstance(items, list) or not 0 < len(items) <= 100:
        raise ValueError('Original Native provider handoff scope is incomplete.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Canonical Native Kubernetes cluster is unavailable.')
    core = runtime_adapter.build_client(cluster).core_api()
    owner = str(release['successor_owner'])
    live_before = []
    keys: set[tuple[str, str, str]] = set()
    for item in items:
        key = (str(item.get('namespace') or ''), str(item.get('kind') or ''), str(item.get('name') or ''))
        if key in keys or item.get('kind') not in ('Namespace', 'ResourceQuota', 'LimitRange'):
            raise ValueError('Duplicated or unsupported Native handback scope.')
        keys.add(key)
        live = _read_resource(core, item)
        _validate_released_component(item=item, live=live, successor_owner=owner)
        live_before.append((item, live))
    # Construct an ephemeral *handback* scope from genuine successor-owned live
    # objects, not from fictional KAORI marker correlation.
    contract = {
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation, 'provider': 'native_kubernetes',
        'handoff_fingerprint': release['handoff_fingerprint'],
        'provider_identity': release['verified_components'],
        'successor_owner': owner, 'change_reference': release_plan_sha256,
        'requested_by': actor_user_id,
        'requested_at': datetime.now(UTC).isoformat(),
        'handoff_components': [
            {
                'kind': item['kind'], 'name': item['name'],
                'namespace': item.get('namespace') or item['name'],
                'uid': item['uid'],
                'resource_version': _resource_metadata(live)[2],
                'handoff': 'external_acceptance_required',
                'ownership': 'external_successor_correlated',
            }
            for item, live in live_before
        ],
    }
    contract['plan_sha256'] = _plan_hash(contract)
    authority = verify_native_successor_resource_authority(
        cluster=cluster, plan=contract, provider_token=provider_token,
        ownership_required='external_successor_correlated',
    )
    if authority.get('resource_authority_verified') is not True:
        raise ValueError('Authenticated successor Kubernetes handback authority was not proven.')
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or locked.generation != tenant.generation
        or latest_native_successor_handback(tenant_id)
    ):
        raise ValueError('Released Tenant handback was replaced or is already in progress.')
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.release.successor_handback_started',
        summary='Explicit authenticated external Native governance handback started.',
        metadata_json={
            'status': 'in_progress', 'tenant_id': tenant_id,
            'release_plan_sha256': release_plan_sha256,
            'provider_principal_uid': authority['provider_principal_uid'],
            'handback_plan_sha256': contract['plan_sha256'],
            'secret_material_persisted': False,
        },
    ))
    db.session.commit()
    verified: list[dict[str, Any]] = []
    errors: list[str] = []
    for item, before in live_before:
        try:
            # Refresh after the authentication exchange, then enforce original
            # CAS values. No automatic retry after partial provider mutation.
            current = _read_resource(core, item)
            if _resource_metadata(current) != _resource_metadata(before):
                raise ValueError('Provider resourceVersion or labels changed before handback.')
            patch = [
                {'op': 'test', 'path': '/metadata/uid', 'value': item['uid']},
                {'op': 'test', 'path': '/metadata/resourceVersion', 'value': _resource_metadata(before)[2]},
                {'op': 'test', 'path': _label_path('app.kubernetes.io/managed-by'), 'value': owner},
                {'op': 'remove', 'path': _label_path('app.kubernetes.io/managed-by')},
            ]
            preview = _dry_run_patch(core, item, patch)
            _, _, _, expected_labels = _resource_metadata(preview)
            before_labels = _resource_metadata(before)[3]
            if (
                expected_labels != {k: v for k, v in before_labels.items() if k != 'app.kubernetes.io/managed-by'}
                or _spec(preview) != _spec(before)
                or _retained_provider_metadata(preview) != _retained_provider_metadata(before)
            ):
                raise ValueError('Kubernetes admission would change non-ownership handback state.')
            params = {'body': patch, '_content_type': _CONTENT_TYPE, '_request_timeout': 5}
            kind, name = item['kind'], item['name']
            namespace = item.get('namespace') or name
            if kind == 'Namespace':
                core.patch_namespace(name=name, **params)
            elif kind == 'ResourceQuota':
                core.patch_namespaced_resource_quota(name=name, namespace=namespace, **params)
            else:
                core.patch_namespaced_limit_range(name=name, namespace=namespace, **params)
            current = _read_resource(core, item)
            _, uid, rv, labels = _resource_metadata(current)
            if (
                uid != item['uid'] or rv == _resource_metadata(before)[2]
                or 'app.kubernetes.io/managed-by' in labels
                or _spec(current) != _spec(before)
                or _retained_provider_metadata(current) != _retained_provider_metadata(before)
            ):
                raise ValueError('Provider post-handback read-back failed.')
            verified.append({
                'namespace': item.get('namespace'), 'kind': kind, 'name': name,
                'uid': uid, 'resource_version': rv,
                'spec_preserved': True, 'foreign_metadata_preserved': True,
            })
        except Exception as exc:
            errors.append(f"{item.get('kind')}/{item.get('name')}: {type(exc).__name__}")
            break
    complete = not errors and len(verified) == len(items)
    receipt = {
        'status': 'verified' if complete else 'partial_handback_recovery_required',
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'release_plan_sha256': release_plan_sha256,
        'handback_plan_sha256': contract['plan_sha256'],
        'successor_owner': owner,
        'provider_principal_uid': authority['provider_principal_uid'],
        'verified_components': verified,
        'verified_count': len(verified),
        'expected_component_count': len(items),
        'errors': errors,
        'provider_resource_deleted': False,
        'provider_specs_preserved': True if complete else False,
        'successor_handback_verified': complete,
        'adoption_automatic': False,
        'secret_material_persisted': False,
        'checked_at': datetime.now(UTC).isoformat(),
    }
    if complete:
        rows = (
            TenantNamespace.query.join(
                TenantEnvironment, TenantNamespace.tenant_environment_id == TenantEnvironment.id
            ).filter(TenantEnvironment.tenant_id == tenant_id)
            .order_by(TenantNamespace.id.asc()).with_for_update().all()
        )
        namespaces = {item['name']: item for item in verified if item['kind'] == 'Namespace'}
        if len(rows) != len(namespaces):
            raise ValueError('Handback Namespace coverage changed; recovery review required.')
        for row in rows:
            matching = namespaces.get(row.namespace)
            if (
                row.provisioning_status != TenantNamespaceProvisioningStatus.RELEASED.value
                or not matching or row.provider_reference != matching['uid']
            ):
                raise ValueError('Released Namespace identity changed during handback finalization.')
            evidence = dict(row.provisioning_evidence_json or {})
            evidence['handback_governance'] = {
                'status': 'verified', 'release_plan_sha256': release_plan_sha256,
                'provider_uid': matching['uid'],
                'resource_version': matching['resource_version'],
                'successor_owner': owner,
            }
            row.provisioning_evidence_json = evidence
        evidence = dict(tenant.provider_evidence_json or {})
        evidence['handback_governance'] = {
            'status': 'verified', 'release_plan_sha256': release_plan_sha256,
            'provider_uid': evidence.get('provider_uid'),
            'provider_resource_versions': {
                item['name']: item['resource_version']
                for item in verified if item['kind'] == 'Namespace'
            },
            'successor_owner': owner,
        }
        tenant.provider_evidence_json = evidence
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action=(
            'tenant.release.native_successor_handback_verified'
            if complete else 'tenant.release.native_successor_handback_recovery_required'
        ),
        summary=(
            'External Native owner relinquished metadata; fresh Discovery/Re-adopt is now eligible.'
            if complete else 'Incomplete Native successor handback; recovery required before Re-adopt.'
        ),
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
