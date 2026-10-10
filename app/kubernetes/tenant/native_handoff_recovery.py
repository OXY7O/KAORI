"""Read-only Native provider handoff recovery classification (#1048).

Never infers successor consent or authorizes provider PATCH/KAORI Released.
The input must come from an explicit authoritative provider read-back; this
module merely classifies the observed state against the canonical dry-run
receipt and immutable provider metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.native_handoff_dry_run import (
    _MARKER_KEYS,
    _resource_metadata,
    _retained_provider_metadata,
    _spec,
    _stable_sha256,
)


def classify_native_handoff_component(
    *, before: Mapping[str, Any], current: Any,
    tenant_id: str, successor_owner: str,
) -> dict[str, Any]:
    """Classify one exact provider object without mutating it."""
    key = (before.get('namespace'), before.get('kind'), before.get('name'), before.get('uid'))
    if (
        before.get('operation') != 'metadata_only_json_patch_dry_run'
        or before.get('dry_run') is not True
        or before.get('live_provider_unchanged') is not True
        or before.get('kind') not in {'Namespace', 'ResourceQuota', 'LimitRange'}
        or not all(isinstance(part, str) and part for part in key[1:])
        or not tenant_id or not successor_owner or successor_owner == 'kaori'
    ):
        raise ValueError('No exact, passing Native preview and successor scope exists.')
    name, uid, resource_version, labels = _resource_metadata(current)
    if name != key[2] or uid != key[3] or not resource_version:
        raise ValueError('Provider object identity changed during ownership handoff.')
    if (
        before.get('spec_sha256') != _stable_sha256(_spec(current))
        or before.get('retained_metadata_sha256') != _stable_sha256(_retained_provider_metadata(current))
    ):
        raise ValueError('Provider resource spec or external metadata changed during handoff.')
    if (
        resource_version == before.get('resource_version')
        and labels.get('app.kubernetes.io/managed-by') == 'kaori'
        and labels.get('kaori.io/tenant-id') == tenant_id
        and set(before.get('label_keys_to_release') or []).issubset(labels)
    ):
        state = 'pending_provider_transfer'
    elif (
        resource_version != before.get('resource_version')
        and labels.get('app.kubernetes.io/managed-by') == successor_owner
        and not any(key in labels for key in _MARKER_KEYS if key != 'app.kubernetes.io/managed-by')
    ):
        state = 'provider_markers_transferred'
    else:
        raise ValueError('Provider owner marker is partial, conflicting or unexpectedly changed.')
    return {
        'namespace': before.get('namespace'),
        'kind': before['kind'],
        'name': name,
        'uid': uid,
        'resource_version': resource_version,
        'state': state,
        'spec_preserved': True,
        'foreign_metadata_preserved': True,
    }


def summarize_native_handoff_recovery(
    *, previewed_components: list[dict[str, Any]],
    live_components: Mapping[tuple[str, str, str, str], Any],
    tenant_id: str, successor_owner: str,
) -> dict[str, Any]:
    """Normalize full provider inventory, including safe partial-failure evidence.

    This is evidence-only. 'provider_markers_transferred' is not consent,
    does not grant retry authority, and cannot commit Released.
    """
    if not previewed_components or len(previewed_components) > 100:
        raise ValueError('Handoff preview inventory is empty or exceeds the bounded scope.')
    keys = [
        (str(item.get('namespace') or ''), str(item.get('kind') or ''),
         str(item.get('name') or ''), str(item.get('uid') or ''))
        for item in previewed_components
    ]
    if len(set(keys)) != len(keys) or set(live_components) != set(keys):
        raise ValueError('Live provider handoff inventory does not match the exact preview.')
    components = [
        classify_native_handoff_component(
            before=before, current=live_components[key],
            tenant_id=tenant_id, successor_owner=successor_owner,
        )
        for before, key in zip(previewed_components, keys, strict=True)
    ]
    transferred = sum(item['state'] == 'provider_markers_transferred' for item in components)
    pending = len(components) - transferred
    if transferred == len(components):
        status = 'provider_markers_transferred_consent_unverified'
    elif transferred:
        status = 'partial_handoff_recovery_required'
    else:
        status = 'provider_handoff_not_started'
    return {
        'status': status,
        'components': components,
        'transferred_count': transferred,
        'pending_count': pending,
        'provider_spec_preserved': True,
        'provider_resource_deleted': False,
        'successor_consent_verified': False,
        'resume_authorized': False,
        'release_authorized': False,
    }
