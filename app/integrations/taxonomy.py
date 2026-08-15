from __future__ import annotations

from dataclasses import dataclass

from app.definitions.integration_registry import integration_taxonomy_document
from app.definitions.validation import require_int, require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True, slots=True)
class IntegrationDomainDefinition:
    key: str
    label: str
    description: str
    icon: str
    workspace_endpoint: str
    order: int


@dataclass(frozen=True, slots=True)
class IntegrationCapabilityDefinition:
    key: str
    domain_key: str
    label: str
    description: str
    order: int
    asset_types: tuple[str, ...] = ()


def _load_taxonomy() -> tuple[
    tuple[IntegrationDomainDefinition, ...],
    tuple[IntegrationCapabilityDefinition, ...],
]:
    document = integration_taxonomy_document()
    domains: list[IntegrationDomainDefinition] = []
    for index, raw in enumerate(require_list(document.get('domains'), 'domains')):
        item = require_mapping(raw, f'domains[{index}]')
        domains.append(
            IntegrationDomainDefinition(
                key=require_str(item, 'key', f'domains[{index}]'),
                label=require_str(item, 'label', f'domains[{index}]'),
                description=require_str(item, 'description', f'domains[{index}]'),
                icon=require_str(item, 'icon', f'domains[{index}]'),
                workspace_endpoint=require_str(item, 'workspace_endpoint', f'domains[{index}]'),
                order=require_int(item, 'order', f'domains[{index}]'),
            )
        )
    capabilities: list[IntegrationCapabilityDefinition] = []
    for index, raw in enumerate(require_list(document.get('capabilities'), 'capabilities')):
        item = require_mapping(raw, f'capabilities[{index}]')
        capabilities.append(
            IntegrationCapabilityDefinition(
                key=require_str(item, 'key', f'capabilities[{index}]'),
                domain_key=require_str(item, 'domain_key', f'capabilities[{index}]'),
                label=require_str(item, 'label', f'capabilities[{index}]'),
                description=require_str(item, 'description', f'capabilities[{index}]'),
                order=require_int(item, 'order', f'capabilities[{index}]'),
                asset_types=string_tuple(item.get('asset_types'), f'capabilities[{index}].asset_types'),
            )
        )
    return tuple(domains), tuple(capabilities)


_DOMAIN_DEFINITIONS, _CAPABILITY_DEFINITIONS = _load_taxonomy()
DOMAINS = {item.key: item for item in _DOMAIN_DEFINITIONS}
CAPABILITIES = {(item.domain_key, item.key): item for item in _CAPABILITY_DEFINITIONS}


def get_domain_definition(domain_key: str) -> IntegrationDomainDefinition:
    normalized = str(domain_key or '').strip().lower()
    try:
        return DOMAINS[normalized]
    except KeyError as exc:
        raise ValueError(f'Unknown integration domain: {domain_key!r}.') from exc


def get_capability_definition(
    domain_key: str,
    capability_key: str,
) -> IntegrationCapabilityDefinition:
    domain = str(domain_key or '').strip().lower()
    capability = str(capability_key or '').strip().lower()
    try:
        return CAPABILITIES[(domain, capability)]
    except KeyError as exc:
        raise ValueError(f'Unknown integration capability {capability_key!r} for domain {domain_key!r}.') from exc


def ordered_domain_definitions() -> tuple[IntegrationDomainDefinition, ...]:
    return tuple(sorted(DOMAINS.values(), key=lambda item: (item.order, item.key)))


def capability_definitions_for_domain(domain_key: str) -> tuple[IntegrationCapabilityDefinition, ...]:
    normalized = str(domain_key or '').strip().lower()
    return tuple(
        sorted(
            (item for item in CAPABILITIES.values() if item.domain_key == normalized),
            key=lambda item: (item.order, item.key),
        )
    )


def asset_types_for_domain(domain_key: str) -> tuple[str, ...]:
    """Return managed asset types owned by one Integration domain."""
    return tuple(
        asset_type
        for capability in capability_definitions_for_domain(domain_key)
        for asset_type in capability.asset_types
    )


def domain_key_for_asset_type(asset_type: str) -> str | None:
    """Resolve the domain that owns a managed asset type, if registered."""
    normalized = str(asset_type or '').strip().lower()
    if not normalized:
        return None
    for capability in CAPABILITIES.values():
        if normalized in capability.asset_types:
            return capability.domain_key
    return None
