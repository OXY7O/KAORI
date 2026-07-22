"""Stable public facade for Kubernetes Inventory domain services."""

from app.inventory.formatting import (
    convert_ki_to_gib,
    convert_storage_to_gib,
    format_byte_count,
    format_gib,
    format_kubernetes_size,
    format_quota_value,
)
from app.inventory.overview import (
    get_cluster_by_id,
    get_inventory_cluster_summary,
    get_inventory_clusters,
    get_inventory_health,
    get_inventory_overview,
    get_recent_inventory_activity,
)
from app.inventory.persistence import (
    get_node_ready_status,
    get_node_role,
    save_cluster_info,
    save_configuration_inventory,
    save_ingresses,
    save_namespaces,
    save_nodes,
    save_pods,
    save_resource_quotas,
    save_services,
    save_storage_inventory,
    save_workloads,
)
from app.inventory.resources.common import format_age
from app.inventory.resources.configuration import (
    get_configuration_detail,
    get_configuration_filter_namespaces,
    get_configuration_inventory_view,
)
from app.inventory.resources.ingresses import (
    get_ingress_detail,
    get_ingress_filter_classes,
    get_ingress_inventory,
)
from app.inventory.resources.namespaces import (
    get_namespace_detail,
    get_namespace_filter_statuses,
    get_namespace_inventory,
)
from app.inventory.resources.nodes import (
    get_node_detail,
    get_node_filter_roles,
    get_node_filter_statuses,
    get_node_inventory,
)
from app.inventory.resources.pods import (
    get_pod_detail,
    get_pod_filter_namespaces,
    get_pod_filter_nodes,
    get_pod_filter_owner_types,
    get_pod_filter_statuses,
    get_pod_inventory,
)
from app.inventory.resources.services import (
    get_service_detail,
    get_service_filter_types,
    get_service_inventory,
)
from app.inventory.resources.storage import (
    get_storage_detail,
    get_storage_filter_statuses,
    get_storage_filter_types,
    get_storage_inventory_view,
)
from app.inventory.resources.workloads import (
    get_workload_detail,
    get_workload_filter_namespaces,
    get_workload_filter_statuses,
    get_workload_filter_types,
    get_workload_inventory,
)
from app.inventory.synchronization import sync_inventory

__all__ = (
    'convert_ki_to_gib',
    'convert_storage_to_gib',
    'format_age',
    'format_byte_count',
    'format_gib',
    'format_kubernetes_size',
    'format_quota_value',
    'get_cluster_by_id',
    'get_configuration_detail',
    'get_configuration_filter_namespaces',
    'get_configuration_inventory_view',
    'get_ingress_detail',
    'get_ingress_filter_classes',
    'get_ingress_inventory',
    'get_inventory_cluster_summary',
    'get_inventory_clusters',
    'get_inventory_health',
    'get_inventory_overview',
    'get_namespace_detail',
    'get_namespace_filter_statuses',
    'get_namespace_inventory',
    'get_node_detail',
    'get_node_filter_roles',
    'get_node_filter_statuses',
    'get_node_inventory',
    'get_node_ready_status',
    'get_node_role',
    'get_pod_detail',
    'get_pod_filter_namespaces',
    'get_pod_filter_nodes',
    'get_pod_filter_owner_types',
    'get_pod_filter_statuses',
    'get_pod_inventory',
    'get_recent_inventory_activity',
    'get_service_detail',
    'get_service_filter_types',
    'get_service_inventory',
    'get_storage_detail',
    'get_storage_filter_statuses',
    'get_storage_filter_types',
    'get_storage_inventory_view',
    'get_workload_detail',
    'get_workload_filter_namespaces',
    'get_workload_filter_statuses',
    'get_workload_filter_types',
    'get_workload_inventory',
    'save_cluster_info',
    'save_configuration_inventory',
    'save_ingresses',
    'save_namespaces',
    'save_nodes',
    'save_pods',
    'save_resource_quotas',
    'save_services',
    'save_storage_inventory',
    'save_workloads',
    'sync_inventory',
)
