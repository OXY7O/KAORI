from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import InvalidOperation
from typing import Any

from kubernetes.client import (
    V1DeleteOptions,
    V1LimitRange,
    V1LimitRangeItem,
    V1LimitRangeSpec,
    V1ObjectMeta,
    V1Preconditions,
    V1ResourceQuota,
    V1ResourceQuotaSpec,
)
from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_observation import observe_native_namespace_allocation
from app.kubernetes.tenant.validation import COUNT_QUOTA_KEYS, validate_profile_spec, validate_storage_policy
from app.models import Cluster
from app.models.tenant import TenantNamespace, TenantOwnershipStatus, TenantResourceProfile

_MANAGED_BY_KEY = 'app.kubernetes.io/managed-by'
_MANAGED_BY_VALUE = 'kaori'
_TENANT_ID_KEY = 'kaori.io/tenant-id'
_ENVIRONMENT_KEY = 'kaori.io/environment'
_PROFILE_ID_KEY = 'kaori.io/resource-profile'
_DEFAULT_QUOTA_NAME = 'kaori-tenant-quota'
_DEFAULT_LIMIT_RANGE_NAME = 'kaori-tenant-limits'


def allocation_control_state(record: TenantNamespace) -> str:
    evidence = dict(record.provisioning_evidence_json or {})
    explicit = str(evidence.get('allocation_control_state') or '').strip()
    if explicit:
        return explicit
    allocation = evidence.get('allocation')
    if isinstance(allocation, dict):
        explicit = str(allocation.get('control_state') or '').strip()
        if explicit == 'observed':
            return 'adopted_observed'
        if explicit:
            return explicit
    return 'kaori_managed' if record.ownership_status == TenantOwnershipStatus.MANAGED.value else 'adopted_observed'


def _source_resources(record: TenantNamespace) -> list[dict[str, str]]:
    evidence = dict(record.provisioning_evidence_json or {})
    allocation = evidence.get('allocation')
    if not isinstance(allocation, dict):
        return []
    resources = allocation.get('source_resources')
    if not isinstance(resources, list):
        return []
    return [dict(item) for item in resources if isinstance(item, dict)]


def build_allocation_cutover_state(record: TenantNamespace) -> dict[str, Any]:
    tenant = record.environment.tenant
    control = allocation_control_state(record)
    if control == 'kaori_managed':
        return {
            'supported': False,
            'state': 'kaori_managed',
            'reason': 'Allocation governance is already managed by KAORI.',
            'authority': tenant.reconciliation_authority,
        }
    if record.ownership_status != TenantOwnershipStatus.ADOPTED.value:
        return {
            'supported': False,
            'state': 'not_adopted',
            'reason': 'Governance cutover applies only to adopted Namespace allocations.',
            'authority': tenant.reconciliation_authority,
        }

    evidence = dict(record.provisioning_evidence_json or {})
    allocation = evidence.get('allocation')
    if not isinstance(allocation, dict) or allocation.get('provenance') != 'adopted_observed':
        return {
            'supported': False,
            'state': 'control_unavailable',
            'reason': 'Committed Adopted / Observed allocation evidence is missing.',
            'authority': tenant.reconciliation_authority,
        }
    if allocation.get('control_state') != 'observed':
        return {
            'supported': False,
            'state': 'control_unavailable',
            'reason': str(allocation.get('control_reason') or 'Observed allocation authority is not safe for cutover.'),
            'authority': tenant.reconciliation_authority,
        }

    if tenant.provider_key == 'capsule':
        tenant_evidence = dict(tenant.provider_evidence_json or {})
        baseline = tenant_evidence.get('allocation_baseline')
        authority = str(baseline.get('allocation_authority') or 'capsule') if isinstance(baseline, dict) else 'capsule'
        return {
            'supported': False,
            'state': 'control_unavailable',
            'reason': (
                'Capsule allocation cutover requires an admitted Capsule mutation capability. '
                'KAORI will not bypass Capsule by writing Native quota directly.'
            ),
            'authority': authority,
        }

    if tenant.provider_key != 'native_kubernetes' or tenant.reconciliation_authority != 'native_kubernetes':
        return {
            'supported': False,
            'state': 'control_unavailable',
            'reason': 'Native allocation cutover requires Native Kubernetes reconciliation authority.',
            'authority': tenant.reconciliation_authority,
        }

    resources = _source_resources(record)
    quota_sources = [item for item in resources if item.get('kind') == 'ResourceQuota']
    limit_sources = [item for item in resources if item.get('kind') == 'LimitRange']
    if len(quota_sources) > 1 or len(limit_sources) > 1:
        return {
            'supported': False,
            'state': 'control_unavailable',
            'reason': (
                'Initial governance cutover supports at most one authoritative ResourceQuota and one LimitRange. '
                'Multiple legacy sources require explicit operator consolidation first.'
            ),
            'authority': 'native_kubernetes',
        }

    return {
        'supported': True,
        'state': 'adopted_observed',
        'reason': 'Native ResourceQuota / LimitRange authority is eligible for explicit governance cutover.',
        'authority': 'native_kubernetes',
    }


