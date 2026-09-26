from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import RbacV1Subject, V1ObjectMeta, V1PolicyRule, V1Role, V1RoleBinding, V1RoleRef
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.access import (
    TenantAccessScope,
    get_access_profile,
    membership_subject,
    validate_active_grant,
    validate_grant_scope,
)
from app.models import Cluster
from app.models.tenant import (
    TenantAccessGrant,
    TenantAccessReconciliationStatus,
    TenantNamespace,
    TenantOwnershipStatus,
)

_MANAGED_BY_KEY = 'app.kubernetes.io/managed-by'
_MANAGED_BY_VALUE = 'kaori'
_TENANT_ID_KEY = 'kaori.io/tenant-id'
_ACCESS_PROFILE_KEY = 'kaori.io/access-profile'
_ACCESS_GRANT_KEY = 'kaori.io/access-grant'


def _canonical_hash(payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _role_name(grant: TenantAccessGrant) -> str:
    profile = grant.access_profile.replace('_', '-')
    return f'kaori-tenant-{profile}-v{grant.access_profile_version}'


def _binding_name(grant: TenantAccessGrant) -> str:
    return f'kaori-tenant-grant-{grant.public_id}'


def _role_labels(grant: TenantAccessGrant) -> dict[str, str]:
    return {
        _MANAGED_BY_KEY: _MANAGED_BY_VALUE,
        _TENANT_ID_KEY: grant.tenant_id,
        _ACCESS_PROFILE_KEY: grant.access_profile,
    }


def _binding_labels(grant: TenantAccessGrant) -> dict[str, str]:
    return {
        **_role_labels(grant),
        _ACCESS_GRANT_KEY: grant.public_id,
    }


def target_namespaces(grant: TenantAccessGrant) -> list[TenantNamespace]:
    validate_grant_scope(grant)
    scope = TenantAccessScope(grant.scope_type)
    if scope is TenantAccessScope.NAMESPACE:
        candidates = [grant.namespace] if grant.namespace is not None else []
    elif scope is TenantAccessScope.ENVIRONMENT:
        candidates = list(grant.environment.namespaces) if grant.environment is not None else []
    else:
        candidates = [namespace for environment in grant.tenant.environments for namespace in environment.namespaces]

    return sorted(
        (
            namespace
            for namespace in candidates
            if namespace is not None
            and namespace.ownership_status in {TenantOwnershipStatus.MANAGED.value, TenantOwnershipStatus.ADOPTED.value}
        ),
        key=lambda item: item.namespace,
    )


def desired_native_access_contract(grant: TenantAccessGrant, namespace: str) -> dict[str, Any]:
    profile = get_access_profile(grant.access_profile, grant.access_profile_version)
    subject_kind, subject_name = membership_subject(grant.membership)
    role_labels = _role_labels(grant)
    binding_labels = _binding_labels(grant)
    rules = [
        {
            'api_groups': list(rule.api_groups),
            'resources': list(rule.resources),
            'verbs': list(rule.verbs),
        }
        for rule in profile.rules
    ]
    return {
        'namespace': namespace,
        'role': {
            'name': _role_name(grant),
            'labels': role_labels,
            'rules': rules,
        },
        'role_binding': {
            'name': _binding_name(grant),
            'labels': binding_labels,
            'role_ref': {
                'api_group': 'rbac.authorization.k8s.io',
                'kind': 'Role',
                'name': _role_name(grant),
            },
            'subjects': [
                {
                    'api_group': 'rbac.authorization.k8s.io',
                    'kind': subject_kind,
                    'name': subject_name,
                }
            ],
        },
    }


def _managed_or_absent(meta: V1ObjectMeta | None, *, kind: str) -> None:
    labels = dict((meta.labels or {}) if meta is not None else {})
    owner = labels.get(_MANAGED_BY_KEY)
    if owner and owner != _MANAGED_BY_VALUE:
        raise ValueError(f'{kind} is already managed by {owner}; refusing to overwrite provider ownership')


def _read_or_none(reader, *args):
    try:
        return reader(*args)
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _role_body(desired: dict[str, Any]) -> V1Role:
    role = desired['role']
    return V1Role(
        metadata=V1ObjectMeta(name=role['name'], namespace=desired['namespace'], labels=role['labels']),
        rules=[
            V1PolicyRule(api_groups=item['api_groups'], resources=item['resources'], verbs=item['verbs'])
            for item in role['rules']
        ],
    )


def _binding_body(desired: dict[str, Any]) -> V1RoleBinding:
    binding = desired['role_binding']
    role_ref = binding['role_ref']
    return V1RoleBinding(
        metadata=V1ObjectMeta(name=binding['name'], namespace=desired['namespace'], labels=binding['labels']),
        role_ref=V1RoleRef(
            api_group=role_ref['api_group'],
            kind=role_ref['kind'],
            name=role_ref['name'],
        ),
        subjects=[
            RbacV1Subject(
                api_group=item['api_group'],
                kind=item['kind'],
                name=item['name'],
                namespace=None,
            )
            for item in binding['subjects']
        ],
    )


def _upsert_role(api, desired: dict[str, Any]) -> None:
    namespace = desired['namespace']
    name = desired['role']['name']
    existing = _read_or_none(api.read_namespaced_role, name, namespace)
    body = _role_body(desired)
    if existing is None:
        api.create_namespaced_role(namespace=namespace, body=body)
        return
    _managed_or_absent(existing.metadata, kind='Role')
    api.patch_namespaced_role(name=name, namespace=namespace, body=body)


def _upsert_binding(api, desired: dict[str, Any]) -> None:
    namespace = desired['namespace']
    name = desired['role_binding']['name']
    existing = _read_or_none(api.read_namespaced_role_binding, name, namespace)
    body = _binding_body(desired)
    if existing is None:
        api.create_namespaced_role_binding(namespace=namespace, body=body)
        return
    _managed_or_absent(existing.metadata, kind='RoleBinding')
    api.patch_namespaced_role_binding(name=name, namespace=namespace, body=body)


def _delete_binding(api, grant: TenantAccessGrant, namespace: str) -> None:
    name = _binding_name(grant)
    existing = _read_or_none(api.read_namespaced_role_binding, name, namespace)
    if existing is None:
        return
    _managed_or_absent(existing.metadata, kind='RoleBinding')
    api.delete_namespaced_role_binding(name=name, namespace=namespace)


def _normalized_rules(role: V1Role) -> list[dict[str, list[str]]]:
    normalized = [
        {
            'api_groups': sorted(item.api_groups or []),
            'resources': sorted(item.resources or []),
            'verbs': sorted(item.verbs or []),
        }
        for item in (role.rules or [])
    ]
    return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))


