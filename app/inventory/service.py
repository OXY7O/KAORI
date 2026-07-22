from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.extensions import db
from app.models import (
    Cluster,
    ClusterInventory,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)
from app.inventory.formatting import (
    convert_ki_to_gib,
    convert_storage_to_gib,
    format_byte_count,
    format_gib,
    format_kubernetes_size,
    format_quota_value,
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

INVENTORY_FRESHNESS_HOURS = 24

_WORKLOAD_UPDATE_STRATEGIES = {
    'rollingupdate': ('Rolling Update', 'rolling_update'),
    'recreate': ('Recreate', 'recreate'),
    'ondelete': ('On Delete', 'on_delete'),
}


def _normalize_datetime(
    value: datetime | None,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        UTC,
    )


def _is_stale_inventory(
    value: datetime | None,
) -> bool:
    collected_at = _normalize_datetime(
        value,
    )

    if collected_at is None:
        return False

    age = (
        datetime.now(
            UTC,
        )
        - collected_at
    )

    return age.total_seconds() > INVENTORY_FRESHNESS_HOURS * 3600


def _build_inventory_risk_hints(
    *,
    connected: bool,
    synced_at: datetime | None,
    node_count: int,
    workload_count: int,
    pod_count: int,
    storage_count: int,
) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []

    if not connected:
        hints.append(
            {
                'label': 'Connection risk',
                'tone': 'red',
                'icon': 'unlink',
            }
        )

    if synced_at is None:
        hints.append(
            {
                'label': 'Never synced',
                'tone': 'amber',
                'icon': 'triangle-alert',
            }
        )
    elif _is_stale_inventory(
        synced_at,
    ):
        hints.append(
            {
                'label': 'Stale sync',
                'tone': 'amber',
                'icon': 'clock-alert',
            }
        )
    else:
        hints.append(
            {
                'label': 'Fresh sync',
                'tone': 'green',
                'icon': 'check-circle-2',
            }
        )

    if pod_count >= 100 or workload_count >= 50:
        hints.append(
            {
                'label': 'High density',
                'tone': 'blue',
                'icon': 'activity',
            }
        )

    if node_count > 0 and storage_count == 0:
        hints.append(
            {
                'label': 'No storage data',
                'tone': 'slate',
                'icon': 'hard-drive',
            }
        )

    return hints[:3]


def get_cluster_by_id(
    cluster_id: str,
) -> Cluster | None:
    return db.session.get(
        Cluster,
        cluster_id,
    )


def get_inventory_clusters() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(), Cluster.id.asc(),
    ).all()


NODE_ROLE_DESCRIPTIONS = {
    'control-plane': (
        'Runs Kubernetes control-plane components that coordinate cluster state, '
        'scheduling, and API operations. Application workloads are usually kept off this node.'
    ),
    'master': (
        'Runs Kubernetes control-plane components that coordinate cluster state, '
        'scheduling, and API operations. Application workloads are usually kept off this node.'
    ),
    'worker': (
        'Runs application Pods and provides compute, memory, networking, and storage capacity for Kubernetes workloads.'
    ),
    'data-plane': ('Provides runtime capacity for application workloads and data-plane traffic.'),
}

WORKLOAD_TYPE_DESCRIPTIONS = {
    'Deployment': ('Maintains a desired number of interchangeable Pods and supports controlled rolling updates.'),
    'StatefulSet': (
        'Runs stateful Pods with stable identities, ordered rollout behavior, and persistent storage mappings.'
    ),
    'DaemonSet': (
        'Ensures a Pod runs on every matching node, commonly for agents, networking, logging, or monitoring.'
    ),
    'Job': ('Runs one-time or finite work until the required number of Pods completes successfully.'),
    'CronJob': ('Creates Jobs on a recurring schedule for periodic operational or application tasks.'),
}

SERVICE_TYPE_DESCRIPTIONS = {
    'ClusterIP': ('Exposes selected Pods on an internal virtual IP that is reachable only inside the cluster.'),
    'NodePort': ('Exposes the Service on a fixed port on every node and forwards traffic to selected Pods.'),
    'LoadBalancer': ('Requests an external load balancer and forwards external traffic to selected Pods.'),
    'ExternalName': ('Maps the Service DNS name to an external DNS hostname without selecting cluster Pods.'),
    'Headless': ('Uses no virtual ClusterIP and returns Pod endpoints directly through Kubernetes DNS.'),
}


