from __future__ import annotations

from dataclasses import dataclass


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


_DOMAIN_DEFINITIONS = (
    IntegrationDomainDefinition(
        key='orchestration',
        label='Orchestration',
        description='Cluster orchestration providers, control-plane connectivity, discovery, and runtime access.',
        icon='boxes',
        workspace_endpoint='integrations.orchestration',
        order=10,
    ),
    IntegrationDomainDefinition(
        key='observability',
        label='Observability',
        description='Metrics, alerting, runtime validation, and operational telemetry providers.',
        icon='activity',
        workspace_endpoint='integrations.observability',
        order=20,
    ),
    IntegrationDomainDefinition(
        key='storage',
        label='Storage',
        description='Object, file, and block storage providers used for operational visibility and data services.',
        icon='database',
        workspace_endpoint='integrations.storage',
        order=30,
    ),
)

_CAPABILITY_DEFINITIONS = (
    IntegrationCapabilityDefinition(
        key='cluster_orchestration',
        domain_key='orchestration',
        label='Cluster Orchestration',
        description='Cluster API connectivity, inventory discovery, and control-plane operations.',
        order=10,
        asset_types=('kubernetes_cluster',),
    ),
    IntegrationCapabilityDefinition(
        key='metrics',
        domain_key='observability',
        label='Metrics',
        description='Metrics query, historical telemetry, and capability validation.',
        order=10,
    ),
    IntegrationCapabilityDefinition(
        key='alerting',
        domain_key='observability',
        label='Alerting',
        description='Alert retrieval, routing context, silence capability, and alert API validation.',
        order=20,
    ),
    IntegrationCapabilityDefinition(
        key='object_storage',
        domain_key='storage',
        label='Object Storage',
        description='S3 and object-storage provider connectivity, inventory, analytics, and governance.',
        order=10,
        asset_types=('object_storage_system',),
    ),
    IntegrationCapabilityDefinition(
        key='file_storage',
        domain_key='storage',
        label='File Storage',
        description='Shared filesystem provider connectivity, inventory, and operational telemetry.',
        order=20,
    ),
    IntegrationCapabilityDefinition(
        key='block_storage',
        domain_key='storage',
        label='Block Storage',
        description='Block-device provider connectivity, inventory, and operational telemetry.',
        order=30,
    ),
)

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
