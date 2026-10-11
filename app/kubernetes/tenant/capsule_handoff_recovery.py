"""Read-only Capsule handoff recovery decisions, never automatic retry (#1229).

Non-atomic Kubernetes/SQL transfer attempts demand authoritative read-back
and explicit human recovery. A partial attempt is not permission to resume.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS
from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity, _labels, _successor, capsule_preservation_digest,
)
from app.kubernetes.tenant.native_handoff_dry_run import _MARKER_KEYS


def capture_capsule_namespace_baseline(
    component: Mapping[str, Any], resource: Any, *, tenant_id: str,
    capsule_tenant_name: str,
) -> dict[str, Any]:
    """No-secret immutable baseline for *one* KAORI-owned Capsule Namespace."""
    if (
        component.get('kind') != 'Namespace'
        or component.get('handoff') != 'external_acceptance_required'
        or component.get('ownership') != 'kaori_marker_correlated'
        or component.get('authority') != 'capsule'
        or component.get('namespace') != component.get('name')
        or _identity(resource) != (
            component.get('name'), component.get('uid'), component.get('resource_version')
        )
    ):
        raise ValueError('Missing exact Capsule Namespace baseline authority.')
    labels = _labels(resource)
    claims = {labels[k] for k in _CAPSULE_TENANT_LABEL_KEYS if k in labels}
    if (
        labels.get('app.kubernetes.io/managed-by') != 'kaori'
        or labels.get('kaori.io/tenant-id') != tenant_id
        or claims != {capsule_tenant_name}
        or any(k.startswith('kaori.io/') and k not in _MARKER_KEYS for k in labels)
    ):
        raise ValueError('Incomplete KAORI/Capsule correlated metadata baseline.')
    return {
        'kind': 'Namespace', 'namespace': component['namespace'],
        'name': component['name'], 'uid': component['uid'],
        'resource_version': component['resource_version'],
        'operation': 'capsule_metadata_only_json_patch_dry_run',
        'dry_run': True, 'live_provider_unchanged': True,
        'capsule_tenant_name': capsule_tenant_name,
        'preserved': capsule_preservation_digest(resource),
        'label_keys_to_release': [k for k in _MARKER_KEYS if k in labels],
    }


def classify_capsule_namespace_handoff(
    *, baseline: Mapping[str, Any], current: Any,
    tenant_id: str, successor_owner: str,
) -> dict[str, Any]:
    """Classify read-back as pending/transferred or fail on ambiguity.

    Even transferred state is not successor acknowledgement or Released.
    """
    owner = _successor(successor_owner)
    if (
        baseline.get('kind') != 'Namespace'
        or baseline.get('operation') != 'capsule_metadata_only_json_patch_dry_run'
        or baseline.get('dry_run') is not True
        or baseline.get('live_provider_unchanged') is not True
        or not isinstance(baseline.get('preserved'), Mapping)
        or baseline.get('namespace') != baseline.get('name')
        or not tenant_id or not baseline.get('capsule_tenant_name')
    ):
        raise ValueError('Capsule handoff recovery lacks an exact passing baseline.')
    name, uid, rv = _identity(current)
    if (
        (name, uid) != (baseline.get('name'), baseline.get('uid'))
        or not rv or capsule_preservation_digest(current) != baseline['preserved']
    ):
        raise ValueError('Capsule provider identity/spec/external ownership changed.')
    release_keys = baseline.get('label_keys_to_release')
    if (
        not isinstance(release_keys, list)
        or len(release_keys) != len(set(release_keys))
        or not {'app.kubernetes.io/managed-by', 'kaori.io/tenant-id'}.issubset(release_keys)
        or any(not isinstance(key, str) or key not in _MARKER_KEYS for key in release_keys)
    ):
        raise ValueError('Capsule ownership baseline marker inventory is invalid.')
    labels = _labels(current)
    claims = {labels[k] for k in _CAPSULE_TENANT_LABEL_KEYS if k in labels}
    if claims != {baseline['capsule_tenant_name']} or any(
        k.startswith('kaori.io/') and k not in _MARKER_KEYS for k in labels
    ):
        raise ValueError('Capsule membership or unknown governance control changed.')
    if (
        rv == baseline.get('resource_version')
        and labels.get('app.kubernetes.io/managed-by') == 'kaori'
        and labels.get('kaori.io/tenant-id') == tenant_id
        and all(k in labels for k in baseline.get('label_keys_to_release') or [])
    ):
        state = 'pending_provider_transfer'
    elif (
        rv != baseline.get('resource_version')
        and labels.get('app.kubernetes.io/managed-by') == owner
        and not any(k in labels for k in _MARKER_KEYS if k != 'app.kubernetes.io/managed-by')
    ):
        state = 'provider_markers_transferred'
    else:
        raise ValueError('Unknown partial, competing or stale Capsule ownership state.')
    return {
        'kind': 'Namespace', 'namespace': baseline['namespace'],
        'name': name, 'uid': uid, 'resource_version': rv,
        'state': state, 'spec_preserved': True, 'foreign_metadata_preserved': True,
        'provider_deleted': False, 'release_authorized': False,
    }


def summarize_capsule_recovery(
    *, baselines: list[dict[str, Any]],
    live_namespaces: Mapping[tuple[str, str], Any],
    tenant_id: str, successor_owner: str,
) -> dict[str, Any]:
    """Read-only complete scope classification; NEVER grants retry or Release."""
    if not isinstance(baselines, list) or not 0 < len(baselines) <= 30:
        raise ValueError('Capsule recovery requires a bounded nonempty Namespace inventory.')
    keys = [(row.get('name'), row.get('uid')) for row in baselines]
    if (
        len(set(keys)) != len(keys) or set(live_namespaces) != set(keys)
        or any(not isinstance(row, Mapping) for row in baselines)
    ):
        raise ValueError('Capsule recovery live read-back differs from approved scope.')
    rows = [
        classify_capsule_namespace_handoff(
            baseline=row, current=live_namespaces[key],
            tenant_id=tenant_id, successor_owner=successor_owner,
        )
        for row, key in zip(baselines, keys, strict=True)
    ]
    transferred = sum(row['state'] == 'provider_markers_transferred' for row in rows)
    return {
        'status': (
            'provider_markers_transferred_consent_unverified'
            if transferred == len(rows)
            else 'partial_handoff_recovery_required'
            if transferred
            else 'provider_handoff_not_started'
        ),
        'components': rows, 'expected_count': len(rows),
        'transferred_count': transferred, 'pending_count': len(rows) - transferred,
        'provider_spec_preserved': True, 'provider_resource_deleted': False,
        'provider_handoff_verified': False, 'successor_consent_verified': False,
        'resume_authorized': False, 'auto_retry_authorized': False,
        'release_authorized': False,
    }
