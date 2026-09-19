from __future__ import annotations

from dataclasses import dataclass

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    required_by: tuple[str, ...]
    impact: str
    source_owner: str
    recommendation: str
    expected_signals: tuple[str, ...] = ()


def _load_capability_contract() -> tuple[
    dict[str, CapabilityDefinition],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    document = integration_provider_document('metrics_source')
    capabilities: dict[str, CapabilityDefinition] = {}
    for index, raw in enumerate(require_list(document.get('capabilities'), 'metrics_source.capabilities')):
        item = require_mapping(raw, f'metrics_source.capabilities[{index}]')
        capability = CapabilityDefinition(
            key=require_str(item, 'key', f'metrics_source.capabilities[{index}]'),
            label=require_str(item, 'label', f'metrics_source.capabilities[{index}]'),
            required_by=string_tuple(item.get('required_by'), f'metrics_source.capabilities[{index}].required_by'),
            impact=require_str(item, 'impact', f'metrics_source.capabilities[{index}]'),
            source_owner=require_str(item, 'source_owner', f'metrics_source.capabilities[{index}]'),
            recommendation=require_str(item, 'recommendation', f'metrics_source.capabilities[{index}]'),
            expected_signals=string_tuple(
                item.get('expected_signals'),
                f'metrics_source.capabilities[{index}].expected_signals',
            ),
        )
        capabilities[capability.key] = capability
    return (
        capabilities,
        string_tuple(document.get('provider_capability_keys'), 'metrics_source.provider_capability_keys'),
        string_tuple(document.get('compatibility_profiles'), 'metrics_source.compatibility_profiles'),
        string_tuple(document.get('binding_capability_keys'), 'metrics_source.binding_capability_keys'),
    )


CAPABILITIES, PROVIDER_CAPABILITY_KEYS, COMPATIBILITY_PROFILES, BINDING_CAPABILITY_KEYS = _load_capability_contract()
CAPABILITY_KEYS = PROVIDER_CAPABILITY_KEYS


def definition(key: str) -> CapabilityDefinition | None:
    return CAPABILITIES.get(key)