def _effective_target_contract(api, desired: dict[str, Any]) -> dict[str, Any] | None:
    namespace = desired['namespace']
    role_name = desired['role']['name']
    binding_name = desired['role_binding']['name']
    role = _read_or_none(api.read_namespaced_role, role_name, namespace)
    binding = _read_or_none(api.read_namespaced_role_binding, binding_name, namespace)
    if role is None or binding is None:
        return None

    return {
        'namespace': namespace,
        'role': {
            'name': role.metadata.name,
            'labels': {key: (role.metadata.labels or {}).get(key) for key in desired['role']['labels']},
            'rules': _normalized_rules(role),
        },
        'role_binding': {
            'name': binding.metadata.name,
            'labels': {key: (binding.metadata.labels or {}).get(key) for key in desired['role_binding']['labels']},
            'role_ref': {
                'api_group': binding.role_ref.api_group,
                'kind': binding.role_ref.kind,
                'name': binding.role_ref.name,
            },
            'subjects': sorted(
                [
                    {
                        'api_group': item.api_group or '',
                        'kind': item.kind,
                        'name': item.name,
                    }
                    for item in (binding.subjects or [])
                ],
                key=lambda item: (item['kind'], item['name']),
            ),
        },
    }


def _normalized_desired(desired: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(desired))
    normalized['role']['rules'] = sorted(
        [
            {
                'api_groups': sorted(item['api_groups']),
                'resources': sorted(item['resources']),
                'verbs': sorted(item['verbs']),
            }
            for item in normalized['role']['rules']
        ],
        key=lambda item: json.dumps(item, sort_keys=True),
    )
    normalized['role_binding']['subjects'] = sorted(
        normalized['role_binding']['subjects'],
        key=lambda item: (item['kind'], item['name']),
    )
    return normalized


def _previous_target_names(grant: TenantAccessGrant) -> set[str]:
    evidence = grant.reconciliation_evidence_json or {}
    return {str(item.get('namespace')) for item in (evidence.get('desired_targets') or []) if item.get('namespace')}


