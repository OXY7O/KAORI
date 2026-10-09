from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.access import get_access_profile, membership_subject, validate_active_grant
from app.kubernetes.tenant.access_reconciliation import target_namespaces
from app.kubernetes.tenant.capsule_provider import discover_capsule
from app.models import Cluster
from app.models.tenant import TenantAccessGrant, TenantAccessReconciliationStatus, TenantAccessScope

_GROUP = 'capsule.clastix.io'
_PLURAL = 'tenants'
_GRANT_LABEL = 'kaori.io/access-grant'
_MANAGED_LABEL = 'app.kubernetes.io/managed-by'
_NAME_LABEL = 'kubernetes.io/metadata.name'
_TENANT_LABEL = 'capsule.clastix.io/tenant'


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _context(grant: TenantAccessGrant) -> tuple[Any, str, str]:
    tenant = grant.tenant
    if (
        tenant.provider_key != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.lifecycle_status != 'ready'
    ):
        raise ValueError('Healthy Capsule reconciliation authority is required; Native RBAC fallback is forbidden.')
    evidence = (tenant.provider_evidence_json or {}).get('capsule')
    capabilities = evidence.get('capabilities') if isinstance(evidence, dict) else None
    if not isinstance(capabilities, dict) or capabilities.get('admission_enforcement') != 'available':
        raise ValueError('Committed healthy Capsule admission evidence is required for Access Grant mutation.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None or not tenant.provider_reference:
        raise ValueError('Capsule Tenant cluster or provider reference is missing.')
    return runtime_adapter.build_client(cluster), str(tenant.provider_reference), str(tenant.id)


def _capability(grant: TenantAccessGrant, client: Any, *, scoped: bool) -> str:
    snapshot = discover_capsule(client.custom_objects_api().api_client)
    evidence = dict(grant.tenant.provider_evidence_json or {})
    capsule_evidence = dict(evidence.get('capsule') or {})
    capabilities = dict(capsule_evidence.get('capabilities') or {})
    for capability in ('access_grants_tenant', 'access_grants_scoped'):
        capabilities[capability] = snapshot.capabilities[capability].value
    capsule_evidence['capabilities'] = capabilities
    capsule_evidence['access_grants_discovered_at'] = datetime.now(UTC).isoformat()
    evidence['capsule'] = capsule_evidence
    grant.tenant.provider_evidence_json = evidence
    key = 'access_grants_scoped' if scoped else 'access_grants_tenant'
    if snapshot.capabilities.get(key) is None or snapshot.capabilities[key].value != 'available':
        raise ValueError(f'Capsule {key} is unsupported on the served CRD/schema; grant fails closed.')
    if 'v1beta2' not in snapshot.tenant_api_versions:
        raise ValueError('Capsule Access Grant reconciliation requires a served v1beta2 Tenant API.')
    return 'v1beta2'


def _tenant_object(api: Any, version: str, name: str, tenant_id: str, tenant: Any) -> dict[str, Any]:
    item = api.get_cluster_custom_object(_GROUP, version, _PLURAL, name, _request_timeout=5)
    if not isinstance(item, dict):
        raise ValueError('Capsule returned an invalid Tenant object.')
    metadata = item.get('metadata') or {}
    if metadata.get('name') != name or not metadata.get('resourceVersion') or not metadata.get('uid'):
        raise ValueError('Capsule Tenant identity or resourceVersion is incomplete.')
    prior_uid = (tenant.provider_evidence_json or {}).get('provider_uid')
    if prior_uid and prior_uid != metadata['uid']:
        raise ValueError('Capsule Tenant provider UID changed; re-adoption review is required.')
    labels = metadata.get('labels') or {}
    bound_id = labels.get('kaori.io/tenant-id')
    if bound_id and bound_id != tenant_id:
        raise ValueError('Capsule Tenant is labeled as owned by another KAORI Tenant.')
    return item


def _namespaces(grant: TenantAccessGrant, client: Any, item: dict[str, Any]) -> list[str]:
    names = [record.namespace for record in target_namespaces(grant)]
    if not names:
        raise ValueError('Access Grant requires at least one committed managed/adopted Namespace.')
    if any(record.provisioning_status != 'ready' for record in target_namespaces(grant)):
        raise ValueError('All Capsule Access Grant Namespace targets must be Ready.')
    status = item.get('status') or {}
    observed = status.get('namespaces')
    if not isinstance(observed, list):
        raise ValueError('Capsule status.namespaces evidence is unavailable; reconciliation fails closed.')
    tenant_names = set(str(name) for name in observed)
    if not set(names).issubset(tenant_names):
        raise ValueError('One or more KAORI Namespace targets are not registered to the authoritative Capsule Tenant.')
    if grant.scope_type == TenantAccessScope.TENANT.value and tenant_names != set(names):
        raise ValueError('Capsule Tenant scope contains namespaces not yet governed in KAORI.')
    core = client.core_api()
    for name in names:
        namespace = core.read_namespace(name, _request_timeout=5)
        labels = getattr(getattr(namespace, 'metadata', None), 'labels', None) or {}
        if labels.get(_NAME_LABEL) != name or labels.get(_TENANT_LABEL) != grant.tenant.provider_reference:
            raise ValueError(f'Namespace {name} has unverified Capsule ownership/immutable name label.')
    return sorted(names)


def _role_name(grant: TenantAccessGrant) -> str:
    return f'kaori-tenant-{grant.access_profile.replace("_", "-")}-v{grant.access_profile_version}'


def _check_profile(grant: TenantAccessGrant, rbac_api: Any) -> str:
    profile = get_access_profile(grant.access_profile, grant.access_profile_version)
    name = _role_name(grant)
    try:
        role = rbac_api.read_cluster_role(name, _request_timeout=5)
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError(
                f'Pre-approved exact permission ClusterRole/{name} is missing; '
                'a cluster administrator must provision and authorize it.'
            ) from exc
        raise

    def normalized(rules: Any) -> list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]]:
        values = []
        for rule in rules:
            api_groups = rule.api_groups if hasattr(rule, 'api_groups') else rule['api_groups']
            resources = rule.resources if hasattr(rule, 'resources') else rule['resources']
            verbs = rule.verbs if hasattr(rule, 'verbs') else rule['verbs']
            if getattr(rule, 'resource_names', None) or getattr(rule, 'non_resource_urls', None):
                raise ValueError('Capsule profile ClusterRole has unsupported RBAC restrictions/URLs.')
            values.append((
                tuple(sorted(api_groups or [])),
                tuple(sorted(resources or [])),
                tuple(sorted(verbs or [])),
            ))
        return sorted(values)

    if getattr(role, 'aggregation_rule', None) is not None:
        raise ValueError(f'ClusterRole/{name} uses aggregation and cannot be a fixed KAORI security contract.')
    if normalized(role.rules or []) != normalized(profile.rules):
        raise ValueError(f'ClusterRole/{name} does not match versioned KAORI {profile.label} permissions.')
    return name


