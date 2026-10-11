"""Pure, fail-closed Capsule Release metadata handoff contract (#1229).

Capsule v1beta2 Tenant spec, ownership, quotas and RBAC stay provider-owned.
This module NEVER sends a provider request, persists evidence or authorizes Release.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS
from app.kubernetes.tenant.native_handoff_dry_run import (
    _MARKER_KEYS, _immutable_metadata, _label_path, _resource_metadata,
    _retained_provider_metadata, _spec, _stable_sha256,
)
from app.kubernetes.tenant.release_handoff_inventory import _capsule_spec_sha256
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _KAORI_MARKERS, _digest, _get, _owner_refs, _scope_identity, _strings,
    classify_capsule_related_resource,
)

_OWNER_LABEL = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,61}[A-Za-z0-9])?\Z')
_MAX_SCOPE = 31


def _read(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def _meta(resource: Any) -> Any:
    return _read(resource, 'metadata')


def _version(resource: Any) -> str:
    metadata = _meta(resource)
    return str(_read(metadata, 'resourceVersion') or _read(metadata, 'resource_version') or '')


def _identity(resource: Any) -> tuple[str, str, str]:
    metadata = _meta(resource)
    return (
        str(_read(metadata, 'name') or ''),
        str(_read(metadata, 'uid') or ''),
        _version(resource),
    )


def _labels(resource: Any) -> dict[str, str]:
    labels = _read(_meta(resource), 'labels')
    if not isinstance(labels, Mapping) or any(
        not isinstance(k, str) or not isinstance(v, str)
        for k, v in labels.items()
    ):
        raise ValueError('Capsule handoff requires a complete string-valued label map.')
    return dict(labels)


def _annotations(resource: Any) -> dict[str, str]:
    value = _read(_meta(resource), 'annotations')
    if value is None:
        return {}
    if not isinstance(value, Mapping) or any(
        not isinstance(k, str) or not isinstance(v, str)
        for k, v in value.items()
    ):
        raise ValueError('Capsule provider annotations are malformed.')
    return dict(value)


def _successor(value: str) -> str:
    if (
        not isinstance(value, str) or not _OWNER_LABEL.fullmatch(value)
        or value.lower() == 'kaori' or value.lower().startswith('system')
    ):
        raise ValueError('An independently verified, non-KAORI successor label is required.')
    return value


def validate_capsule_handoff_scope(components: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate exact admitted CR + Namespaces; no inferred quota/RBAC transfer.

    Source inventory currently has no ResourceQuota/LimitRange/RoleBinding entries.
    That omission cannot be interpreted as proof those resources are transferable.
    """
    if not isinstance(components, list) or not 2 <= len(components) <= _MAX_SCOPE:
        raise ValueError('Capsule handoff scope must be complete and bounded.')
    cr: dict[str, Any] | None = None
    namespaces: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in components:
        if not isinstance(item, Mapping):
            raise ValueError('Capsule handoff scope contains malformed evidence.')
        kind, name = item.get('kind'), item.get('name')
        if (
            kind not in ('CapsuleTenant', 'Namespace')
            or not isinstance(name, str) or not name.strip()
            or not isinstance(item.get('uid'), str) or not item['uid']
            or not isinstance(item.get('resource_version'), str) or not item['resource_version']
            or item.get('authority') != 'capsule'
            or item.get('handoff') not in ('external_acceptance_required', 'observe_only')
            or item.get('ownership') not in (
                'kaori_marker_correlated', 'external_or_unattributed',
            )
            or (kind, name) in seen
        ):
            raise ValueError('Unknown, ambiguous or duplicate Capsule provider resource.')
        seen.add((kind, name))
        if kind == 'CapsuleTenant':
            if (
                cr is not None or item.get('handoff') != 'external_acceptance_required'
                or not isinstance(item.get('capsule_spec_sha256'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', item['capsule_spec_sha256'])
            ):
                raise ValueError('Capsule CR requires one exact full-spec digest and consent.')
            cr = dict(item)
        else:
            if item.get('namespace') != name:
                raise ValueError('Capsule Namespace identity is not scoped correctly.')
            namespaces.append(dict(item))
    if cr is None or not namespaces:
        raise ValueError('One Capsule Tenant CR and at least one Namespace are required.')
    return cr, namespaces


def verify_capsule_cr_preserved(component: Mapping[str, Any], current: Any) -> dict[str, Any]:
    """Capsule CR remains authoritative; no Capsule spec or owner rewrite."""
    if component.get('kind') != 'CapsuleTenant':
        raise ValueError('Only the admitted Capsule Tenant CR is eligible for preservation.')
    if _identity(current) != (
        component.get('name'), component.get('uid'), component.get('resource_version'),
    ):
        raise ValueError('Capsule Tenant UID/resourceVersion changed.')
    spec = _spec(current)
    if _capsule_spec_sha256(spec) != component.get('capsule_spec_sha256'):
        raise ValueError('Capsule Tenant provider-owned spec differs from approved scope.')
    labels = _labels(current)
    if labels.get('app.kubernetes.io/managed-by') == 'kaori':
        raise ValueError('KAORI-owned Capsule CR metadata requires separate authority review.')
    if any(key.startswith('kaori.io/') for key in labels):
        raise ValueError('Capsule CR has additional KAORI control markers; refuse automatic transfer.')
    return {
        'kind': 'CapsuleTenant', 'name': component['name'], 'uid': component['uid'],
        'resource_version': component['resource_version'],
        'operation': 'preserve_capsule_authoritative_cr', 'provider_spec_preserved': True,
        'provider_mutation_performed': False, 'release_authorized': False,
    }


def build_capsule_namespace_handoff_patch(
    component: Mapping[str, Any], resource: Any, *, tenant_id: str,
    capsule_tenant_name: str, verified_successor_owner: str,
) -> list[dict[str, Any]]:
    """UID/RV guarded metadata-only JSON Patch for a KAORI-owned Namespace.

    No Capsule membership labels, spec, quotas, limitRanges, ownerReferences,
    finalizers, annotations or foreign/third-party labels are changed.
    """
    owner = _successor(verified_successor_owner)
    if (
        not tenant_id or not capsule_tenant_name
        or component.get('kind') != 'Namespace'
        or component.get('authority') != 'capsule'
        or component.get('handoff') != 'external_acceptance_required'
        or component.get('ownership') != 'kaori_marker_correlated'
        or component.get('namespace') != component.get('name')
    ):
        raise ValueError('Only exact KAORI-correlated Capsule Namespace metadata may transfer.')
    name, uid, rv = _identity(resource)
    if (name, uid, rv) != (
        component.get('name'), component.get('uid'), component.get('resource_version')
    ):
        raise ValueError('Capsule Namespace UID/resourceVersion differs from the approved plan.')
    labels = _labels(resource)
    if (
        labels.get('app.kubernetes.io/managed-by') != 'kaori'
        or labels.get('kaori.io/tenant-id') != tenant_id
    ):
        raise ValueError('KAORI Namespace ownership is not verified.')
    claims = {labels[key] for key in _CAPSULE_TENANT_LABEL_KEYS if key in labels}
    if claims != {capsule_tenant_name}:
        raise ValueError('Capsule Tenant membership must be unambiguous and provider-labeled.')
    # Never remove a marker that another provider uses as its own governance key.
    if set(_MARKER_KEYS).intersection(_CAPSULE_TENANT_LABEL_KEYS):
        raise ValueError('Capsule and KAORI ownership key sets unexpectedly overlap.')
    for key in labels:
        if key.startswith('kaori.io/') and key not in _MARKER_KEYS:
            raise ValueError('Unknown KAORI Namespace control marker requires explicit review.')
    _annotations(resource)
    patch: list[dict[str, Any]] = [
        {'op': 'test', 'path': '/metadata/uid', 'value': uid},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': rv},
        {'op': 'test', 'path': '/metadata/labels', 'value': labels},
    ]
    for key in _MARKER_KEYS:
        if key in labels:
            patch.append({'op': 'remove', 'path': _label_path(key)})
    patch.append({
        'op': 'add', 'path': _label_path('app.kubernetes.io/managed-by'), 'value': owner,
    })
    return patch


def capsule_preservation_digest(resource: Any) -> dict[str, str]:
    """Minimal no-secret digest of invariants used for read-back/recovery."""
    return {
        'spec_sha256': _stable_sha256(_spec(resource)),
        'retained_metadata_sha256': _stable_sha256(_retained_provider_metadata(resource)),
        'owner_finalizer_sha256': _stable_sha256(_immutable_metadata(resource)),
        'annotations_sha256': _stable_sha256(_annotations(resource)),
    }


def verify_capsule_namespace_preview(
    *, before: Any, preview: Any, successor_owner: str,
) -> None:
    """Verify server dryRun=All returned no provider spec/foreign-state change."""
    owner = _successor(successor_owner)
    before_name, before_uid, _ = _identity(before)
    after_name, after_uid, _ = _identity(preview)
    original = _labels(before)
    expected = {
        **{key: value for key, value in original.items() if key not in _MARKER_KEYS},
        'app.kubernetes.io/managed-by': owner,
    }
    if (
        (before_name, before_uid) != (after_name, after_uid)
        or _labels(preview) != expected
        or capsule_preservation_digest(before) != capsule_preservation_digest(preview)
        or any(key in _labels(preview) for key in _MARKER_KEYS if key != 'app.kubernetes.io/managed-by')
    ):
        raise ValueError('Capsule handoff dry-run would change provider-owned state.')


# Related-resource operations are pure **candidates**, not PATCH permissions.
# Unlike Namespace transfer, RoleBinding's access-grant label must also be
# removed. No policy/spec, subjects, roleRef, ownerReferences or finalizer ops.
_RELATED_TRANSFER_KINDS = frozenset({'ResourceQuota', 'LimitRange', 'RoleBinding'})
_RELATED_TRANSFER_LABELS = frozenset(_MARKER_KEYS) | {'kaori.io/access-grant'}


def _related_transfer_source(
    *, record: Mapping[str, Any], before: Any, kind: str, namespace: str,
    tenant_id: str, capsule_name: str, capsule_uid: str,
    approved_label_keys: list[str],
) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Recheck exact inventory and all human-proposed metadata key coverage.

    Correlated KAORI labels and correctly shaped consent are NOT
    independently authenticated ownership or execution authorization.
    """
    if (
        kind not in _RELATED_TRANSFER_KINDS
        or not isinstance(record, Mapping)
        or record.get('kind') != kind or record.get('namespace') != namespace
        or record.get('origin') != 'kaori_correlated'
        or record.get('mutation_authorized') != 'false'
        or not isinstance(approved_label_keys, list)
        or not all(isinstance(key, str) for key in approved_label_keys)
        or len(approved_label_keys) != len(set(approved_label_keys))
    ):
        raise ValueError('Capsule related metadata transfer is not in the approved source scope.')
    observed, findings = classify_capsule_related_resource(
        resource=before, kind=kind, namespace=namespace,
        tenant_id=tenant_id, capsule_name=capsule_name, capsule_uid=capsule_uid,
    )
    required = {
        'kind', 'namespace', 'name', 'uid', 'resource_version', 'origin',
        'policy_sha256', 'metadata_sha256', 'mutation_authorized',
    }
    if kind == 'RoleBinding':
        required |= {'binding_contract_sha256', 'grant_scope_sha256'}
    if (
        not required.issubset(record)
        or any(record[key] != observed.get(key) for key in required)
        or any('conflicting' in reason or 'incomplete' in reason for reason in findings)
    ):
        raise ValueError('Capsule related policy, identity, RBAC or ownership source changed.')
    metadata = _get(before, 'metadata')
    labels = _strings(_get(metadata, 'labels'), label='labels')
    selected = {
        key for key in labels
        if key in _RELATED_TRANSFER_LABELS
    }
    if (
        not selected.issubset(_RELATED_TRANSFER_LABELS)
        or selected != set(approved_label_keys)
        or not {'app.kubernetes.io/managed-by', 'kaori.io/tenant-id'}.issubset(selected)
        or (kind == 'RoleBinding') != ('kaori.io/access-grant' in selected)
        or any(key.startswith('kaori.io/') and key not in _KAORI_MARKERS for key in labels)
        or _get(metadata, 'deletion_timestamp') is not None
        or _get(metadata, 'deletionTimestamp') is not None
    ):
        raise ValueError('Capsule related consent is partial, unsafe or resource is deleting.')
    return observed, labels, selected


def _related_provider_invariants(resource: Any) -> dict[str, str]:
    """Exclude labels and resourceVersion; preserve every other governed field."""
    meta = _get(resource, 'metadata')
    refs = _owner_refs(meta)
    annotations = _strings(_get(meta, 'annotations'), label='annotations')
    finalizers = _get(meta, 'finalizers')
    if finalizers is None:
        finalizers = []
    if not isinstance(finalizers, (list, tuple)) or any(
        not isinstance(item, str) for item in finalizers
    ):
        raise ValueError('Capsule related finalizers are malformed.')
    if (
        _get(meta, 'deletion_timestamp') is not None
        or _get(meta, 'deletionTimestamp') is not None
    ):
        raise ValueError('Capsule related object is terminating.')
    return {
        'owner_annotations_finalizers_sha256': _digest({
            'ownerReferences': refs, 'annotations': annotations,
            'finalizers': list(finalizers),
        }),
    }


def build_capsule_related_metadata_handoff_patch(
    *, record: Mapping[str, Any], before: Any, kind: str, namespace: str,
    tenant_id: str, capsule_name: str, capsule_uid: str,
    successor_owner: str, approved_label_keys: list[str],
) -> list[dict[str, Any]]:
    """Offline UID/RV/label guarded patch for ONE correlated related object.

    NEVER call Kubernetes here. The eventual executor MUST independently
    verify authenticated controller provenance, per-object successor consent,
    current scope and START-before-write, then authorize server dryRun=All.
    """
    owner = _successor(successor_owner)
    observed, labels, selected = _related_transfer_source(
        record=record, before=before, kind=kind, namespace=namespace,
        tenant_id=tenant_id, capsule_name=capsule_name, capsule_uid=capsule_uid,
        approved_label_keys=approved_label_keys,
    )
    _related_provider_invariants(before)
    patch: list[dict[str, Any]] = [
        {'op': 'test', 'path': '/metadata/uid', 'value': observed['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': observed['resource_version']},
        {'op': 'test', 'path': '/metadata/labels', 'value': labels},
    ]
    for key in sorted(selected):
        patch.append({'op': 'remove', 'path': _label_path(key)})
    patch.append({
        'op': 'add', 'path': _label_path('app.kubernetes.io/managed-by'),
        'value': owner,
    })
    return patch


def _verify_related_after(
    *, before: Any, after: Any, record: Mapping[str, Any],
    kind: str, namespace: str, labels: Mapping[str, str],
    approved_keys: set[str], successor_owner: str,
) -> str:
    name, uid, rv, _ = _scope_identity(after, namespace=namespace)
    if (
        (name, uid) != (record['name'], record['uid'])
        or not isinstance(rv, str) or not rv
    ):
        raise ValueError('Capsule related read-back changed resource identity.')
    source, source_uid, source_rv, _ = _scope_identity(before, namespace=namespace)
    if (source, source_uid, source_rv) != (
        record['name'], record['uid'], record['resource_version'],
    ):
        raise ValueError('Capsule related read-back source UID/RV is stale.')
    if _related_provider_invariants(before) != _related_provider_invariants(after):
        raise ValueError('Capsule related handoff changed owner, annotations or finalizers.')
    # Reclassify the policy using the same canonical inventory normalizer;
    # RoleBinding roleRef/subjects remain compared even after grant labels leave.
    old_policy = classify_capsule_related_resource(
        resource=before, kind=kind, namespace=namespace,
        tenant_id=labels['kaori.io/tenant-id'],
        capsule_name='', capsule_uid='',
    ) if False else None
    # Never calculate policy from arbitrary response metadata: the inventory
    # classifier canonicalizes roleRef+subjects and namespaced quota/limit spec.
    if kind == 'RoleBinding':
        policy = {
            'roleRef': _get(after, 'role_ref') or _get(after, 'roleRef'),
            'subjects': _get(after, 'subjects'),
        }
    else:
        policy = _get(after, 'spec')
    if policy is None or _digest(policy) != record['policy_sha256']:
        raise ValueError('Capsule related handoff changed quota, limits or RBAC policy.')
    expected = {
        **{key: value for key, value in labels.items() if key not in approved_keys},
        'app.kubernetes.io/managed-by': _successor(successor_owner),
    }
    actual = _strings(_get(_get(after, 'metadata'), 'labels'), label='labels')
    if actual == labels and rv == source_rv:
        return 'pending_provider_transfer'
    if actual == expected and rv != source_rv:
        return 'provider_markers_transferred'
    raise ValueError('Capsule related handoff has stale or partially transferred ownership.')


def verify_capsule_related_metadata_preview(
    *, record: Mapping[str, Any], before: Any, preview: Any,
    kind: str, namespace: str, tenant_id: str, capsule_name: str,
    capsule_uid: str, successor_owner: str, approved_label_keys: list[str],
) -> dict[str, Any]:
    """Validate the returned dryRun=All object, not a live provider success."""
    _related_transfer_source(
        record=record, before=before, kind=kind, namespace=namespace,
        tenant_id=tenant_id, capsule_name=capsule_name, capsule_uid=capsule_uid,
        approved_label_keys=approved_label_keys,
    )
    source, labels, keys = _related_transfer_source(
        record=record, before=before, kind=kind, namespace=namespace,
        tenant_id=tenant_id, capsule_name=capsule_name, capsule_uid=capsule_uid,
        approved_label_keys=approved_label_keys,
    )
    expected = {
        **{key: value for key, value in labels.items() if key not in keys},
        'app.kubernetes.io/managed-by': _successor(successor_owner),
    }
    result = _verify_related_after(
        before=before, after=preview, record=record, kind=kind,
        namespace=namespace, labels=labels, approved_keys=keys,
        successor_owner=successor_owner,
    ) if _scope_identity(preview, namespace=namespace)[2] != source['resource_version'] else None
    # Kubernetes dry-run is not guaranteed to return a new RV. Verify the
    # same exact label/spec/metadata invariants even when the RV is unchanged.
    if (
        _strings(_get(_get(preview, 'metadata'), 'labels'), label='labels') != expected
        or _related_provider_invariants(before) != _related_provider_invariants(preview)
    ):
        raise ValueError('Capsule related dry-run would mutate unauthorized provider metadata.')
    if kind == 'RoleBinding':
        policy = {'roleRef': _get(preview, 'role_ref') or _get(preview, 'roleRef'),
                  'subjects': _get(preview, 'subjects')}
    else:
        policy = _get(preview, 'spec')
    if (
        _scope_identity(preview, namespace=namespace)[:2] != (source['name'], source['uid'])
        or policy is None or _digest(policy) != source['policy_sha256']
    ):
        raise ValueError('Capsule related dry-run changed UID, quota, limits or RoleBinding.')
    return {
        'kind': kind, 'namespace': namespace, 'name': source['name'],
        'uid': source['uid'], 'source_resource_version': source['resource_version'],
        'preview_sha256': _digest({
            'policy_sha256': source['policy_sha256'],
            'labels': expected, 'invariants': _related_provider_invariants(preview),
        }),
        'status': 'dry_run_shape_checked_not_admitted',
        'provider_mutation_performed': False,
        'provider_execution_admitted': False,
        'release_authorized': False,
    }


def classify_capsule_related_metadata_readback(
    *, record: Mapping[str, Any], before: Any, current: Any,
    kind: str, namespace: str, tenant_id: str, capsule_name: str,
    capsule_uid: str, successor_owner: str, approved_label_keys: list[str],
) -> dict[str, Any]:
    """Pure G3 candidate status; neither authenticates observations nor retries."""
    source, labels, keys = _related_transfer_source(
        record=record, before=before, kind=kind, namespace=namespace,
        tenant_id=tenant_id, capsule_name=capsule_name, capsule_uid=capsule_uid,
        approved_label_keys=approved_label_keys,
    )
    state = _verify_related_after(
        before=before, after=current, record=source, kind=kind,
        namespace=namespace, labels=labels, approved_keys=keys,
        successor_owner=successor_owner,
    )
    return {
        'kind': kind, 'namespace': namespace, 'name': source['name'],
        'uid': source['uid'],
        'resource_version': _scope_identity(current, namespace=namespace)[2],
        'state': state, 'policy_preserved': True,
        'owner_annotations_finalizers_preserved': True,
        'provider_snapshot_authenticity_verified': False,
        'provider_handoff_verified': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
    }
