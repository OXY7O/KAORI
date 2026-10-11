"""Bounded read-only Capsule-adjacent governance inventory for Release #1229.

Enumerates scoped ResourceQuota, LimitRange and RoleBinding without PATCH. It
records hashes, identities and origins, never raw policy, subjects or secrets.
This is *evidence*, not proof of successful handoff or consent.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS

_MAX_NS = 30
_PAGE_SIZE = 101
_MAX_PER_NS = 100
_MAX_TOTAL = 300
_MAX_HASH_BYTES = 262_144
_KINDS = ('ResourceQuota', 'LimitRange', 'RoleBinding')
_KAORI_MARKERS = frozenset({
    'kaori.io/tenant-id', 'kaori.io/environment', 'kaori.io/resource-profile',
    'kaori.io/tenant-generation', 'kaori.io/profile-id',
    'kaori.io/access-grant',
})


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _canonical(value: Any) -> bytes:
    if hasattr(value, 'to_dict'):
        value = value.to_dict()
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError('Provider inventory has unsupported mapping keys.')
        value = {key: _canonical_value(item) for key, item in value.items()}
    else:
        value = _canonical_value(value)
    try:
        rendered = json.dumps(
            value, sort_keys=True, ensure_ascii=True,
            separators=(',', ':'), allow_nan=False,
        ).encode()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Provider inventory has noncanonical policy data.') from exc
    if len(rendered) > _MAX_HASH_BYTES:
        raise ValueError('Provider inventory object exceeds maximum digest input.')
    return rendered


def _canonical_value(value: Any) -> Any:
    if hasattr(value, 'to_dict'):
        return _canonical_value(value.to_dict())
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError('Provider inventory has malformed policy map.')
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise ValueError('Provider inventory contains unsupported policy data.')


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def capsule_related_scope_sha256(
    *, resources: list[dict[str, str]],
    list_snapshots: list[dict[str, str | int]],
) -> str:
    """SHA-bind exact objects and bounded LIST coverage, not volatile LIST RV.

    Each LIST must first be complete, versioned, non-paginated and bounded.
    That LIST resourceVersion stays committed for provenance, but Kubernetes
    may increment the collection RV without changing any relevant object.
    Individual resource UID/RV, policy and metadata hashes remain included.
    """
    scopes: list[dict[str, str | int]] = []
    for row in list_snapshots:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get('list_resource_version'), str)
            or not row['list_resource_version']
            or not isinstance(row.get('namespace'), str) or not row['namespace']
            or row.get('kind') not in _KINDS
            or type(row.get('count')) is not int
            or not 0 <= row['count'] <= _MAX_PER_NS
        ):
            raise ValueError('Capsule scope digest requires complete versioned LIST coverage.')
        scopes.append({
            'namespace': row['namespace'], 'kind': row['kind'],
            'count': row['count'],
        })
    if (
        not isinstance(resources, list) or len(resources) > _MAX_TOTAL
        or len(scopes) > _MAX_NS * len(_KINDS)
    ):
        raise ValueError('Capsule scope digest exceeds bounded resource coverage.')
    return _digest({'resources': resources, 'lists': scopes})


def capsule_related_scope_unchanged(before: Any, after: Any) -> bool:
    """Match *all* whole-scope evidence except collection LIST revisions.

    Only raw LIST RV values are excluded. This does not waive a missing LIST,
    any changed object UID/resourceVersion/spec/metadata, governance warning,
    GlobalResourceQuota scope digest, or RBAC lineage.
    """
    def stable_copy(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, Mapping):
            return None
        scopes = value.get('list_snapshots')
        quota = value.get('global_quota')
        if not isinstance(scopes, list) or not isinstance(quota, Mapping):
            return None
        if not isinstance(quota.get('list_resource_version'), str) or not quota['list_resource_version']:
            return None
        clean_scopes: list[dict[str, Any]] = []
        for scope in scopes:
            if (
                not isinstance(scope, Mapping)
                or not isinstance(scope.get('list_resource_version'), str)
                or not scope['list_resource_version']
            ):
                return None
            clean_scopes.append({
                key: item for key, item in scope.items()
                if key != 'list_resource_version'
            })
        return {
            **value,
            'list_snapshots': clean_scopes,
            'global_quota': {
                key: item for key, item in quota.items()
                if key != 'list_resource_version'
            },
        }
    prior, current = stable_copy(before), stable_copy(after)
    return prior is not None and current is not None and prior == current


def _role_contract_sha256(*, role: Any, subjects: Any, grant: Any, tenant: Any) -> str:
    """Hash only the exact Capsule access contract, never persist principals."""
    if not all(isinstance(val, str) and val for val in (role, grant, tenant)):
        raise ValueError('Capsule RBAC contract is missing role, grant or Tenant identity.')
    if not isinstance(subjects, (list, tuple)) or not 0 < len(subjects) <= 30:
        raise ValueError('Capsule RBAC contract subjects are unavailable or unbounded.')
    normalized: list[dict[str, str]] = []
    for item in subjects:
        kind, name = _get(item, 'kind'), _get(item, 'name')
        group = _get(item, 'api_group') or _get(item, 'apiGroup') or ''
        namespace = _get(item, 'namespace') or ''
        if (
            not isinstance(kind, str) or not kind or not isinstance(name, str) or not name
            or not isinstance(group, str) or not isinstance(namespace, str)
        ):
            raise ValueError('Capsule RoleBinding has malformed subject identity.')
        normalized.append({
            'kind': kind, 'name': name, 'api_group': group, 'namespace': namespace,
        })
    normalized.sort(key=lambda x: (x['kind'], x['name'], x['namespace'], x['api_group']))
    return _digest({
        'role': role, 'subjects': normalized, 'grant': grant, 'tenant': tenant,
    })


def _owner_refs(meta: Any) -> list[dict[str, Any]]:
    refs = _get(meta, 'owner_references')
    if refs is None:
        refs = _get(meta, 'ownerReferences')
    if refs is None:
        return []
    result = _canonical_value(refs)
    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
        raise ValueError('Provider ownerReferences must be a list of objects.')
    return result


def _strings(value: Any, *, label: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError(f'Provider {label} must be a string map.')
    return dict(value)


def _scope_identity(item: Any, *, namespace: str) -> tuple[str, str, str, Any]:
    meta = _get(item, 'metadata')
    name = _get(meta, 'name')
    uid = _get(meta, 'uid')
    rv = _get(meta, 'resource_version') or _get(meta, 'resourceVersion')
    scope = _get(meta, 'namespace')
    if (
        not all(isinstance(v, str) and v for v in (name, uid, rv))
        or scope not in (None, namespace)
    ):
        raise ValueError('Capsule-related resource lacks exact namespaced UID/resourceVersion.')
    return name, uid, rv, meta


def classify_capsule_related_resource(
    *, resource: Any, kind: str, namespace: str,
    tenant_id: str, capsule_name: str, capsule_uid: str,
) -> tuple[dict[str, str], list[str]]:
    """Correlate observed provenance, while preserving every foreign control."""
    if kind not in _KINDS or not namespace or not tenant_id or not capsule_name or not capsule_uid:
        raise ValueError('Capsule related inventory requires canonical provider scope.')
    name, uid, rv, meta = _scope_identity(resource, namespace=namespace)
    labels = _strings(_get(meta, 'labels'), label='labels')
    annotations = _strings(_get(meta, 'annotations'), label='annotations')
    refs = _owner_refs(meta)
    spec = _get(resource, 'spec') if kind != 'RoleBinding' else {
        'roleRef': _get(resource, 'role_ref') or _get(resource, 'roleRef'),
        'subjects': _get(resource, 'subjects'),
    }
    if spec is None or (kind == 'RoleBinding' and (
        spec['roleRef'] is None or not isinstance(spec['subjects'], (list, tuple))
    )):
        raise ValueError('Capsule-related provider policy is incomplete.')
    spec_sha256 = _digest(spec)
    metadata_sha256 = _digest({
        'labels': labels, 'annotations': annotations, 'ownerReferences': refs,
        'finalizers': _get(meta, 'finalizers') or [],
    })
    manager = labels.get('app.kubernetes.io/managed-by')
    kaori_id = labels.get('kaori.io/tenant-id')
    capsule_claims = {
        labels[k] for k in _CAPSULE_TENANT_LABEL_KEYS if k in labels
    }
    capsule_refs = [
        ref for ref in refs
        if ref.get('kind') == 'Tenant'
        and str(ref.get('apiVersion') or ref.get('api_version') or '').startswith('capsule.clastix.io/')
    ]
    capsule_ref_matches = bool(capsule_refs) and all(
        ref.get('name') == capsule_name and ref.get('uid') == capsule_uid
        for ref in capsule_refs
    )
    foreign_refs = [ref for ref in refs if ref not in capsule_refs]
    has_kaori_controls = manager == 'kaori' or any(
        key.startswith('kaori.io/') for key in labels
    )
    problems: list[str] = []
    # A KAORI management label never overrides Capsule membership or a
    # foreign ownerReference. Correlation must not hide competing authority.
    origin_conflict = bool(
        (capsule_claims and capsule_claims != {capsule_name})
        or (capsule_refs and not capsule_ref_matches)
        or foreign_refs
    )
    if origin_conflict:
        problems.append(f'Capsule {kind}/{namespace}/{name} has conflicting or unverified provider ownership.')
    if has_kaori_controls:
        if (
            origin_conflict
            or manager != 'kaori' or kaori_id != tenant_id
            or any(k.startswith('kaori.io/') and k not in _KAORI_MARKERS for k in labels)
            or (kind == 'RoleBinding' and not labels.get('kaori.io/access-grant'))
            or (kind != 'RoleBinding' and 'kaori.io/access-grant' in labels)
        ):
            origin = 'ambiguous_kaori'
            problems.append(f'Capsule {kind}/{namespace}/{name} KAORI ownership requires independent review.')
        else:
            origin = 'kaori_correlated'
            problems.append(f'Capsule {kind}/{namespace}/{name} retains KAORI provider controls requiring separately admitted handoff.')
    elif capsule_claims == {capsule_name} or capsule_ref_matches:
        origin = 'capsule_provider'
    elif isinstance(manager, str) and manager:
        origin = 'foreign_preserved'
    else:
        origin = 'unattributed'
        problems.append(f'Capsule {kind}/{namespace}/{name} ownership has no verifiable origin.')
    evidence = {
        'kind': kind, 'namespace': namespace, 'name': name,
        'uid': uid, 'resource_version': rv, 'origin': origin,
        'policy_sha256': spec_sha256, 'metadata_sha256': metadata_sha256,
        'mutation_authorized': 'false',
    }
    if kind == 'RoleBinding' and has_kaori_controls:
        grant = labels.get('kaori.io/access-grant')
        role_ref = _get(resource, 'role_ref') or _get(resource, 'roleRef')
        role = _get(role_ref, 'name')
        role_kind = _get(role_ref, 'kind')
        role_group = _get(role_ref, 'api_group') or _get(role_ref, 'apiGroup')
        if (
            not isinstance(grant, str) or not grant
            or role_kind != 'ClusterRole'
            or role_group != 'rbac.authorization.k8s.io'
            or not isinstance(role, str) or not role
            or kaori_id != tenant_id
        ):
            problems.append(f'Capsule RoleBinding/{namespace}/{name} origin contract is incomplete.')
        else:
            evidence['grant_scope_sha256'] = _digest({'namespace': namespace, 'grant': grant})
            evidence['binding_contract_sha256'] = _role_contract_sha256(
                role=role, subjects=_get(resource, 'subjects'),
                grant=grant, tenant=tenant_id,
            )
    return evidence, problems


def _listing(api: Any, *, kind: str, namespace: str) -> tuple[list[Any], str]:
    # CoreV1Api only exposes quota/limit operations, while RoleBinding LIST
    # belongs to RbacAuthorizationV1Api. Never eagerly resolve all attributes:
    # doing so raises AttributeError even for a fully authorized API client.
    method_name = {
        'ResourceQuota': 'list_namespaced_resource_quota',
        'LimitRange': 'list_namespaced_limit_range',
        'RoleBinding': 'list_namespaced_role_binding',
    }[kind]
    method = getattr(api, method_name)
    response = method(namespace, limit=_PAGE_SIZE, _request_timeout=5)
    meta = _get(response, 'metadata')
    if _get(meta, '_continue') or _get(meta, 'continue'):
        raise ValueError('Capsule inventory returned a paginated partial resource list.')
    list_rv = _get(meta, 'resource_version') or _get(meta, 'resourceVersion')
    if not isinstance(list_rv, str) or not list_rv:
        raise ValueError('Capsule inventory list has no authoritative resourceVersion.')
    items = _get(response, 'items')
    if not isinstance(items, list) or len(items) > _MAX_PER_NS:
        raise ValueError('Capsule inventory list is unavailable, partial or too large.')
    return items, list_rv


def observe_capsule_related_inventory(
    *, core: Any, rbac: Any, namespace_components: list[dict[str, Any]],
    tenant_id: str, capsule_name: str, capsule_uid: str,
) -> dict[str, Any]:
    """Read the complete bounded namespaced source lists; no provider writes.

    This does not discover cluster-scoped shared quota objects or prove Capsule
    controller-translated RoleBinding lineage. These are separate admission gates.
    """
    if (
        not isinstance(namespace_components, list)
        or not 0 < len(namespace_components) <= _MAX_NS
        or any(
            not isinstance(row, Mapping) or row.get('kind') != 'Namespace'
            or row.get('authority') != 'capsule'
            or row.get('namespace') != row.get('name')
            or not isinstance(row.get('name'), str) or not row.get('name')
            or not isinstance(row.get('uid'), str) or not row.get('uid')
            or not isinstance(row.get('resource_version'), str) or not row.get('resource_version')
            for row in namespace_components
        )
    ):
        raise ValueError('Scoped Capsule Namespace set is not complete or bounded.')
    if len({row['name'] for row in namespace_components}) != len(namespace_components):
        raise ValueError('Duplicate Capsule Namespace scopes are not admissible.')
    rows: list[dict[str, str]] = []
    list_snapshots: list[dict[str, str | int]] = []
    blockers: list[str] = []
    for ns in namespace_components:
        for kind, api in (
            ('ResourceQuota', core), ('LimitRange', core), ('RoleBinding', rbac),
        ):
            observed, list_rv = _listing(api, kind=kind, namespace=ns['name'])
            list_snapshots.append({
                'namespace': ns['name'], 'kind': kind,
                'list_resource_version': list_rv, 'count': len(observed),
            })
            for item in observed:
                evidence, problems = classify_capsule_related_resource(
                    resource=item, kind=kind, namespace=ns['name'],
                    tenant_id=tenant_id, capsule_name=capsule_name,
                    capsule_uid=capsule_uid,
                )
                rows.append(evidence)
                blockers.extend(problems)
                if len(rows) > _MAX_TOTAL:
                    raise ValueError('Capsule related provider scope exceeds 300 resources.')
    unique_keys = {(row['namespace'], row['kind'], row['name']) for row in rows}
    if len(unique_keys) != len(rows):
        raise ValueError('Duplicate namespaced provider resources were observed.')
    rows.sort(key=lambda x: (x['namespace'], x['kind'], x['name']))
    list_snapshots.sort(key=lambda x: (str(x['namespace']), str(x['kind'])))
    return {
        'status': 'read_only_related_inventory',
        'resources': rows, 'resource_count': len(rows),
        'list_snapshots': list_snapshots,
        'resource_sha256': capsule_related_scope_sha256(
            resources=rows, list_snapshots=list_snapshots,
        ),
        'blockers': blockers,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'shared_quota_and_controller_origin_verified': False,
    }
