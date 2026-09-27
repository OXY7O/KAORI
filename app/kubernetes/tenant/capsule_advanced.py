from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from kubernetes.client import V1DeleteOptions
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_provider import CapsuleTenantProvider, require_capsule_capability
from app.models import Cluster
from app.models.tenant_advanced import (
    TenantAdvancedCapabilityIntent,
    TenantAdvancedCapabilityStatus,
)

_CAPSULE_GROUP = 'capsule.clastix.io'
_ADVANCED_API_VERSION = 'v1beta2'
_MANAGED_BY_LABEL = 'app.kubernetes.io/managed-by'
_INTENT_LABEL = 'kaori.io/tenant-advanced-intent'


class CapsuleAdvancedResourceKind(StrEnum):
    GLOBAL_RESOURCE_QUOTA = 'global_resource_quota'
    RESOURCE_POOL = 'resource_pool'
    RESOURCE_POOL_CLAIM = 'resource_pool_claim'
    TENANT_RESOURCE = 'tenant_resource'
    GLOBAL_TENANT_RESOURCE = 'global_tenant_resource'
    TENANT_CORDON = 'tenant_cordon'
    NAMESPACE_CONTROLS = 'namespace_controls'
    RESOURCE_RULES = 'resource_rules'
    CROSS_NAMESPACE_CREDENTIAL = 'cross_namespace_credential'


@dataclass(frozen=True, slots=True)
class CapsuleResourceDescriptor:
    capability: str
    plural: str | None
    api_kind: str | None
    namespaced: bool
    tenant_patch: bool = False
    evidence_only: bool = False
    allowed_spec_keys: frozenset[str] = frozenset()
    reset_spec: dict[str, object] | None = None


_DESCRIPTORS = {
    CapsuleAdvancedResourceKind.GLOBAL_RESOURCE_QUOTA: CapsuleResourceDescriptor(
        capability='shared_global_quota',
        plural='globalresourcequotas',
        api_kind='GlobalResourceQuota',
        namespaced=False,
    ),
    CapsuleAdvancedResourceKind.RESOURCE_POOL: CapsuleResourceDescriptor(
        capability='resource_pools',
        plural='resourcepools',
        api_kind='ResourcePool',
        namespaced=False,
    ),
    CapsuleAdvancedResourceKind.RESOURCE_POOL_CLAIM: CapsuleResourceDescriptor(
        capability='resource_pools',
        plural='resourcepoolclaims',
        api_kind='ResourcePoolClaim',
        namespaced=True,
    ),
    CapsuleAdvancedResourceKind.TENANT_RESOURCE: CapsuleResourceDescriptor(
        capability='replication',
        plural='tenantresources',
        api_kind='TenantResource',
        namespaced=True,
    ),
    CapsuleAdvancedResourceKind.GLOBAL_TENANT_RESOURCE: CapsuleResourceDescriptor(
        capability='replication',
        plural='globaltenantresources',
        api_kind='GlobalTenantResource',
        namespaced=False,
    ),
    CapsuleAdvancedResourceKind.TENANT_CORDON: CapsuleResourceDescriptor(
        capability='tenant_cordon',
        plural='tenants',
        api_kind='Tenant',
        namespaced=False,
        tenant_patch=True,
        allowed_spec_keys=frozenset({'cordoned', 'preventDeletion'}),
        reset_spec={'cordoned': False, 'preventDeletion': False},
    ),
    CapsuleAdvancedResourceKind.NAMESPACE_CONTROLS: CapsuleResourceDescriptor(
        capability='namespace_controls',
        plural='tenants',
        api_kind='Tenant',
        namespaced=False,
        tenant_patch=True,
        allowed_spec_keys=frozenset({'forceTenantPrefix', 'namespaceOptions'}),
        reset_spec={'forceTenantPrefix': None, 'namespaceOptions': None},
    ),
    CapsuleAdvancedResourceKind.RESOURCE_RULES: CapsuleResourceDescriptor(
        capability='resource_rules',
        plural='tenants',
        api_kind='Tenant',
        namespaced=False,
        tenant_patch=True,
        allowed_spec_keys=frozenset({'containerRegistries', 'priorityClasses', 'rules', 'storageClasses'}),
        reset_spec={
            'containerRegistries': None,
            'priorityClasses': None,
            'rules': None,
            'storageClasses': None,
        },
    ),
    CapsuleAdvancedResourceKind.CROSS_NAMESPACE_CREDENTIAL: CapsuleResourceDescriptor(
        capability='cross_namespace_credential',
        plural=None,
        api_kind=None,
        namespaced=False,
        evidence_only=True,
        allowed_spec_keys=frozenset({'approved_namespaces', 'requested_namespaces'}),
    ),
}