def _binding(grant: TenantAccessGrant, role: str, namespaces: list[str]) -> dict[str, Any]:
    kind, name = membership_subject(grant.membership)
    if kind == 'ServiceAccount' and (
        grant.scope_type != TenantAccessScope.NAMESPACE.value or len(namespaces) != 1
    ):
        raise ValueError('Capsule ServiceAccount grants require exactly one Namespace scope.')
    subject = {'kind': kind, 'name': name, 'apiGroup': '' if kind == 'ServiceAccount' else 'rbac.authorization.k8s.io'}
    if kind == 'ServiceAccount':
        subject['namespace'] = namespaces[0]
    return {
        'clusterRoleName': role,
        'subjects': [subject],
        'labels': {_MANAGED_LABEL: 'kaori', _GRANT_LABEL: grant.public_id, 'kaori.io/tenant-id': grant.tenant_id},
    }


def _identity(binding: dict[str, Any]) -> str | None:
    labels = binding.get('labels') or {}
    if not isinstance(labels, dict):
        raise ValueError('Capsule RBAC binding labels are malformed.')
    grant_id = labels.get(_GRANT_LABEL)
    if grant_id and labels.get(_MANAGED_LABEL) != 'kaori':
        raise ValueError('Capsule RBAC binding carries a foreign grant ownership marker.')
    return str(grant_id) if grant_id else None


