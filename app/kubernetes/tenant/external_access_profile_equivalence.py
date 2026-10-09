"""Read-only provider Role permission equivalence preview under #996.

An exact role permission match is necessary but NOT sufficient to import an
external identity or create a KAORI Access Grant. Kubernetes and IdP remain
authoritative. This inspection never writes Kubernetes or KAORI grants.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.access import ACCESS_PROFILE_CATALOG, get_access_profile
from app.kubernetes.tenant.external_access_observation import (
    latest_external_capsule_access_evidence,
    normalize_capsule_access_spec,
)
from app.kubernetes.tenant.external_native_access_observation import (
    latest_external_native_access_evidence,
    normalize_native_role_binding,
)
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant

_TARGET = 'kubernetes_tenant_external_role_profile_review'
_MAX_AGE_SECONDS = 900


def _value(obj: Any, key: str, alt: str = '') -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, obj.get(alt) if alt else None)
    return getattr(obj, key, getattr(obj, alt, None) if alt else None)


def _items(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f'Provider Role {field} is unavailable or unsupported.')
    results = tuple(str(item).strip() for item in value)
    if any(not item or item == '*' or len(item) > 253 for item in results):
        raise ValueError(f'Provider Role {field} contains unsupported wildcard/empty values.')
    return results


def _role_rules_signature(role: Any) -> tuple[tuple[str, str, str], ...]:
    """Reject non-resource/wildcard/conditioned rules; preserve exact privileges."""
    if _value(role, 'aggregation_rule', 'aggregationRule') is not None:
        raise ValueError('Aggregated ClusterRoles cannot be imported from a name alone.')
    rules = _value(role, 'rules')
    if not isinstance(rules, (list, tuple)) or not rules or len(rules) > 100:
        raise ValueError('Provider Role rule evidence is missing, malformed or unbounded.')
    atomics: set[tuple[str, str, str]] = set()
    for rule in rules:
        if (
            _value(rule, 'resource_names', 'resourceNames')
            or _value(rule, 'non_resource_urls', 'nonResourceURLs')
        ):
            raise ValueError('Conditioned or non-resource Role permissions need manual review.')
        api_groups = _value(rule, 'api_groups', 'apiGroups')
        resources = _items(_value(rule, 'resources'), field='resources')
        verbs = _items(_value(rule, 'verbs'), field='verbs')
        # Kubernetes core group is the empty string; wildcard groups fail.
        if not isinstance(api_groups, (list, tuple)) or not api_groups:
            raise ValueError('Role API groups are missing or unsupported.')
        if any(not isinstance(group, str) or group == '*' or len(group) > 253 for group in api_groups):
            raise ValueError('Role API groups are unsupported or wildcard.')
        atomics.update((api_group, resource, verb)
                       for api_group in api_groups for resource in resources for verb in verbs)
        if len(atomics) > 5000:
            raise ValueError('Role permission expansion exceeds bounded preview.')
    return tuple(sorted(atomics))


def _canonical_profile_signature(key: str, version: int) -> tuple[tuple[str, str, str], ...]:
    profile = get_access_profile(key, version)
    return tuple(sorted({
        (api_group, resource, verb)
        for rule in profile.rules
        for api_group in rule.api_groups
        for resource in rule.resources
        for verb in rule.verbs
    }))


def classify_external_role_profile(role: Any) -> dict[str, Any]:
    """Match exact canonical rules, never imply identity or effective RBAC proof."""
    meta = _value(role, 'metadata')
    kind = str(_value(role, 'kind') or '')
    name = str(_value(meta, 'name') or '')
    uid = str(_value(meta, 'uid') or '')
    resource_version = str(_value(meta, 'resource_version', 'resourceVersion') or '')
    if kind not in {'Role', 'ClusterRole'} or not name or not uid or not resource_version:
        raise ValueError('Provider Role kind/UID/resourceVersion is unavailable.')
    signature = _role_rules_signature(role)
    matches = [
        (key, version) for key, version in sorted(ACCESS_PROFILE_CATALOG)
        if signature == _canonical_profile_signature(key, version)
    ]
    digest = hashlib.sha256(json.dumps(signature, separators=(',', ':')).encode()).hexdigest()
    exact = matches[0] if len(matches) == 1 else None
    return {
        'role_kind': kind, 'role_name': name, 'role_uid': uid,
        'role_resource_version': resource_version,
        'permission_sha256': digest,
        'equivalent_profile': exact[0] if exact else None,
        'equivalent_version': exact[1] if exact else None,
        'decision': 'principal_and_scope_review_required' if exact else 'no_exact_profile',
        'effective_rbac_verified': False, 'identity_verified': False,
        'import_authorized': False, 'provider_mutation_performed': False,
    }


def _require_stable_role_review(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Fail closed if Role identity or effective rule signature changed mid-review."""
    for key in (
        'role_kind', 'role_name', 'role_uid', 'role_resource_version',
        'permission_sha256', 'equivalent_profile', 'equivalent_version',
    ):
        if before.get(key) != after.get(key):
            raise ValueError('Provider Role changed during exact permission review.')


