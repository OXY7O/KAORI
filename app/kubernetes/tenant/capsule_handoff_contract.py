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
