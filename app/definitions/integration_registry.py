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
    'kubernetes': 'integrations/kubernetes.yaml',
    'prometheus': 'integrations/prometheus.yaml',
    'alertmanager': 'integrations/alertmanager.yaml',
    'object_storage': 'integrations/object_storage.yaml',
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
        'supported_version_label',
    ):
        require_str(policy, key, 'kubernetes_lifecycle_policy')
    profiles = [
        require_mapping(item, f'profiles[{index}]')
        for index, item in enumerate(require_list(document.get('profiles'), 'profiles'))
    ]
    unique_by(profiles, 'key', 'profiles')
    for index, item in enumerate(profiles):
        path = f'profiles[{index}]'
        require_str(item, 'product', path)
        require_str(item, 'version_constraint', path)
        require_str(item, 'support_level', path)
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

    if provider_key == 'prometheus':
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
    integration_compatibility_document.cache_clear()
    integration_provider_document.cache_clear()
