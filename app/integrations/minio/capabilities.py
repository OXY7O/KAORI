from __future__ import annotations

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_bool, require_list, require_mapping, require_str, string_tuple
from app.integrations.contracts import CapabilityDefinition


def _load_capability_contract() -> tuple[
    tuple[CapabilityDefinition, ...],
    tuple[str, ...],
    str,
    str,
    tuple[str, ...],
]:
    document = integration_provider_document('object_storage')
    capabilities: list[CapabilityDefinition] = []
    for index, raw in enumerate(require_list(document.get('capabilities'), 'object_storage.capabilities')):
        item = require_mapping(raw, f'object_storage.capabilities[{index}]')
        capabilities.append(
            CapabilityDefinition(
                require_str(item, 'key', f'object_storage.capabilities[{index}]'),
                require_str(item, 'label', f'object_storage.capabilities[{index}]'),
                require_str(item, 'description', f'object_storage.capabilities[{index}]'),
                required=require_bool(item, 'required', f'object_storage.capabilities[{index}]', default=False),
            )
        )
    profile_keys = tuple(
        require_str(profile, 'key', f'object_storage.products[{product_index}].compatibility_profiles[{profile_index}]')
        for product_index, raw_product in enumerate(require_list(document.get('products'), 'object_storage.products'))
        for profile_index, profile in enumerate(
            require_list(
                require_mapping(raw_product, f'object_storage.products[{product_index}]').get('compatibility_profiles'),
                f'object_storage.products[{product_index}].compatibility_profiles',
            )
        )
    )
    return (
        tuple(capabilities),
        profile_keys,
        require_str(document, 'capability_profile', 'object_storage'),
        require_str(document, 'object_storage_system_scope', 'object_storage'),
        string_tuple(document.get('metrics_source_capability_scope'), 'object_storage.metrics_source_capability_scope'),
    )


(
    API_CAPABILITIES,
    COMPATIBILITY_PROFILES,
    CAPABILITY_PROFILE,
    OBJECT_STORAGE_SYSTEM_SCOPE,
    METRICS_SOURCE_CAPABILITY_SCOPE,
) = _load_capability_contract()
CAPABILITY_KEYS = tuple(item.key for item in API_CAPABILITIES)
