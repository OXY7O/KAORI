from app.inventory.collectors.configuration import (
    get_configuration_inventory,
    get_resource_quotas,
)
from app.inventory.collectors.ingresses import get_ingresses
from app.inventory.collectors.pods import get_pods
from app.inventory.collectors.runtime import get_cluster_version, get_nodes
from app.inventory.collectors.services import get_services
from app.inventory.collectors.storage import get_storage_inventory
from app.inventory.collectors.workloads import get_workloads

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
