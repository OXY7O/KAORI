from __future__ import annotations

import hashlib
import json
import time
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
from app.kubernetes.tenant.validation import validate_namespace_name, validate_profile_spec, validate_storage_policy
from app.models import Cluster
from app.models.tenant import (
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
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
    storage_policy: dict[str, str] | None = None,
) -> dict[str, Any]:
    tenant = tenant_environment.tenant
    normalized_namespace = validate_namespace_name(namespace)
    quota_source = profile.quota_hard_json if quota_hard is None else quota_hard
    limits_source = profile.limit_defaults_json if limit_defaults is None else limit_defaults
    storage_source = profile.storage_policy_json if storage_policy is None else storage_policy
    quota, limits = validate_profile_spec(quota_source or {}, limits_source or {})
    normalized_storage = validate_storage_policy(storage_source or {})
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
        'storage_policy': normalized_storage,
        'provider_key': tenant.provider_key,
    }


def create_namespace_intent(
    *,
    tenant_environment: TenantEnvironment,
    profile: TenantResourceProfile,
    namespace: str,
    quota_hard: dict[str, str] | None = None,
    limit_defaults: dict[str, dict[str, str]] | None = None,
    storage_policy: dict[str, str] | None = None,
    allocation_customized: bool = False,
) -> TenantNamespace:
    tenant = tenant_environment.tenant
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant must be Ready before provisioning a namespace.')
    if tenant.cluster_id is None:
        raise ValueError('tenant must have an assigned Kubernetes cluster')
    if not profile.enabled:
        raise ValueError('resource profile is disabled')

    quota_source = profile.quota_hard_json if quota_hard is None else quota_hard
    limits_source = profile.limit_defaults_json if limit_defaults is None else limit_defaults
    storage_source = profile.storage_policy_json if storage_policy is None else storage_policy
    quota, limits = validate_profile_spec(quota_source or {}, limits_source or {})
    normalized_storage = validate_storage_policy(storage_source or {})
    desired = desired_namespace_contract(
        tenant_environment=tenant_environment,
        namespace=namespace,
        profile=profile,
        quota_hard=quota,
        limit_defaults=limits,
        storage_policy=normalized_storage,
    )
    record = TenantNamespace()
    record.tenant_environment_id = tenant_environment.id
    record.cluster_id = tenant.cluster_id
    record.resource_profile_id = profile.id
    record.resource_profile_version = profile.version
    record.allocation_quota_json = quota
    record.allocation_limit_defaults_json = limits
    record.allocation_storage_policy_json = normalized_storage
    record.allocation_customized = allocation_customized
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
    items: list[V1LimitRangeItem] = []
    limits = desired.get('limits') or {}
    if limits:
        items.append(
            V1LimitRangeItem(
                type='Container',
                default=limits.get('default') or None,
                default_request=limits.get('default_request') or None,
            )
        )

    storage = validate_storage_policy(desired.get('storage_policy') or {})
    if storage:
        items.append(
            V1LimitRangeItem(
                type='PersistentVolumeClaim',
                min={'storage': storage['min']} if storage.get('min') else None,
                max={'storage': storage['max']} if storage.get('max') else None,
                default={'storage': storage['default']} if storage.get('default') else None,
                default_request=(
                    {'storage': storage['default_request']}
                    if storage.get('default_request')
                    else None
                ),
            )
        )
    return items


