from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import InvalidOperation
from typing import Any

from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity

from app.kubernetes.tenant.validation import (
    COUNT_QUOTA_KEYS,
    SUPPORTED_LIMIT_KEYS,
    SUPPORTED_QUOTA_KEYS,
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
    return {
        'kind': kind,
        'name': _metadata_value(metadata, 'name'),
        'uid': _metadata_value(metadata, 'uid'),
        'resource_version': _metadata_value(metadata, 'resourceVersion', 'resource_version'),
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


def _merge_limit_sources(
    limit_ranges: list[Any],
) -> tuple[dict[str, dict[str, str]], list[str], list[str], list[dict[str, str]]]:
    candidates: dict[tuple[str, str], list[tuple[str, str]]] = {}
    unsupported: list[str] = []
    source_refs: list[dict[str, str]] = []

    for limit_range in limit_ranges:
        reference = _resource_reference('LimitRange', limit_range)
        source_refs.append(reference)
        source_name = f'LimitRange/{reference["name"] or "unknown"}'
        spec = _value(limit_range, 'spec', {}) or {}
        for item in list(_value(spec, 'limits', []) or []):
            item_type = str(_value(item, 'type', '') or '')
            if item_type and item_type != 'Container':
                continue
            for field, attr_name in (('default', 'default'), ('default_request', 'default_request')):
                values = _value(item, attr_name, {}) or {}
                for key, raw_value in dict(values).items():
                    if key not in SUPPORTED_LIMIT_KEYS:
                        unsupported.append(f'{source_name}:{field}.{key}')
                        continue
                    candidates.setdefault((field, str(key)), []).append((source_name, str(raw_value).strip()))

    limits: dict[str, dict[str, str]] = {}
    ambiguous: list[str] = []
    for (field, key), values in sorted(candidates.items()):
        if len(values) != 1:
            source_names = ', '.join(source for source, _value_text in values)
            ambiguous.append(f'{field}.{key} is defined by multiple LimitRange sources: {source_names}.')
            continue
        limits.setdefault(field, {})[key] = values[0][1]

    return limits, unsupported, ambiguous, source_refs


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
) -> dict[str, Any]:
    from app.kubernetes.tenant.service import RESOURCE_PROFILE_PRESETS

    for profile_class, preset in RESOURCE_PROFILE_PRESETS.items():
        preset_quota = {str(key): str(value) for key, value in dict(preset['quota']).items()}
        preset_limits = {
            str(field): {str(key): str(value) for key, value in dict(values).items()}
            for field, values in dict(preset['limits']).items()
        }
        if _mapping_equivalent(quota, preset_quota) and _limits_equivalent(limits, preset_limits):
            return {
                'kind': 'kaori_preset',
                'profile_class': profile_class,
                'profile_version': int(preset['version']),
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
    limits, unsupported_limits, ambiguous_limits, limit_refs = _merge_limit_sources(limit_range_items)
    source_resources.extend(limit_refs)

    unsupported = sorted(set(unsupported_quota + unsupported_limits))
    ambiguous = sorted(set(ambiguous_quota + ambiguous_limits))
    control_state = 'observed' if not unsupported and not ambiguous else 'control_unavailable'
    control_reason = (
        'Observed allocation is unambiguous and remains read-only until explicit governance cutover.'
        if control_state == 'observed'
        else 'Observed allocation contains unsupported or ambiguous dimensions; governance cutover must fail closed.'
    )
    lineage = profile_lineage_for_observed_allocation(quota, limits)
    payload = {'quota': quota, 'limits': limits}

    return {
        'namespace': namespace,
        'quota': quota,
        'limits': limits,
        'display_values': _display_values(quota, limits),
        'source_resources': source_resources,
        'unsupported_dimensions': unsupported,
        'ambiguous_dimensions': ambiguous,
        'control_state': control_state,
        'control_reason': control_reason,
        'provenance': 'adopted_observed',
        'profile_lineage': lineage,
        'effective_hash': _canonical_hash(payload),
        'baseline_kind': 'unbounded' if not quota and not limits else 'allocation',
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


def _capsule_status_namespace_names(tenant_item: Mapping[str, Any]) -> set[str]:
    status = tenant_item.get('status') or {}
    if not isinstance(status, Mapping):
        return set()
    return {
        str(name).strip()
        for name in list(status.get('namespaces') or [])
        if str(name).strip()
    }


def _capsule_namespace_correlation(
    *,
    core_api: Any,
    tenant_name: str,
    tenant_item: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    payload = core_api.list_namespace(_request_timeout=5)
    namespace_items = list(_value(payload, 'items', []) or [])
    status_names = _capsule_status_namespace_names(tenant_item)
    correlated: list[dict[str, Any]] = []
    ambiguities: list[str] = []
    observed_names: set[str] = set()

    for item in namespace_items:
        metadata = _value(item, 'metadata', {}) or {}
        name = _metadata_value(metadata, 'name')
        if not name:
            continue
        observed_names.add(name)
        labels = dict(_value(metadata, 'labels', {}) or {})
        label_claims = {
            str(labels[key]).strip()
            for key in _CAPSULE_TENANT_LABEL_KEYS
            if key in labels and str(labels[key]).strip()
        }
        owner_claims = {
            str(_value(owner, 'name', '') or '').strip()
            for owner in list(_value(metadata, 'owner_references', None) or _value(metadata, 'ownerReferences', []) or [])
            if str(_value(owner, 'kind', '') or '') == 'Tenant'
            and str(_value(owner, 'api_version', None) or _value(owner, 'apiVersion', '') or '').startswith(
                f'{_CAPSULE_GROUP}/'
            )
        }
        selected = name in status_names or tenant_name in label_claims or tenant_name in owner_claims
        if not selected:
            continue
        if label_claims and tenant_name not in label_claims:
            ambiguities.append(
                f'Namespace/{name} is listed for {tenant_name} but its Capsule tenant label points to '
                f'{", ".join(sorted(label_claims))}.'
            )
        if owner_claims and tenant_name not in owner_claims:
            ambiguities.append(
                f'Namespace/{name} is listed for {tenant_name} but its Capsule Tenant owner points to '
                f'{", ".join(sorted(owner_claims))}.'
            )
        correlated.append(
            {
                'name': name,
                'uid': _metadata_value(metadata, 'uid'),
                'resource_version': _metadata_value(metadata, 'resourceVersion', 'resource_version'),
                'label_claims': sorted(label_claims),
                'owner_claims': sorted(owner_claims),
            }
        )

    for missing in sorted(status_names - observed_names):
        ambiguities.append(f'Capsule Tenant status references Namespace/{missing}, but the Namespace is not present.')

    correlated.sort(key=lambda row: row['name'])
    return correlated, sorted(set(ambiguities))


def _capsule_tenant_quota(tenant_item: Mapping[str, Any]) -> dict[str, Any] | None:
    spec = tenant_item.get('spec') or {}
    if not isinstance(spec, Mapping):
        return None
    resource_quotas = spec.get('resourceQuotas')
    if not isinstance(resource_quotas, Mapping):
        return None
    items = [item for item in list(resource_quotas.get('items') or []) if isinstance(item, Mapping)]
    if not items:
        return None

    hard_sources = [
        (f'Tenant.spec.resourceQuotas.items[{index}]', dict(item.get('hard') or {}))
        for index, item in enumerate(items)
    ]
    quota, unsupported, ambiguous = _merge_hard_sources(hard_sources)
    return {
        'scope': str(resource_quotas.get('scope') or 'Namespace'),
        'quota': quota,
        'source_count': len(items),
        'unsupported_dimensions': unsupported,
        'ambiguous_dimensions': ambiguous,
    }


def _selector_targets_tenant(selector: Mapping[str, Any], tenant_name: str) -> tuple[bool, bool]:
    match_labels = selector.get('matchLabels') or {}
    if isinstance(match_labels, Mapping):
        for key in _CAPSULE_TENANT_LABEL_KEYS:
            if str(match_labels.get(key) or '').strip() == tenant_name:
                return True, False

    match_expressions = selector.get('matchExpressions') or []
    for expression in match_expressions if isinstance(match_expressions, list) else []:
        if not isinstance(expression, Mapping):
            continue
        if str(expression.get('key') or '') not in _CAPSULE_TENANT_LABEL_KEYS:
            continue
        values = {str(value).strip() for value in list(expression.get('values') or [])}
        if tenant_name in values:
            return False, True
    return False, False


def _capsule_global_resource_quotas(custom_api: Any, tenant_name: str) -> dict[str, Any]:
    matched: list[Mapping[str, Any]] = []
    unsupported_selectors: list[str] = []
    served_version: str | None = None

    for version in _CAPSULE_VERSIONS:
        try:
            payload = custom_api.list_cluster_custom_object(
                _CAPSULE_GROUP,
                version,
                'globalresourcequotas',
                _request_timeout=5,
            )
        except ApiException as exc:
            if exc.status == 404:
                continue
            raise
        served_version = version
        for item in list((payload or {}).get('items') or []):
            if not isinstance(item, Mapping):
                continue
            metadata = item.get('metadata') or {}
            name = str(metadata.get('name') or 'unknown')
            spec = item.get('spec') or {}
            selectors = spec.get('namespaceSelectors') or []
            targets = False
            expression_match = False
            for selector in selectors if isinstance(selectors, list) else []:
                if not isinstance(selector, Mapping):
                    continue
                direct, expression = _selector_targets_tenant(selector, tenant_name)
                targets = targets or direct
                expression_match = expression_match or expression
            if expression_match:
                unsupported_selectors.append(
                    f'GlobalResourceQuota/{name} uses a tenant matchExpression that KAORI does not normalize yet.'
                )
            if targets:
                matched.append(item)
        break

    hard_sources: list[tuple[str, Mapping[str, Any]]] = []
    source_resources: list[dict[str, str]] = []
    for item in matched:
        reference = _resource_reference('GlobalResourceQuota', item)
        source_resources.append(reference)
        spec = item.get('spec') or {}
        quota_spec = spec.get('quota') or {}
        hard_sources.append(
            (
                f'GlobalResourceQuota/{reference["name"] or "unknown"}',
                dict(quota_spec.get('hard') or {}) if isinstance(quota_spec, Mapping) else {},
            )
        )
    quota, unsupported, ambiguous = _merge_hard_sources(hard_sources)
    return {
        'served_version': served_version,
        'quota': quota,
        'source_resources': source_resources,
        'unsupported_dimensions': sorted(set(unsupported + unsupported_selectors)),
        'ambiguous_dimensions': ambiguous,
    }


def observe_capsule_tenant_allocation(
    client: Any,
    *,
    tenant_name: str,
    tenant_item: Mapping[str, Any],
) -> dict[str, Any]:
    core_api = client.core_api()
    correlated, correlation_ambiguities = _capsule_namespace_correlation(
        core_api=core_api,
        tenant_name=tenant_name,
        tenant_item=tenant_item,
    )

    namespace_rows: list[dict[str, Any]] = []
    native_quota_present = False
    native_limits_present = False
    for namespace in correlated:
        observation = observe_native_namespace_allocation(core_api, namespace['name'])
        native_quota_present = native_quota_present or bool(observation['quota'])
        native_limits_present = native_limits_present or bool(observation['limits'])
        namespace_rows.append({**namespace, 'allocation': observation})

    tenant_quota = _capsule_tenant_quota(tenant_item)
    global_quota = _capsule_global_resource_quotas(client.custom_objects_api(), tenant_name)
    global_quota_present = bool(global_quota['source_resources'])
    tenant_quota_present = tenant_quota is not None

    shared_quota: dict[str, str] = {}
    shared_scope: str | None = None
    if tenant_quota_present and tenant_quota is not None:
        shared_quota = dict(tenant_quota['quota'])
        shared_scope = str(tenant_quota['scope'])
    elif global_quota_present:
        shared_quota = dict(global_quota['quota'])
        shared_scope = 'Tenant'

    native_quota_matches_shared = bool(shared_quota)
    if native_quota_matches_shared:
        observed_quota_rows = [
            dict(namespace['allocation'].get('quota') or {})
            for namespace in namespace_rows
            if namespace['allocation'].get('quota')
        ]
        native_quota_matches_shared = bool(observed_quota_rows) and all(
            _mapping_equivalent(quota, shared_quota) for quota in observed_quota_rows
        )

    authority_paths: list[str] = []
    if tenant_quota_present:
        authority_paths.append('capsule_tenant_resource_quotas')
    if global_quota_present:
        authority_paths.append('capsule_global_resource_quota')
    if (native_quota_present and not native_quota_matches_shared) or (
        not tenant_quota_present and not global_quota_present and (native_quota_present or native_limits_present)
    ):
        authority_paths.append('native_namespaced')

    unsupported = list(global_quota['unsupported_dimensions'])
    ambiguous = list(correlation_ambiguities) + list(global_quota['ambiguous_dimensions'])
    if tenant_quota is not None:
        unsupported.extend(tenant_quota['unsupported_dimensions'])
        ambiguous.extend(tenant_quota['ambiguous_dimensions'])

    for namespace in namespace_rows:
        unsupported.extend(namespace['allocation']['unsupported_dimensions'])
        ambiguous.extend(namespace['allocation']['ambiguous_dimensions'])

    if len(authority_paths) > 1:
        ambiguous.append(
            'Multiple effective allocation authority paths were detected: '
            + ', '.join(authority_paths)
            + '.'
        )

    if not authority_paths:
        allocation_authority = 'none_observed'
    elif len(authority_paths) == 1:
        allocation_authority = authority_paths[0]
    else:
        allocation_authority = 'ambiguous'

    unsupported = sorted(set(unsupported))
    ambiguous = sorted(set(ambiguous))
    control_state = 'observed' if not unsupported and not ambiguous else 'control_unavailable'
    if allocation_authority in {'capsule_tenant_resource_quotas', 'capsule_global_resource_quota'}:
        control_state = 'control_unavailable'
        control_reason = (
            'Capsule shared/Tenant quota is observed and preserved as provider evidence, but KAORI has not admitted '
            'that mutation path for governance cutover yet.'
        )
    elif control_state == 'control_unavailable':
        control_reason = (
            'Capsule allocation authority or dimensions are ambiguous/unsupported; governance cutover must fail closed.'
        )
    else:
        control_reason = (
            'Capsule namespace allocation is observed without provider mutation and remains read-only until explicit '
            'governance cutover.'
        )

    return {
        'provider': 'capsule',
        'tenant_name': tenant_name,
        'correlated_namespaces': namespace_rows,
        'allocation_authority': allocation_authority,
        'authority_paths': authority_paths,
        'tenant_resource_quota': tenant_quota,
        'global_resource_quota': global_quota,
        'shared_quota': shared_quota,
        'shared_scope': shared_scope,
        'unsupported_dimensions': unsupported,
        'ambiguous_dimensions': ambiguous,
        'control_state': control_state,
        'control_reason': control_reason,
        'provenance': 'adopted_observed',
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