def capsule_resource_descriptor(kind: CapsuleAdvancedResourceKind | str) -> CapsuleResourceDescriptor:
    selected = CapsuleAdvancedResourceKind(kind)
    descriptor = _DESCRIPTORS.get(selected)
    if descriptor is None:
        raise ValueError(f'Unsupported Capsule advanced resource kind: {selected.value}.')
    return descriptor


def _canonical_hash(payload: object) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _project_desired(desired: object, effective: object) -> object:
    if isinstance(desired, dict):
        current = effective if isinstance(effective, dict) else {}
        return {key: _project_desired(value, current.get(key)) for key, value in desired.items()}
    if isinstance(desired, list):
        return effective if isinstance(effective, list) else []
    return effective


def _namespace_name(intent: TenantAdvancedCapabilityIntent) -> str:
    namespace = intent.namespace
    if namespace is None:
        raise ValueError('Advanced Capsule resource requires a governed Tenant namespace.')
    return namespace.namespace


def _labels(intent: TenantAdvancedCapabilityIntent) -> dict[str, str]:
    return {
        _MANAGED_BY_LABEL: 'kaori',
        _INTENT_LABEL: intent.public_id,
        'kaori.io/tenant-id': intent.tenant_id,
    }


def validate_cross_namespace_credential_scope(
    provider: CapsuleTenantProvider,
    *,
    cluster_id: str,
    approved_namespaces: set[str],
    requested_namespaces: set[str],
) -> tuple[str, ...]:
    require_capsule_capability(
        provider,
        cluster_id=cluster_id,
        capability='cross_namespace_credential',
    )
    if not requested_namespaces:
        raise ValueError('Cross-namespace credential scope requires at least one requested namespace.')
    if not requested_namespaces.issubset(approved_namespaces):
        raise ValueError('Cross-namespace credential scope exceeds the explicitly approved namespaces.')
    return tuple(sorted(requested_namespaces))


