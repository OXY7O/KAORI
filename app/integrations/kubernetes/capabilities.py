from __future__ import annotations

from app.integrations.contracts import CapabilityDefinition

CAPABILITIES = (
    CapabilityDefinition('discovery', 'API Discovery', 'Discover supported Kubernetes API resources.', required=True),
    CapabilityDefinition('inventory', 'Inventory', 'Collect Kubernetes inventory snapshots.', required=True),
    CapabilityDefinition('operations', 'Operations', 'Execute governed Kubernetes operational actions.'),
    CapabilityDefinition('governance', 'Governance', 'Inspect Kubernetes governance and TLS controls.'),
)

CAPABILITY_KEYS = tuple(item.key for item in CAPABILITIES)
COMPATIBILITY_PROFILES = ('kubernetes-v1',)
