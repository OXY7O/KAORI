"""Read-only cluster-scoped quota and Capsule RBAC lineage evidence (#1229).

Candidate provenance never authorizes mutation, handoff, retry, or Released.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kubernetes.client.rest import ApiException

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _canonical_value,
    _digest,
    _owner_refs,
    _role_contract_sha256,
    _strings,
)

_VERSIONS = ('v1beta2', 'v1beta1')
_MAX_GLOBAL_QUOTAS = 100
_MAX_BINDINGS = 100
_KAORI_MANAGER = 'app.kubernetes.io/managed-by'
_GRANT_ID = 'kaori.io/access-grant'
_TENANT_ID = 'kaori.io/tenant-id'
_NAMESPACE_KEY = 'kubernetes.io/metadata.name'


def _bounded_custom_list(custom: Any) -> tuple[str, dict[str, Any]]:
    """Enumerate one served Capsule globalquota version, never a partial LIST."""
    for version in _VERSIONS:
        try:
            response = custom.list_cluster_custom_object(
                'capsule.clastix.io',
                version,
                'globalresourcequotas',
                limit=_MAX_GLOBAL_QUOTAS + 1,
                _request_timeout=5,
            )
        except ApiException as exc:
            if exc.status == 404:
                continue
            raise
        if not isinstance(response, Mapping):
            raise ValueError('Capsule global quota provider returned malformed LIST.')
        meta = response.get('metadata')
        if not isinstance(meta, Mapping):
            raise ValueError('Capsule global quota LIST metadata is missing.')
        rv = meta.get('resourceVersion')
        items = response.get('items')
        if (
            not isinstance(rv, str)
            or not rv
            or meta.get('continue')
            or meta.get('remainingItemCount')
            or not isinstance(items, list)
            or len(items) > _MAX_GLOBAL_QUOTAS
        ):
            raise ValueError('Capsule global quota list is incomplete or unbounded.')
        return version, dict(response)
    raise ValueError('Capsule global quota API is not available on supported versions.')


def _quota_selector_scope(spec: Mapping[str, Any], tenant_name: str) -> tuple[str, list[str]]:
    selectors = spec.get('namespaceSelectors')
    if not isinstance(selectors, list) or not selectors or len(selectors) > 30:
        return 'unverified_selector', ['Capsule global quota namespaceSelectors cannot be proven.']
    matched = False
    unknown = False
    for selector in selectors:
        if not isinstance(selector, Mapping):
            unknown = True
            continue
        labels = selector.get('matchLabels')
        expressions = selector.get('matchExpressions')
        if (
            not isinstance(labels, Mapping)
            or expressions not in (None, [])
            or any(not isinstance(key, str) or not isinstance(val, str) for key, val in labels.items())
        ):
            unknown = True
            continue
        tenant_labels = [(key, labels[key]) for key in _CAPSULE_TENANT_LABEL_KEYS if key in labels]
        if len(tenant_labels) != 1 or len(labels) != 1:
            unknown = True
            continue
        if tenant_labels[0][1] == tenant_name:
            matched = True
    if unknown:
        return 'unverified_selector', ['Capsule global quota selector scope may include the target Tenant.']
    return ('direct_tenant_selector' if matched else 'other_tenant_selector'), []


def observe_capsule_global_quotas(*, custom: Any, tenant_name: str) -> dict[str, Any]:
    """Digest entire bounded cluster-level quota LIST and classify targeted CRs."""
    if not isinstance(tenant_name, str) or not tenant_name:
        raise ValueError('Exact Capsule Tenant name is required for global quota inspection.')
    version, payload = _bounded_custom_list(custom)
    resources: list[dict[str, str]] = []
    blockers: list[str] = []
    seen: set[str] = set()
    for item in payload['items']:
        if not isinstance(item, Mapping):
            raise ValueError('Capsule global quota object is malformed.')
        meta, spec = item.get('metadata'), item.get('spec')
        if not isinstance(meta, Mapping) or not isinstance(spec, Mapping):
            raise ValueError('Capsule global quota spec/metadata is incomplete.')
        name, uid, rv = meta.get('name'), meta.get('uid'), meta.get('resourceVersion')
        if not all(isinstance(value, str) and value for value in (name, uid, rv)) or name in seen:
            raise ValueError('Capsule global quota identity is missing or duplicated.')
        name, uid, rv = str(name), str(uid), str(rv)
        seen.add(name)
        labels = _strings(meta.get('labels'), label='global quota labels')
        annotations = _strings(meta.get('annotations'), label='global quota annotations')
        owners = _owner_refs(meta)
        source = _canonical_value(spec)
        sha = _digest(source)
        scope, issues = _quota_selector_scope(spec, tenant_name)
        blockers.extend(issues)
        if scope == 'direct_tenant_selector' and (
            labels.get(_KAORI_MANAGER) == 'kaori' or any(key.startswith('kaori.io/') for key in labels)
        ):
            blockers.append(
                f'Capsule GlobalResourceQuota/{name} retains KAORI labels; independent scope review is required.'
            )
        resources.append(
            {
                'kind': 'GlobalResourceQuota',
                'name': name,
                'uid': uid,
                'resource_version': rv,
                'api_version': version,
                'scope': scope,
                'policy_sha256': sha,
                'metadata_sha256': _digest(
                    {
                        'labels': labels,
                        'annotations': annotations,
                        'ownerReferences': owners,
                        'finalizers': meta.get('finalizers') or [],
                    }
                ),
            }
        )
    resources.sort(key=lambda x: x['name'])
    return {
        'status': 'observed_not_handoff_authorized',
        'served_version': version,
        'list_resource_version': payload['metadata']['resourceVersion'],
        'resources': resources,
        'count': len(resources),
        # Collection LIST RV is evidence of complete/current LIST, but it
        # may advance without changing a single relevant GlobalResourceQuota.
        # Bind each object UID/RV and complete policy/metadata SHA instead.
        'scope_sha256': _digest(
            {
                'api_version': version,
                'resources': resources,
            }
        ),
        'blockers': sorted(set(blockers)),
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
    }


def _expected_scopes(selector: Any, namespaces: set[str]) -> set[str]:
    """Only the exact supported Namespace-name In selector can be normalized."""
    if not isinstance(selector, Mapping) or set(selector) != {'matchExpressions'}:
        raise ValueError('Capsule RBAC selector is not an exact Namespace-name scope.')
    expressions = selector.get('matchExpressions')
    if not isinstance(expressions, list) or len(expressions) != 1:
        raise ValueError('Capsule RBAC selector expression shape is unsupported.')
    entry = expressions[0]
    if (
        not isinstance(entry, Mapping)
        or set(entry) != {'key', 'operator', 'values'}
        or entry.get('key') != _NAMESPACE_KEY
        or entry.get('operator') != 'In'
        or not isinstance(entry.get('values'), list)
        or not entry['values']
        or len(entry['values']) > len(namespaces)
        or any(not isinstance(item, str) or not item for item in entry['values'])
    ):
        raise ValueError('Capsule RBAC selector contains unbounded/unsupported namespace values.')
    values = set(entry['values'])
    if len(values) != len(entry['values']) or not values.issubset(namespaces):
        raise ValueError('Capsule RBAC selector targets unknown/duplicated Namespaces.')
    return values


def _intent_bindings(
    spec: Mapping[str, Any],
    namespaces: set[str],
    *,
    tenant_id: str,
) -> tuple[dict[str, str], list[str]]:
    if not isinstance(tenant_id, str) or not tenant_id:
        raise ValueError('Capsule RBAC intent requires the exact KAORI Tenant identity.')
    intents: dict[str, str] = {}
    blockers: list[str] = []
    additional = spec.get('additionalRoleBindings', [])
    rules = spec.get('rules', [])
    if not isinstance(additional, list) or not isinstance(rules, list):
        raise ValueError('Capsule RBAC spec bindings are malformed.')
    if len(additional) + len(rules) > _MAX_BINDINGS:
        raise ValueError('Capsule RBAC spec binding inventory exceeds bounds.')
    for binding in additional:
        if not isinstance(binding, Mapping):
            raise ValueError('Capsule additionalRoleBindings contains malformed entry.')
        labels = _strings(binding.get('labels'), label='Capsule spec RoleBinding labels')
        if labels.get(_KAORI_MANAGER) == 'kaori' or _GRANT_ID in labels:
            blockers.append('Unbounded KAORI Capsule additionalRoleBindings cannot authorize successor handoff.')
    for rule in rules:
        if not isinstance(rule, Mapping):
            raise ValueError('Capsule RBAC rule is malformed.')
        permissions = rule.get('permissions') or {}
        if not isinstance(permissions, Mapping):
            raise ValueError('Capsule RBAC permissions are malformed.')
        entries = permissions.get('bindings', [])
        if not isinstance(entries, list) or len(entries) > _MAX_BINDINGS:
            raise ValueError('Capsule RBAC rule binding list is invalid.')
        if not entries:
            continue
        scope = _expected_scopes(rule.get('namespaceSelector'), namespaces)
        for binding in entries:
            if not isinstance(binding, Mapping):
                raise ValueError('Capsule RBAC spec binding is malformed.')
            labels = _strings(binding.get('labels'), label='Capsule spec RBAC labels')
            claims_kaori = labels.get(_KAORI_MANAGER) == 'kaori' or any(key.startswith('kaori.io/') for key in labels)
            if not claims_kaori:
                continue  # Pure Capsule/external intent; preserve without transfer.
            if (
                labels.get(_KAORI_MANAGER) != 'kaori'
                or not isinstance(labels.get(_GRANT_ID), str)
                or not labels[_GRANT_ID]
                or labels.get(_TENANT_ID) != tenant_id
                or any(key.startswith('kaori.io/') and key not in (_GRANT_ID, _TENANT_ID) for key in labels)
            ):
                blockers.append('Capsule RoleBinding intent has foreign, partial or unknown KAORI ownership.')
                continue
            signature = _role_contract_sha256(
                role=binding.get('clusterRoleName'),
                subjects=binding.get('subjects'),
                grant=labels[_GRANT_ID],
                tenant=labels[_TENANT_ID],
            )
            for ns in scope:
                key = _digest({'namespace': ns, 'grant': labels[_GRANT_ID]})
                if key in intents:
                    raise ValueError('Duplicate KAORI Capsule RBAC intent contract.')
                intents[key] = signature
                if len(intents) > _MAX_BINDINGS:
                    raise ValueError('Capsule RBAC effective binding scope is unbounded.')
    return intents, blockers


def _require_exact_namespaces(names: set[Any], namespaces: list[dict[str, Any]]) -> None:
    """Reject incomplete Namespace identity before correlating RBAC contracts."""
    if len(names) != len(namespaces) or not all(isinstance(ns, str) and ns for ns in names):
        raise ValueError('Capsule RBAC lineage Namespace identity is incomplete.')


def inspect_capsule_role_binding_lineage(
    *,
    capsule_spec: Any,
    related: Mapping[str, Any],
    namespaces: list[dict[str, Any]],
    tenant_id: str,
) -> dict[str, Any]:
    """Compare intent-vs-effective digest; never infer controller causality.

    Even an exact roleRef+subjects match does NOT verify the creating controller.
    """
    if (
        not isinstance(capsule_spec, Mapping)
        or not isinstance(related, Mapping)
        or not isinstance(namespaces, list)
        or not namespaces
        or len(namespaces) > 30
        or not isinstance(tenant_id, str)
        or not tenant_id
    ):
        raise ValueError('Capsule RBAC lineage requires exact bounded provider scope.')
    ns_set = {item.get('name') for item in namespaces if isinstance(item, Mapping)}
    _require_exact_namespaces(ns_set, namespaces)
    intents, blockers = _intent_bindings(capsule_spec, {str(ns) for ns in ns_set}, tenant_id=tenant_id)
    resources = related.get('resources')
    if not isinstance(resources, list) or len(resources) > 300:
        raise ValueError('Capsule related RBAC inventory is incomplete.')
    observed: dict[str, str] = {}
    for item in resources:
        if not isinstance(item, Mapping):
            raise ValueError('Capsule RBAC observed object is malformed.')
        if item.get('kind') != 'RoleBinding':
            continue
        if item.get('origin') == 'ambiguous_kaori':
            blockers.append('Capsule effective RoleBinding has ambiguous or foreign KAORI ownership.')
            continue
        if item.get('origin') != 'kaori_correlated':
            continue
        ns, combined = item.get('namespace'), item.get('grant_scope_sha256')
        if not isinstance(ns, str) or ns not in ns_set or not isinstance(combined, str) or len(combined) != 64:
            raise ValueError('Capsule KAORI RoleBinding has an unverifiable grant identity.')
        if combined in observed:
            raise ValueError('Duplicate effective KAORI Capsule RBAC grant.')
        signature = item.get('binding_contract_sha256')
        if not isinstance(signature, str) or len(signature) != 64:
            raise ValueError('Capsule KAORI binding policy digest is unavailable.')
        observed[combined] = signature
    for key in sorted(set(intents) | set(observed)):
        if intents.get(key) != observed.get(key):
            blockers.append('Capsule KAORI Access Grant contract differs from effective RoleBinding.')
    return {
        'status': 'contract_correlated_controller_origin_unverified',
        'intent_count': len(intents),
        'effective_kaori_count': len(observed),
        'lineage_sha256': _digest({'intents': sorted(intents.items()), 'observed': sorted(observed.items())}),
        'contract_correlated': not blockers,
        'controller_origin_verified': False,
        'blockers': sorted(set(blockers)),
        'provider_mutation_performed': False,
        'release_authorized': False,
    }