def _update_spec(
    spec: dict[str, Any], grant: TenantAccessGrant, binding: dict[str, Any] | None, names: list[str]
) -> dict[str, Any]:
    result = deepcopy(spec)
    additional = result.get('additionalRoleBindings') or []
    rules = result.get('rules') or []
    if not isinstance(additional, list) or not isinstance(rules, list):
        raise ValueError('Capsule Tenant RBAC spec is malformed.')
    retained = []
    found = 0
    for entry in additional:
        if not isinstance(entry, dict):
            raise ValueError('Capsule additionalRoleBindings entry is invalid.')
        if _identity(entry) == grant.public_id:
            found += 1
        else:
            retained.append(entry)
    filtered_rules = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('Capsule Tenant rule is invalid.')
        rule = deepcopy(rule)
        permissions = rule.get('permissions') or {}
        if not isinstance(permissions, dict):
            raise ValueError('Capsule Tenant permissions structure is malformed.')
        bindings = permissions.get('bindings') or []
        if not isinstance(bindings, list):
            raise ValueError('Capsule Tenant permissions bindings are malformed.')
        remaining = []
        for entry in bindings or []:
            if not isinstance(entry, dict):
                raise ValueError('Capsule Tenant scoped binding is invalid.')
            if _identity(entry) == grant.public_id:
                found += 1
            else:
                remaining.append(entry)
        changed = len(remaining) != len(bindings or [])
        if changed:
            if remaining:
                permissions['bindings'] = remaining
                rule['permissions'] = permissions
            else:
                permissions.pop('bindings', None)
                if permissions:
                    rule['permissions'] = permissions
                else:
                    rule.pop('permissions', None)
        if not changed or rule.get('permissions') or any(key != 'namespaceSelector' for key in rule):
            filtered_rules.append(rule)
    if found > 1:
        raise ValueError('Duplicate Capsule grant bindings were observed; refuse to modify.')
    if binding is None and found == 0:
        return deepcopy(spec)
    if binding is not None:
        for foreign in retained + [
            value for rule in filtered_rules for value in (rule.get('permissions') or {}).get('bindings', [])
        ]:
            if foreign.get('clusterRoleName') == binding['clusterRoleName']:
                raise ValueError('Capsule ClusterRole already has another provider-owned/KAORI grant binding.')
        if found == 1:
            selector = {'matchExpressions': [{'key': _NAME_LABEL, 'operator': 'In', 'values': names}]}
            if any(
                rule.get('namespaceSelector') == selector
                and (rule.get('permissions') or {}).get('bindings') == [binding]
                and set(rule) == {'namespaceSelector', 'permissions'}
                for rule in rules
            ):
                return deepcopy(spec)
        filtered_rules.append(
                {
                    'namespaceSelector': {'matchExpressions': [
                        {'key': _NAME_LABEL, 'operator': 'In', 'values': names}
                    ]},
                    'permissions': {'bindings': [binding]},
                }
            )
    result['additionalRoleBindings'] = retained
    result['rules'] = filtered_rules
    return result


def _effective(client: Any, grant: TenantAccessGrant, role_name: str, names: list[str]) -> list[dict[str, str]]:
    kind, subject_name = membership_subject(grant.membership) if grant.status == 'active' else (
        'ServiceAccount' if grant.membership.principal_type == 'service_account'
        else grant.membership.principal_type.title(),
        grant.membership.subject_name,
    )
    found = []
    for name in names:
        listing = client.rbac_authorization_api().list_namespaced_role_binding(name, _request_timeout=5)
        matches = []
        for binding in listing.items or []:
            metadata = binding.metadata
            labels = getattr(metadata, 'labels', None) or {}
            if labels.get(_GRANT_LABEL) != grant.public_id:
                continue
            if labels.get(_MANAGED_LABEL) != 'kaori':
                raise ValueError('Effective RoleBinding has a conflicting manager for this Access Grant.')
            role_ref = binding.role_ref
            subjects = binding.subjects or []
            expected = any(
                value.kind == kind and value.name == subject_name
                and (kind != 'ServiceAccount' or value.namespace == name)
                for value in subjects
            )
            if role_ref.kind != 'ClusterRole' or role_ref.name != role_name or not expected or len(subjects) != 1:
                raise ValueError('Capsule effective RoleBinding differs from the KAORI access contract.')
            matches.append(str(metadata.name))
        if len(matches) > 1:
            raise ValueError('Duplicate effective Capsule grant RoleBindings detected.')
        if matches:
            found.append({'namespace': name, 'role_binding': matches[0]})
    return found


