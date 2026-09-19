from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import (
    require_list,
    require_mapping,
    require_str,
    unique_by,
)

_PROVIDER_FILES = {
    'kubernetes': 'integrations/orchestration/container_orchestrator/providers/kubernetes.yaml',
    'metrics_source': 'integrations/observability/metrics_source/contract.yaml',
    'alertmanager': 'integrations/observability/alert_source/providers/alertmanager.yaml',
    'object_storage': 'integrations/storage/object_storage/contract.yaml',
}


@lru_cache(maxsize=1)
def integration_taxonomy_document() -> dict[str, Any]:
    document = load_definition_document(
        'integrations/taxonomy.yaml',
        expected_kind='integration_taxonomy',
    )
    domains = [
        require_mapping(item, f'domains[{index}]')
        for index, item in enumerate(require_list(document.get('domains'), 'domains'))
    ]
    capabilities = [
        require_mapping(item, f'capabilities[{index}]')
        for index, item in enumerate(require_list(document.get('capabilities'), 'capabilities'))
    ]
    unique_by(domains, 'key', 'domains')
    domain_keys = {require_str(item, 'key', f'domains[{index}]') for index, item in enumerate(domains)}
    seen_capabilities: set[tuple[str, str]] = set()
    for index, item in enumerate(capabilities):
        path = f'capabilities[{index}]'
        domain_key = require_str(item, 'domain_key', path)
        capability_key = require_str(item, 'key', path)
        if domain_key not in domain_keys:
            raise DefinitionError(f'{path}.domain_key references unknown domain {domain_key!r}.')
        identity = (domain_key, capability_key)
        if identity in seen_capabilities:
            raise DefinitionError(f'Duplicate integration capability: {domain_key}.{capability_key}.')
        seen_capabilities.add(identity)
    consumer_assets = [
        require_mapping(item, f'consumer_assets[{index}]')
        for index, item in enumerate(require_list(document.get('consumer_assets'), 'consumer_assets'))
    ]
    unique_by(consumer_assets, 'asset_type', 'consumer_assets')
    for index, item in enumerate(consumer_assets):
        require_str(item, 'model_key', f'consumer_assets[{index}]')
    return document


@lru_cache(maxsize=1)
def integration_provider_matrix_document() -> dict[str, Any]:
    document = load_definition_document(
        'integrations/provider_matrix.yaml',
        expected_kind='integration_provider_matrix',
    )
    integration_types = [
        require_mapping(item, f'integration_types[{index}]')
        for index, item in enumerate(require_list(document.get('integration_types'), 'integration_types'))
    ]
    unique_by(integration_types, 'key', 'integration_types')
    taxonomy = integration_taxonomy_document()
    capability_keys = {
        require_str(item, 'key', f'capabilities[{index}]')
        for index, item in enumerate(require_list(taxonomy.get('capabilities'), 'capabilities'))
    }
    domain_by_capability = {
        require_str(item, 'key', f'capabilities[{index}]'): require_str(item, 'domain_key', f'capabilities[{index}]')
        for index, item in enumerate(require_list(taxonomy.get('capabilities'), 'capabilities'))
    }
    for index, raw in enumerate(integration_types):
        path = f'integration_types[{index}]'
        integration_type = require_str(raw, 'key', path)
        domain_key = require_str(raw, 'domain_key', path)
        if integration_type not in capability_keys:
            raise DefinitionError(f'{path}.key references unknown integration capability {integration_type!r}.')
        if domain_by_capability[integration_type] != domain_key:
            raise DefinitionError(
                f'{path}.domain_key must be {domain_by_capability[integration_type]!r} for {integration_type!r}.'
            )
        providers = [
            require_mapping(item, f'{path}.providers[{provider_index}]')
            for provider_index, item in enumerate(require_list(raw.get('providers'), f'{path}.providers'))
        ]
        unique_by(providers, 'key', f'{path}.providers')
        for provider_index, provider in enumerate(providers):
            provider_path = f'{path}.providers[{provider_index}]'
            require_str(provider, 'label', provider_path)
            require_str(provider, 'adapter_key', provider_path)
            lifecycle = require_str(provider, 'lifecycle', provider_path)
            if lifecycle not in {'available', 'planned'}:
                raise DefinitionError(f'{provider_path}.lifecycle must be available or planned; got {lifecycle!r}.')
            require_str(provider, 'protocol', provider_path)
    return document


