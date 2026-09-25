from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import (
    V1LimitRange,
    V1LimitRangeItem,
    V1LimitRangeSpec,
    V1Namespace,
    V1ObjectMeta,
    V1ResourceQuota,
    V1ResourceQuotaSpec,
)
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.validation import validate_namespace_name, validate_profile_spec
from app.models import Cluster
from app.models.tenant import (
    TenantEnvironment,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantResourceProfile,
)

_MANAGED_BY_KEY = 'app.kubernetes.io/managed-by'
_MANAGED_BY_VALUE = 'kaori'
_TENANT_ID_KEY = 'kaori.io/tenant-id'
_ENVIRONMENT_KEY = 'kaori.io/environment'
_PROFILE_ID_KEY = 'kaori.io/resource-profile'
_QUOTA_NAME = 'kaori-tenant-quota'
_LIMIT_RANGE_NAME = 'kaori-tenant-limits'


def _canonical_hash(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def desired_namespace_contract(
    *,
    tenant_environment: TenantEnvironment,
    namespace: str,
    profile: TenantResourceProfile,
    quota_hard: dict[str, str] | None = None,
    limit_defaults: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    tenant = tenant_environment.tenant
    normalized_namespace = validate_namespace_name(namespace)
    quota_source = profile.quota_hard_json if quota_hard is None else quota_hard
    limits_source = profile.limit_defaults_json if limit_defaults is None else limit_defaults
    quota, limits = validate_profile_spec(quota_source or {}, limits_source or {})
    return {
        'namespace': normalized_namespace,
        'labels': {
            _MANAGED_BY_KEY: _MANAGED_BY_VALUE,
            _TENANT_ID_KEY: tenant.id,
            _ENVIRONMENT_KEY: tenant_environment.environment,
            _PROFILE_ID_KEY: profile.public_id,
        },
        'quota': quota,
        'limits': limits,
        'provider_key': tenant.provider_key,
    }


def create_namespace_intent(
    *,
    tenant_environment: TenantEnvironment,
    profile: TenantResourceProfile,
    namespace: str,
) -> TenantNamespace:
    tenant = tenant_environment.tenant
    if tenant.lifecycle_status == 'decommissioned':
        raise ValueError('cannot provision a namespace for a decommissioned tenant')
    if tenant.cluster_id is None:
        raise ValueError('tenant must have an assigned Kubernetes cluster')
    if not profile.enabled:
        raise ValueError('resource profile is disabled')

    quota, limits = validate_profile_spec(profile.quota_hard_json or {}, profile.limit_defaults_json or {})
    desired = desired_namespace_contract(
        tenant_environment=tenant_environment,
        namespace=namespace,
        profile=profile,
        quota_hard=quota,
        limit_defaults=limits,
    )
    record = TenantNamespace()
    record.tenant_environment_id = tenant_environment.id
    record.cluster_id = tenant.cluster_id
    record.resource_profile_id = profile.id
    record.resource_profile_version = profile.version
    record.allocation_quota_json = quota
    record.allocation_limit_defaults_json = limits
    record.allocation_customized = False
    record.namespace = desired['namespace']
    record.provisioning_status = TenantNamespaceProvisioningStatus.PENDING.value
    record.desired_hash = _canonical_hash(desired)
    record.provisioning_evidence_json = {'desired': desired}
    db.session.add(record)
    db.session.flush()
    return record


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


def _upsert_namespace(api, desired: dict[str, Any]) -> None:
    name = desired['namespace']
    existing = _read_or_none(api.read_namespace, name)
    body = V1Namespace(metadata=V1ObjectMeta(name=name, labels=desired['labels']))
    if existing is None:
        api.create_namespace(body=body)
        return
    _managed_or_absent(existing.metadata, kind='Namespace')
    api.patch_namespace(name=name, body=body)


def _upsert_quota(api, desired: dict[str, Any]) -> None:
    namespace = desired['namespace']
    existing = _read_or_none(api.read_namespaced_resource_quota, _QUOTA_NAME, namespace)
    if not desired['quota']:
        if existing is not None:
            _managed_or_absent(existing.metadata, kind='ResourceQuota')
            api.delete_namespaced_resource_quota(name=_QUOTA_NAME, namespace=namespace)
        return

    body = V1ResourceQuota(
        metadata=V1ObjectMeta(name=_QUOTA_NAME, namespace=namespace, labels=desired['labels']),
        spec=V1ResourceQuotaSpec(hard=desired['quota']),
    )
    if existing is None:
        api.create_namespaced_resource_quota(namespace=namespace, body=body)
        return
    _managed_or_absent(existing.metadata, kind='ResourceQuota')
    api.patch_namespaced_resource_quota(name=_QUOTA_NAME, namespace=namespace, body=body)


def _limit_items(desired: dict[str, Any]) -> list[V1LimitRangeItem]:
    limits = desired['limits']
    if not limits:
        return []
    return [
        V1LimitRangeItem(
            type='Container',
            default=limits.get('default') or None,
            default_request=limits.get('default_request') or None,
        )
    ]


def _upsert_limit_range(api, desired: dict[str, Any]) -> None:
    namespace = desired['namespace']
    existing = _read_or_none(api.read_namespaced_limit_range, _LIMIT_RANGE_NAME, namespace)
    if not desired['limits']:
        if existing is not None:
            _managed_or_absent(existing.metadata, kind='LimitRange')
            api.delete_namespaced_limit_range(name=_LIMIT_RANGE_NAME, namespace=namespace)
        return

    body = V1LimitRange(
        metadata=V1ObjectMeta(name=_LIMIT_RANGE_NAME, namespace=namespace, labels=desired['labels']),
        spec=V1LimitRangeSpec(limits=_limit_items(desired)),
    )
    if existing is None:
        api.create_namespaced_limit_range(namespace=namespace, body=body)
        return
    _managed_or_absent(existing.metadata, kind='LimitRange')
    api.patch_namespaced_limit_range(name=_LIMIT_RANGE_NAME, namespace=namespace, body=body)


def _effective_contract(api, desired: dict[str, Any]) -> dict[str, Any]:
    namespace = desired['namespace']
    ns = api.read_namespace(namespace)
    quota = _read_or_none(api.read_namespaced_resource_quota, _QUOTA_NAME, namespace)
    limit_range = _read_or_none(api.read_namespaced_limit_range, _LIMIT_RANGE_NAME, namespace)
    item = (
        limit_range.spec.limits[0]
        if limit_range is not None and limit_range.spec and limit_range.spec.limits
        else None
    )
    return {
        'namespace': namespace,
        'labels': {key: (ns.metadata.labels or {}).get(key) for key in desired['labels']},
        'quota': {key: str(value) for key, value in ((quota.spec.hard or {}) if quota is not None else {}).items()},
        'limits': {
            'default': {key: str(value) for key, value in ((item.default or {}) if item else {}).items()},
            'default_request': {
                key: str(value) for key, value in ((item.default_request or {}) if item else {}).items()
            },
        }
        if limit_range is not None
        else {},
        'provider_key': desired['provider_key'],
    }


def reconcile_native_namespace(record: TenantNamespace) -> TenantNamespace:
    environment = record.environment
    tenant = environment.tenant
    profile = record.resource_profile
    if profile is None:
        raise ValueError('tenant namespace requires a Resource Profile')
    if tenant.provider_key != 'native_kubernetes':
        raise ValueError('native namespace reconciliation requires Native Kubernetes provider authority')

    cluster = db.session.get(Cluster, record.cluster_id)
    if cluster is None:
        raise ValueError('tenant namespace cluster no longer exists')

    if record.allocation_quota_json is None or record.allocation_limit_defaults_json is None:
        quota, limits = validate_profile_spec(profile.quota_hard_json or {}, profile.limit_defaults_json or {})
        record.resource_profile_version = record.resource_profile_version or profile.version
        record.allocation_quota_json = quota
        record.allocation_limit_defaults_json = limits
        record.allocation_customized = False

    desired = desired_namespace_contract(
        tenant_environment=environment,
        namespace=record.namespace,
        profile=profile,
        quota_hard=record.allocation_quota_json,
        limit_defaults=record.allocation_limit_defaults_json,
    )
    desired_hash = _canonical_hash(desired)
    record.desired_hash = desired_hash
    record.provisioning_status = TenantNamespaceProvisioningStatus.PENDING.value

    try:
        api = runtime_adapter.build_client(cluster).core_api()
        _upsert_namespace(api, desired)
        _upsert_quota(api, desired)
        _upsert_limit_range(api, desired)
        effective = _effective_contract(api, desired)
        effective_hash = _canonical_hash(effective)
        record.effective_hash = effective_hash
        record.last_reconciled_at = datetime.now(UTC)
        record.provisioning_evidence_json = {
            'allocation': {
                'resource_profile_id': profile.public_id,
                'resource_profile_version': record.resource_profile_version,
                'customized': record.allocation_customized,
            },
            'desired': desired,
            'effective': effective,
        }
        if effective_hash == desired_hash:
            record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
            record.provisioning_message = 'Namespace, ResourceQuota, and LimitRange match committed Tenant intent.'
        else:
            record.provisioning_status = TenantNamespaceProvisioningStatus.DRIFTED.value
            record.provisioning_message = 'Provider state does not match committed Tenant intent.'
    except (ApiException, ValueError) as exc:
        record.provisioning_status = TenantNamespaceProvisioningStatus.FAILED.value
        record.provisioning_message = str(exc)[:1000]
        record.last_reconciled_at = datetime.now(UTC)
        record.provisioning_evidence_json = {
            'allocation': {
                'resource_profile_id': profile.public_id,
                'resource_profile_version': record.resource_profile_version,
                'customized': record.allocation_customized,
            },
            'desired': desired,
            'error': record.provisioning_message,
        }
        raise

    return record