def _write_state(
    grant: TenantAccessGrant, *, item: dict[str, Any], desired: list[str], effective: list[dict[str, str]]
) -> None:
    now = datetime.now(UTC)
    granted = grant.status == 'active'
    matched = {value['namespace'] for value in effective}
    complete = matched == set(desired) if granted else not effective
    grant.desired_hash = _hash({'grant': grant.public_id, 'active': granted, 'namespaces': desired})
    grant.effective_hash = _hash(effective)
    grant.last_reconciled_at = now
    grant.reconciliation_status = (
        TenantAccessReconciliationStatus.READY.value if granted and complete else
        TenantAccessReconciliationStatus.REVOKED.value if not granted and complete else
        TenantAccessReconciliationStatus.DRIFTED.value
    )
    grant.reconciliation_message = (
        'Capsule RoleBindings verified against committed grant and Namespace scope.'
        if granted and complete else
        'Capsule grant revoked; no effective managed RoleBinding remains.'
        if not granted and complete else
        'Capsule provider has not converged to the committed Access Grant; inspect and retry.'
    )
    meta = item['metadata']
    grant.reconciliation_evidence_json = {
        'provider': 'capsule',
        'api_version': 'v1beta2',
        'tenant_uid': meta['uid'],
        'resource_version': meta['resourceVersion'],
        'cluster_role': _role_name(grant),
        'desired_targets': [{'namespace': name} for name in desired],
        'effective_targets': effective,
        'secret_material_persisted': False,
    }


def _reconcile(grant: TenantAccessGrant, *, mutate: bool) -> TenantAccessGrant:
    client, name, tenant_id = _context(grant)
    # Capsule additionalRoleBindings would silently authorize future, ungoverned Namespaces.
    # Every KAORI scope is therefore represented by an exact governed Namespace selector.
    version = _capability(grant, client, scoped=True)
    api = client.custom_objects_api()
    item = _tenant_object(api, version, name, tenant_id, grant.tenant)
    prior = grant.reconciliation_evidence_json or {}
    previous = {str(value['namespace']) for value in prior.get('desired_targets', []) if value.get('namespace')}
    active = grant.status == 'active'
    if active:
        validate_active_grant(grant)
        names = _namespaces(grant, client, item)
    else:
        names = sorted(previous | {target.namespace for target in target_namespaces(grant)})
    role = _check_profile(grant, client.rbac_authorization_api()) if active else _role_name(grant)
    binding = _binding(grant, role, names) if active else None
    desired_spec = _update_spec(item.get('spec') or {}, grant, binding, names)
    if mutate and desired_spec != (item.get('spec') or {}):
        patch = {
            'metadata': {'resourceVersion': item['metadata']['resourceVersion']},
            'spec': {
                'additionalRoleBindings': desired_spec['additionalRoleBindings'],
                'rules': desired_spec['rules'],
            },
        }
        api.patch_cluster_custom_object(_GROUP, version, _PLURAL, name, patch, dry_run='All', _request_timeout=5)
        api.patch_cluster_custom_object(_GROUP, version, _PLURAL, name, patch, _request_timeout=5)
        item = _tenant_object(api, version, name, tenant_id, grant.tenant)
    current_spec = item.get('spec') or {}
    spec_verified = all(
        (current_spec.get(key) or []) == (desired_spec.get(key) or [])
        for key in ('additionalRoleBindings', 'rules')
    )
    effective = _effective(client, grant, role, sorted(set(names) | previous))
    _write_state(grant, item=item, desired=names, effective=effective)
    if not spec_verified:
        grant.reconciliation_status = TenantAccessReconciliationStatus.DRIFTED.value
        grant.reconciliation_message = 'Capsule Tenant spec has not converged to the committed Access Grant.'
    return grant


def reconcile_capsule_access_grant(grant: TenantAccessGrant) -> TenantAccessGrant:
    try:
        return _reconcile(grant, mutate=True)
    except (ApiException, ValueError) as exc:
        grant.reconciliation_status = TenantAccessReconciliationStatus.FAILED.value
        grant.reconciliation_message = str(exc)[:1000]
        grant.last_reconciled_at = datetime.now(UTC)
        grant.reconciliation_evidence_json = {
            **(grant.reconciliation_evidence_json or {}),
            'provider': 'capsule', 'error': grant.reconciliation_message, 'secret_material_persisted': False,
        }
        raise


def inspect_capsule_access_grant(grant: TenantAccessGrant) -> TenantAccessGrant:
    return _reconcile(grant, mutate=False)