def _metadata_value(metadata: Any, key: str, fallback: str = '') -> str:
    value = getattr(metadata, key, None)
    return str(value if value not in (None, '') else fallback)


def _observed_source(observation: dict[str, Any], kind: str) -> dict[str, str] | None:
    resources = observation.get('source_resources')
    if not isinstance(resources, list):
        return None
    matches = [dict(item) for item in resources if isinstance(item, dict) and item.get('kind') == kind]
    if len(matches) > 1:
        raise ValueError(f'Allocation reconciliation requires one authoritative {kind}; multiple sources remain.')
    return matches[0] if matches else None


def _expected_source(record: TenantNamespace, kind: str) -> dict[str, str] | None:
    evidence = dict(record.provisioning_evidence_json or {})
    managed_names = evidence.get('managed_resource_names')
    if allocation_control_state(record) == 'kaori_managed' and isinstance(managed_names, dict):
        name = str(managed_names.get('quota' if kind == 'ResourceQuota' else 'limit_range') or '').strip()
        if name:
            return {'kind': kind, 'name': name, 'uid': '', 'resource_version': ''}

    matches = [item for item in _source_resources(record) if item.get('kind') == kind]
    if len(matches) > 1:
        raise ValueError(f'Allocation governance requires one authoritative {kind}; multiple sources remain.')
    return matches[0] if matches else None


def _labels(record: TenantNamespace, profile: TenantResourceProfile) -> dict[str, str]:
    return {
        _MANAGED_BY_KEY: _MANAGED_BY_VALUE,
        _TENANT_ID_KEY: record.environment.tenant.id,
        _ENVIRONMENT_KEY: record.environment.environment,
        _PROFILE_ID_KEY: profile.public_id,
    }


def _verify_existing(existing: Any, expected: dict[str, str] | None, *, kind: str, managed: bool) -> None:
    if existing is None:
        if expected and expected.get('name'):
            raise ValueError(
                f'{kind}/{expected["name"]} is no longer present; refresh adoption evidence before cutover.'
            )
        return

    metadata = getattr(existing, 'metadata', None)
    labels = dict(getattr(metadata, 'labels', None) or {})
    owner = str(labels.get(_MANAGED_BY_KEY) or '')
    if owner and owner != _MANAGED_BY_VALUE:
        raise ValueError(f'{kind} is managed by {owner}; allocation governance fails closed.')
    if managed and owner != _MANAGED_BY_VALUE:
        raise ValueError(f'{kind} lost KAORI ownership metadata; reconcile provider ownership before retrying.')

    if expected:
        expected_uid = str(expected.get('uid') or '')
        expected_rv = str(expected.get('resource_version') or '')
        current_uid = _metadata_value(metadata, 'uid')
        current_rv = _metadata_value(metadata, 'resource_version')
        if expected_uid and current_uid and expected_uid != current_uid:
            raise ValueError(f'{kind} UID changed since observation; refresh provider evidence before cutover.')
        if expected_rv and current_rv and expected_rv != current_rv:
            raise ValueError(
                f'{kind} resourceVersion changed since observation; refresh provider evidence before cutover.'
            )