@lru_cache(maxsize=1)
def integration_compatibility_document() -> dict[str, Any]:
    document = load_definition_document(
        'integrations/compatibility.yaml',
        expected_kind='integration_compatibility',
    )
    policy = require_mapping(document.get('kubernetes_lifecycle_policy'), 'kubernetes_lifecycle_policy')
    for key in (
        'supported_version_constraint',
        'current_min_version',
        'current_max_version_exclusive',
        'current_version_label',
        'upstream_supported_version_label',
        'supported_version_label',
    ):
        require_str(policy, key, 'kubernetes_lifecycle_policy')

    contracts = [
        require_mapping(item, f'contract_profiles[{index}]')
        for index, item in enumerate(require_list(document.get('contract_profiles'), 'contract_profiles'))
    ]
    unique_by(contracts, 'key', 'contract_profiles')
    contract_keys = set()
    for index, item in enumerate(contracts):
        path = f'contract_profiles[{index}]'
        key = require_str(item, 'key', path)
        contract_keys.add(key)
        require_str(item, 'adapter_key', path)
        require_str(item, 'notes', path)
        products = require_list(item.get('products'), f'{path}.products')
        if not products:
            raise DefinitionError(f'{path}.products must not be empty.')

    products = [
        require_mapping(item, f'products[{index}]')
        for index, item in enumerate(require_list(document.get('products'), 'products'))
    ]
    unique_by(products, 'key', 'products')
    product_keys = set()
    for index, item in enumerate(products):
        path = f'products[{index}]'
        product_key = require_str(item, 'key', path)
        product_keys.add(product_key)
        contract_key = require_str(item, 'contract_profile', path)
        if contract_key not in contract_keys:
            raise DefinitionError(f'{path}.contract_profile references unknown contract {contract_key!r}.')
        for field in (
            'label',
            'icon',
            'version_scheme',
            'minimum_label',
            'recommended_label',
            'qualified_version_label',
            'upstream_lifecycle_label',
            'support_label',
            'support_tone',
            'capability_summary',
            'validation_basis',
        ):
            require_str(item, field, path)

    qualifications = [
        require_mapping(item, f'qualifications[{index}]')
        for index, item in enumerate(require_list(document.get('qualifications'), 'qualifications'))
    ]
    unique_by(qualifications, 'key', 'qualifications')
    for index, item in enumerate(qualifications):
        path = f'qualifications[{index}]'
        product_key = require_str(item, 'product', path)
        if product_key not in product_keys:
            raise DefinitionError(f'{path}.product references unknown product {product_key!r}.')
        contract_key = require_str(item, 'contract_profile', path)
        if contract_key not in contract_keys:
            raise DefinitionError(f'{path}.contract_profile references unknown contract {contract_key!r}.')
        require_str(item, 'version_constraint', path)
        require_str(item, 'support_level', path)
        require_str(item, 'upstream_lifecycle', path)
        require_str(item, 'notes', path)
    return document


