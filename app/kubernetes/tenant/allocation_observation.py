from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import InvalidOperation
from typing import Any

from kubernetes.utils.quantity import parse_quantity

from app.kubernetes.tenant.service_contracts import RESOURCE_PROFILE_PRESETS
from app.kubernetes.tenant.validation import (
    COUNT_QUOTA_KEYS,
    SUPPORTED_LIMIT_KEYS,
    SUPPORTED_QUOTA_KEYS,
    validate_storage_policy,
)

_CAPSULE_GROUP = 'capsule.clastix.io'
_CAPSULE_VERSIONS = ('v1beta2', 'v1beta1')
_CAPSULE_TENANT_LABEL_KEYS = (
    'projectcapsule.dev/tenant',
    'capsule.clastix.io/tenant',
)
_QUOTA_DISPLAY_ORDER = (
    'requests.cpu',
    'limits.cpu',
    'requests.memory',
    'limits.memory',
    'pods',
    'persistentvolumeclaims',
    'requests.storage',
    'services',
    'configmaps',
    'secrets',
)
_LIMIT_DISPLAY_ORDER = (
    ('default_request', 'cpu'),
    ('default_request', 'memory'),
    ('default', 'cpu'),
    ('default', 'memory'),
)


def _value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _metadata_value(metadata: Any, *keys: str) -> str:
    for key in keys:
        value = _value(metadata, key)
        if value not in (None, ''):
            return str(value)
    return ''


def _resource_reference(kind: str, item: Any) -> dict[str, str]:
    metadata = _value(item, 'metadata', {}) or {}
    labels = dict(_value(metadata, 'labels', {}) or {})
    return {
        'kind': kind,
        'name': _metadata_value(metadata, 'name'),
        'uid': _metadata_value(metadata, 'uid'),
        'resource_version': _metadata_value(metadata, 'resourceVersion', 'resource_version'),
        'managed_by': str(labels.get('app.kubernetes.io/managed-by') or ''),
        'tenant_id': str(labels.get('kaori.io/tenant-id') or ''),
    }


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _merge_hard_sources(
    sources: list[tuple[str, Mapping[str, Any]]],
) -> tuple[dict[str, str], list[str], list[str]]:
    candidates: dict[str, list[tuple[str, str]]] = {}
    unsupported: list[str] = []
    for source_name, hard in sources:
        for key, raw_value in hard.items():
            rendered = str(raw_value).strip()
            if key not in SUPPORTED_QUOTA_KEYS:
                unsupported.append(f'{source_name}:{key}')
                continue
            candidates.setdefault(str(key), []).append((source_name, rendered))

    quota: dict[str, str] = {}
    ambiguous: list[str] = []
    for key in sorted(candidates):
        values = candidates[key]
        if len(values) != 1:
            source_names = ', '.join(source for source, _value_text in values)
            ambiguous.append(f'{key} is defined by multiple quota sources: {source_names}.')
            continue
        quota[key] = values[0][1]
    return quota, unsupported, ambiguous


def _collect_pvc_limit_item(
    item: Any,
    *,
    source_name: str,
    reference: Mapping[str, str],
    storage_candidates: dict[str, list[tuple[str, str]]],
    unsupported: list[str],
    external_constraints: list[dict[str, Any]],
) -> None:
    supported_fields: dict[str, str] = {}
    unsupported_fields: dict[str, dict[str, str]] = {}
    for field, attr_names in (
        ('min', ('min',)),
        ('max', ('max',)),
        ('default', ('default',)),
        ('default_request', ('default_request', 'defaultRequest')),
        ('max_limit_request_ratio', ('max_limit_request_ratio', 'maxLimitRequestRatio')),
    ):
        values: dict[str, Any] = {}
        for attr_name in attr_names:
            candidate = _value(item, attr_name, {}) or {}
            if candidate:
                values.update(dict(candidate))
        for key, raw_value in values.items():
            rendered = str(raw_value).strip()
            if str(key) != 'storage' or field not in {'min', 'max'}:
                unsupported.append(f'{source_name}:pvc.{field}.{key}')
                unsupported_fields.setdefault(field, {})[str(key)] = rendered
                continue
            storage_candidates.setdefault(field, []).append((source_name, rendered))
            supported_fields[field] = rendered

    if unsupported_fields:
        external_constraints.append(
            {
                'constraint_type': 'unsupported_pvc_limit_range',
                'kind': 'LimitRange',
                'name': reference['name'],
                'uid': reference['uid'],
                'resource_version': reference['resource_version'],
                'item_type': 'PersistentVolumeClaim',
                'fields': unsupported_fields,
            }
        )