def _upsert_limit_range(api, desired: dict[str, Any]) -> None:
    namespace = desired['namespace']
    existing = _read_or_none(api.read_namespaced_limit_range, _LIMIT_RANGE_NAME, namespace)
    if not desired.get('limits') and not desired.get('storage_policy'):
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

    container_item = None
    pvc_item = None
    for item in list(
        (limit_range.spec.limits or [])
        if limit_range is not None and limit_range.spec
        else []
    ):
        item_type = str(getattr(item, 'type', '') or '')
        if item_type == 'Container':
            container_item = item
        elif item_type == 'PersistentVolumeClaim':
            pvc_item = item

    effective_limits = {}
    if container_item is not None:
        effective_limits = {
            'default': {
                key: str(value)
                for key, value in dict(container_item.default or {}).items()
            },
            'default_request': {
                key: str(value)
                for key, value in dict(container_item.default_request or {}).items()
            },
        }
        effective_limits = {key: value for key, value in effective_limits.items() if value}

    storage_policy: dict[str, str] = {}
    if pvc_item is not None:
        for field, value in (
            ('min', getattr(pvc_item, 'min', None)),
            ('max', getattr(pvc_item, 'max', None)),
            ('default', getattr(pvc_item, 'default', None)),
            ('default_request', getattr(pvc_item, 'default_request', None)),
        ):
            storage = dict(value or {}).get('storage')
            if storage not in (None, ''):
                storage_policy[field] = str(storage)
    storage_policy = validate_storage_policy(storage_policy)

    return {
        'namespace': namespace,
        'labels': {key: (ns.metadata.labels or {}).get(key) for key in desired['labels']},
        'quota': {key: str(value) for key, value in ((quota.spec.hard or {}) if quota is not None else {}).items()},
        'limits': effective_limits,
        'storage_policy': storage_policy,
        'provider_key': desired['provider_key'],
    }


def _namespace_delete_observation(api, name: str) -> tuple[bool, dict[str, Any]]:
    current = _read_or_none(api.read_namespace, name)
    if current is None:
        return True, {
            'namespace': name,
            'observed_absent': True,
            'phase': 'Absent',
            'deletion_timestamp': None,
            'finalizers': [],
        }

    metadata = getattr(current, 'metadata', None)
    spec = getattr(current, 'spec', None)
    status = getattr(current, 'status', None)
    finalizers = list(getattr(spec, 'finalizers', None) or getattr(metadata, 'finalizers', None) or [])
    deletion_timestamp = getattr(metadata, 'deletion_timestamp', None)
    phase = str(getattr(status, 'phase', None) or ('Terminating' if deletion_timestamp else 'Present'))
    return False, {
        'namespace': name,
        'observed_absent': False,
        'phase': phase,
        'deletion_timestamp': (
            deletion_timestamp.isoformat()
            if isinstance(deletion_timestamp, datetime)
            else str(deletion_timestamp or '')
        ),
        'finalizers': [str(item) for item in finalizers],
    }


