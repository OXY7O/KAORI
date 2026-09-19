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
    tuple[str, ...],
]:
    document = integration_provider_document('alertmanager')
    capabilities: list[CapabilityDefinition] = []
    for index, raw in enumerate(require_list(document.get('capabilities'), 'alertmanager.capabilities')):
        item = require_mapping(raw, f'alertmanager.capabilities[{index}]')
        capabilities.append(
            CapabilityDefinition(
                key=require_str(item, 'key', f'alertmanager.capabilities[{index}]'),
                label=require_str(item, 'label', f'alertmanager.capabilities[{index}]'),
                category=require_str(item, 'category', f'alertmanager.capabilities[{index}]'),
                description=require_str(item, 'description', f'alertmanager.capabilities[{index}]'),
                required=require_bool(item, 'required', f'alertmanager.capabilities[{index}]', default=False),
                probe=str(item.get('probe') or '').strip(),
                success_criteria=str(item.get('success_criteria') or '').strip(),
                configuration_guidance=str(item.get('configuration_guidance') or '').strip(),
                impact=str(item.get('impact') or '').strip(),
                remediation=string_tuple(
                    item.get('remediation'),
                    f'alertmanager.capabilities[{index}].remediation',
                ),
            )
        )
    return (
        tuple(capabilities),
        string_tuple(document.get('compatibility_profiles'), 'alertmanager.compatibility_profiles'),
        string_tuple(document.get('binding_capability_keys'), 'alertmanager.binding_capability_keys'),
        string_tuple(document.get('core_capability_keys'), 'alertmanager.core_capability_keys'),
    )


CAPABILITIES, COMPATIBILITY_PROFILES, BINDING_CAPABILITY_KEYS, CORE_CAPABILITY_KEYS = _load_capability_contract()
CAPABILITY_BY_KEY = {item.key: item for item in CAPABILITIES}
CAPABILITY_KEYS = tuple(item.key for item in CAPABILITIES)
CORE_CAPABILITIES = tuple(item for item in CAPABILITIES if item.key in CORE_CAPABILITY_KEYS)
CONSUMER_PAYLOAD_CAPABILITY_KEYS = tuple(item.key for item in CAPABILITIES if item.key not in CORE_CAPABILITY_KEYS)