def _cluster_for_grant(grant: TenantAccessGrant) -> Cluster:
    if grant.tenant.provider_key != 'native_kubernetes':
        raise ValueError('Native access reconciliation requires Native Kubernetes provider authority.')
    cluster = db.session.get(Cluster, grant.tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')
    return cluster


def inspect_native_access_grant(grant: TenantAccessGrant) -> TenantAccessGrant:
    validate_grant_scope(grant)
    cluster = _cluster_for_grant(grant)
    api = runtime_adapter.build_client(cluster).rbac_authorization_api()
    now = datetime.now(UTC)

    if grant.status == 'revoked':
        target_names = {item.namespace for item in target_namespaces(grant)} | _previous_target_names(grant)
        remaining = [
            namespace
            for namespace in sorted(target_names)
            if _read_or_none(api.read_namespaced_role_binding, _binding_name(grant), namespace) is not None
        ]
        grant.last_reconciled_at = now
        grant.effective_hash = _canonical_hash({'remaining_bindings': remaining})
        if remaining:
            grant.reconciliation_status = TenantAccessReconciliationStatus.DRIFTED.value
            grant.reconciliation_message = 'Revoked Tenant Access Grant still has effective RoleBinding state.'
        else:
            grant.reconciliation_status = TenantAccessReconciliationStatus.REVOKED.value
            grant.reconciliation_message = 'Revoked Tenant Access Grant has no effective RoleBinding state.'
        return grant

    validate_active_grant(grant)
    desired_targets = [desired_native_access_contract(grant, item.namespace) for item in target_namespaces(grant)]
    effective_targets = [
        effective for desired in desired_targets if (effective := _effective_target_contract(api, desired)) is not None
    ]
    desired_payload = [_normalized_desired(item) for item in desired_targets]
    grant.desired_hash = _canonical_hash(desired_payload)
    grant.effective_hash = _canonical_hash(effective_targets)
    grant.last_reconciled_at = now
    if desired_payload == effective_targets:
        grant.reconciliation_status = TenantAccessReconciliationStatus.READY.value
        grant.reconciliation_message = 'Native Kubernetes Role and RoleBinding match committed Tenant access intent.'
    else:
        grant.reconciliation_status = TenantAccessReconciliationStatus.DRIFTED.value
        grant.reconciliation_message = 'Native Kubernetes RBAC does not match committed Tenant access intent.'
    grant.reconciliation_evidence_json = {
        'desired_targets': desired_payload,
        'effective_targets': effective_targets,
    }
    return grant


def reconcile_native_access_grant(grant: TenantAccessGrant) -> TenantAccessGrant:
    validate_grant_scope(grant)
    cluster = _cluster_for_grant(grant)
    api = runtime_adapter.build_client(cluster).rbac_authorization_api()
    now = datetime.now(UTC)

    try:
        if grant.status == 'revoked':
            target_names = {item.namespace for item in target_namespaces(grant)} | _previous_target_names(grant)
            for namespace in sorted(target_names):
                _delete_binding(api, grant, namespace)
            grant.last_reconciled_at = now
            grant.reconciliation_evidence_json = {
                'desired_status': 'revoked',
                'desired_targets': [{'namespace': namespace} for namespace in sorted(target_names)],
                'target_namespaces': sorted(target_names),
            }
            return inspect_native_access_grant(grant)

        validate_active_grant(grant)
        desired_targets = [desired_native_access_contract(grant, item.namespace) for item in target_namespaces(grant)]
        if not desired_targets:
            grant.reconciliation_status = TenantAccessReconciliationStatus.PENDING.value
            grant.reconciliation_message = 'Access Grant is committed but has no managed namespace target yet.'
            grant.last_reconciled_at = now
            grant.desired_hash = _canonical_hash([])
            grant.effective_hash = _canonical_hash([])
            grant.reconciliation_evidence_json = {'desired_targets': [], 'effective_targets': []}
            return grant

        for desired in desired_targets:
            _upsert_role(api, desired)
            _upsert_binding(api, desired)
        return inspect_native_access_grant(grant)
    except (ApiException, ValueError) as exc:
        grant.reconciliation_status = TenantAccessReconciliationStatus.FAILED.value
        grant.reconciliation_message = str(exc)[:1000]
        grant.last_reconciled_at = now
        grant.reconciliation_evidence_json = {
            **(grant.reconciliation_evidence_json or {}),
            'error': grant.reconciliation_message,
        }
        raise
