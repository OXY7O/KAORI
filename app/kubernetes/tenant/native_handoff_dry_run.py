"""Preview exact Native Kubernetes ownership-marker handoff without persistence.

Kubernetes dryRun=All verifies admission and permissions; the external provider
continues to own actual state. This module has NO non-dry-run mutating path.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan,
    _checked_recently,
    _plan_hash,
    latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import review_tenant_release_preflight_committed
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_native_handoff_dry_run'
_CONTENT_TYPE = 'application/json-patch+json'
_MARKER_KEYS = (
    'app.kubernetes.io/managed-by',
    'kaori.io/tenant-id',
    'kaori.io/environment',
    'kaori.io/profile-id',
)
_MAX_COMPONENTS = 100


def _read(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


def _metadata(resource: Any) -> Any:
    return _read(resource, 'metadata')


def _resource_metadata(resource: Any) -> tuple[str, str, str, dict[str, str]]:
    meta = _metadata(resource)
    name = str(_read(meta, 'name') or '')
    uid = str(_read(meta, 'uid') or '')
    rv = str(_read(meta, 'resource_version') or _read(meta, 'resourceVersion') or '')
    labels = _read(meta, 'labels') or {}
    if not name or not uid or not rv or not isinstance(labels, Mapping):
        raise ValueError('Provider identity or ownership labels are unavailable.')
    return name, uid, rv, dict(labels)


def _label_path(name: str) -> str:
    return '/metadata/labels/' + name.replace('~', '~0').replace('/', '~1')


def build_native_handoff_patch(
    component: Mapping[str, str], resource: Any, *, tenant_id: str,
) -> list[dict[str, str]]:
    """Test immutable identity and owner labels, then remove ONLY KAORI markers.

    This is not evidence of external successor acceptance and does not touch
    quota/limit specs, other labels, annotations, RBAC or Namespace objects.
    """
    if component.get('handoff') != 'external_acceptance_required':
        raise ValueError('The selected provider component is not in the admitted handoff scope.')
    if component.get('ownership') != 'kaori_marker_correlated':
        raise ValueError('Ownership marker is not verified as belonging to the same KAORI Tenant.')
    name, uid, rv, labels = _resource_metadata(resource)
    if (
        name != component.get('name')
        or uid != component.get('uid')
        or rv != component.get('resource_version')
    ):
        raise ValueError('Provider UID/resourceVersion differs from approved handoff evidence.')
    if labels.get('app.kubernetes.io/managed-by') != 'kaori' or labels.get('kaori.io/tenant-id') != tenant_id:
        raise ValueError('Provider KAORI ownership labels do not match the approved Tenant.')

    ops = [
        {'op': 'test', 'path': '/metadata/uid', 'value': uid},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': rv},
        {'op': 'test', 'path': _label_path('app.kubernetes.io/managed-by'), 'value': 'kaori'},
        {'op': 'test', 'path': _label_path('kaori.io/tenant-id'), 'value': tenant_id},
    ]
    for key in _MARKER_KEYS:
        if key in labels:
            ops.append({'op': 'remove', 'path': _label_path(key)})
    if len(ops) < 6:
        raise ValueError('No correlated KAORI ownership markers remain to transfer.')
    return ops


def _read_resource(core: Any, component: Mapping[str, str]) -> Any:
    kind, name = component['kind'], component['name']
    namespace = component.get('namespace') or name
    if kind == 'Namespace':
        return core.read_namespace(name, _request_timeout=5)
    if kind == 'ResourceQuota':
        return core.read_namespaced_resource_quota(name, namespace, _request_timeout=5)
    if kind == 'LimitRange':
        return core.read_namespaced_limit_range(name, namespace, _request_timeout=5)
    raise ValueError('Capsule or unsupported provider resource is not eligible for Native dry-run.')


def _dry_run_patch(core: Any, component: Mapping[str, str], body: list[dict[str, str]]) -> Any:
    params = {
        'body': body, 'dry_run': 'All', '_content_type': _CONTENT_TYPE,
        '_request_timeout': 5,
    }
    kind, name = component['kind'], component['name']
    namespace = component.get('namespace') or name
    if kind == 'Namespace':
        return core.patch_namespace(name=name, **params)
    if kind == 'ResourceQuota':
        return core.patch_namespaced_resource_quota(name=name, namespace=namespace, **params)
    if kind == 'LimitRange':
        return core.patch_namespaced_limit_range(name=name, namespace=namespace, **params)
    raise ValueError('Unsupported provider handoff component.')


def _spec(resource: Any) -> Any:
    value = _read(resource, 'spec')
    return value.to_dict() if hasattr(value, 'to_dict') else value


def dry_run_native_handoff_component(
    core: Any, component: Mapping[str, str], *, tenant_id: str,
) -> dict[str, Any]:
    """Server-side dry-run + returned-spec and unchanged-live-state verification."""
    before = _read_resource(core, component)
    before_identity = _resource_metadata(before)
    patch = build_native_handoff_patch(component, before, tenant_id=tenant_id)
    preview = _dry_run_patch(core, component, patch)
    after_name, after_uid, _, after_labels = _resource_metadata(preview)
    if (after_name, after_uid) != before_identity[:2]:
        raise ValueError('Dry-run unexpectedly changed provider immutable identity.')
    if any(key in after_labels for key in _MARKER_KEYS):
        raise ValueError('Dry-run did not remove all KAORI ownership markers.')
    if _spec(before) != _spec(preview):
        raise ValueError('Dry-run changed Kubernetes spec; ownership handoff is blocked.')
    expected_labels = {
        key: value for key, value in before_identity[3].items()
        if key not in _MARKER_KEYS
    }
    if after_labels != expected_labels:
        raise ValueError('Dry-run changed unrelated Kubernetes labels; handoff is blocked.')
    before_annotations = _read(_metadata(before), 'annotations') or {}
    preview_annotations = _read(_metadata(preview), 'annotations') or {}
    if before_annotations != preview_annotations:
        raise ValueError('Dry-run changed provider annotations; ownership handoff is blocked.')

    live = _read_resource(core, component)
    if (
        _resource_metadata(live) != before_identity
        or _spec(live) != _spec(before)
        or (_read(_metadata(live), 'annotations') or {}) != before_annotations
    ):
        raise ValueError('Kubernetes live state changed during dry-run verification.')
    return {
        'namespace': component.get('namespace'),
        'kind': component['kind'], 'name': component['name'],
        'uid': component['uid'], 'resource_version': component['resource_version'],
        'operation': 'metadata_only_json_patch_dry_run',
        'dry_run': True,
        'spec_unchanged': True,
        'live_provider_unchanged': True,
        'label_keys_to_release': [
            key for key in _MARKER_KEYS if key in before_identity[3]
        ],
    }


def dry_run_native_release_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
) -> dict[str, Any]:
    """Execute ONLY Kubernetes dry-run calls after independent approval."""
    plan = latest_release_handoff_plan(tenant_id)
    approved = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approved
        or plan.get('tenant_id') != tenant_id
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or approved.get('plan_sha256') != plan_sha256
        or approved.get('status') != 'acknowledged_pending_provider_handoff'
        or approved.get('approved_by') == actor_user_id
        or not _checked_recently(approved.get('approved_at'))
    ):
        raise ValueError('Current, independently approved handoff plan is required.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'native_kubernetes'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.ownership_status != 'adopted'
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Only the exact approved Native adopted Tenant is eligible.')
    # Preflight is an explicitly authorized live read that commits new evidence.
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id
    )
    _can_confirm_plan(fresh)
    if (
        fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
    ):
        raise ValueError('Provider ownership evidence changed after independent approval.')
    components = fresh['handoff_components']
    if len(components) > _MAX_COMPONENTS:
        raise ValueError('Native transfer scope is too large for a bounded dry-run.')
    selected = [
        item for item in components
        if item.get('handoff') == 'external_acceptance_required'
    ]
    if not selected or any(item.get('ownership') != 'kaori_marker_correlated' for item in selected):
        raise ValueError('Native handoff requires exact KAORI-correlated ownership evidence.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Canonical Native Kubernetes cluster is unavailable.')
    core = runtime_adapter.build_client(cluster).core_api()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for component in selected:
        try:
            results.append(
                dry_run_native_handoff_component(core, component, tenant_id=tenant_id)
            )
        except Exception as exc:
            # Failed preview must still commit partial diagnostic evidence.
            errors.append(f"{component['kind']}/{component['name']}: {type(exc).__name__}")
            break
    status = 'dry_run_passed' if not errors and len(results) == len(selected) else 'dry_run_failed'
    receipt = {
        'status': status, 'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': fresh['handoff_fingerprint'],
        'previewed_components': results, 'expected_component_count': len(selected),
        'errors': errors, 'checked_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': False, 'provider_handoff_verified': False,
        'release_authorized': False, 'dry_run_only': True,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action=f'tenant.release.native_handoff.{status}',
        summary='Native provider handoff dry-run; no provider mutation persisted.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