def _mutate_namespace_ownership(
    api: Any,
    record: TenantNamespace,
    *,
    profile: TenantResourceProfile,
) -> None:
    existing = api.read_namespace(record.namespace)
    metadata = getattr(existing, 'metadata', None)
    labels = dict(getattr(metadata, 'labels', None) or {})
    owner = str(labels.get(_MANAGED_BY_KEY) or '')
    if owner and owner != _MANAGED_BY_VALUE:
        raise ValueError(f'Namespace is managed by {owner}; governance takeover fails closed.')

    desired_labels = {**labels, **_labels(record, profile)}
    body = {
        'metadata': {
            'name': record.namespace,
            'resourceVersion': _metadata_value(metadata, 'resource_version') or None,
            'labels': desired_labels,
        }
    }
    api.patch_namespace(name=record.namespace, body=body)
    verified = api.read_namespace(record.namespace)
    verified_labels = dict(getattr(getattr(verified, 'metadata', None), 'labels', None) or {})
    if (
        verified_labels.get(_MANAGED_BY_KEY) != _MANAGED_BY_VALUE
        or verified_labels.get(_TENANT_ID_KEY) != record.environment.tenant.id
        or verified_labels.get(_PROFILE_ID_KEY) != profile.public_id
    ):
        raise ValueError(
            'Namespace ownership metadata did not survive provider read-back; governance takeover fails closed.'
        )


def _read_quota(api: Any, *, namespace: str, name: str) -> Any | None:
    try:
        return api.read_namespaced_resource_quota(name, namespace)
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _read_limit_range(api: Any, *, namespace: str, name: str) -> Any | None:
    try:
        return api.read_namespaced_limit_range(name, namespace)
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _delete_options(existing: Any) -> V1DeleteOptions:
    metadata = getattr(existing, 'metadata', None)
    uid = _metadata_value(metadata, 'uid')
    return V1DeleteOptions(preconditions=V1Preconditions(uid=uid) if uid else None)


def _mutate_quota(
    api: Any,
    record: TenantNamespace,
    *,
    desired: dict[str, str],
    expected: dict[str, str] | None,
    managed: bool,
    profile: TenantResourceProfile,
) -> str:
    name = str((expected or {}).get('name') or _DEFAULT_QUOTA_NAME)
    existing = _read_quota(api, namespace=record.namespace, name=name)
    _verify_existing(existing, expected, kind='ResourceQuota', managed=managed)

    if not desired:
        if existing is not None:
            api.delete_namespaced_resource_quota(
                name=name,
                namespace=record.namespace,
                body=_delete_options(existing),
            )
        return name

    existing_labels = dict(getattr(getattr(existing, 'metadata', None), 'labels', None) or {})
    metadata = V1ObjectMeta(
        name=name,
        namespace=record.namespace,
        labels={**existing_labels, **_labels(record, profile)},
        resource_version=(
            _metadata_value(getattr(existing, 'metadata', None), 'resource_version') if existing else None
        ),
    )
    body = V1ResourceQuota(metadata=metadata, spec=V1ResourceQuotaSpec(hard=desired))
    if existing is None:
        api.create_namespaced_resource_quota(namespace=record.namespace, body=body)
    else:
        api.patch_namespaced_resource_quota(name=name, namespace=record.namespace, body=body)
    return name


