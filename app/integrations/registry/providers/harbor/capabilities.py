from __future__ import annotations

from dataclasses import dataclass

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_bool, require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    category: str
    description: str
    required: bool = False
    probe: str = ''
    success_criteria: str = ''
    configuration_guidance: str = ''
    impact: str = ''
    remediation: tuple[str, ...] = ()


def _load_capability_contract() -> tuple[
    tuple[CapabilityDefinition, ...],
    tuple[str, ...],
    tuple[str, ...],
    str,
]:
    document = integration_provider_document('registry')
    capabilities: list[CapabilityDefinition] = []
    for index, raw in enumerate(require_list(document.get('capabilities'), 'registry.capabilities')):
        item = require_mapping(raw, f'registry.capabilities[{index}]')
        capabilities.append(
            CapabilityDefinition(
                key=require_str(item, 'key', f'registry.capabilities[{index}]'),
                label=require_str(item, 'label', f'registry.capabilities[{index}]'),
                category=require_str(item, 'category', f'registry.capabilities[{index}]'),
                description=require_str(item, 'description', f'registry.capabilities[{index}]'),
                required=require_bool(item, 'required', f'registry.capabilities[{index}]', default=False),
                probe=str(item.get('probe') or '').strip(),
                success_criteria=str(item.get('success_criteria') or '').strip(),
                configuration_guidance=str(item.get('configuration_guidance') or '').strip(),
                impact=str(item.get('impact') or '').strip(),
                remediation=string_tuple(item.get('remediation'), f'registry.capabilities[{index}].remediation'),
            )
        )
    return (
        tuple(capabilities),
        string_tuple(document.get('compatibility_profiles'), 'registry.compatibility_profiles'),
        string_tuple(document.get('core_capability_keys'), 'registry.core_capability_keys'),
        require_str(document, 'capability_profile', 'registry'),
    )


CAPABILITIES, COMPATIBILITY_PROFILES, CORE_CAPABILITY_KEYS, CAPABILITY_PROFILE = _load_capability_contract()
CAPABILITY_BY_KEY = {item.key: item for item in CAPABILITIES}
CAPABILITY_KEYS = tuple(item.key for item in CAPABILITIES)
CORE_CAPABILITIES = tuple(item for item in CAPABILITIES if item.key in CORE_CAPABILITY_KEYS)
