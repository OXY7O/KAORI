from __future__ import annotations

from dataclasses import dataclass

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import optional_str, require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    required_by: tuple[str, ...]
    impact: str
    source_owner: str
    recommendation: str
    expected_signals: tuple[str, ...] = ()
    validation_query: str | None = None


def _load_capability_contract() -> tuple[
    dict[str, CapabilityDefinition],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    document = integration_provider_document('prometheus')
    capabilities: dict[str, CapabilityDefinition] = {}
    for index, raw in enumerate(require_list(document.get('capabilities'), 'prometheus.capabilities')):
        item = require_mapping(raw, f'prometheus.capabilities[{index}]')
        capability = CapabilityDefinition(
            key=require_str(item, 'key', f'prometheus.capabilities[{index}]'),
            label=require_str(item, 'label', f'prometheus.capabilities[{index}]'),
            required_by=string_tuple(item.get('required_by'), f'prometheus.capabilities[{index}].required_by'),
            impact=require_str(item, 'impact', f'prometheus.capabilities[{index}]'),
            source_owner=require_str(item, 'source_owner', f'prometheus.capabilities[{index}]'),
            recommendation=require_str(item, 'recommendation', f'prometheus.capabilities[{index}]'),
            expected_signals=string_tuple(
                item.get('expected_signals'),
                f'prometheus.capabilities[{index}].expected_signals',
            ),
            validation_query=optional_str(item, 'validation_query', f'prometheus.capabilities[{index}]'),
        )
        capabilities[capability.key] = capability
    return (
        capabilities,
        string_tuple(document.get('provider_capability_keys'), 'prometheus.provider_capability_keys'),
        string_tuple(document.get('compatibility_profiles'), 'prometheus.compatibility_profiles'),
        string_tuple(document.get('binding_capability_keys'), 'prometheus.binding_capability_keys'),
    )


CAPABILITIES, PROVIDER_CAPABILITY_KEYS, COMPATIBILITY_PROFILES, BINDING_CAPABILITY_KEYS = _load_capability_contract()
CAPABILITY_KEYS = PROVIDER_CAPABILITY_KEYS


def definition(key: str) -> CapabilityDefinition | None:
    return CAPABILITIES.get(key)
