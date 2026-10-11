"""Capsule-specific server-side dry-run preview, without live PATCH or Release (#1229).

No route or scheduled job exposes this draft review helper. A successful preview
DOES NOT prove quota, limitRange, RoleBinding coverage or authorize execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS
from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity, _labels, _successor, build_capsule_namespace_handoff_patch,
    capsule_preservation_digest, validate_capsule_handoff_scope,
    verify_capsule_cr_preserved, verify_capsule_namespace_preview,
)
from app.kubernetes.tenant.capsule_handoff_recovery import capture_capsule_namespace_baseline

_CONTENT_TYPE = 'application/json-patch+json'


def preview_capsule_namespace_handoff(
    core: Any, component: Mapping[str, Any], *, tenant_id: str,
    capsule_tenant_name: str, successor_owner: str,
) -> dict[str, Any]:
    """Bound UID/RV conditional dryRun=All; independently reread unchanged live state."""
    _successor(successor_owner)
    if component.get('kind') != 'Namespace' or component.get('namespace') != component.get('name'):
        raise ValueError('Capsule dry-run requires an approved Namespace component.')
    before = core.read_namespace(component['name'], _request_timeout=5)
    if _identity(before) != (
        component.get('name'), component.get('uid'), component.get('resource_version')
    ):
        raise ValueError('Capsule Namespace drifted from approved preflight.')
    before_digest = capsule_preservation_digest(before)
    before_labels = _labels(before)
    claims = {before_labels[k] for k in _CAPSULE_TENANT_LABEL_KEYS if k in before_labels}
    if claims != {capsule_tenant_name}:
        raise ValueError('Capsule Namespace provider label correlation is incomplete.')

    if component.get('handoff') == 'external_acceptance_required':
        patch = build_capsule_namespace_handoff_patch(
            component, before, tenant_id=tenant_id,
            capsule_tenant_name=capsule_tenant_name,
            verified_successor_owner=successor_owner,
        )
        preview = core.patch_namespace(
            name=component['name'], body=patch, dry_run='All',
            _content_type=_CONTENT_TYPE, _request_timeout=5,
        )
        verify_capsule_namespace_preview(
            before=before, preview=preview, successor_owner=successor_owner,
        )
        result = capture_capsule_namespace_baseline(
            component, before, tenant_id=tenant_id,
            capsule_tenant_name=capsule_tenant_name,
        )
    elif (
        component.get('handoff') == 'observe_only'
        and component.get('ownership') == 'external_or_unattributed'
        and not any(k in before_labels for k in ('kaori.io/tenant-id', 'app.kubernetes.io/managed-by'))
        and not any(k.startswith('kaori.io/') for k in before_labels)
    ):
        # No-op read-back of an externally owned Capsule Namespace. No patch.
        result = {
            'kind': 'Namespace', 'namespace': component['name'],
            'name': component['name'], 'uid': component['uid'],
            'resource_version': component['resource_version'],
            'operation': 'observe_capsule_namespace_without_transfer',
            'dry_run': False, 'live_provider_unchanged': True,
            'preserved': before_digest,
        }
    else:
        raise ValueError('Namespace handoff source ownership is ambiguous.')
    live = core.read_namespace(component['name'], _request_timeout=5)
    if (
        _identity(live) != _identity(before)
        or _labels(live) != before_labels
        or capsule_preservation_digest(live) != before_digest
    ):
        raise ValueError('Capsule live provider changed during dry-run preview.')
    return result


def preview_capsule_handoff_scope(
    *, custom: Any, core: Any, components: list[dict[str, Any]],
    tenant_id: str, successor_owner: str,
) -> dict[str, Any]:
    """Scope preview only, not a sufficient provider-authority/readiness proof.

    No Runtime adapter, persistence, approval or external patch in this module.
    Caller must separately authenticate the X.509 actor and verify exact plan,
    independent consent, SAR and live dependency evidence before invoking it.
    """
    cr, namespaces = validate_capsule_handoff_scope(components)
    _successor(successor_owner)
    if not tenant_id:
        raise ValueError('Capsule handoff must bind the canonical Tenant identity.')
    live_cr = custom.get_cluster_custom_object(
        'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'],
        _request_timeout=5,
    )
    if not isinstance(live_cr, Mapping):
        raise ValueError('Unsupported Capsule v1beta2 CR provider response.')
    cr_observation = verify_capsule_cr_preserved(cr, live_cr)
    rows = [
        preview_capsule_namespace_handoff(
            core, component, tenant_id=tenant_id,
            capsule_tenant_name=cr['name'], successor_owner=successor_owner,
        )
        for component in namespaces
    ]
    cr_after = custom.get_cluster_custom_object(
        'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'],
        _request_timeout=5,
    )
    verify_capsule_cr_preserved(cr, cr_after)
    if (
        _labels(live_cr) != _labels(cr_after)
        or len(rows) != len(namespaces)
        or not any(row['operation'] == 'capsule_metadata_only_json_patch_dry_run' for row in rows)
    ):
        raise ValueError('Capsule CR changed, preview is partial or no transfer is provable.')
    return {
        'status': 'preview_observed_coverage_incomplete',
        'capsule_cr': cr_observation, 'namespace_previews': rows,
        'namespace_count': len(rows),
        'quota_limit_rbac_inventory_verified': False,
        'dry_run_complete': False,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
