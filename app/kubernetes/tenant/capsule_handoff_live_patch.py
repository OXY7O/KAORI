"""Disabled Capsule metadata-only live PATCH adapter for #1229.

This is source wiring for the eventual G2 executor, NOT an execution entry
point. G1 consent/dry-run evidence cannot authorize a provider write. START
must be durably committed, independently checked and fenced before this
module can be enabled by a separate authorized change.

No route, background job, task registration or feature flag imports this
adapter. Failed or unknown PATCH outcomes require human recovery, never retry.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity,
    _labels,
    build_capsule_namespace_handoff_patch,
    build_capsule_related_metadata_handoff_patch,
    capsule_preservation_digest,
    classify_capsule_related_metadata_readback,
    verify_capsule_namespace_preview,
    verify_capsule_related_metadata_preview,
)
from app.kubernetes.tenant.capsule_handoff_recovery import (
    capture_capsule_namespace_baseline,
    classify_capsule_namespace_handoff,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    classify_capsule_related_resource,
)

_CONTENT_TYPE = 'application/json-patch+json'

# Non-configurable hold. Never infer authority from source preview, a caller
# flag, an AuditEvent or a self-declared "start_committed" value.
_CAPSULE_LIVE_PATCH_ENABLED = False


def _provider_methods(
    *, core: Any, rbac: Any, kind: str,
) -> tuple[Any, Any]:
    if kind == 'Namespace':
        return core.read_namespace, core.patch_namespace
    if kind == 'ResourceQuota':
        return core.read_namespaced_resource_quota, core.patch_namespaced_resource_quota
    if kind == 'LimitRange':
        return core.read_namespaced_limit_range, core.patch_namespaced_limit_range
    if kind == 'RoleBinding':
        return rbac.read_namespaced_role_binding, rbac.patch_namespaced_role_binding
    raise ValueError('Capsule live metadata transfer does not support this provider kind.')


def _provider_read(
    read: Any, *, kind: str, name: str, namespace: str,
) -> Any:
    if kind == 'Namespace':
        return read(name=name, _request_timeout=5)
    return read(name=name, namespace=namespace, _request_timeout=5)


def _provider_patch(
    patch: Any, *, kind: str, name: str, namespace: str,
    body: list[dict[str, Any]], dry_run: bool,
) -> Any:
    args: dict[str, Any] = {
        'name': name, 'body': body, '_content_type': _CONTENT_TYPE,
        '_request_timeout': 5,
    }
    if kind != 'Namespace':
        args['namespace'] = namespace
    if dry_run:
        args['dry_run'] = 'All'
    # JSON Patch carries exact test ops for UID, resourceVersion and full
    # original labels. No force, replace, delete, create or spec mutation.
    return patch(**args)


def _require_source_still_unchanged(
    *, kind: str, before: Any, current: Any,
    record: Mapping[str, Any], tenant_id: str,
    capsule_name: str, capsule_uid: str,
) -> None:
    if kind == 'Namespace':
        if (
            _identity(before) != _identity(current)
            or _labels(before) != _labels(current)
            or capsule_preservation_digest(before) != capsule_preservation_digest(current)
        ):
            raise ValueError('Capsule Namespace changed during live dry-run; abort PATCH.')
        return
    prior, problems = classify_capsule_related_resource(
        resource=before, kind=kind, namespace=record['namespace'],
        tenant_id=tenant_id, capsule_name=capsule_name,
        capsule_uid=capsule_uid,
    )
    live, live_problems = classify_capsule_related_resource(
        resource=current, kind=kind, namespace=record['namespace'],
        tenant_id=tenant_id, capsule_name=capsule_name,
        capsule_uid=capsule_uid,
    )
    if prior != dict(record) or live != prior or live_problems != problems:
        raise ValueError('Capsule related provider identity, policy or owner changed before PATCH.')


def execute_capsule_single_metadata_patch_staged(
    *, core: Any, rbac: Any, component: Mapping[str, Any],
    tenant_id: str, capsule_name: str, capsule_uid: str,
    successor_owner: str, related_record: Mapping[str, Any] | None = None,
    consented_label_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Preview, conditionally PATCH once and re-read exactly one resource.

    Never enabled. Future caller must *independently* verify installed
    PostgreSQL write-once START, X.509 identity, resource-specific actor
    consent, controller provenance and complete canonical worklist BEFORE
    invoking a batch; this adapter intentionally cannot assert those gates.
    A failure after live PATCH is an UNKNOWN outcome, not a retry signal.
    """
    if not _CAPSULE_LIVE_PATCH_ENABLED:
        raise PermissionError(
            'Capsule live metadata PATCH is disabled pending durable START, '
            'independent per-resource consent and authorized provider UAT.'
        )
    if (
        not isinstance(component, Mapping)
        or component.get('kind') not in (
            'Namespace', 'ResourceQuota', 'LimitRange', 'RoleBinding',
        )
        or not all(
            isinstance(component.get(key), str) and component[key]
            for key in ('kind', 'name', 'uid', 'resource_version')
        )
        or not isinstance(tenant_id, str) or not tenant_id
        or not isinstance(capsule_name, str) or not capsule_name
        or not isinstance(capsule_uid, str) or not capsule_uid
    ):
        raise ValueError('Capsule live PATCH has no complete approved object identity.')

    kind, name = component['kind'], component['name']
    namespace = component.get('namespace') or ''
    if kind == 'Namespace':
        if namespace != name or related_record is not None or consented_label_keys is not None:
            raise ValueError('Capsule Namespace PATCH may not inherit related-resource consent.')
    elif (
        not isinstance(namespace, str) or not namespace
        or not isinstance(related_record, Mapping)
        or related_record.get('namespace') != namespace
        or related_record.get('kind') != kind
        or related_record.get('name') != name
        or related_record.get('uid') != component['uid']
        or related_record.get('resource_version') != component['resource_version']
        or not isinstance(consented_label_keys, list)
    ):
        raise ValueError('Capsule related PATCH requires the exact consented inventory row.')
    read, patch = _provider_methods(core=core, rbac=rbac, kind=kind)
    before = _provider_read(read, kind=kind, name=name, namespace=namespace)
    if kind == 'Namespace':
        baseline = capture_capsule_namespace_baseline(
            component, before, tenant_id=tenant_id, capsule_tenant_name=capsule_name,
        )
        operations = build_capsule_namespace_handoff_patch(
            component, before, tenant_id=tenant_id,
            capsule_tenant_name=capsule_name,
            verified_successor_owner=successor_owner,
        )
        preview = _provider_patch(
            patch, kind=kind, name=name, namespace=namespace,
            body=operations, dry_run=True,
        )
        verify_capsule_namespace_preview(
            before=before, preview=preview, successor_owner=successor_owner,
        )
    else:
        operations = build_capsule_related_metadata_handoff_patch(
            record=related_record, before=before, kind=kind,
            namespace=namespace, tenant_id=tenant_id,
            capsule_name=capsule_name, capsule_uid=capsule_uid,
            successor_owner=successor_owner,
            approved_label_keys=consented_label_keys,
        )
        preview = _provider_patch(
            patch, kind=kind, name=name, namespace=namespace,
            body=operations, dry_run=True,
        )
        verify_capsule_related_metadata_preview(
            record=related_record, before=before, preview=preview,
            kind=kind, namespace=namespace, tenant_id=tenant_id,
            capsule_name=capsule_name, capsule_uid=capsule_uid,
            successor_owner=successor_owner,
            approved_label_keys=consented_label_keys,
        )

    # First compare-and-swap is from the approved source identity, second
    # provider read proves that server dry-run did not mutate anything.
    unchanged = _provider_read(read, kind=kind, name=name, namespace=namespace)
    _require_source_still_unchanged(
        kind=kind, before=before, current=unchanged,
        record=related_record if kind != 'Namespace' else component,
        tenant_id=tenant_id, capsule_name=capsule_name, capsule_uid=capsule_uid,
    )

    # No retries: if the provider times out here, an external reviewer must
    # re-observe live objects and reconcile the immutable START history.
    _provider_patch(
        patch, kind=kind, name=name, namespace=namespace,
        body=operations, dry_run=False,
    )
    after = _provider_read(read, kind=kind, name=name, namespace=namespace)
    if kind == 'Namespace':
        result = classify_capsule_namespace_handoff(
            baseline=baseline, current=after,
            tenant_id=tenant_id, successor_owner=successor_owner,
        )
    else:
        result = classify_capsule_related_metadata_readback(
            record=related_record, before=before, current=after,
            kind=kind, namespace=namespace, tenant_id=tenant_id,
            capsule_name=capsule_name, capsule_uid=capsule_uid,
            successor_owner=successor_owner,
            approved_label_keys=consented_label_keys,
        )
    if result.get('state') != 'provider_markers_transferred':
        raise ValueError('Capsule post-PATCH read-back is incomplete: operator recovery required.')
    return {
        'kind': kind, 'namespace': namespace, 'name': name,
        'uid': component['uid'],
        'source_resource_version': component['resource_version'],
        'observed_resource_version': result['resource_version'],
        'status': 'single_object_metadata_transfer_observed_not_full_handoff',
        'provider_mutation_performed': True,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'auto_retry_authorized': False,
    }