def deprovision_native_namespace(
    record: TenantNamespace,
    *,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> TenantNamespace:
    """Delete one KAORI-managed namespace and prove provider absence.

    Namespace deletion is intentionally observation-driven: a successful DELETE
    request is not treated as teardown completion. KAORI waits until Kubernetes
    returns 404 and surfaces Terminating/finalizer evidence when the timeout is
    reached. Finalizers are never force-removed by this managed path.
    """

    tenant = record.environment.tenant
    if tenant.provider_key != 'native_kubernetes' or tenant.provider_state != 'native':
        raise ValueError('Native namespace deprovisioning requires Native Kubernetes provider authority.')
    if tenant.reconciliation_authority != 'native_kubernetes':
        raise ValueError('Native namespace deprovisioning requires Native Kubernetes reconciliation authority.')
    if record.ownership_status != TenantOwnershipStatus.MANAGED.value:
        raise ValueError('Automatic namespace deprovisioning is limited to KAORI-managed namespaces.')

    cluster = db.session.get(Cluster, record.cluster_id)
    if cluster is None:
        raise ValueError('Tenant namespace cluster no longer exists.')

    api = runtime_adapter.build_client(cluster).core_api()
    current = _read_or_none(api.read_namespace, record.namespace)
    if current is not None:
        _managed_or_absent(getattr(current, 'metadata', None), kind='Namespace')

    record.provisioning_status = TenantNamespaceProvisioningStatus.DEPROVISIONING.value
    record.provisioning_message = 'Namespace deletion requested; waiting for Kubernetes to confirm absence.'
    record.last_reconciled_at = datetime.now(UTC)

    try:
        if current is not None:
            try:
                api.delete_namespace(name=record.namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise

        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        observed_absent, observation = _namespace_delete_observation(api, record.namespace)
        while not observed_absent and time.monotonic() < deadline:
            time.sleep(max(float(poll_interval_seconds), 0.0))
            observed_absent, observation = _namespace_delete_observation(api, record.namespace)

        record.last_reconciled_at = datetime.now(UTC)
        evidence = dict(record.provisioning_evidence_json or {})
        evidence['deprovision'] = {
            **observation,
            'provider': 'native_kubernetes',
            'observed_at': record.last_reconciled_at.isoformat(),
            'secret_material_persisted': False,
        }
        record.provisioning_evidence_json = evidence

        if not observed_absent:
            finalizers = ', '.join(observation.get('finalizers') or []) or 'none reported'
            phase = str(observation.get('phase') or 'Terminating')
            record.provisioning_status = TenantNamespaceProvisioningStatus.FAILED.value
            record.provisioning_message = (
                f'Namespace deletion is still {phase}; provider absence was not observed before timeout. '
                f'Finalizers: {finalizers}. Resolve the blocker and retry.'
            )
            raise ValueError(record.provisioning_message)

        record.provisioning_status = TenantNamespaceProvisioningStatus.DEPROVISIONED.value
        record.provisioning_message = 'Kubernetes confirmed the namespace is absent.'
        record.effective_hash = None
        return record
    except ApiException as exc:
        record.provisioning_status = TenantNamespaceProvisioningStatus.FAILED.value
        record.provisioning_message = str(exc)[:1000]
        record.last_reconciled_at = datetime.now(UTC)
        evidence = dict(record.provisioning_evidence_json or {})
        evidence['deprovision'] = {
            'namespace': record.namespace,
            'provider': 'native_kubernetes',
            'observed_absent': False,
            'error': record.provisioning_message,
            'observed_at': record.last_reconciled_at.isoformat(),
            'secret_material_persisted': False,
        }
        record.provisioning_evidence_json = evidence
        raise


def deprovision_native_namespace_committed(
    *,
    namespace_id: int,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> TenantNamespace:
    record = db.session.get(TenantNamespace, namespace_id)
    if record is None:
        raise ValueError('Selected Tenant namespace no longer exists.')
    if record.provisioning_status == TenantNamespaceProvisioningStatus.DEPROVISIONED.value:
        return record

    try:
        deprovision_native_namespace(
            record,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        db.session.commit()
        return record
    except (ApiException, ValueError):
        # Preserve fail-closed teardown evidence so retry/UAT can see the exact
        # Terminating/finalizer or provider error instead of rolling it away.
        if record.id is not None:
            db.session.commit()
        raise


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

    if (
        record.allocation_quota_json is None
        or record.allocation_limit_defaults_json is None
        or record.allocation_storage_policy_json is None
    ):
        quota, limits = validate_profile_spec(profile.quota_hard_json or {}, profile.limit_defaults_json or {})
        storage_policy = validate_storage_policy(profile.storage_policy_json or {})
        record.resource_profile_version = record.resource_profile_version or profile.version
        record.allocation_quota_json = quota
        record.allocation_limit_defaults_json = limits
        record.allocation_storage_policy_json = storage_policy
        record.allocation_customized = False

    desired = desired_namespace_contract(
        tenant_environment=environment,
        namespace=record.namespace,
        profile=profile,
        quota_hard=record.allocation_quota_json,
        limit_defaults=record.allocation_limit_defaults_json,
        storage_policy=record.allocation_storage_policy_json or {},
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
                'capacity_decision_id': record.capacity_decision_id,
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
