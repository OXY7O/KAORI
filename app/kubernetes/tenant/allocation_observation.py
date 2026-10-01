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
                        if str(key) != 'storage':
                            unsupported.append(f'{source_name}:pvc.{field}.{key}')
                            unsupported_fields.setdefault(field, {})[str(key)] = rendered
                            continue
                        if field == 'max_limit_request_ratio':
                            unsupported.append(f'{source_name}:pvc.{field}.storage')
                            unsupported_fields.setdefault(field, {})['storage'] = rendered
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
                continue

            if item_type and item_type != 'Container':
                unsupported.append(f'{source_name}:type={item_type}')
                continue
            for unsupported_field, attr_name in (
                ('max', 'max'),
                ('min', 'min'),
                ('max_limit_request_ratio', 'max_limit_request_ratio'),
                ('max_limit_request_ratio', 'maxLimitRequestRatio'),
            ):
                values = _value(item, attr_name, {}) or {}
                if values:
                    unsupported.extend(
                        f'{source_name}:{unsupported_field}.{key}' for key in dict(values)
                    )
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
    from app.kubernetes.tenant.service import RESOURCE_PROFILE_PRESETS

    for profile_class, preset in RESOURCE_PROFILE_PRESETS.items():
        preset_quota = {str(key): str(value) for key, value in dict(preset['quota']).items()}
        preset_limits = {
            str(field): {str(key): str(value) for key, value in dict(values).items()}
            for field, values in dict(preset['limits']).items()
        }
        preset_storage = validate_storage_policy(preset.get('storage_policy') or {})
        if (
            _mapping_equivalent(quota, preset_quota)
            and _limits_equivalent(limits, preset_limits)
            and _mapping_equivalent(storage_policy or {}, preset_storage)
        ):
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
        'default_request': 'PVC Default Request',
        'default': 'PVC Default Limit',
    }
    for field in ('min', 'max', 'default_request', 'default'):
        if field in (storage_policy or {}):
            rows.append({
                'key': f'pvc.{field}.storage',
                'label': storage_labels[field],
                'value': str((storage_policy or {})[field]),
            })
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
            for owner in list(
                _value(metadata, 'owner_references', None)
                or _value(metadata, 'ownerReferences', [])
                or []
            )
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

    scope = str(resource_quotas.get('scope') or 'Tenant')
    unsupported: list[str] = []
    if scope not in {'Tenant', 'Namespace'}:
        unsupported.append(f'Tenant.spec.resourceQuotas.scope={scope}')

    hard_sources: list[tuple[str, Mapping[str, Any]]] = []
    observed_items: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        hard = item.get('hard') or {}
        if not isinstance(hard, Mapping):
            unsupported.append(f'Tenant.spec.resourceQuotas.items[{index}].hard')
            hard = {}
        hard_sources.append((f'Tenant.spec.resourceQuotas.items[{index}]', dict(hard)))

        scopes = item.get('scopes')
        if scopes:
            unsupported.append(f'Tenant.spec.resourceQuotas.items[{index}].scopes')
        scope_selector = item.get('scopeSelector')
        if scope_selector:
            unsupported.append(f'Tenant.spec.resourceQuotas.items[{index}].scopeSelector')
        for field, value in item.items():
            if field in {'hard', 'scopes', 'scopeSelector'}:
                continue
            if value not in (None, '', [], {}):
                unsupported.append(f'Tenant.spec.resourceQuotas.items[{index}].{field}')
        observed_items.append(dict(item))

    quota, quota_unsupported, ambiguous = _merge_hard_sources(hard_sources)
    unsupported.extend(quota_unsupported)
    return {
        'scope': scope,
        'quota': quota,
        'items': observed_items,
        'source_count': len(items),
        'unsupported_dimensions': sorted(set(unsupported)),
        'ambiguous_dimensions': ambiguous,
    }