def _limit_items(
    desired: dict[str, dict[str, str]],
    storage_policy: dict[str, str],
) -> list[V1LimitRangeItem]:
    items: list[V1LimitRangeItem] = []
    if desired:
        items.append(
            V1LimitRangeItem(
                type='Container',
                default=desired.get('default') or None,
                default_request=desired.get('default_request') or None,
            )
        )
    storage = validate_storage_policy(storage_policy)
    if storage:
        items.append(
            V1LimitRangeItem(
                type='PersistentVolumeClaim',
                min={'storage': storage['min']} if storage.get('min') else None,
                max={'storage': storage['max']} if storage.get('max') else None,
            )
        )
    return items


def _mutate_limit_range(
    api: Any,
    record: TenantNamespace,
    *,
    desired: dict[str, dict[str, str]],
    storage_policy: dict[str, str],
    expected: dict[str, str] | None,
    managed: bool,
    profile: TenantResourceProfile,
) -> str:
    name = str((expected or {}).get('name') or _DEFAULT_LIMIT_RANGE_NAME)
    existing = _read_limit_range(api, namespace=record.namespace, name=name)
    _verify_existing(existing, expected, kind='LimitRange', managed=managed)

    if not desired and not storage_policy:
        if existing is not None:
            api.delete_namespaced_limit_range(
                name=name,
                namespace=record.namespace,
                body=_delete_options(existing),
            )
        return name

    existing_labels = dict(getattr(getattr(existing, 'metadata', None), 'labels', None) or {})
    metadata = V1ObjectMeta(
        name=name,
        namespace=record.namespace,
        labels={**existing_labels, **_labels(record, profile)},
        resource_version=(
            _metadata_value(getattr(existing, 'metadata', None), 'resource_version') if existing else None
        ),
    )
    body = V1LimitRange(
        metadata=metadata,
        spec=V1LimitRangeSpec(limits=_limit_items(desired, storage_policy)),
    )
    if existing is None:
        api.create_namespaced_limit_range(namespace=record.namespace, body=body)
    else:
        api.patch_namespaced_limit_range(name=name, namespace=record.namespace, body=body)
    return name


def _quantity_equal(key: str, left: str, right: str) -> bool:
    if key in COUNT_QUOTA_KEYS:
        try:
            return int(left) == int(right)
        except (TypeError, ValueError):
            return False
    try:
        return parse_quantity(left) == parse_quantity(right)
    except (InvalidOperation, TypeError, ValueError):
        return left == right


def _quota_equal(observed: dict[str, str], desired: dict[str, str]) -> bool:
    return set(observed) == set(desired) and all(
        _quantity_equal(key, str(observed[key]), str(desired[key])) for key in observed
    )


def _limits_equal(
    observed: dict[str, dict[str, str]],
    desired: dict[str, dict[str, str]],
) -> bool:
    if set(observed) != set(desired):
        return False
    for field in observed:
        if set(observed[field]) != set(desired[field]):
            return False
        for key in observed[field]:
            try:
                if parse_quantity(str(observed[field][key])) != parse_quantity(str(desired[field][key])):
                    return False
            except (InvalidOperation, TypeError, ValueError):
                if str(observed[field][key]) != str(desired[field][key]):
                    return False
    return True


def _storage_policy_equal(
    observed: dict[str, str],
    desired: dict[str, str],
) -> bool:
    if set(observed) != set(desired):
        return False
    for field in observed:
        try:
            if parse_quantity(str(observed[field])) != parse_quantity(str(desired[field])):
                return False
        except (InvalidOperation, TypeError, ValueError):
            if str(observed[field]) != str(desired[field]):
                return False
    return True


@dataclass(frozen=True, slots=True)
class _NativeAllocationReconcileRequest:
    profile: TenantResourceProfile
    resource_profile_version: int
    allocation_customized: bool
    capacity_decision_id: int | None
    quota_hard: dict[str, str]
    limit_defaults: dict[str, dict[str, str]]
    storage_policy: dict[str, str]
    operation: str
    expected_observed_hash: str | None
    failure_status: str


