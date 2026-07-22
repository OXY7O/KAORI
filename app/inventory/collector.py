"""Stable public facade for Kubernetes inventory collectors.

Resource implementations live in ``app.inventory.collectors``. Existing
callers continue importing from this module so collector modularization does
not leak into persistence or synchronization boundaries.
"""

from app.inventory.collectors import (
    get_cluster_version,
    get_configuration_inventory,
    get_ingresses,
    get_nodes,
    get_pods,
    get_resource_quotas,
    get_services,
    get_storage_inventory,
    get_workloads,
)

__all__ = (
    'get_cluster_version',
    'get_configuration_inventory',
    'get_ingresses',
    'get_nodes',
    'get_pods',
    'get_resource_quotas',
    'get_services',
    'get_storage_inventory',
    'get_workloads',
)
