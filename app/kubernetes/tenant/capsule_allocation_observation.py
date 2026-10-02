from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kubernetes.client.rest import ApiException

from app.kubernetes.tenant.allocation_observation import (
    _CAPSULE_GROUP,
    _CAPSULE_TENANT_LABEL_KEYS,
    _CAPSULE_VERSIONS,
    _mapping_equivalent,
    _merge_hard_sources,
    _metadata_value,
    _resource_reference,
    _value,
    observe_native_namespace_allocation,
)


def _capsule_status_namespace_names(tenant_item: Mapping[str, Any]) -> set[str]:
    status = tenant_item.get('status') or {}
    if not isinstance(status, Mapping):
        return set()
    return {str(name).strip() for name in list(status.get('namespaces') or []) if str(name).strip()}


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
            str(labels[key]).strip() for key in _CAPSULE_TENANT_LABEL_KEYS if key in labels and str(labels[key]).strip()
        }
        owner_claims = {
            str(_value(owner, 'name', '') or '').strip()
            for owner in list(
                _value(metadata, 'owner_references', None) or _value(metadata, 'ownerReferences', []) or []
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




def observe_capsule_tenant_resource_quota(tenant_item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize the legacy Capsule Tenant.spec.resourceQuotas authority without provider mutation."""

    return _capsule_tenant_quota(tenant_item)


def _namespace_observations(
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
    rows: list[dict[str, Any]] = []
    for namespace in correlated:
        observation = observe_native_namespace_allocation(core_api, namespace['name'])
        rows.append({**namespace, 'allocation': observation})
    return {
        'rows': rows,
        'correlation_ambiguities': correlation_ambiguities,
        'native_quota_present': any(bool(row['allocation']['quota']) for row in rows),
        'native_limits_present': any(bool(row['allocation']['limits']) for row in rows),
    }


def _shared_authority_sources(
    client: Any,
    *,
    tenant_name: str,
    tenant_item: Mapping[str, Any],
    namespace_state: Mapping[str, Any],
) -> dict[str, Any]:
    tenant_quota = _capsule_tenant_quota(tenant_item)
    global_quota = _capsule_global_resource_quotas(client.custom_objects_api(), tenant_name)
    global_quota_present = bool(global_quota['source_resources'])
    tenant_quota_present = tenant_quota is not None

    shared_quota: dict[str, str] = {}
    shared_scope: str | None = None
    if tenant_quota is not None:
        shared_quota = dict(tenant_quota['quota'])
        shared_scope = str(tenant_quota['scope'])
    elif global_quota_present:
        shared_quota = dict(global_quota['quota'])
        shared_scope = 'Tenant'

    observed_quota_rows = [
        dict(namespace['allocation'].get('quota') or {})
        for namespace in namespace_state['rows']
        if namespace['allocation'].get('quota')
    ]
    native_quota_matches_shared = bool(shared_quota) and bool(observed_quota_rows) and all(
        _mapping_equivalent(quota, shared_quota) for quota in observed_quota_rows
    )

    authority_paths: list[str] = []
    if tenant_quota_present:
        authority_paths.append('capsule_tenant_resource_quotas')
    if global_quota_present:
        authority_paths.append('capsule_global_resource_quota')
    native_only = (
        bool(namespace_state['native_quota_present']) and not native_quota_matches_shared
    ) or (
        not tenant_quota_present
        and not global_quota_present
        and (bool(namespace_state['native_quota_present']) or bool(namespace_state['native_limits_present']))
    )
    if native_only:
        authority_paths.append('native_namespaced')

    return {
        'tenant_quota': tenant_quota,
        'global_quota': global_quota,
        'shared_quota': shared_quota,
        'shared_scope': shared_scope,
        'authority_paths': authority_paths,
    }


def _namespace_constraint_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unsupported: list[str] = []
    ambiguous: list[str] = []
    details: list[dict[str, Any]] = []
    for namespace in rows:
        name = str(namespace.get('name') or 'unknown')
        allocation = namespace['allocation']
        unsupported.extend(f'Namespace/{name}: {value}' for value in allocation['unsupported_dimensions'])
        ambiguous.extend(f'Namespace/{name}: {value}' for value in allocation['ambiguous_dimensions'])
        for constraint in allocation.get('external_limit_constraints') or []:
            details.append(
                {
                    **dict(constraint),
                    'namespace': name,
                    'authority': 'namespace_limit_range',
                    'management_state': 'observed_preserved',
                }
            )
        storage_policy = dict(allocation.get('storage_policy') or {})
        if not storage_policy:
            continue
        limit_source = next(
            (
                item
                for item in allocation.get('source_resources') or []
                if isinstance(item, Mapping) and item.get('kind') == 'LimitRange'
            ),
            {},
        )
        details.append(
            {
                'constraint_type': 'pvc_storage_limit_range',
                'kind': 'LimitRange',
                'name': str(limit_source.get('name') or ''),
                'uid': str(limit_source.get('uid') or ''),
                'resource_version': str(limit_source.get('resource_version') or ''),
                'item_type': 'PersistentVolumeClaim',
                'fields': {field: {'storage': value} for field, value in storage_policy.items()},
                'namespace': name,
                'authority': 'namespace_limit_range',
                'management_state': 'observed_preserved',
            }
        )
    return {'unsupported': unsupported, 'ambiguous': ambiguous, 'details': details}


def _allocation_authority(authority_paths: list[str]) -> str:
    if not authority_paths:
        return 'none_observed'
    if len(authority_paths) == 1:
        return authority_paths[0]
    return 'ambiguous'


def _constraint_state(
    *,
    namespace_state: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> dict[str, Any]:
    global_quota = sources['global_quota']
    tenant_quota = sources['tenant_quota']
    namespace = _namespace_constraint_summary(list(namespace_state['rows']))
    correlation = list(namespace_state['correlation_ambiguities'])
    global_unsupported = list(global_quota['unsupported_dimensions'])
    global_ambiguous = list(global_quota['ambiguous_dimensions'])
    tenant_unsupported = list(tenant_quota['unsupported_dimensions']) if tenant_quota is not None else []
    tenant_ambiguous = list(tenant_quota['ambiguous_dimensions']) if tenant_quota is not None else []
    multiple_reason = ''
    if len(sources['authority_paths']) > 1:
        multiple_reason = (
            'Multiple effective allocation authority paths were detected: '
            + ', '.join(sources['authority_paths'])
            + '.'
        )
    return {
        'global_unsupported': global_unsupported,
        'global_ambiguous': global_ambiguous,
        'tenant_unsupported': tenant_unsupported,
        'tenant_ambiguous': tenant_ambiguous,
        'namespace_unsupported': namespace['unsupported'],
        'namespace_ambiguous': namespace['ambiguous'],
        'external_constraint_details': namespace['details'],
        'correlation_ambiguities': correlation,
        'multiple_reason': multiple_reason,
        'unsupported': sorted(set(global_unsupported + tenant_unsupported + namespace['unsupported'])),
        'ambiguous': sorted(
            set(correlation + global_ambiguous + tenant_ambiguous + namespace['ambiguous'] + ([multiple_reason] if multiple_reason else []))
        ),
    }


def _authority_constraints(allocation_authority: str, state: Mapping[str, Any], tenant_quota: Any) -> dict[str, list[str]]:
    unsupported: list[str] = []
    ambiguous: list[str] = []
    external: list[str] = []
    if allocation_authority == 'capsule_tenant_resource_quotas':
        unsupported.extend(state['tenant_unsupported'])
        ambiguous.extend(state['tenant_ambiguous'])
        if tenant_quota is not None and tenant_quota.get('scope') == 'Namespace':
            ambiguous.extend(state['correlation_ambiguities'])
        else:
            external.extend(state['correlation_ambiguities'])
        external.extend(state['namespace_unsupported'])
        external.extend(state['namespace_ambiguous'])
    elif allocation_authority == 'capsule_global_resource_quota':
        unsupported.extend(state['global_unsupported'])
        ambiguous.extend(state['global_ambiguous'])
        external.extend(state['correlation_ambiguities'])
        external.extend(state['namespace_unsupported'])
        external.extend(state['namespace_ambiguous'])
    elif allocation_authority == 'native_namespaced':
        unsupported.extend(state['namespace_unsupported'])
        ambiguous.extend(state['correlation_ambiguities'])
        ambiguous.extend(state['namespace_ambiguous'])
    elif allocation_authority == 'ambiguous':
        unsupported.extend(state['global_unsupported'])
        unsupported.extend(state['tenant_unsupported'])
        unsupported.extend(state['namespace_unsupported'])
        ambiguous.extend(state['correlation_ambiguities'])
        ambiguous.extend(state['global_ambiguous'])
        ambiguous.extend(state['tenant_ambiguous'])
        ambiguous.extend(state['namespace_ambiguous'])
        if state['multiple_reason']:
            ambiguous.append(state['multiple_reason'])
    return {
        'unsupported': sorted(set(unsupported)),
        'ambiguous': sorted(set(ambiguous)),
        'external': sorted(set(external)),
    }


def _control_state(allocation_authority: str, constraints: Mapping[str, list[str]]) -> tuple[str, str]:
    unavailable = bool(constraints['unsupported'] or constraints['ambiguous'])
    if allocation_authority in {'capsule_tenant_resource_quotas', 'capsule_global_resource_quota'}:
        return (
            'control_unavailable',
            'Capsule shared/Tenant quota is observed and preserved as provider evidence. '
            'Capability admission is required before governance cutover.',
        )
    if unavailable:
        return (
            'control_unavailable',
            'Capsule allocation authority or dimensions are ambiguous/unsupported; governance cutover must fail closed.',
        )
    return (
        'observed',
        'Capsule namespace allocation is observed without provider mutation and remains read-only until explicit '
        'governance cutover.',
    )


def observe_capsule_tenant_allocation(
    client: Any,
    *,
    tenant_name: str,
    tenant_item: Mapping[str, Any],
) -> dict[str, Any]:
    namespace_state = _namespace_observations(client, tenant_name=tenant_name, tenant_item=tenant_item)
    sources = _shared_authority_sources(
        client,
        tenant_name=tenant_name,
        tenant_item=tenant_item,
        namespace_state=namespace_state,
    )
    allocation_authority = _allocation_authority(list(sources['authority_paths']))
    state = _constraint_state(namespace_state=namespace_state, sources=sources)
    authority = _authority_constraints(allocation_authority, state, sources['tenant_quota'])
    control_state, control_reason = _control_state(allocation_authority, authority)

    return {
        'provider': 'capsule',
        'tenant_name': tenant_name,
        'correlated_namespaces': namespace_state['rows'],
        'allocation_authority': allocation_authority,
        'authority_paths': sources['authority_paths'],
        'tenant_resource_quota': sources['tenant_quota'],
        'global_resource_quota': sources['global_quota'],
        'shared_quota': sources['shared_quota'],
        'shared_scope': sources['shared_scope'],
        'unsupported_dimensions': state['unsupported'],
        'ambiguous_dimensions': state['ambiguous'],
        'authority_unsupported_dimensions': authority['unsupported'],
        'authority_ambiguous_dimensions': authority['ambiguous'],
        'external_constraints': authority['external'],
        'external_constraint_details': state['external_constraint_details'],
        'control_state': control_state,
        'control_reason': control_reason,
        'provenance': 'adopted_observed',
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