@dataclass(frozen=True, slots=True)
class _PreparedNativeAllocationReconcile:
    api: Any
    managed: bool
    quota: dict[str, str]
    limits: dict[str, dict[str, str]]
    storage: dict[str, str]
    before: dict[str, Any]
    quota_expected: dict[str, str] | None
    limit_expected: dict[str, str] | None


@dataclass(frozen=True, slots=True)
class _NativeAllocationMutationResult:
    quota_name: str
    limit_name: str
    after: dict[str, Any]


def _legacy_reconcile_request(options: dict[str, Any]) -> _NativeAllocationReconcileRequest:
    required = {
        'profile',
        'resource_profile_version',
        'allocation_customized',
        'capacity_decision_id',
        'quota_hard',
        'limit_defaults',
    }
    allowed = required | {'storage_policy', 'operation', 'expected_observed_hash', 'failure_status'}
    unknown = sorted(set(options) - allowed)
    missing = sorted(required - set(options))
    if unknown:
        raise TypeError('Unexpected allocation reconciliation options: ' + ', '.join(unknown) + '.')
    if missing:
        raise TypeError('Missing allocation reconciliation options: ' + ', '.join(missing) + '.')

    profile = options['profile']
    if not isinstance(profile, TenantResourceProfile):
        raise TypeError('Allocation reconciliation requires a TenantResourceProfile.')

    return _NativeAllocationReconcileRequest(
        profile=profile,
        resource_profile_version=int(options['resource_profile_version']),
        allocation_customized=bool(options['allocation_customized']),
        capacity_decision_id=options['capacity_decision_id'],
        quota_hard=dict(options['quota_hard']),
        limit_defaults={
            str(field): dict(values)
            for field, values in dict(options['limit_defaults']).items()
        },
        storage_policy=dict(options.get('storage_policy') or {}),
        operation=str(options.get('operation') or 'allocation_reconcile'),
        expected_observed_hash=(
            str(options['expected_observed_hash'])
            if options.get('expected_observed_hash') not in (None, '')
            else None
        ),
        failure_status=str(options.get('failure_status') or 'failed'),
    )


def reconcile_adopted_native_allocation(
    record: TenantNamespace,
    *,
    request: _NativeAllocationReconcileRequest | None = None,
    **legacy_options: Any,
) -> TenantNamespace:
    """Reconcile Native allocation through one typed request while preserving legacy keyword callers."""

    if request is not None and legacy_options:
        raise TypeError('Pass either request or legacy allocation reconciliation options, not both.')
    resolved = request or _legacy_reconcile_request(legacy_options)
    return _reconcile_adopted_native_allocation(record, resolved)


def _prepare_native_allocation_reconcile(
    record: TenantNamespace,
    request: _NativeAllocationReconcileRequest,
) -> _PreparedNativeAllocationReconcile:
    eligibility = build_allocation_cutover_state(record)
    managed = allocation_control_state(record) == 'kaori_managed'
    if not managed and not eligibility['supported']:
        raise ValueError(str(eligibility['reason']))

    quota, limits = validate_profile_spec(request.quota_hard, request.limit_defaults)
    storage = validate_storage_policy(request.storage_policy)
    cluster = db.session.get(Cluster, record.cluster_id)
    if cluster is None:
        raise ValueError('Tenant namespace cluster no longer exists.')

    api = runtime_adapter.build_client(cluster).core_api()
    before = observe_native_namespace_allocation(api, record.namespace)
    if before['control_state'] != 'observed':
        raise ValueError(before['control_reason'])

    if request.expected_observed_hash:
        if str(before['effective_hash']) != request.expected_observed_hash:
            raise ValueError(
                'Live provider allocation changed again after the committed drift observation; sync before retrying.'
            )
        quota_expected = _observed_source(before, 'ResourceQuota')
        limit_expected = _observed_source(before, 'LimitRange')
    else:
        if record.effective_hash and str(before['effective_hash']) != str(record.effective_hash):
            raise ValueError(
                'Live provider allocation changed since the last committed observation; '
                'sync/review drift before mutation.'
            )
        quota_expected = _expected_source(record, 'ResourceQuota')
        limit_expected = _expected_source(record, 'LimitRange')

    return _PreparedNativeAllocationReconcile(
        api=api,
        managed=managed,
        quota=quota,
        limits=limits,
        storage=storage,
        before=before,
        quota_expected=quota_expected,
        limit_expected=limit_expected,
    )