def validate_advanced_intent(
    intent: TenantAdvancedCapabilityIntent | Any,
    *,
    provider: CapsuleTenantProvider,
) -> CapsuleResourceDescriptor:
    provider_key = str(getattr(intent, 'provider_key', '') or '')
    if provider_key != 'capsule':
        raise ValueError('Capsule provider authority is required for advanced Tenant capabilities.')

    tenant = getattr(intent, 'tenant', None)
    if tenant is not None:
        provider.validate_tenant_authority(tenant)
        if str(getattr(tenant, 'provider_state', '') or '') != 'capsule':
            from app.kubernetes.tenant.providers import TenantProviderError

            raise TenantProviderError(
                'capsule_provider_degraded',
                'Advanced Capsule mutations fail closed unless Capsule is the healthy reconciliation authority.',
            )

    if _ADVANCED_API_VERSION not in provider.snapshot.tenant_api_versions:
        from app.kubernetes.tenant.providers import TenantProviderError

        raise TenantProviderError(
            'capsule_advanced_api_unavailable',
            'Advanced Capsule resources require served capsule.clastix.io/v1beta2.',
        )

    descriptor = capsule_resource_descriptor(str(getattr(intent, 'resource_kind', '') or ''))
    cluster_id = str(getattr(tenant, 'cluster_id', '') or getattr(intent, 'cluster_id', '') or '')
    require_capsule_capability(provider, cluster_id=cluster_id, capability=descriptor.capability)

    namespace = getattr(intent, 'namespace', None)
    if descriptor.namespaced and namespace is None:
        raise ValueError('This advanced Capsule resource requires a governed Tenant namespace.')
    if namespace is not None and tenant is not None and namespace.environment.tenant_id != tenant.id:
        raise ValueError('Advanced Capsule resource namespace belongs to another Tenant.')

    desired = getattr(intent, 'desired_spec_json', None)
    if not isinstance(desired, dict) or not desired:
        raise ValueError('Advanced Capsule resource requires a non-empty desired specification.')

    if descriptor.allowed_spec_keys and not set(desired).issubset(descriptor.allowed_spec_keys):
        raise ValueError('Advanced Capsule resource contains fields outside the approved capability contract.')

    if descriptor.evidence_only:
        approved = {str(value) for value in desired.get('approved_namespaces', [])}
        requested = {str(value) for value in desired.get('requested_namespaces', [])}
        validate_cross_namespace_credential_scope(
            provider,
            cluster_id=cluster_id,
            approved_namespaces=approved,
            requested_namespaces=requested,
        )

    if not str(getattr(intent, 'resource_name', '') or '').strip():
        raise ValueError('Advanced Capsule resource name is required.')
    return descriptor


def _read_custom_object(api, intent: TenantAdvancedCapabilityIntent, descriptor: CapsuleResourceDescriptor):
    try:
        if descriptor.namespaced:
            return api.get_namespaced_custom_object(
                _CAPSULE_GROUP,
                _ADVANCED_API_VERSION,
                _namespace_name(intent),
                str(descriptor.plural),
                intent.resource_name,
            )
        return api.get_cluster_custom_object(
            _CAPSULE_GROUP,
            _ADVANCED_API_VERSION,
            str(descriptor.plural),
            intent.resource_name,
        )
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _desired_body(intent: TenantAdvancedCapabilityIntent, descriptor: CapsuleResourceDescriptor) -> dict[str, object]:
    if descriptor.tenant_patch:
        return {'spec': dict(intent.desired_spec_json)}
    return {
        'apiVersion': f'{_CAPSULE_GROUP}/{_ADVANCED_API_VERSION}',
        'kind': str(descriptor.api_kind),
        'metadata': {'name': intent.resource_name, 'labels': _labels(intent)},
        'spec': dict(intent.desired_spec_json),
    }


def _write_custom_object(api, intent: TenantAdvancedCapabilityIntent, descriptor: CapsuleResourceDescriptor):
    body = _desired_body(intent, descriptor)
    if descriptor.tenant_patch:
        api.patch_cluster_custom_object(
            _CAPSULE_GROUP,
            _ADVANCED_API_VERSION,
            'tenants',
            intent.resource_name,
            body,
        )
        return _read_custom_object(api, intent, descriptor)

    current = _read_custom_object(api, intent, descriptor)
    if descriptor.namespaced:
        namespace = _namespace_name(intent)
        if current is None:
            api.create_namespaced_custom_object(
                _CAPSULE_GROUP,
                _ADVANCED_API_VERSION,
                namespace,
                str(descriptor.plural),
                body,
            )
        else:
            api.patch_namespaced_custom_object(
                _CAPSULE_GROUP,
                _ADVANCED_API_VERSION,
                namespace,
                str(descriptor.plural),
                intent.resource_name,
                body,
            )
    elif current is None:
        api.create_cluster_custom_object(
            _CAPSULE_GROUP,
            _ADVANCED_API_VERSION,
            str(descriptor.plural),
            body,
        )
    else:
        api.patch_cluster_custom_object(
            _CAPSULE_GROUP,
            _ADVANCED_API_VERSION,
            str(descriptor.plural),
            intent.resource_name,
            body,
        )
    return _read_custom_object(api, intent, descriptor)


