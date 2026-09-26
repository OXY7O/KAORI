from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import V1ObjectMeta, V1Secret
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.models import Cluster
from app.models.tenant import (
    TenantManagedResourceIntent,
    TenantManagedResourceKind,
    TenantManagedResourceMode,
    TenantManagedResourceStatus,
)

_MANAGED_BY_KEY = 'app.kubernetes.io/managed-by'
_MANAGED_BY_VALUE = 'kaori'
_TENANT_ID_KEY = 'kaori.io/tenant-id'
_MANAGED_RESOURCE_KEY = 'kaori.io/managed-resource'
_PLATFORM_SECURITY_KEY = 'kaori.io/platform-security'
_PAYLOAD_DIGEST_KEY = 'kaori.io/payload-digest'


@dataclass(frozen=True, slots=True)
class ManagedResourceSecretMaterial:
    data: dict[str, str] = field(repr=False)


def _canonical_hash(payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _payload_digest(material: ManagedResourceSecretMaterial | None) -> str | None:
    if material is None:
        return None
    return _canonical_hash(material.data)


def _labels(intent: TenantManagedResourceIntent) -> dict[str, str]:
    return {
        _MANAGED_BY_KEY: _MANAGED_BY_VALUE,
        _TENANT_ID_KEY: intent.tenant_id,
        _MANAGED_RESOURCE_KEY: intent.public_id,
        _PLATFORM_SECURITY_KEY: 'true',
    }


def _read_or_none(reader, *args):
    try:
        return reader(*args)
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _managed_or_absent(meta: V1ObjectMeta | None, intent: TenantManagedResourceIntent) -> None:
    labels = dict((meta.labels or {}) if meta is not None else {})
    owner = labels.get(_MANAGED_BY_KEY)
    resource_id = labels.get(_MANAGED_RESOURCE_KEY)
    if owner and owner != _MANAGED_BY_VALUE:
        raise ValueError(f'Managed Secret is already owned by {owner}; refusing provider takeover.')
    if owner != _MANAGED_BY_VALUE or resource_id != intent.public_id:
        raise ValueError('Existing Secret is not owned by this KAORI managed-resource intent.')


def validate_managed_resource_intent(
    intent: TenantManagedResourceIntent,
    *,
    material: ManagedResourceSecretMaterial | None,
) -> None:
    if intent.namespace.environment.tenant_id != intent.tenant_id:
        raise ValueError('Managed resource namespace belongs to another Tenant.')

    kind = TenantManagedResourceKind(intent.resource_kind)
    mode = TenantManagedResourceMode(intent.mode)
    source_reference = str(intent.source_reference or '').strip()

    if kind is TenantManagedResourceKind.TLS:
        if mode is TenantManagedResourceMode.PLATFORM_TLS:
            if material is not None:
                raise ValueError('Platform TLS keeps private key material outside the Tenant namespace.')
            return
        if mode is not TenantManagedResourceMode.NAMESPACE_TLS_COMPAT:
            raise ValueError('TLS managed resources require Platform TLS or explicit namespace compatibility mode.')
        if not source_reference:
            raise ValueError('TLS compatibility mode requires a non-secret source reference.')
        if material is None or not {'tls.crt', 'tls.key'}.issubset(material.data):
            raise ValueError('TLS material must contain tls.crt and tls.key for compatibility mode.')
        return

    if mode is TenantManagedResourceMode.IMAGE_PULL_SECRET:
        if not source_reference:
            raise ValueError('Managed registry Secret requires a non-secret source reference.')
        if material is None or '.dockerconfigjson' not in material.data:
            raise ValueError('Managed registry material must contain .dockerconfigjson.')
        return
    if mode is TenantManagedResourceMode.EXTERNAL_CREDENTIAL_PROVIDER:
        if material is not None:
            raise ValueError('External registry credential provider must not receive namespace Secret material.')
        return
    raise ValueError('Registry managed resources require image-pull Secret or external credential provider mode.')


def _secret_type(intent: TenantManagedResourceIntent) -> str:
    if intent.mode == TenantManagedResourceMode.NAMESPACE_TLS_COMPAT.value:
        return 'kubernetes.io/tls'
    if intent.mode == TenantManagedResourceMode.IMAGE_PULL_SECRET.value:
        return 'kubernetes.io/dockerconfigjson'
    raise ValueError('This managed-resource mode does not materialize a Kubernetes Secret.')


def _delete_managed_secret(api, intent: TenantManagedResourceIntent) -> None:
    current = _read_or_none(api.read_namespaced_secret, intent.resource_name, intent.namespace.namespace)
    if current is None:
        return
    _managed_or_absent(current.metadata, intent)
    api.delete_namespaced_secret(name=intent.resource_name, namespace=intent.namespace.namespace)


def _upsert_managed_secret(
    api,
    intent: TenantManagedResourceIntent,
    material: ManagedResourceSecretMaterial,
) -> str:
    namespace = intent.namespace.namespace
    current = _read_or_none(api.read_namespaced_secret, intent.resource_name, namespace)
    if current is not None:
        _managed_or_absent(current.metadata, intent)
    digest = _payload_digest(material)
    annotations = {_PAYLOAD_DIGEST_KEY: str(digest)}
    body = V1Secret(
        metadata=V1ObjectMeta(
            name=intent.resource_name,
            namespace=namespace,
            labels=_labels(intent),
            annotations=annotations,
        ),
        type=_secret_type(intent),
        string_data=dict(material.data),
    )
    if current is None:
        api.create_namespaced_secret(namespace=namespace, body=body)
    else:
        api.patch_namespaced_secret(name=intent.resource_name, namespace=namespace, body=body)
    return str(digest)


def _effective_secret_contract(api, intent: TenantManagedResourceIntent) -> dict[str, object] | None:
    current = _read_or_none(api.read_namespaced_secret, intent.resource_name, intent.namespace.namespace)
    if current is None:
        return None
    return {
        'resource_name': current.metadata.name,
        'namespace': intent.namespace.namespace,
        'type': current.type,
        'labels': {key: (current.metadata.labels or {}).get(key) for key in _labels(intent)},
        'payload_digest': (current.metadata.annotations or {}).get(_PAYLOAD_DIGEST_KEY),
    }


def remove_native_managed_resource(intent: TenantManagedResourceIntent) -> TenantManagedResourceIntent:
    cluster = db.session.get(Cluster, intent.namespace.cluster_id)
    if cluster is None:
        raise ValueError('Tenant namespace cluster no longer exists.')
    api = runtime_adapter.build_client(cluster).core_api()
    if intent.mode in {
        TenantManagedResourceMode.NAMESPACE_TLS_COMPAT.value,
        TenantManagedResourceMode.IMAGE_PULL_SECRET.value,
    }:
        _delete_managed_secret(api, intent)
    intent.status = TenantManagedResourceStatus.DISABLED.value
    intent.last_reconciled_at = datetime.now(UTC)
    intent.reconciliation_message = 'Managed resource is disabled and has no KAORI-owned namespace Secret.'
    intent.reconciliation_evidence_json = {
        'mode': intent.mode,
        'resource_name': intent.resource_name,
        'secret_material_persisted': False,
        'removed': True,
    }
    return intent


def reconcile_native_managed_resource(
    intent: TenantManagedResourceIntent,
    *,
    material: ManagedResourceSecretMaterial | None = None,
    external_provider_ready: bool = False,
) -> TenantManagedResourceIntent:
    validate_managed_resource_intent(intent, material=material)
    cluster = db.session.get(Cluster, intent.namespace.cluster_id)
    if cluster is None:
        raise ValueError('Tenant namespace cluster no longer exists.')
    if intent.namespace.environment.tenant.provider_key != 'native_kubernetes':
        raise ValueError('Native managed-resource reconciliation requires Native Kubernetes provider authority.')

    now = datetime.now(UTC)
    api = runtime_adapter.build_client(cluster).core_api()
    desired: dict[str, object] = {
        'tenant_id': intent.tenant_id,
        'namespace': intent.namespace.namespace,
        'resource_kind': intent.resource_kind,
        'mode': intent.mode,
        'resource_name': intent.resource_name,
        'source_reference': intent.source_reference,
        'rotation_generation': intent.rotation_generation,
    }

    try:
        if intent.mode == TenantManagedResourceMode.PLATFORM_TLS.value:
            _delete_managed_secret(api, intent)
            desired['platform_termination'] = True
            effective = dict(desired)
        elif intent.mode == TenantManagedResourceMode.EXTERNAL_CREDENTIAL_PROVIDER.value:
            _delete_managed_secret(api, intent)
            if not external_provider_ready:
                raise ValueError('External registry credential provider capability is not Ready on this cluster.')
            desired['external_credential_provider'] = True
            effective = dict(desired)
        else:
            if material is None:
                raise ValueError('Managed namespace Secret reconciliation requires ephemeral secret material.')
            digest = _upsert_managed_secret(api, intent, material)
            desired['secret_type'] = _secret_type(intent)
            desired['payload_digest'] = digest
            effective = _effective_secret_contract(api, intent)

        intent.desired_hash = _canonical_hash(desired)
        intent.effective_hash = _canonical_hash(effective)
        intent.last_reconciled_at = now
        intent.reconciliation_evidence_json = {
            'desired': desired,
            'effective': effective,
            'secret_material_persisted': False,
        }
        if intent.desired_hash == intent.effective_hash:
            intent.status = TenantManagedResourceStatus.READY.value
            intent.reconciliation_message = 'Managed Tenant resource matches committed platform-security intent.'
        else:
            intent.status = TenantManagedResourceStatus.DRIFTED.value
            intent.reconciliation_message = 'Managed Tenant resource differs from committed platform-security intent.'
    except (ApiException, ValueError) as exc:
        intent.status = TenantManagedResourceStatus.FAILED.value
        intent.last_reconciled_at = now
        intent.reconciliation_message = str(exc)[:1000]
        intent.reconciliation_evidence_json = {
            **(intent.reconciliation_evidence_json or {}),
            'mode': intent.mode,
            'resource_name': intent.resource_name,
            'error': intent.reconciliation_message,
            'secret_material_persisted': False,
        }
        raise
    return intent