def _verify_reconcile_sources(
    record: TenantNamespace,
    prepared: _PreparedNativeAllocationReconcile,
) -> None:
    quota_probe_name = str((prepared.quota_expected or {}).get('name') or _DEFAULT_QUOTA_NAME)
    limit_probe_name = str((prepared.limit_expected or {}).get('name') or _DEFAULT_LIMIT_RANGE_NAME)
    _verify_existing(
        _read_quota(prepared.api, namespace=record.namespace, name=quota_probe_name),
        prepared.quota_expected,
        kind='ResourceQuota',
        managed=prepared.managed,
    )
    _verify_existing(
        _read_limit_range(prepared.api, namespace=record.namespace, name=limit_probe_name),
        prepared.limit_expected,
        kind='LimitRange',
        managed=prepared.managed,
    )


def _mutate_native_allocation(
    record: TenantNamespace,
    request: _NativeAllocationReconcileRequest,
    prepared: _PreparedNativeAllocationReconcile,
) -> _NativeAllocationMutationResult:
    _mutate_namespace_ownership(
        prepared.api,
        record,
        profile=request.profile,
    )
    quota_name = _mutate_quota(
        prepared.api,
        record,
        desired=prepared.quota,
        expected=prepared.quota_expected,
        managed=prepared.managed,
        profile=request.profile,
    )
    limit_name = _mutate_limit_range(
        prepared.api,
        record,
        desired=prepared.limits,
        storage_policy=prepared.storage,
        expected=prepared.limit_expected,
        managed=prepared.managed,
        profile=request.profile,
    )

    after = observe_native_namespace_allocation(prepared.api, record.namespace)
    if after['control_state'] != 'observed':
        raise ValueError(
            'Provider mutation completed but effective allocation authority is no longer unambiguous; '
            'KAORI will not mark cutover successful.'
        )
    if (
        not _quota_equal(dict(after['quota']), prepared.quota)
        or not _limits_equal(dict(after['limits']), prepared.limits)
        or not _storage_policy_equal(dict(after.get('storage_policy') or {}), prepared.storage)
    ):
        raise ValueError(
            'Provider read-back does not match the proposed allocation/storage policy; '
            'KAORI will not mark allocation control managed.'
        )
    return _NativeAllocationMutationResult(
        quota_name=quota_name,
        limit_name=limit_name,
        after=after,
    )


def _record_native_allocation_reconcile_failure(
    record: TenantNamespace,
    request: _NativeAllocationReconcileRequest,
    prepared: _PreparedNativeAllocationReconcile,
    exc: ApiException | ValueError,
    *,
    mutation_started: bool,
) -> None:
    failed_at = datetime.now(UTC)
    evidence = dict(record.provisioning_evidence_json or {})
    evidence['allocation_reconcile_failure'] = {
        'operation': request.operation,
        'at': failed_at.isoformat(),
        'control_state': allocation_control_state(record),
        'provider': 'native_kubernetes',
        'provider_mutation_may_have_started': mutation_started,
        'error': str(exc)[:1000],
        'proposed': {
            'resource_profile_id': request.profile.public_id,
            'resource_profile_version': request.resource_profile_version,
            'quota': prepared.quota,
            'limits': prepared.limits,
            'storage_policy': prepared.storage,
        },
        'secret_material_persisted': False,
    }
    record.provisioning_evidence_json = evidence
    record.provisioning_status = request.failure_status
    record.provisioning_message = str(exc)[:1000]
    record.last_reconciled_at = failed_at