def _require_committed_binding(
    evidence: dict[str, Any] | None, *, tenant: Tenant,
    namespace: str, binding_uid: str, now: datetime,
) -> tuple[dict[str, Any], dict[str, str]]:
    if (
        not evidence or evidence.get('tenant_id') != tenant.id
        or evidence.get('cluster_id') != tenant.cluster_id
        or evidence.get('provider') != 'native_kubernetes'
    ):
        raise ValueError('Inspect the canonical Native RBAC inventory first.')
    try:
        observed = datetime.fromisoformat(str(evidence.get('observed_at') or ''))
    except ValueError as exc:
        raise ValueError('Native RBAC inventory timestamp is invalid.') from exc
    age = (now - observed.astimezone(UTC)).total_seconds() if observed.tzinfo else -1
    if age < 0 or age > _MAX_AGE_SECONDS:
        raise ValueError('Native RBAC inventory expired; inspect again.')
    objects = evidence.get('bindings')
    namespaces = evidence.get('namespaces')
    if not isinstance(objects, list) or not isinstance(namespaces, list):
        raise ValueError('Native RBAC inventory is malformed.')
    matches = [
        binding for binding in objects
        if isinstance(binding, dict)
        and binding.get('namespace') == namespace and binding.get('uid') == binding_uid
        and binding.get('ownership') == 'external_observed'
    ]
    scope = [
        row for row in namespaces
        if isinstance(row, dict) and row.get('name') == namespace
        and row.get('uid') and row.get('resource_version')
    ]
    if len(matches) != 1 or len(scope) != 1:
        raise ValueError('Binding has no unique foreign-owned identity in committed Tenant scope.')
    return matches[0], scope[0]