def observe_capsule_tenant_resource_quota(tenant_item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize the legacy Capsule Tenant.spec.resourceQuotas authority without provider mutation."""

    return _capsule_tenant_quota(tenant_item)


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

    global_unsupported = list(global_quota['unsupported_dimensions'])
    global_ambiguous = list(global_quota['ambiguous_dimensions'])
    tenant_unsupported = list(tenant_quota['unsupported_dimensions']) if tenant_quota is not None else []
    tenant_ambiguous = list(tenant_quota['ambiguous_dimensions']) if tenant_quota is not None else []
    namespace_unsupported: list[str] = []
    namespace_ambiguous: list[str] = []
    external_constraint_details: list[dict[str, Any]] = []
    for namespace in namespace_rows:
        name = str(namespace.get('name') or 'unknown')
        namespace_unsupported.extend(
            f'Namespace/{name}: {value}' for value in namespace['allocation']['unsupported_dimensions']
        )
        namespace_ambiguous.extend(
            f'Namespace/{name}: {value}' for value in namespace['allocation']['ambiguous_dimensions']
        )
        for constraint in namespace['allocation'].get('external_limit_constraints') or []:
            external_constraint_details.append(
                {
                    **dict(constraint),
                    'namespace': name,
                    'authority': 'namespace_limit_range',
                    'management_state': 'observed_preserved',
                }
            )
        storage_policy = dict(namespace['allocation'].get('storage_policy') or {})
        if storage_policy:
            limit_source = next(
                (
                    item
                    for item in namespace['allocation'].get('source_resources') or []
                    if isinstance(item, Mapping) and item.get('kind') == 'LimitRange'
                ),
                {},
            )
            external_constraint_details.append(
                {
                    'constraint_type': 'pvc_storage_limit_range',
                    'kind': 'LimitRange',
                    'name': str(limit_source.get('name') or ''),
                    'uid': str(limit_source.get('uid') or ''),
                    'resource_version': str(limit_source.get('resource_version') or ''),
                    'item_type': 'PersistentVolumeClaim',
                    'fields': {
                        field: {'storage': value}
                        for field, value in storage_policy.items()
                    },
                    'namespace': name,
                    'authority': 'namespace_limit_range',
                    'management_state': 'observed_preserved',
                }
            )

    multiple_authority_reason = ''
    if len(authority_paths) > 1:
        multiple_authority_reason = (
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

    authority_unsupported: list[str] = []
    authority_ambiguous: list[str] = []
    external_constraints: list[str] = []
    if allocation_authority == 'capsule_tenant_resource_quotas':
        authority_unsupported.extend(tenant_unsupported)
        authority_ambiguous.extend(tenant_ambiguous)
        if tenant_quota is not None and tenant_quota.get('scope') == 'Namespace':
            authority_ambiguous.extend(correlation_ambiguities)
        else:
            external_constraints.extend(correlation_ambiguities)
        external_constraints.extend(namespace_unsupported)
        external_constraints.extend(namespace_ambiguous)
    elif allocation_authority == 'capsule_global_resource_quota':
        authority_unsupported.extend(global_unsupported)
        authority_ambiguous.extend(global_ambiguous)
        external_constraints.extend(correlation_ambiguities)
        external_constraints.extend(namespace_unsupported)
        external_constraints.extend(namespace_ambiguous)
    elif allocation_authority == 'native_namespaced':
        authority_unsupported.extend(namespace_unsupported)
        authority_ambiguous.extend(correlation_ambiguities)
        authority_ambiguous.extend(namespace_ambiguous)
    elif allocation_authority == 'ambiguous':
        authority_unsupported.extend(global_unsupported)
        authority_unsupported.extend(tenant_unsupported)
        authority_unsupported.extend(namespace_unsupported)
        authority_ambiguous.extend(correlation_ambiguities)
        authority_ambiguous.extend(global_ambiguous)
        authority_ambiguous.extend(tenant_ambiguous)
        authority_ambiguous.extend(namespace_ambiguous)
        if multiple_authority_reason:
            authority_ambiguous.append(multiple_authority_reason)

    unsupported = sorted(set(global_unsupported + tenant_unsupported + namespace_unsupported))
    ambiguous = sorted(
        set(
            list(correlation_ambiguities)
            + global_ambiguous
            + tenant_ambiguous
            + namespace_ambiguous
            + ([multiple_authority_reason] if multiple_authority_reason else [])
        )
    )
    authority_unsupported = sorted(set(authority_unsupported))
    authority_ambiguous = sorted(set(authority_ambiguous))
    external_constraints = sorted(set(external_constraints))

    control_state = 'observed' if not authority_unsupported and not authority_ambiguous else 'control_unavailable'
    if allocation_authority in {'capsule_tenant_resource_quotas', 'capsule_global_resource_quota'}:
        control_state = 'control_unavailable'
        control_reason = (
            'Capsule shared/Tenant quota is observed and preserved as provider evidence. '
            'Capability admission is required before governance cutover.'
        )
    elif control_state == 'control_unavailable':
        control_reason = (
            'Capsule allocation authority or dimensions are ambiguous/unsupported; '
            'governance cutover must fail closed.'
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
        'authority_unsupported_dimensions': authority_unsupported,
        'authority_ambiguous_dimensions': authority_ambiguous,
        'external_constraints': external_constraints,
        'external_constraint_details': external_constraint_details,
        'control_state': control_state,
        'control_reason': control_reason,
        'provenance': 'adopted_observed',
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
