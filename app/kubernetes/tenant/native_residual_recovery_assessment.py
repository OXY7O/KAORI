"""Read-only admission assessment for legacy Native post-Handback profile residue.

Issue #1129. This module contains no provider PATCH, AuditEvent INSERT,
Released/Handback status mutation, or new Re-adoption admission shortcut.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import (
    runtime_adapter,
)
from app.kubernetes.tenant.native_handoff_dry_run import (
    _immutable_metadata,
    _metadata,
    _read,
    _read_resource,
    _resource_metadata,
    _spec,
    _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_readback import _latest_native_dry_run
from app.kubernetes.tenant.native_platform_admin_authority import (
    require_platform_admin_actor,
    verify_native_provider_admin_authority,
)
from app.kubernetes.tenant.native_successor_handback import latest_native_successor_handback
from app.kubernetes.tenant.release_preflight import _release_dependency_counts
from app.models import Cluster
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
)

# Exactly the historical pre-#1126 owner label taxonomy. The old SHA-bound
# dry-run counted resource-profile as foreign metadata. It must NOT be
# recomputed using today's _MARKER_KEYS, otherwise history changes meaning.
_LEGACY_OWNER_MARKERS = frozenset({
    'app.kubernetes.io/managed-by',
    'kaori.io/tenant-id',
    'kaori.io/environment',
    'kaori.io/profile-id',
})
_RESIDUAL_LABEL = 'kaori.io/resource-profile'
_ONLY_RESIDUE_ALLOWED = frozenset({_RESIDUAL_LABEL})
_GOVERNED_LABELS = frozenset({
    'app.kubernetes.io/managed-by',
    'kaori.io/tenant-id',
    'kaori.io/environment',
    'kaori.io/resource-profile',
    'kaori.io/tenant-generation',
    'kaori.io/profile-id',
})
_SUPPORTED = frozenset({'Namespace', 'ResourceQuota', 'LimitRange'})


def _scope_key(item: Mapping[str, Any]) -> tuple[str, str, str, str]:
    kind = str(item.get('kind') or '')
    name = str(item.get('name') or '')
    namespace = str(item.get('namespace') or name)
    uid = str(item.get('uid') or '')
    if (
        kind not in _SUPPORTED or not name or not namespace or not uid
        or (kind == 'Namespace' and name != namespace)
    ):
        raise ValueError('Legacy Native recovery evidence has an invalid resource identity.')
    return kind, namespace, name, uid


def _index_scope(
    values: Any, *, title: str,
) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    if not isinstance(values, list) or not 0 < len(values) <= 100:
        raise ValueError(f'{title} has missing or unbounded resource coverage.')
    result = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError(f'{title} contains malformed provider identity.')
        key = _scope_key(value)
        if key in result:
            raise ValueError(f'{title} contains duplicate provider identity.')
        result[key] = value
    return result


def _legacy_retained_metadata(resource: Any) -> dict[str, Any]:
    """Reconstruct only the original historical foreign-label SHA recipe."""
    labels = _resource_metadata(resource)[3]
    return {
        'foreign_labels': {
            key: value for key, value in labels.items()
            if key not in _LEGACY_OWNER_MARKERS
        },
        'annotations': _read(_metadata(resource), 'annotations') or {},
        'immutable_metadata': _immutable_metadata(resource),
    }


def inspect_legacy_profile_residue_component(
    *, preview: Mapping[str, Any], handback: Mapping[str, Any],
    live: Any, profile_public_id: str,
) -> dict[str, Any]:
    """Evaluate one exact provider component; never authorize a PATCH.

    No legacy receipt fields are edited. A positive result is an observation
    requiring a separate, approved recovery design, not a mutation token.
    """
    key = _scope_key(preview)
    if (
        _scope_key(handback) != key
        or preview.get('operation') != 'metadata_only_json_patch_dry_run'
        or preview.get('dry_run') is not True
        or preview.get('spec_unchanged') is not True
        or preview.get('live_provider_unchanged') is not True
    ):
        raise ValueError('Original Native handoff receipt is not canonical.')

    removed = preview.get('label_keys_to_release')
    if (
        not isinstance(removed, list)
        or not {'app.kubernetes.io/managed-by', 'kaori.io/tenant-id'}.issubset(removed)
        or any(not isinstance(label, str) or label not in _LEGACY_OWNER_MARKERS
               for label in removed)
        or len(set(removed)) != len(removed)
    ):
        raise ValueError('This is not a recognized pre-#1126 ownership receipt.')

    name, uid, rv, labels = _resource_metadata(live)
    if (
        name != key[2] or uid != key[3]
        or not rv or rv != handback.get('resource_version')
        or not profile_public_id
    ):
        raise ValueError('Provider UID/resourceVersion or profile evidence changed.')

    if any(label in labels for label in _GOVERNED_LABELS - _ONLY_RESIDUE_ALLOWED):
        raise ValueError('Unexpected KAORI or successor ownership remains in provider.')
    if (
        preview.get('spec_sha256') != _stable_sha256(_spec(live))
        or preview.get('retained_metadata_sha256')
        != _stable_sha256(_legacy_retained_metadata(live))
    ):
        raise ValueError('Historical provider spec/foreign metadata evidence changed.')

    observed_profile = labels.get(_RESIDUAL_LABEL)
    if observed_profile is not None and observed_profile != profile_public_id:
        raise ValueError('Residual profile label does not match committed allocation.')
    return {
        'kind': key[0],
        'namespace': key[1],
        'name': key[2],
        'uid': uid,
        'resource_version': rv,
        'residual_label': _RESIDUAL_LABEL if observed_profile is not None else None,
        'legacy_spec_sha256': preview['spec_sha256'],
        'legacy_foreign_metadata_sha256': preview['retained_metadata_sha256'],
        'provider_spec_preserved': True,
        'foreign_metadata_preserved': True,
        'provider_mutation_performed': False,
    }


def assess_legacy_native_profile_residue_readonly(
    *, tenant_id: str, actor_user_id: int,
) -> dict[str, Any]:
    """Collect governed read-only evidence, not permission to remediate.

    Uses only existing KAORI database, AuditEvents and provider GET/SSR/SAR.
    Requires an authorized Platform Admin and a fully verified old lineage.
    """
    require_platform_admin_actor(actor_user_id)
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None
        or tenant.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.ownership_status != 'adopted'
        or tenant.reconciliation_authority != 'native_kubernetes'
    ):
        raise ValueError('Only verified Released Native Adopted history may be assessed.')

    evidence = tenant.provider_evidence_json or {}
    release = evidence.get('release_governance') or {}
    committed_handback = evidence.get('handback_governance') or {}
    handback = latest_native_successor_handback(tenant_id)
    dry_run = _latest_native_dry_run(tenant_id)
    if not isinstance(handback, Mapping) or not isinstance(dry_run, Mapping):
        raise ValueError('Verified immutable Native Release/Handback receipts are required.')
    plan_sha = release.get('plan_sha256')
    if (
        release.get('status') != 'released'
        or release.get('release_mode') != 'managed_handoff'
        or release.get('provider_handoff_verified') is not True
        or release.get('authority_mode') != 'platform_admin_governed'
        or release.get('tenant_id') != tenant_id
        or release.get('cluster_id') != tenant.cluster_id
        or release.get('generation') != tenant.generation
        or not isinstance(plan_sha, str) or len(plan_sha) != 64
        or not release.get('successor_owner')
        or committed_handback.get('status') != 'verified'
        or committed_handback.get('release_plan_sha256') != plan_sha
        or committed_handback.get('successor_owner') != release.get('successor_owner')
        or handback.get('status') != 'verified'
        or handback.get('successor_handback_verified') is not True
        or handback.get('tenant_id') != tenant_id
        or handback.get('cluster_id') != tenant.cluster_id
        or handback.get('generation') != tenant.generation
        or handback.get('release_plan_sha256') != plan_sha
        or handback.get('successor_owner') != release.get('successor_owner')
        or dry_run.get('status') != 'dry_run_passed'
        or dry_run.get('plan_sha256') != plan_sha
        or dry_run.get('handoff_fingerprint') != release.get('handoff_fingerprint')
        or handback.get('errors') != []
        or handback.get('provider_specs_preserved') is not True
    ):
        raise ValueError('Native Release and successor Handback lineage is not fully verified.')

    previews = _index_scope(dry_run.get('previewed_components'), title='Legacy dry-run')
    released = _index_scope(release.get('verified_components'), title='Released provider')
    verified = _index_scope(handback.get('verified_components'), title='Verified Handback')
    if (
        set(previews) != set(released) or set(previews) != set(verified)
        or handback.get('verified_count') != len(previews)
        or handback.get('expected_component_count') != len(previews)
        or release.get('released_namespace_count') != sum(
            kind == 'Namespace' for kind, _, _, _ in previews
        )
    ):
        raise ValueError('Canonical Released and Handback provider scopes differ.')

    records = (
        TenantNamespace.query.join(TenantEnvironment)
        .filter(TenantEnvironment.tenant_id == tenant_id)
        .order_by(TenantNamespace.id.asc()).all()
    )
    namespace_map = {row.namespace: row for row in records}
    if len(namespace_map) != len(records):
        raise ValueError('Released Namespace lineage is ambiguous.')
    if len(namespace_map) != release['released_namespace_count']:
        raise ValueError('Committed and released Namespace counts differ.')
    for kind, namespace, name, uid in previews:
        row = namespace_map.get(namespace)
        if (
            row is None
            or row.cluster_id != tenant.cluster_id
            or row.provisioning_status != TenantNamespaceProvisioningStatus.RELEASED.value
            or row.resource_profile is None
            or kind == 'Namespace' and row.provider_reference != uid
        ):
            raise ValueError('Released Namespace/Resource Profile lineage is incomplete.')
        if kind == 'Namespace':
            recorded = (row.provisioning_evidence_json or {}).get('handback_governance') or {}
            if (
                recorded.get('status') != 'verified'
                or recorded.get('release_plan_sha256') != plan_sha
                or recorded.get('provider_uid') != uid
                or recorded.get('resource_version') != verified[(kind, namespace, name, uid)].get(
                    'resource_version'
                )
                or (committed_handback.get('provider_resource_versions') or {}).get(name)
                != recorded.get('resource_version')
            ):
                raise ValueError('Committed Namespace handback RV ledger is not verified.')

    if any(type(value) is not int or value != 0 for value in
           _release_dependency_counts(tenant_id).values()):
        raise ValueError('Released Tenant has active KAORI governance dependencies.')

    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Original Native provider cluster is unavailable.')
    core = runtime_adapter.build_client(cluster).core_api()
    live_resources = {}
    authority_scope = []
    for key, component in previews.items():
        live = _read_resource(core, component)
        name, uid, rv, _ = _resource_metadata(live)
        if (name, uid, rv) != (
            key[2], key[3], verified[key].get('resource_version')
        ):
            raise ValueError('Live provider identity changed since verified Handback.')
        live_resources[key] = live
        authority_scope.append({
            'kind': key[0], 'namespace': key[1], 'name': name,
            'uid': uid, 'resource_version': rv,
        })
    provider = verify_native_provider_admin_authority(
        cluster=cluster, components=authority_scope,
    )
    if (
        provider.get('resource_authority_verified') is not True
        or provider.get('provider_username') != release.get('provider_username')
        or provider.get('provider_credential_id') != release.get('provider_credential_id')
        or provider.get('provider_username') != handback.get('provider_username')
        or provider.get('provider_credential_id') != handback.get('provider_credential_id')
    ):
        raise ValueError('Verified Platform Admin provider principal changed.')

    components = [
        inspect_legacy_profile_residue_component(
            preview=previews[key], handback=verified[key],
            live=live_resources[key],
            profile_public_id=str(namespace_map[key[1]].resource_profile.public_id),
        )
        for key in sorted(previews)
    ]
    residual = [item for item in components if item['residual_label'] is not None]
    if not residual:
        raise ValueError('No legacy profile marker residue requires recovery.')
    return {
        'status': 'read_only_recovery_candidate',
        'tenant_id': tenant.id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'release_plan_sha256': plan_sha,
        'successor_owner': release['successor_owner'],
        'historical_handback_plan_sha256': handback.get('handback_plan_sha256'),
        'components': components,
        'component_count': len(components),
        'residual_component_count': len(residual),
        'provider_identity_verified': True,
        'historical_spec_and_foreign_metadata_verified': True,
        'provider_mutation_performed': False,
        'cleanup_authorized': False,
        're_adopt_admitted': False,
        'evidence_committed': False,
    }