def review_native_external_role_profile_committed(
    *, tenant_id: str, namespace: str, binding_uid: str, actor_user_id: int,
) -> dict[str, Any]:
    """Live authorized provider read and committed non-mutating review receipt."""
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.lifecycle_status != 'ready'
    ):
        raise ValueError('Choose a Ready Native Tenant with matching provider authority.')
    evidence = latest_external_native_access_evidence(tenant_id)
    selected, scope = _require_committed_binding(
        evidence, tenant=tenant, namespace=namespace,
        binding_uid=binding_uid, now=datetime.now(UTC),
    )
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Connected Native Kubernetes provider is unavailable.')
    client = runtime_adapter.build_client(cluster)
    core = client.core_api()
    rbac = client.rbac_authorization_api()

    observed_namespace = core.read_namespace(namespace, _request_timeout=5)
    ns_meta = getattr(observed_namespace, 'metadata', None)
    if (
        str(getattr(ns_meta, 'uid', '') or '') != scope['uid']
        or str(getattr(ns_meta, 'resource_version', '') or '') != scope['resource_version']
    ):
        raise ValueError('Namespace provider UID/resourceVersion changed; inspect again.')
    live = rbac.read_namespaced_role_binding(
        selected['name'], namespace, _request_timeout=5
    )
    normalized = normalize_native_role_binding(
        live, namespace=namespace, grant_ids=set()
    )
    if any(normalized.get(key) != selected.get(key) for key in (
        'namespace', 'name', 'uid', 'resource_version',
        'role_ref', 'subjects', 'ownership',
    )):
        raise ValueError('RoleBinding or principal changed since inventory.')
    ref = selected['role_ref']
    if ref['kind'] == 'Role':
        role = rbac.read_namespaced_role(ref['name'], namespace, _request_timeout=5)
    elif ref['kind'] == 'ClusterRole':
        role = rbac.read_cluster_role(ref['name'], _request_timeout=5)
    else:
        raise ValueError('Unsupported provider Role reference.')
    result = classify_external_role_profile(role)
    if (result['role_kind'], result['role_name']) != (ref['kind'], ref['name']):
        raise ValueError('Role UID or reference changed during the review.')
    reread = rbac.read_namespaced_role_binding(selected['name'], namespace, _request_timeout=5)
    verified = normalize_native_role_binding(
        reread, namespace=namespace, grant_ids=set()
    )
    if verified != normalized:
        raise ValueError('RoleBinding changed during permission review.')
    if ref['kind'] == 'Role':
        confirmed_role = rbac.read_namespaced_role(ref['name'], namespace, _request_timeout=5)
    else:
        confirmed_role = rbac.read_cluster_role(ref['name'], _request_timeout=5)
    _require_stable_role_review(result, classify_external_role_profile(confirmed_role))
    receipt = {
        **result,
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'provider': 'native_kubernetes',
        'namespace': namespace, 'binding_name': selected['name'],
        'binding_uid': selected['uid'],
        'binding_resource_version': selected['resource_version'],
        'subjects': selected['subjects'],
        'source_observed_at': evidence['observed_at'],
        'reviewed_at': datetime.now(UTC).isoformat(),
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.external_role.profile_reviewed',
        summary='Compared foreign Native Role rules to exact KAORI Access Profiles; no import.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt


def _require_committed_capsule_binding(
    evidence: dict[str, Any] | None, *, tenant: Tenant,
    binding_index: int, now: datetime,
) -> dict[str, Any]:
    """Index only a unique, foreign-owned Capsule binding from fresh evidence."""
    if (
        not evidence or evidence.get('provider') != 'capsule'
        or evidence.get('tenant_id') != tenant.id
        or evidence.get('cluster_id') != tenant.cluster_id
    ):
        raise ValueError('Inspect committed Capsule RBAC inventory first.')
    try:
        observed = datetime.fromisoformat(str(evidence.get('observed_at') or ''))
    except ValueError as exc:
        raise ValueError('Capsule RBAC inventory timestamp is invalid.') from exc
    age = (now - observed.astimezone(UTC)).total_seconds() if observed.tzinfo else -1
    if age < 0 or age > _MAX_AGE_SECONDS:
        raise ValueError('Capsule RBAC inventory expired; inspect again.')
    bindings = evidence.get('bindings')
    if (
        not isinstance(bindings, list) or type(binding_index) is not int
        or not 0 <= binding_index < min(len(bindings), 200)
    ):
        raise ValueError('Select one bounded observed Capsule binding.')
    item = bindings[binding_index]
    if (
        not isinstance(item, dict)
        or item.get('ownership') != 'external'
        or not item.get('cluster_role_name')
        or not isinstance(item.get('subjects'), list)
        or not item['subjects']
        or bindings.count(item) != 1
    ):
        raise ValueError('Capsule binding identity is foreign, unsupported or ambiguous.')
    return item


def review_capsule_external_role_profile_committed(
    *, tenant_id: str, binding_index: int, actor_user_id: int,
) -> dict[str, Any]:
    """Observe Capsule authoritative CR + referenced ClusterRole; never import."""
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.lifecycle_status != 'ready'
        or not tenant.provider_reference
    ):
        raise ValueError('Select a Ready Capsule Tenant with provider authority.')
    evidence = latest_external_capsule_access_evidence(tenant_id)
    selected = _require_committed_capsule_binding(
        evidence, tenant=tenant, binding_index=binding_index, now=datetime.now(UTC)
    )
    assert evidence is not None
    expected_uid = str((tenant.provider_evidence_json or {}).get('provider_uid') or '')
    if not expected_uid or expected_uid != evidence.get('provider_uid'):
        raise ValueError('Committed Capsule Tenant UID is missing or changed.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Connected Capsule Kubernetes provider is unavailable.')
    client = runtime_adapter.build_client(cluster)
    custom = client.custom_objects_api()
    rbac = client.rbac_authorization_api()

    def read_capsule() -> dict[str, Any]:
        item = custom.get_cluster_custom_object(
            'capsule.clastix.io', 'v1beta2', 'tenants',
            str(tenant.provider_reference), _request_timeout=5,
        )
        if not isinstance(item, dict) or not isinstance(item.get('spec'), dict):
            raise ValueError('Capsule Tenant spec could not be verified.')
        meta = item.get('metadata') or {}
        if (
            meta.get('uid') != expected_uid
            or meta.get('resourceVersion') != evidence.get('resource_version')
            or meta.get('name') != tenant.provider_reference
            or normalize_capsule_access_spec(item['spec'])['bindings'] != evidence.get('bindings')
        ):
            raise ValueError('Capsule provider RBAC changed since observed inventory.')
        return item

    read_capsule()
    role = rbac.read_cluster_role(selected['cluster_role_name'], _request_timeout=5)
    reviewed = classify_external_role_profile(role)
    if (
        reviewed['role_kind'] != 'ClusterRole'
        or reviewed['role_name'] != selected['cluster_role_name']
    ):
        raise ValueError('Referenced Capsule ClusterRole identity changed during review.')
    read_capsule()
    confirmed_role = rbac.read_cluster_role(selected['cluster_role_name'], _request_timeout=5)
    _require_stable_role_review(reviewed, classify_external_role_profile(confirmed_role))
    receipt = {
        **reviewed,
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'provider': 'capsule', 'capsule_tenant_name': tenant.provider_reference,
        'capsule_tenant_uid': expected_uid,
        'capsule_tenant_resource_version': evidence['resource_version'],
        'binding_index': binding_index,
        'binding_source': selected['source'],
        'scope_selector': selected.get('scope_selector'),
        'subjects': selected['subjects'],
        'source_observed_at': evidence['observed_at'],
        'reviewed_at': datetime.now(UTC).isoformat(),
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action='tenant.external_capsule_role.profile_reviewed',
        summary='Reviewed Capsule external ClusterRole equivalence without importing principals.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
