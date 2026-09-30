from __future__ import annotations

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
from app.kubernetes.tenant.validation import COUNT_QUOTA_KEYS, validate_profile_spec
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
        authority = (
            str(baseline.get('allocation_authority') or 'capsule')
            if isinstance(baseline, dict)
            else 'capsule'
        )
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
            raise ValueError(f'{kind}/{expected["name"]} is no longer present; refresh adoption evidence before cutover.')
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
            raise ValueError(f'{kind} resourceVersion changed since observation; refresh provider evidence before cutover.')


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

    metadata = V1ObjectMeta(
        name=name,
        namespace=record.namespace,
        labels=_labels(record, profile),
        resource_version=_metadata_value(getattr(existing, 'metadata', None), 'resource_version') if existing else None,
    )
    body = V1ResourceQuota(metadata=metadata, spec=V1ResourceQuotaSpec(hard=desired))
    if existing is None:
        api.create_namespaced_resource_quota(namespace=record.namespace, body=body)
    else:
        api.patch_namespaced_resource_quota(name=name, namespace=record.namespace, body=body)
    return name


def _limit_items(desired: dict[str, dict[str, str]]) -> list[V1LimitRangeItem]:
    if not desired:
        return []
    return [
        V1LimitRangeItem(
            type='Container',
            default=desired.get('default') or None,
            default_request=desired.get('default_request') or None,
        )
    ]


