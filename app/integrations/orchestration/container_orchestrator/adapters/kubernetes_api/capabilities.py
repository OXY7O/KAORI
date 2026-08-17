from __future__ import annotations

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_bool, require_list, require_mapping, require_str, string_tuple
from app.integrations.contracts import CapabilityDefinition


def _load_capabilities() -> tuple[tuple[CapabilityDefinition, ...], tuple[str, ...]]:
    document = integration_provider_document('kubernetes')
    capabilities: list[CapabilityDefinition] = []
    for index, raw in enumerate(require_list(document.get('capabilities'), 'kubernetes.capabilities')):
        item = require_mapping(raw, f'kubernetes.capabilities[{index}]')
        capabilities.append(
            CapabilityDefinition(
                require_str(item, 'key', f'kubernetes.capabilities[{index}]'),
                require_str(item, 'label', f'kubernetes.capabilities[{index}]'),
                require_str(item, 'description', f'kubernetes.capabilities[{index}]'),
                required=require_bool(item, 'required', f'kubernetes.capabilities[{index}]', default=False),
            )
        )
    profiles = string_tuple(document.get('compatibility_profiles'), 'kubernetes.compatibility_profiles')
    return tuple(capabilities), profiles


CAPABILITIES, COMPATIBILITY_PROFILES = _load_capabilities()
CAPABILITY_KEYS = tuple(item.key for item in CAPABILITIES)