@lru_cache(maxsize=8)
def integration_provider_document(provider: str) -> dict[str, Any]:
    provider_key = str(provider or '').strip().lower()
    try:
        relative_path = _PROVIDER_FILES[provider_key]
    except KeyError as exc:
        raise DefinitionError(f'Unknown integration provider definition: {provider!r}.') from exc
    document = load_definition_document(
        relative_path,
        expected_kind='integration_provider_contract',
    )
    declared_provider = require_str(document, 'provider', relative_path)
    if declared_provider != provider_key:
        raise DefinitionError(f'{relative_path}.provider must be {provider_key!r}; got {declared_provider!r}.')
    capabilities = [
        require_mapping(item, f'{relative_path}.capabilities[{index}]')
        for index, item in enumerate(require_list(document.get('capabilities'), f'{relative_path}.capabilities'))
    ]
    unique_by(capabilities, 'key', f'{relative_path}.capabilities')
    capability_keys = {
        require_str(item, 'key', f'{relative_path}.capabilities[{index}]') for index, item in enumerate(capabilities)
    }

    if provider_key == 'alertmanager':
        profiles = [
            require_mapping(item, f'{relative_path}.profiles[{index}]')
            for index, item in enumerate(require_list(document.get('profiles'), f'{relative_path}.profiles'))
        ]
        unique_by(profiles, 'key', f'{relative_path}.profiles')
        for index, profile in enumerate(profiles):
            for capability_key in profile.get('required_capabilities') or ():
                if str(capability_key) not in capability_keys:
                    raise DefinitionError(
                        f'{relative_path}.profiles[{index}] references unknown capability {capability_key!r}.'
                    )
        consumer_profiles = [
            require_mapping(item, f'{relative_path}.consumer_profiles[{index}]')
            for index, item in enumerate(
                require_list(document.get('consumer_profiles'), f'{relative_path}.consumer_profiles')
            )
        ]
        unique_by(consumer_profiles, 'asset_type', f'{relative_path}.consumer_profiles')
        for index, profile in enumerate(consumer_profiles):
            for field in ('required_capabilities', 'optional_capabilities'):
                for capability_key in profile.get(field) or ():
                    if str(capability_key) not in capability_keys:
                        raise DefinitionError(
                            f'{relative_path}.consumer_profiles[{index}].{field} references unknown capability '
                            f'{capability_key!r}.'
                        )

    if provider_key == 'metrics_source':
        provider_kinds = [
            require_mapping(item, f'{relative_path}.provider_kinds[{index}]')
            for index, item in enumerate(
                require_list(document.get('provider_kinds'), f'{relative_path}.provider_kinds')
            )
        ]
        unique_by(provider_kinds, 'key', f'{relative_path}.provider_kinds')
        for index, provider_kind in enumerate(provider_kinds):
            path = f'{relative_path}.provider_kinds[{index}]'
            require_str(provider_kind, 'label', path)
            require_str(provider_kind, 'adapter_key', path)
            require_str(provider_kind, 'query_language', path)
            require_str(provider_kind, 'default_query_horizon', path)
            require_str(provider_kind, 'version_detection_mode', path)
            require_str(provider_kind, 'endpoint_placeholder', path)
            require_str(provider_kind, 'icon', path)
        binding_profiles = [
            require_mapping(item, f'{relative_path}.binding_profiles[{index}]')
            for index, item in enumerate(
                require_list(document.get('binding_profiles'), f'{relative_path}.binding_profiles')
            )
        ]
        unique_by(binding_profiles, 'asset_type', f'{relative_path}.binding_profiles')
        for index, profile in enumerate(binding_profiles):
            require_str(profile, 'validation_strategy', f'{relative_path}.binding_profiles[{index}]')

    if provider_key == 'object_storage':
        products = [
            require_mapping(item, f'{relative_path}.products[{index}]')
            for index, item in enumerate(require_list(document.get('products'), f'{relative_path}.products'))
        ]
        unique_by(products, 'key', f'{relative_path}.products')
        profile_keys: set[str] = set()
        for product_index, product in enumerate(products):
            require_str(product, 'label', f'{relative_path}.products[{product_index}]')
            profiles = require_list(
                product.get('compatibility_profiles'),
                f'{relative_path}.products[{product_index}].compatibility_profiles',
            )
            for profile_index, raw_profile in enumerate(profiles):
                profile = require_mapping(
                    raw_profile,
                    f'{relative_path}.products[{product_index}].compatibility_profiles[{profile_index}]',
                )
                profile_key = require_str(
                    profile,
                    'key',
                    f'{relative_path}.products[{product_index}].compatibility_profiles[{profile_index}]',
                )
                if profile_key in profile_keys:
                    raise DefinitionError(f'Duplicate object-storage compatibility profile: {profile_key!r}.')
                profile_keys.add(profile_key)
    return document


def clear_integration_definition_cache() -> None:
    integration_taxonomy_document.cache_clear()
    integration_provider_matrix_document.cache_clear()
    integration_compatibility_document.cache_clear()
    integration_provider_document.cache_clear()
