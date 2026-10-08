from __future__ import annotations

from app.integrations.registry.collectors import (
    CollectorCallable,
    InventoryProgressCallback,
    ProgressCollectorCallable,
    RegistryInventoryCollector,
    get_registry_collector,
    register_registry_collector,
    registered_registry_collectors,
)

__all__ = [
    'CollectorCallable',
    'InventoryProgressCallback',
    'ProgressCollectorCallable',
    'RegistryInventoryCollector',
    'get_registry_collector',
    'register_registry_collector',
    'registered_registry_collectors',
]