def _commit_native_allocation_reconcile(
    record: TenantNamespace,
    request: _NativeAllocationReconcileRequest,
    prepared: _PreparedNativeAllocationReconcile,
    mutation: _NativeAllocationMutationResult,
) -> TenantNamespace:
    now = datetime.now(UTC)
    evidence = dict(record.provisioning_evidence_json or {})
    previous_allocation = evidence.get('allocation')
    previous_provenance = (
        str(previous_allocation.get('provenance') or '') if isinstance(previous_allocation, dict) else ''
    ) or ('kaori_managed' if prepared.managed else 'adopted_observed')
    history = list(evidence.get('allocation_history') or [])
    history.append(
        {
            'event': request.operation,
            'at': now.isoformat(),
            'from': {
                'control_state': allocation_control_state(record),
                'effective_hash': record.effective_hash,
                'quota': prepared.before['quota'],
                'limits': prepared.before['limits'],
                'storage_policy': prepared.before.get('storage_policy') or {},
            },
            'to': {
                'control_state': 'kaori_managed',
                'effective_hash': mutation.after['effective_hash'],
                'quota': mutation.after['quota'],
                'limits': mutation.after['limits'],
                'storage_policy': mutation.after.get('storage_policy') or {},
            },
        }
    )
    evidence.update(
        {
            'allocation_control_state': 'kaori_managed',
            'managed_resource_names': {
                'quota': mutation.quota_name,
                'limit_range': mutation.limit_name,
            },
            'allocation': {
                **mutation.after,
                'provenance': 'kaori_managed',
                'previous_provenance': previous_provenance,
                'resource_profile_id': request.profile.public_id,
                'resource_profile_version': request.resource_profile_version,
                'capacity_decision_id': request.capacity_decision_id,
            },
            'allocation_history': history,
            'provider_mutation_performed': True,
            'secret_material_persisted': False,
        }
    )
    evidence.pop('allocation_drift', None)
    evidence.pop('allocation_reconcile_failure', None)
    record.ownership_status = TenantOwnershipStatus.MANAGED.value
    record.resource_profile = request.profile
    record.resource_profile_id = request.profile.id
    record.resource_profile_version = request.resource_profile_version
    record.allocation_quota_json = prepared.quota
    record.allocation_limit_defaults_json = prepared.limits
    record.allocation_storage_policy_json = prepared.storage
    record.allocation_customized = request.allocation_customized
    record.capacity_decision_id = request.capacity_decision_id
    record.provisioning_evidence_json = evidence
    record.desired_hash = str(mutation.after['effective_hash'])
    record.effective_hash = str(mutation.after['effective_hash'])
    record.last_reconciled_at = now
    record.provisioning_status = 'ready'
    record.provisioning_message = (
        'KAORI Managed namespace allocation verified against Native Kubernetes provider read-back. '
        'Adoption origin remains retained in evidence.'
    )
    return record


def _reconcile_adopted_native_allocation(
    record: TenantNamespace,
    request: _NativeAllocationReconcileRequest,
) -> TenantNamespace:
    prepared = _prepare_native_allocation_reconcile(record, request)
    mutation_started = False
    try:
        _verify_reconcile_sources(record, prepared)
        mutation_started = True
        mutation = _mutate_native_allocation(record, request, prepared)
    except (ApiException, ValueError) as exc:
        _record_native_allocation_reconcile_failure(
            record,
            request,
            prepared,
            exc,
            mutation_started=mutation_started,
        )
        raise
    return _commit_native_allocation_reconcile(record, request, prepared, mutation)
