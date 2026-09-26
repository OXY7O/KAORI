from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import (
    RbacV1Subject,
    V1ClusterRoleBinding,
    V1ObjectMeta,
    V1RoleBinding,
    V1RoleRef,
    V1ServiceAccount,
)
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.access_reconciliation import desired_native_access_contract
from app.kubernetes.tenant.credential import (
    credential_target_namespaces,
    refresh_credential_status,
    validate_credential_contract,
)
from app.models import Cluster
from app.models.tenant import (
    TenantCredential,
    TenantCredentialReconciliationStatus,
    TenantCredentialStatus,
    TenantCredentialType,
)

_MANAGED_BY_KEY = 'app.kubernetes.io/managed-by'
_MANAGED_BY_VALUE = 'kaori'
_TENANT_ID_KEY = 'kaori.io/tenant-id'
_CREDENTIAL_ID_KEY = 'kaori.io/tenant-credential'
_ACCESS_GRANT_KEY = 'kaori.io/access-grant'


def _canonical_hash(payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _read_or_none(reader, *args):
    try:
        return reader(*args)
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _labels(credential: TenantCredential) -> dict[str, str]:
    labels = {
        _MANAGED_BY_KEY: _MANAGED_BY_VALUE,
        _TENANT_ID_KEY: credential.tenant_id,
        _CREDENTIAL_ID_KEY: credential.public_id,
    }
    if credential.access_grant is not None:
        labels[_ACCESS_GRANT_KEY] = credential.access_grant.public_id
    return labels


def _managed_or_absent(meta: V1ObjectMeta | None, credential: TenantCredential, *, kind: str) -> None:
    labels = dict((meta.labels or {}) if meta is not None else {})
    owner = labels.get(_MANAGED_BY_KEY)
    credential_id = labels.get(_CREDENTIAL_ID_KEY)
    if owner and owner != _MANAGED_BY_VALUE:
        raise ValueError(f'{kind} is already managed by {owner}; refusing to overwrite provider ownership.')
    if credential_id and credential_id != credential.public_id:
        raise ValueError(f'{kind} belongs to another Tenant credential; refusing to overwrite provider ownership.')


def _cluster_for_credential(credential: TenantCredential) -> Cluster:
    if credential.tenant.provider_key != 'native_kubernetes':
        raise ValueError('Native credential reconciliation requires Native Kubernetes provider authority.')
    cluster = db.session.get(Cluster, credential.tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')
    return cluster


def _human_binding_name(credential: TenantCredential) -> str:
    return f'kaori-tenant-credential-{credential.public_id}'


def _admin_binding_name(credential: TenantCredential) -> str:
    return f'kaori-admin-credential-{credential.public_id}'


def _upsert_service_account(api, credential: TenantCredential, namespace: str) -> V1ServiceAccount:
    current = _read_or_none(api.read_namespaced_service_account, credential.service_account_name, namespace)
    if current is not None:
        _managed_or_absent(current.metadata, credential, kind='ServiceAccount')
    body = V1ServiceAccount(
        metadata=V1ObjectMeta(
            name=credential.service_account_name,
            namespace=namespace,
            labels=_labels(credential),
        ),
        automount_service_account_token=False,
    )
    if current is None:
        api.create_namespaced_service_account(namespace=namespace, body=body)
    else:
        api.patch_namespaced_service_account(name=credential.service_account_name, namespace=namespace, body=body)
    return body


def _human_role_name(credential: TenantCredential, namespace: str) -> str:
    grant = credential.access_grant
    if grant is None:
        raise ValueError('Human Tenant credential requires an Access Grant.')
    desired = desired_native_access_contract(grant, namespace)
    return str(desired['role']['name'])


def _upsert_human_binding(rbac_api, credential: TenantCredential, namespace: str) -> V1RoleBinding:
    name = _human_binding_name(credential)
    current = _read_or_none(rbac_api.read_namespaced_role_binding, name, namespace)
    if current is not None:
        _managed_or_absent(current.metadata, credential, kind='RoleBinding')

    role_name = _human_role_name(credential, namespace)
    role = _read_or_none(rbac_api.read_namespaced_role, role_name, namespace)
    if role is None:
        raise ValueError('Tenant Access Grant Role is missing; reconcile the Access Grant before issuing credentials.')

    body = V1RoleBinding(
        metadata=V1ObjectMeta(name=name, namespace=namespace, labels=_labels(credential)),
        role_ref=V1RoleRef(
            api_group='rbac.authorization.k8s.io',
            kind='Role',
            name=role_name,
        ),
        subjects=[
            RbacV1Subject(
                api_group='',
                kind='ServiceAccount',
                name=credential.service_account_name,
                namespace=namespace,
            )
        ],
    )
    if current is None:
        rbac_api.create_namespaced_role_binding(namespace=namespace, body=body)
    else:
        rbac_api.patch_namespaced_role_binding(name=name, namespace=namespace, body=body)
    return body


def _upsert_admin_binding(rbac_api, credential: TenantCredential, namespace: str) -> V1ClusterRoleBinding:
    name = _admin_binding_name(credential)
    current = _read_or_none(rbac_api.read_cluster_role_binding, name)
    if current is not None:
        _managed_or_absent(current.metadata, credential, kind='ClusterRoleBinding')

    body = V1ClusterRoleBinding(
        metadata=V1ObjectMeta(name=name, labels=_labels(credential)),
        role_ref=V1RoleRef(
            api_group='rbac.authorization.k8s.io',
            kind='ClusterRole',
            name='cluster-admin',
        ),
        subjects=[
            RbacV1Subject(
                api_group='',
                kind='ServiceAccount',
                name=credential.service_account_name,
                namespace=namespace,
            )
        ],
    )
    if current is None:
        rbac_api.create_cluster_role_binding(body=body)
    else:
        rbac_api.patch_cluster_role_binding(name=name, body=body)
    return body


def _delete_service_account(api, credential: TenantCredential, namespace: str) -> None:
    current = _read_or_none(api.read_namespaced_service_account, credential.service_account_name, namespace)
    if current is None:
        return
    _managed_or_absent(current.metadata, credential, kind='ServiceAccount')
    api.delete_namespaced_service_account(name=credential.service_account_name, namespace=namespace)


def _delete_human_binding(rbac_api, credential: TenantCredential, namespace: str) -> None:
    name = _human_binding_name(credential)
    current = _read_or_none(rbac_api.read_namespaced_role_binding, name, namespace)
    if current is None:
        return
    _managed_or_absent(current.metadata, credential, kind='RoleBinding')
    rbac_api.delete_namespaced_role_binding(name=name, namespace=namespace)


def _delete_admin_binding(rbac_api, credential: TenantCredential) -> None:
    name = _admin_binding_name(credential)
    current = _read_or_none(rbac_api.read_cluster_role_binding, name)
    if current is None:
        return
    _managed_or_absent(current.metadata, credential, kind='ClusterRoleBinding')
    rbac_api.delete_cluster_role_binding(name=name)


def _desired_target(credential: TenantCredential, namespace: str) -> dict[str, Any]:
    target = {
        'namespace': namespace,
        'service_account': {
            'name': credential.service_account_name,
            'labels': _labels(credential),
            'automount_service_account_token': False,
        },
    }
    if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
        target['binding'] = {
            'kind': 'RoleBinding',
            'name': _human_binding_name(credential),
            'role_kind': 'Role',
            'role_name': _human_role_name(credential, namespace),
        }
    else:
        target['binding'] = {
            'kind': 'ClusterRoleBinding',
            'name': _admin_binding_name(credential),
            'role_kind': 'ClusterRole',
            'role_name': 'cluster-admin',
        }
    return target


def _effective_target(core_api, rbac_api, credential: TenantCredential, namespace: str) -> dict[str, Any] | None:
    service_account = _read_or_none(
        core_api.read_namespaced_service_account,
        credential.service_account_name,
        namespace,
    )
    if service_account is None:
        return None

    desired = _desired_target(credential, namespace)
    if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
        binding = _read_or_none(rbac_api.read_namespaced_role_binding, _human_binding_name(credential), namespace)
    else:
        binding = _read_or_none(rbac_api.read_cluster_role_binding, _admin_binding_name(credential))
    if binding is None:
        return None

    subject = (binding.subjects or [None])[0]
    return {
        'namespace': namespace,
        'service_account': {
            'name': service_account.metadata.name,
            'labels': {key: (service_account.metadata.labels or {}).get(key) for key in _labels(credential)},
            'automount_service_account_token': bool(service_account.automount_service_account_token),
        },
        'binding': {
            'kind': desired['binding']['kind'],
            'name': binding.metadata.name,
            'role_kind': binding.role_ref.kind,
            'role_name': binding.role_ref.name,
            'subject_kind': getattr(subject, 'kind', None),
            'subject_name': getattr(subject, 'name', None),
            'subject_namespace': getattr(subject, 'namespace', None),
        },
    }


def _normalized_desired(target: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(target))
    binding = normalized['binding']
    binding['subject_kind'] = 'ServiceAccount'
    binding['subject_name'] = normalized['service_account']['name']
    binding['subject_namespace'] = normalized['namespace']
    return normalized


def remove_native_credential_access(credential: TenantCredential) -> TenantCredential:
    cluster = _cluster_for_credential(credential)
    client = runtime_adapter.build_client(cluster)
    core_api = client.core_api()
    rbac_api = client.rbac_authorization_api()
    targets = credential_target_namespaces(credential)

    if credential.credential_type == TenantCredentialType.ADMIN_KUBECONFIG.value:
        _delete_admin_binding(rbac_api, credential)

    for namespace in targets:
        if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
            _delete_human_binding(rbac_api, credential, namespace.namespace)
        _delete_service_account(core_api, credential, namespace.namespace)
    return credential


def inspect_native_credential(credential: TenantCredential) -> TenantCredential:
    cluster = _cluster_for_credential(credential)
    client = runtime_adapter.build_client(cluster)
    core_api = client.core_api()
    rbac_api = client.rbac_authorization_api()
    now = datetime.now(UTC)
    refresh_credential_status(credential, now=now)

    targets = credential_target_namespaces(credential)
    desired_targets = [_normalized_desired(_desired_target(credential, item.namespace)) for item in targets]
    effective_targets = [
        effective
        for item in targets
        if (effective := _effective_target(core_api, rbac_api, credential, item.namespace)) is not None
    ]

    credential.desired_hash = _canonical_hash(desired_targets)
    credential.effective_hash = _canonical_hash(effective_targets)
    credential.last_reconciled_at = now

    active = credential.status in {
        TenantCredentialStatus.ACTIVE.value,
        TenantCredentialStatus.RENEWAL_DUE.value,
    }
    if active and desired_targets == effective_targets:
        credential.reconciliation_status = TenantCredentialReconciliationStatus.READY.value
        credential.reconciliation_message = 'Native Kubernetes credential identity matches committed Tenant intent.'
    elif not active and not effective_targets:
        credential.reconciliation_status = TenantCredentialReconciliationStatus.DISABLED.value
        credential.reconciliation_message = 'Tenant credential has no effective Kubernetes identity or binding.'
    else:
        credential.reconciliation_status = TenantCredentialReconciliationStatus.DRIFTED.value
        credential.reconciliation_message = 'Native Kubernetes credential identity differs from committed Tenant intent.'

    credential.reconciliation_evidence_json = {
        'generation': credential.rotation_generation,
        'desired_targets': desired_targets if active else [],
        'effective_targets': effective_targets,
        'secret_material_persisted': False,
    }
    return credential


def reconcile_native_credential(credential: TenantCredential) -> TenantCredential:
    validate_credential_contract(credential)
    cluster = _cluster_for_credential(credential)
    client = runtime_adapter.build_client(cluster)
    core_api = client.core_api()
    rbac_api = client.rbac_authorization_api()
    now = datetime.now(UTC)
    refresh_credential_status(credential, now=now)

    try:
        if credential.status not in {
            TenantCredentialStatus.ACTIVE.value,
            TenantCredentialStatus.RENEWAL_DUE.value,
        }:
            remove_native_credential_access(credential)
            return inspect_native_credential(credential)

        for target in credential_target_namespaces(credential):
            _upsert_service_account(core_api, credential, target.namespace)
            if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
                _upsert_human_binding(rbac_api, credential, target.namespace)
            else:
                _upsert_admin_binding(rbac_api, credential, target.namespace)
        return inspect_native_credential(credential)
    except (ApiException, ValueError) as exc:
        credential.reconciliation_status = TenantCredentialReconciliationStatus.FAILED.value
        credential.reconciliation_message = str(exc)[:1000]
        credential.last_reconciled_at = now
        credential.reconciliation_evidence_json = {
            **(credential.reconciliation_evidence_json or {}),
            'generation': credential.rotation_generation,
            'error': credential.reconciliation_message,
            'secret_material_persisted': False,
        }
        raise