def _mutate_limit_range(
    api: Any,
    record: TenantNamespace,
    *,
    desired: dict[str, dict[str, str]],
    expected: dict[str, str] | None,
    managed: bool,
    profile: TenantResourceProfile,
) -> str:
    name = str((expected or {}).get('name') or _DEFAULT_LIMIT_RANGE_NAME)
    existing = _read_limit_range(api, namespace=record.namespace, name=name)
    _verify_existing(existing, expected, kind='LimitRange', managed=managed)

    if not desired:
        if existing is not None:
            api.delete_namespaced_limit_range(
                name=name,
                namespace=record.namespace,
                body=_delete_options(existing),
            )
        return name

    metadata = V1ObjectMeta(
        name=name,
        namespace=record.namespace,
        labels=_labels(record, profile),
        resource_version=_metadata_value(getattr(existing, 'metadata', None), 'resource_version') if existing else None,
    )
    body = V1LimitRange(
        metadata=metadata,
        spec=V1LimitRangeSpec(limits=_limit_items(desired)),
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


def reconcile_adopted_native_allocation(
    record: TenantNamespace,
    *,
    profile: TenantResourceProfile,
    resource_profile_version: int,
    allocation_customized: bool,
    capacity_decision_id: int | None,
    quota_hard: dict[str, str],
    limit_defaults: dict[str, dict[str, str]],
    operation: str,
) -> TenantNamespace:
    eligibility = build_allocation_cutover_state(record)
    managed = allocation_control_state(record) == 'kaori_managed'
    if not managed and not eligibility['supported']:
        raise ValueError(str(eligibility['reason']))

    quota, limits = validate_profile_spec(quota_hard, limit_defaults)
    cluster = db.session.get(Cluster, record.cluster_id)
    if cluster is None:
        raise ValueError('Tenant namespace cluster no longer exists.')

    api = runtime_adapter.build_client(cluster).core_api()
    before = observe_native_namespace_allocation(api, record.namespace)
    if before['control_state'] != 'observed':
        raise ValueError(before['control_reason'])
    if record.effective_hash and str(before['effective_hash']) != str(record.effective_hash):
        raise ValueError(
            'Live provider allocation changed since the last committed observation; sync/review drift before mutation.'
        )

    quota_expected = _expected_source(record, 'ResourceQuota')
    limit_expected = _expected_source(record, 'LimitRange')
    try:
        quota_probe_name = str((quota_expected or {}).get('name') or _DEFAULT_QUOTA_NAME)
        limit_probe_name = str((limit_expected or {}).get('name') or _DEFAULT_LIMIT_RANGE_NAME)
        _verify_existing(
            _read_quota(api, namespace=record.namespace, name=quota_probe_name),
            quota_expected,
            kind='ResourceQuota',
            managed=managed,
        )
        _verify_existing(
            _read_limit_range(api, namespace=record.namespace, name=limit_probe_name),
            limit_expected,
            kind='LimitRange',
            managed=managed,
        )

        quota_name = _mutate_quota(
            api,
            record,
            desired=quota,
            expected=quota_expected,
            managed=managed,
            profile=profile,
        )
        limit_name = _mutate_limit_range(
            api,
            record,
            desired=limits,
            expected=limit_expected,
            managed=managed,
            profile=profile,
        )

        after = observe_native_namespace_allocation(api, record.namespace)
        if after['control_state'] != 'observed':
            raise ValueError(
                'Provider mutation completed but effective allocation authority is no longer unambiguous; '
                'KAORI will not mark cutover successful.'
            )
        if not _quota_equal(dict(after['quota']), quota) or not _limits_equal(dict(after['limits']), limits):
            raise ValueError(
                'Provider read-back does not match the proposed allocation; '
                'KAORI will not mark allocation control managed.'
            )
    except (ApiException, ValueError) as exc:
        failed_at = datetime.now(UTC)
        evidence = dict(record.provisioning_evidence_json or {})
        evidence['allocation_reconcile_failure'] = {
            'operation': operation,
            'at': failed_at.isoformat(),
            'control_state': allocation_control_state(record),
            'provider': 'native_kubernetes',
            'provider_mutation_may_have_started': True,
            'error': str(exc)[:1000],
            'proposed': {
                'resource_profile_id': profile.public_id,
                'resource_profile_version': resource_profile_version,
                'quota': quota,
                'limits': limits,
            },
            'secret_material_persisted': False,
        }
        record.provisioning_evidence_json = evidence
        record.provisioning_status = 'failed'
        record.provisioning_message = str(exc)[:1000]
        record.last_reconciled_at = failed_at
        raise

    now = datetime.now(UTC)
    evidence = dict(record.provisioning_evidence_json or {})
    history = list(evidence.get('allocation_history') or [])
    history.append(
        {
            'event': operation,
            'at': now.isoformat(),
            'from': {
                'control_state': allocation_control_state(record),
                'effective_hash': record.effective_hash,
                'quota': before['quota'],
                'limits': before['limits'],
            },
            'to': {
                'control_state': 'kaori_managed',
                'effective_hash': after['effective_hash'],
                'quota': after['quota'],
                'limits': after['limits'],
            },
        }
    )
    evidence.update(
        {
            'allocation_control_state': 'kaori_managed',
            'managed_resource_names': {
                'quota': quota_name,
                'limit_range': limit_name,
            },
            'allocation': {
                **after,
                'provenance': 'kaori_managed',
                'previous_provenance': 'adopted_observed',
                'resource_profile_id': profile.public_id,
                'resource_profile_version': resource_profile_version,
                'capacity_decision_id': capacity_decision_id,
            },
            'allocation_history': history,
            'provider_mutation_performed': True,
            'secret_material_persisted': False,
        }
    )
    record.resource_profile = profile
    record.resource_profile_id = profile.id
    record.resource_profile_version = resource_profile_version
    record.allocation_quota_json = quota
    record.allocation_limit_defaults_json = limits
    record.allocation_customized = allocation_customized
    record.capacity_decision_id = capacity_decision_id
    record.provisioning_evidence_json = evidence
    record.desired_hash = str(after['effective_hash'])
    record.effective_hash = str(after['effective_hash'])
    record.last_reconciled_at = now
    record.provisioning_status = 'ready'
    record.provisioning_message = (
        'KAORI Managed allocation verified against Native Kubernetes provider read-back. '
        'Namespace lifecycle ownership remains adopted.'
    )
    return record