def reconcile_capsule_advanced_intent(
    intent: TenantAdvancedCapabilityIntent,
    *,
    provider: CapsuleTenantProvider,
) -> TenantAdvancedCapabilityIntent:
    descriptor = validate_advanced_intent(intent, provider=provider)
    now = datetime.now(UTC)
    desired = dict(intent.desired_spec_json)

    if descriptor.evidence_only:
        effective = dict(desired)
    else:
        cluster = db.session.get(Cluster, intent.tenant.cluster_id)
        if cluster is None:
            raise ValueError('Tenant cluster no longer exists.')
        api = runtime_adapter.build_client(cluster).custom_objects_api()
        observed = _write_custom_object(api, intent, descriptor) or {}
        observed_spec = observed.get('spec') if isinstance(observed, dict) else {}
        effective = _project_desired(desired, observed_spec)

    intent.provider_api_version = _ADVANCED_API_VERSION
    intent.desired_hash = _canonical_hash(desired)
    intent.effective_spec_json = effective if isinstance(effective, dict) else {}
    intent.effective_hash = _canonical_hash(intent.effective_spec_json)
    intent.last_reconciled_at = now
    intent.reconciliation_evidence_json = {
        'provider_key': 'capsule',
        'provider_api_version': _ADVANCED_API_VERSION,
        'capability': descriptor.capability,
        'resource_kind': intent.resource_kind,
        'resource_name': intent.resource_name,
        'namespace': _namespace_name(intent) if intent.namespace is not None else None,
        'secret_material_persisted': False,
    }
    if intent.desired_hash == intent.effective_hash:
        intent.status = TenantAdvancedCapabilityStatus.READY.value
        intent.reconciliation_message = 'Advanced Capsule capability matches committed Tenant intent.'
    else:
        intent.status = TenantAdvancedCapabilityStatus.DRIFTED.value
        intent.reconciliation_message = 'Advanced Capsule capability differs from committed Tenant intent.'
    return intent


def remove_capsule_advanced_intent(
    intent: TenantAdvancedCapabilityIntent,
    *,
    provider: CapsuleTenantProvider,
) -> TenantAdvancedCapabilityIntent:
    descriptor = validate_advanced_intent(intent, provider=provider)
    if not descriptor.evidence_only:
        cluster = db.session.get(Cluster, intent.tenant.cluster_id)
        if cluster is None:
            raise ValueError('Tenant cluster no longer exists.')
        api = runtime_adapter.build_client(cluster).custom_objects_api()
        if descriptor.tenant_patch:
            api.patch_cluster_custom_object(
                _CAPSULE_GROUP,
                _ADVANCED_API_VERSION,
                'tenants',
                intent.resource_name,
                {'spec': dict(descriptor.reset_spec or {})},
            )
        elif descriptor.namespaced:
            api.delete_namespaced_custom_object(
                _CAPSULE_GROUP,
                _ADVANCED_API_VERSION,
                _namespace_name(intent),
                str(descriptor.plural),
                intent.resource_name,
                body=V1DeleteOptions(),
            )
        else:
            api.delete_cluster_custom_object(
                _CAPSULE_GROUP,
                _ADVANCED_API_VERSION,
                str(descriptor.plural),
                intent.resource_name,
                body=V1DeleteOptions(),
            )

    intent.status = TenantAdvancedCapabilityStatus.DISABLED.value
    intent.effective_spec_json = {}
    intent.effective_hash = _canonical_hash({})
    intent.last_reconciled_at = datetime.now(UTC)
    intent.reconciliation_message = 'Advanced Capsule capability intent is disabled.'
    intent.reconciliation_evidence_json = {
        **(intent.reconciliation_evidence_json or {}),
        'removed': True,
        'secret_material_persisted': False,
    }
    return intent