def get_inventory_cluster_summary() -> tuple[list[Cluster], dict[str, dict[str, Any]]]:
    clusters = Cluster.query.order_by(
        Cluster.created_at.asc(), Cluster.id.asc(),
    ).all()

    cluster_ids = [cluster.id for cluster in clusters]

    inventories = {}

    if cluster_ids:
        inventories = {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(
                ClusterInventory.cluster_id.in_(
                    cluster_ids,
                )
            ).all()
        }

    namespace_counts = {}

    if cluster_ids:
        namespace_counts = {
            cluster_id: count
            for cluster_id, count in (
                db.session.query(
                    NamespaceInventory.cluster_id,
                    func.count(
                        NamespaceInventory.id,
                    ),
                )
                .filter(
                    NamespaceInventory.cluster_id.in_(
                        cluster_ids,
                    )
                )
                .group_by(
                    NamespaceInventory.cluster_id,
                )
                .all()
            )
        }

    inventory_summary: dict[str, dict[str, Any]] = {}

    for cluster in clusters:
        inventory = inventories.get(
            cluster.id,
        )

        inventory_summary[cluster.id] = {
            'version': inventory.kubernetes_version if inventory else '-',
            'namespaces': namespace_counts.get(
                cluster.id,
                0,
            ),
            'synced_at': inventory.collected_at if inventory else None,
        }

    return clusters, inventory_summary


def get_inventory_overview() -> dict[str, Any]:
    clusters, inventory_summary = get_inventory_cluster_summary()

    cluster_rows = []

    for cluster in clusters:
        summary = inventory_summary.get(
            cluster.id,
            {},
        )
        synced_at = summary.get(
            'synced_at',
        )
        connected = cluster.status == 'connected'
        node_count = NodeInventory.query.filter_by(
            cluster_id=cluster.id,
        ).count()
        workload_count = WorkloadInventory.query.filter_by(
            cluster_id=cluster.id,
        ).count()
        pod_count = PodInventory.query.filter_by(
            cluster_id=cluster.id,
        ).count()
        service_count = ServiceInventory.query.filter_by(
            cluster_id=cluster.id,
        ).count()
        ingress_count = IngressInventory.query.filter_by(
            cluster_id=cluster.id,
        ).count()
        storage_count = StorageInventory.query.filter_by(
            cluster_id=cluster.id,
        ).count()

        if synced_at is None:
            sync_status = 'never_synced'
            sync_status_label = 'Never synced'
            sync_status_tone = 'amber'
        elif _is_stale_inventory(
            synced_at,
        ):
            sync_status = 'stale'
            sync_status_label = 'Stale'
            sync_status_tone = 'amber'
        else:
            sync_status = 'fresh'
            sync_status_label = 'Fresh'
            sync_status_tone = 'green'

        cluster_rows.append(
            {
                'id': cluster.id,
                'name': cluster.name,
                'environment': cluster.environment,
                'server': cluster.kubernetes_connection.server,
                'status': cluster.status,
                'node_count': node_count,
                'last_check': cluster.last_check,
                'created_at': cluster.created_at,
                'updated_at': cluster.updated_at,
                'kube_verify_ssl': cluster.kubernetes_connection.verify_ssl,
                'kube_allow_weak_tls': cluster.kubernetes_connection.allow_weak_tls,
                'workload_count': workload_count,
                'pod_count': pod_count,
                'service_count': service_count,
                'ingress_count': ingress_count,
                'storage_count': storage_count,
                'sync_status': sync_status,
                'sync_status_label': sync_status_label,
                'sync_status_tone': sync_status_tone,
                'risk_hints': _build_inventory_risk_hints(
                    connected=connected,
                    synced_at=synced_at,
                    node_count=node_count,
                    workload_count=workload_count,
                    pod_count=pod_count,
                    storage_count=storage_count,
                ),
            }
        )

    health = get_inventory_health()
    activities = get_recent_inventory_activity()

    return {
        'total_clusters': (
            db.session.query(
                func.count(
                    Cluster.id,
                )
            ).scalar()
            or 0
        ),
        'total_nodes': (
            db.session.query(
                func.count(
                    NodeInventory.id,
                )
            ).scalar()
            or 0
        ),
        'total_namespaces': (
            db.session.query(
                func.count(
                    NamespaceInventory.id,
                )
            ).scalar()
            or 0
        ),
        'total_workloads': (
            db.session.query(
                func.count(
                    WorkloadInventory.id,
                )
            ).scalar()
            or 0
        ),
        'total_pods': (
            db.session.query(
                func.count(
                    PodInventory.id,
                )
            ).scalar()
            or 0
        ),
        'total_services': (
            db.session.query(
                func.count(
                    ServiceInventory.id,
                )
            ).scalar()
            or 0
        ),
        'total_ingresses': (
            db.session.query(
                func.count(
                    IngressInventory.id,
                )
            ).scalar()
            or 0
        ),
        'total_storage': (
            db.session.query(
                func.count(
                    StorageInventory.id,
                )
            ).scalar()
            or 0
        ),
        'clusters': cluster_rows,
        'inventory_summary': inventory_summary,
        'health': health,
        'activities': activities,
    }