def _collect_container_limit_item(
    item: Any,
    *,
    source_name: str,
    candidates: dict[tuple[str, str], list[tuple[str, str]]],
    unsupported: list[str],
) -> None:
    for unsupported_field, attr_name in (
        ('max', 'max'),
        ('min', 'min'),
        ('max_limit_request_ratio', 'max_limit_request_ratio'),
        ('max_limit_request_ratio', 'maxLimitRequestRatio'),
    ):
        values = _value(item, attr_name, {}) or {}
        if values:
            unsupported.extend(f'{source_name}:{unsupported_field}.{key}' for key in dict(values))
    for field, attr_name in (('default', 'default'), ('default_request', 'default_request')):
        values = _value(item, attr_name, {}) or {}
        for key, raw_value in dict(values).items():
            if key not in SUPPORTED_LIMIT_KEYS:
                unsupported.append(f'{source_name}:{field}.{key}')
                continue
            candidates.setdefault((field, str(key)), []).append((source_name, str(raw_value).strip()))


def _merge_limit_sources(
    limit_ranges: list[Any],
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, str],
    list[str],
    list[str],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    candidates: dict[tuple[str, str], list[tuple[str, str]]] = {}
    storage_candidates: dict[str, list[tuple[str, str]]] = {}
    unsupported: list[str] = []
    source_refs: list[dict[str, str]] = []
    external_constraints: list[dict[str, Any]] = []

    for limit_range in limit_ranges:
        reference = _resource_reference('LimitRange', limit_range)
        source_refs.append(reference)
        source_name = f'LimitRange/{reference["name"] or "unknown"}'
        spec = _value(limit_range, 'spec', {}) or {}
        for item in list(_value(spec, 'limits', []) or []):
            item_type = str(_value(item, 'type', '') or '')
            if item_type == 'PersistentVolumeClaim':
                _collect_pvc_limit_item(
                    item,
                    source_name=source_name,
                    reference=reference,
                    storage_candidates=storage_candidates,
                    unsupported=unsupported,
                    external_constraints=external_constraints,
                )
                continue
            if item_type and item_type != 'Container':
                unsupported.append(f'{source_name}:type={item_type}')
                continue
            _collect_container_limit_item(
                item,
                source_name=source_name,
                candidates=candidates,
                unsupported=unsupported,
            )

    limits: dict[str, dict[str, str]] = {}
    ambiguous: list[str] = []
    for (field, key), values in sorted(candidates.items()):
        if len(values) != 1:
            source_names = ', '.join(source for source, _value_text in values)
            ambiguous.append(f'{field}.{key} is defined by multiple LimitRange sources: {source_names}.')
            continue
        limits.setdefault(field, {})[key] = values[0][1]

    storage_policy: dict[str, str] = {}
    for field, values in sorted(storage_candidates.items()):
        if len(values) != 1:
            source_names = ', '.join(source for source, _value_text in values)
            ambiguous.append(f'pvc.{field}.storage is defined by multiple LimitRange sources: {source_names}.')
            continue
        storage_policy[field] = values[0][1]
    storage_policy = validate_storage_policy(storage_policy)

    return limits, storage_policy, unsupported, ambiguous, source_refs, external_constraints


def _quantity_equivalent(key: str, left: str, right: str) -> bool:
    if key in COUNT_QUOTA_KEYS:
        try:
            return int(left) == int(right)
        except (TypeError, ValueError):
            return False
    try:
        return parse_quantity(left) == parse_quantity(right)
    except (InvalidOperation, TypeError, ValueError):
        return left == right


def _mapping_equivalent(observed: Mapping[str, str], expected: Mapping[str, str]) -> bool:
    if set(observed) != set(expected):
        return False
    return all(_quantity_equivalent(key, str(observed[key]), str(expected[key])) for key in observed)


def _limits_equivalent(
    observed: Mapping[str, Mapping[str, str]],
    expected: Mapping[str, Mapping[str, str]],
) -> bool:
    if set(observed) != set(expected):
        return False
    for field in observed:
        observed_values = observed[field]
        expected_values = expected[field]
        if set(observed_values) != set(expected_values):
            return False
        for key in observed_values:
            try:
                if parse_quantity(str(observed_values[key])) != parse_quantity(str(expected_values[key])):
                    return False
            except (InvalidOperation, TypeError, ValueError):
                if str(observed_values[key]) != str(expected_values[key]):
                    return False
    return True


def profile_lineage_for_observed_allocation(
    quota: Mapping[str, str],
    limits: Mapping[str, Mapping[str, str]],
    storage_policy: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    for profile_class, preset in RESOURCE_PROFILE_PRESETS.items():
        preset_quota = {str(key): str(value) for key, value in dict(preset['quota']).items()}
        preset_limits = {
            str(field): {str(key): str(value) for key, value in dict(values).items()}
            for field, values in dict(preset['limits']).items()
        }
        preset_storage = validate_storage_policy(preset.get('storage_policy') or {})
        quota_and_limits_match = _mapping_equivalent(quota, preset_quota) and _limits_equivalent(limits, preset_limits)
        if quota_and_limits_match and _mapping_equivalent(storage_policy or {}, preset_storage):
            return {
                'kind': 'kaori_preset',
                'profile_class': profile_class,
                'profile_version': int(preset['version']),
                'label': f'{profile_class.title()} · KAORI Preset',
            }
        if quota_and_limits_match and not storage_policy:
            return {
                'kind': 'kaori_preset',
                'profile_class': profile_class,
                'profile_version': 1,
                'label': f'{profile_class.title()} · KAORI Preset',
            }
    return {
        'kind': 'custom_observed_baseline',
        'profile_class': 'custom',
        'profile_version': None,
        'label': 'Adopted Baseline · Observed',
    }


def _display_values(
    quota: Mapping[str, str],
    limits: Mapping[str, Mapping[str, str]],
    storage_policy: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    labels = {
        'requests.cpu': 'CPU Requests',
        'limits.cpu': 'CPU Limits',
        'requests.memory': 'Memory Requests',
        'limits.memory': 'Memory Limits',
        'pods': 'Pods',
        'persistentvolumeclaims': 'PVCs',
        'requests.storage': 'Storage Requests',
        'services': 'Services',
        'configmaps': 'ConfigMaps',
        'secrets': 'Secrets',
        'default_request.cpu': 'Default CPU Request',
        'default_request.memory': 'Default Memory Request',
        'default.cpu': 'Default CPU Limit',
        'default.memory': 'Default Memory Limit',
    }
    rows: list[dict[str, str]] = []
    for key in _QUOTA_DISPLAY_ORDER:
        if key in quota:
            rows.append({'key': key, 'label': labels[key], 'value': str(quota[key])})
    for field, key in _LIMIT_DISPLAY_ORDER:
        if key in (limits.get(field) or {}):
            compound = f'{field}.{key}'
            rows.append({'key': compound, 'label': labels[compound], 'value': str(limits[field][key])})
    storage_labels = {
        'min': 'Min PVC Size',
        'max': 'Max PVC Size',
    }
    for field in ('min', 'max'):
        if field in (storage_policy or {}):
            rows.append(
                {
                    'key': f'pvc.{field}.storage',
                    'label': storage_labels[field],
                    'value': str((storage_policy or {})[field]),
                }
            )
    return rows


def _native_observation_from_items(
    *,
    namespace: str,
    quota_items: list[Any],
    limit_range_items: list[Any],
) -> dict[str, Any]:
    quota_sources: list[tuple[str, Mapping[str, Any]]] = []
    source_resources: list[dict[str, str]] = []

    for item in quota_items:
        reference = _resource_reference('ResourceQuota', item)
        source_resources.append(reference)
        spec = _value(item, 'spec', {}) or {}
        hard = _value(spec, 'hard', {}) or {}
        quota_sources.append((f'ResourceQuota/{reference["name"] or "unknown"}', dict(hard)))

    quota, unsupported_quota, ambiguous_quota = _merge_hard_sources(quota_sources)
    (
        limits,
        storage_policy,
        unsupported_limits,
        ambiguous_limits,
        limit_refs,
        external_limit_constraints,
    ) = _merge_limit_sources(limit_range_items)
    source_resources.extend(limit_refs)

    unsupported = sorted(set(unsupported_quota + unsupported_limits))
    ambiguous = sorted(set(ambiguous_quota + ambiguous_limits))
    control_state = 'observed' if not unsupported and not ambiguous else 'control_unavailable'
    control_reason = (
        'Observed allocation is unambiguous and remains read-only until explicit governance cutover.'
        if control_state == 'observed'
        else 'Observed allocation contains unsupported or ambiguous dimensions; governance cutover must fail closed.'
    )
    lineage = profile_lineage_for_observed_allocation(quota, limits, storage_policy)
    payload = {'quota': quota, 'limits': limits, 'storage_policy': storage_policy}

    return {
        'namespace': namespace,
        'quota': quota,
        'limits': limits,
        'storage_policy': storage_policy,
        'display_values': _display_values(quota, limits, storage_policy),
        'source_resources': source_resources,
        'external_limit_constraints': external_limit_constraints,
        'external_constraint_details': external_limit_constraints,
        'unsupported_dimensions': unsupported,
        'ambiguous_dimensions': ambiguous,
        'control_state': control_state,
        'control_reason': control_reason,
        'provenance': 'adopted_observed',
        'profile_lineage': lineage,
        'effective_hash': _canonical_hash(payload),
        'baseline_kind': 'unbounded' if not quota and not limits and not storage_policy else 'allocation',
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }


def observe_native_namespace_allocation(api: Any, namespace: str) -> dict[str, Any]:
    quota_payload = api.list_namespaced_resource_quota(namespace=namespace, _request_timeout=5)
    limit_payload = api.list_namespaced_limit_range(namespace=namespace, _request_timeout=5)
    return _native_observation_from_items(
        namespace=namespace,
        quota_items=list(_value(quota_payload, 'items', []) or []),
        limit_range_items=list(_value(limit_payload, 'items', []) or []),
    )