def get_inventory_health():
    clusters = Cluster.query.all()

    total_clusters = len(
        clusters,
    )
    healthy_clusters = 0
    never_synced = 0
    stale_synced = 0
    fresh_synced = 0
    last_sync = None
    connected_clusters = 0

    for cluster in clusters:
        if cluster.status == 'connected':
            connected_clusters += 1

        inventory = ClusterInventory.query.filter_by(cluster_id=cluster.id).first()

        if inventory is None:
            never_synced += 1
            continue

        if cluster.status == 'connected':
            healthy_clusters += 1

        collected_at = _normalize_datetime(
            inventory.collected_at,
        )

        if _is_stale_inventory(
            collected_at,
        ):
            stale_synced += 1
        else:
            fresh_synced += 1

        if collected_at and (last_sync is None or collected_at > last_sync):
            last_sync = collected_at

    synced_clusters = total_clusters - never_synced
    disconnected_clusters = total_clusters - connected_clusters
    coverage_score = (
        round(
            (synced_clusters / total_clusters) * 100,
        )
        if total_clusters
        else 0
    )
    connection_score = (
        round(
            (connected_clusters / total_clusters) * 100,
        )
        if total_clusters
        else 0
    )
    freshness_score = (
        round(
            (fresh_synced / total_clusters) * 100,
        )
        if total_clusters
        else 0
    )

    return {
        'connected_clusters': connected_clusters,
        'healthy_clusters': healthy_clusters,
        'never_synced': never_synced,
        'stale_synced': stale_synced,
        'fresh_synced': fresh_synced,
        'synced_clusters': synced_clusters,
        'disconnected_clusters': disconnected_clusters,
        'coverage_score': coverage_score,
        'connection_score': connection_score,
        'freshness_score': freshness_score,
        'freshness_window_hours': INVENTORY_FRESHNESS_HOURS,
        'last_sync': last_sync,
    }


def get_recent_inventory_activity():
    inventories = (
        ClusterInventory.query.order_by(
            ClusterInventory.collected_at.desc(),
        )
        .limit(
            5,
        )
        .all()
    )

    activities = []

    for inventory in inventories:
        cluster = db.session.get(
            Cluster,
            inventory.cluster_id,
        )

        activities.append(
            {
                'cluster': (cluster.name if cluster else 'Unknown'),
                'collected_at': inventory.collected_at,
            }
        )

    return activities






































STORAGE_TYPE_DESCRIPTIONS = {
    'StorageClass': 'Defines dynamic volume provisioning behavior and lifecycle defaults for PersistentVolumes.',
    'PersistentVolume': 'Represents cluster-scoped storage capacity that can be bound to a PersistentVolumeClaim.',
    'PersistentVolumeClaim': 'Represents a namespace-scoped request for storage consumed by one or more Pods.',
}

from app.inventory.formatting import (
    convert_ki_to_gib, convert_storage_to_gib, format_byte_count, format_gib,
    format_kubernetes_size, format_quota_value,
)

# Public Inventory read API. Resource implementation is split by domain while
# existing imports from app.inventory.service remain stable.
from app.inventory.resources.common import format_age
from app.inventory.resources.nodes import (
    get_node_detail, get_node_filter_roles, get_node_filter_statuses, get_node_inventory,
)
from app.inventory.resources.namespaces import (
    get_namespace_detail, get_namespace_filter_statuses, get_namespace_inventory,
)
from app.inventory.resources.configuration import (
    get_configuration_detail, get_configuration_filter_namespaces,
    get_configuration_inventory_view,
)
from app.inventory.resources.workloads import (
    get_workload_detail, get_workload_filter_namespaces, get_workload_filter_statuses,
    get_workload_filter_types, get_workload_inventory,
)
from app.inventory.resources.pods import (
    get_pod_detail, get_pod_filter_namespaces, get_pod_filter_nodes,
    get_pod_filter_owner_types, get_pod_filter_statuses, get_pod_inventory,
)
from app.inventory.resources.services import (
    get_service_detail, get_service_filter_types, get_service_inventory,
)
from app.inventory.resources.ingresses import (
    get_ingress_detail, get_ingress_filter_classes, get_ingress_inventory,
)
from app.inventory.resources.storage import (
    get_storage_detail, get_storage_filter_statuses, get_storage_filter_types,
    get_storage_inventory_view,
)
