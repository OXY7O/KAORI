from datetime import UTC, datetime
from typing import Any, cast

from kubernetes.client import AppsV1Api, BatchV1Api, CoreV1Api, NetworkingV1Api, StorageV1Api, V1NamespaceList, V1Node
from sqlalchemy import func

from app.extensions import db
from app.inventory.collector import (
    get_cluster_version,
    get_ingresses,
    get_nodes,
    get_pods,
    get_services,
    get_storage_inventory,
    get_workloads,
)
from app.kubernetes.client import KubernetesClient
from app.kubernetes.tls import legacy_tls_context
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

INVENTORY_FRESHNESS_HOURS = 24


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
        Cluster.name,
    ).all()


def get_node_role(
    node: V1Node,
) -> str:
    metadata = node.metadata

    if metadata is None:
        return 'unknown'

    labels = metadata.labels or {}

    for key in labels:
        if key.startswith('node-role.kubernetes.io/'):
            return key.split('/')[-1]

    return 'worker'


def _extract_node_addresses(
    node: V1Node,
) -> dict[str, str | None]:
    status = node.status

    addresses = status.addresses if status and status.addresses else []

    result: dict[str, str | None] = {
        'internal_ip': None,
        'external_ip': None,
        'hostname_address': None,
    }

    for address in addresses:
        address_type = getattr(
            address,
            'type',
            None,
        )
        address_value = getattr(
            address,
            'address',
            None,
        )

        if not address_value:
            continue

        if address_type == 'InternalIP' and result['internal_ip'] is None:
            result['internal_ip'] = address_value
        elif address_type == 'ExternalIP' and result['external_ip'] is None:
            result['external_ip'] = address_value
        elif address_type == 'Hostname' and result['hostname_address'] is None:
            result['hostname_address'] = address_value

    return result


def get_node_ready_status(
    node: V1Node,
) -> str:
    status = node.status

    if status is None:
        return 'Unknown'

    for condition in status.conditions or []:
        if condition.type != 'Ready':
            continue

        if condition.status == 'True':
            return 'Ready'

        if condition.status == 'False':
            return 'NotReady'

        return 'Unknown'

    return 'Unknown'


def save_cluster_info(
    cluster: Cluster,
    api: CoreV1Api,
) -> None:
    ClusterInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    cluster_inventory = ClusterInventory()

    cluster_inventory.cluster_id = cluster.id
    cluster_inventory.kubernetes_version = get_cluster_version(
        api,
    )

    db.session.add(
        cluster_inventory,
    )


def save_nodes(
    cluster: Cluster,
    api: CoreV1Api,
) -> None:
    NodeInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    nodes = get_nodes(api)

    for node in nodes:
        metadata = node.metadata
        status = node.status

        if metadata is None:
            continue

        if status is None:
            continue

        if status.node_info is None:
            continue

        capacity = status.capacity or {}

        allocatable = status.allocatable or {}

        cpu_value = capacity.get('cpu')

        try:
            cpu = int(cpu_value) if cpu_value is not None else None
        except (
            ValueError,
            TypeError,
        ):
            cpu = None

        ready_status = get_node_ready_status(
            node,
        )

        node_inventory = NodeInventory()

        node_inventory.cluster_id = cluster.id
        node_inventory.node_name = metadata.name
        node_inventory.role = get_node_role(node)
        node_inventory.status = ready_status

        node_addresses = _extract_node_addresses(
            node,
        )
        node_inventory.internal_ip = node_addresses.get(
            'internal_ip',
        )
        node_inventory.external_ip = node_addresses.get(
            'external_ip',
        )
        node_inventory.hostname_address = node_addresses.get(
            'hostname_address',
        )

        node_inventory.os_image = status.node_info.os_image

        node_inventory.kernel_version = status.node_info.kernel_version

        node_inventory.container_runtime = status.node_info.container_runtime_version

        node_inventory.cpu = cpu
        node_inventory.memory = capacity.get('memory')
        node_inventory.ephemeral_storage = capacity.get(
            'ephemeral-storage',
        )
        node_inventory.ephemeral_storage_allocatable = allocatable.get(
            'ephemeral-storage',
        )

        db.session.add(node_inventory)


def save_namespaces(
    cluster: Cluster,
    api: CoreV1Api,
) -> None:
    NamespaceInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    namespace_list = cast(
        V1NamespaceList,
        api.list_namespace(),
    )

    namespaces = namespace_list.items or []

    for namespace in namespaces:
        metadata = namespace.metadata

        if metadata is None:
            continue

        namespace_inventory = NamespaceInventory()

        namespace_inventory.cluster_id = cluster.id
        namespace_inventory.namespace = metadata.name

        namespace_inventory.status = namespace.status.phase if namespace.status else None

        db.session.add(namespace_inventory)


def save_workloads(
    cluster: Cluster,
    apps_api: AppsV1Api,
    batch_api: BatchV1Api | None = None,
) -> None:
    WorkloadInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    workloads = get_workloads(
        apps_api,
        batch_api,
    )

    for workload in workloads:
        workload_inventory = WorkloadInventory()

        workload_inventory.cluster_id = cluster.id
        workload_inventory.namespace = workload['namespace']
        workload_inventory.name = workload['name']

        workload_inventory.workload_type = workload['workload_type']

        workload_inventory.ready = workload['ready']
        workload_inventory.status = workload['status']

        workload_inventory.created_at = workload['created_at']

        db.session.add(workload_inventory)


def save_pods(
    cluster: Cluster,
    api: CoreV1Api,
) -> None:
    PodInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    pods = get_pods(
        api,
    )

    for pod in pods:
        pod_inventory = PodInventory()

        pod_inventory.cluster_id = cluster.id
        pod_inventory.namespace = pod['namespace']
        pod_inventory.pod_name = pod['pod_name']

        pod_inventory.node_name = pod['node_name']
        pod_inventory.phase = pod['phase']
        pod_inventory.pod_ip = pod['pod_ip']

        pod_inventory.ready = pod['ready']

        pod_inventory.restart_count = pod['restart_count']

        pod_inventory.container_images = pod.get(
            'container_images',
            [],
        )

        pod_inventory.init_container_images = pod.get(
            'init_container_images',
            [],
        )

        pod_inventory.image_count = pod.get(
            'image_count',
            0,
        )

        pod_inventory.created_at = pod['created_at']

        db.session.add(pod_inventory)


def save_services(
    cluster: Cluster,
    api: CoreV1Api,
) -> None:
    ServiceInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    services = get_services(
        api,
    )

    for service in services:
        service_inventory = ServiceInventory()

        service_inventory.cluster_id = cluster.id
        service_inventory.namespace = service['namespace']

        service_inventory.service_name = service['service_name']

        service_inventory.service_type = service['service_type']

        service_inventory.cluster_ip = service['cluster_ip']

        service_inventory.external_ip = service['external_ip']

        service_inventory.ports = service['ports']

        service_inventory.created_at = service['created_at']

        db.session.add(service_inventory)


def save_ingresses(
    cluster: Cluster,
    api: NetworkingV1Api,
) -> None:
    IngressInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    ingresses = get_ingresses(
        api,
    )

    for ingress in ingresses:
        ingress_inventory = IngressInventory()

        ingress_inventory.cluster_id = cluster.id

        ingress_inventory.namespace = ingress['namespace']

        ingress_inventory.ingress_name = ingress['ingress_name']

        ingress_inventory.ingress_class = ingress['ingress_class']

        ingress_inventory.host = ingress['host']

        ingress_inventory.address = ingress['address']

        ingress_inventory.tls_enabled = ingress['tls_enabled']

        ingress_inventory.backend_paths = ingress.get(
            'backend_paths',
            [],
        )

        ingress_inventory.created_at = ingress['created_at']

        db.session.add(ingress_inventory)


def save_storage_inventory(
    cluster: Cluster,
    core_api: CoreV1Api,
    storage_api: StorageV1Api,
) -> None:
    StorageInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    items = get_storage_inventory(
        core_api,
        storage_api,
    )

    for item in items:
        storage_inventory = StorageInventory()

        storage_inventory.cluster_id = cluster.id

        storage_inventory.namespace = item['namespace']

        storage_inventory.name = item['name']

        storage_inventory.storage_type = item['storage_type']

        storage_inventory.storage_class = item['storage_class']

        storage_inventory.capacity = item['capacity']

        storage_inventory.status = item['status']

        storage_inventory.created_at = item['created_at']

        db.session.add(storage_inventory)


def sync_inventory(
    cluster: Cluster,
) -> None:
    verify_ssl = bool(
        getattr(
            cluster,
            'kube_verify_ssl',
            True,
        )
    )

    allow_weak_tls = bool(
        getattr(
            cluster,
            'kube_allow_weak_tls',
            False,
        )
    )

    try:
        with legacy_tls_context(
            enabled=allow_weak_tls,
        ):
            client = KubernetesClient(
                kubeconfig_content=cluster.kubeconfig,
                verify_ssl=verify_ssl,
            )

            core_api = client.core_api()

            apps_api = client.apps_api()

            batch_api = BatchV1Api(
                core_api.api_client,
            )

            networking_api = client.networking_api()

            storage_api = client.storage_api()

            save_cluster_info(
                cluster,
                core_api,
            )

            save_nodes(
                cluster,
                core_api,
            )

            save_namespaces(
                cluster,
                core_api,
            )

            save_workloads(
                cluster,
                apps_api,
                batch_api,
            )

            save_pods(
                cluster,
                core_api,
            )

            save_services(
                cluster,
                core_api,
            )

            save_ingresses(
                cluster,
                networking_api,
            )

            save_storage_inventory(
                cluster,
                core_api,
                storage_api,
            )

        db.session.commit()

    except Exception as exc:
        print('=== INVENTORY SYNC EXCEPTION ===')
        print(type(exc).__name__)
        print(str(exc))

        db.session.rollback()
        raise


def convert_ki_to_gib(
    value: str | None,
) -> float:
    if not value:
        return 0

    if not value.endswith('Ki'):
        return 0

    try:
        kib = int(
            value.replace(
                'Ki',
                '',
            )
        )

        return round(
            kib / 1024 / 1024,
            1,
        )

    except (
        ValueError,
        TypeError,
    ):
        return 0


def convert_storage_to_gib(
    value: str | None,
) -> float:
    if not value:
        return 0

    units = {
        'Ki': 1024,
        'Mi': 1024**2,
        'Gi': 1024**3,
        'Ti': 1024**4,
        'K': 1000,
        'M': 1000**2,
        'G': 1000**3,
        'T': 1000**4,
    }

    try:
        for suffix, multiplier in units.items():
            if value.endswith(
                suffix,
            ):
                number = float(
                    value.removesuffix(
                        suffix,
                    )
                )

                return round(
                    number * multiplier / 1024**3,
                    1,
                )

        return round(
            float(value) / 1024**3,
            1,
        )

    except (
        ValueError,
        TypeError,
    ):
        return 0


def format_gib(
    value: float,
) -> str:
    if value <= 0:
        return '-'

    return f'{value} GiB'


def get_inventory_cluster_summary() -> tuple[list[Cluster], dict[str, dict[str, Any]]]:
    clusters = Cluster.query.order_by(
        Cluster.name,
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
                'server': cluster.server,
                'status': cluster.status,
                'node_count': node_count,
                'last_check': cluster.last_check,
                'created_at': cluster.created_at,
                'updated_at': cluster.updated_at,
                'kube_verify_ssl': cluster.kube_verify_ssl,
                'kube_allow_weak_tls': cluster.kube_allow_weak_tls,
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

    last_sync_human = '-'
    last_sync = (
        health.get(
            'last_sync',
        )
        if health
        else None
    )

    if last_sync:
        last_sync_human = last_sync.strftime(
            '%d %b %Y %H:%M',
        )

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
        'last_sync_human': last_sync_human,
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

    last_sync_display = '-'

    if last_sync:
        last_sync_display = last_sync.strftime('%d %b %Y %H:%M')

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
        'last_sync_display': last_sync_display,
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


def get_node_filter_roles(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        NodeInventory.role,
    )

    if cluster_id:
        query = query.filter(
            NodeInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            NodeInventory.role,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_node_filter_statuses(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        NodeInventory.status,
    )

    if cluster_id:
        query = query.filter(
            NodeInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            NodeInventory.status,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_node_inventory(
    cluster_id=None,
    role=None,
    status=None,
    search=None,
):
    query = db.session.query(
        NodeInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == NodeInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(NodeInventory.cluster_id == cluster_id)

    if role:
        query = query.filter(NodeInventory.role == role)

    if status:
        query = query.filter(NodeInventory.status == status)

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                NodeInventory.node_name.ilike(
                    search_pattern,
                ),
                NodeInventory.internal_ip.ilike(
                    search_pattern,
                ),
                NodeInventory.external_ip.ilike(
                    search_pattern,
                ),
                NodeInventory.hostname_address.ilike(
                    search_pattern,
                ),
            )
        )

    nodes = query.order_by(
        Cluster.name,
        NodeInventory.node_name,
    ).all()

    nodes_data = []

    for node, cluster_name in nodes:
        runtime = node.container_runtime or ''

        runtime_display = runtime.split('://')[0] if '://' in runtime else runtime

        ephemeral_storage_gib = convert_storage_to_gib(
            node.ephemeral_storage,
        )

        ephemeral_storage_allocatable_gib = convert_storage_to_gib(
            node.ephemeral_storage_allocatable,
        )

        node_status = node.status or 'Unknown'

        nodes_data.append(
            {
                'id': node.id,
                'cluster_name': cluster_name,
                'node_name': node.node_name,
                'role': node.role,
                'status': node_status,
                'internal_ip': node.internal_ip,
                'external_ip': node.external_ip,
                'hostname_address': node.hostname_address,
                'has_extra_addresses': bool(
                    node.external_ip or node.hostname_address,
                ),
                'cpu': node.cpu,
                'memory_display': format_gib(
                    convert_ki_to_gib(
                        node.memory,
                    )
                ),
                'ephemeral_storage_display': format_gib(
                    ephemeral_storage_gib,
                ),
                'ephemeral_storage_allocatable_display': format_gib(
                    ephemeral_storage_allocatable_gib,
                ),
                'os_image': node.os_image,
                'runtime_display': runtime_display,
            }
        )

    total_cpu = sum(node.cpu or 0 for node, _ in nodes)

    total_memory = round(
        sum(convert_ki_to_gib(node.memory) for node, _ in nodes),
        1,
    )

    total_ephemeral_storage = round(
        sum(
            convert_storage_to_gib(
                node.ephemeral_storage,
            )
            for node, _ in nodes
        ),
        1,
    )

    ready_nodes = sum(1 for node, _ in nodes if node.status == 'Ready')

    not_ready_nodes = sum(1 for node, _ in nodes if node.status == 'NotReady')

    return {
        'total_nodes': len(nodes),
        'ready_nodes': ready_nodes,
        'not_ready_nodes': not_ready_nodes,
        'total_cpu': total_cpu,
        'total_memory': total_memory,
        'total_ephemeral_storage': total_ephemeral_storage,
        'node_roles': get_node_filter_roles(
            cluster_id=cluster_id,
        ),
        'node_statuses': get_node_filter_statuses(
            cluster_id=cluster_id,
        ),
        'nodes': nodes_data,
    }


def get_namespace_filter_statuses(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        NamespaceInventory.status,
    )

    if cluster_id:
        query = query.filter(
            NamespaceInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            NamespaceInventory.status,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_namespace_inventory(
    cluster_id=None,
    status=None,
    search=None,
):
    query = db.session.query(
        NamespaceInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == NamespaceInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(NamespaceInventory.cluster_id == cluster_id)

    if status:
        query = query.filter(NamespaceInventory.status == status)

    if search:
        query = query.filter(NamespaceInventory.namespace.ilike(f'%{search}%'))

    namespaces = query.order_by(
        Cluster.name,
        NamespaceInventory.namespace,
    ).all()

    cluster_count = len({cluster_name for _, cluster_name in namespaces})

    status_counts = {}

    for namespace, _ in namespaces:
        status = namespace.status or 'Unknown'

        status_counts[status] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    return {
        'total_namespaces': len(
            namespaces,
        ),
        'total_clusters': cluster_count,
        'active_namespaces': (
            status_counts.get(
                'Active',
                0,
            )
        ),
        'status_counts': status_counts,
        'namespace_statuses': get_namespace_filter_statuses(
            cluster_id=cluster_id,
        ),
        'namespaces': namespaces,
    }


def get_namespace_detail(
    namespace_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            NamespaceInventory,
            Cluster.name.label(
                'cluster_name',
            ),
        )
        .join(
            Cluster,
            Cluster.id == NamespaceInventory.cluster_id,
        )
        .filter(
            NamespaceInventory.id == namespace_id,
        )
        .first()
    )

    if result is None:
        return None

    namespace, cluster_name = result

    workload_counts = {
        row[0] or 'Unknown': row[1]
        for row in (
            db.session.query(
                WorkloadInventory.workload_type,
                func.count(WorkloadInventory.id),
            )
            .filter(
                WorkloadInventory.cluster_id == namespace.cluster_id,
                WorkloadInventory.namespace == namespace.namespace,
            )
            .group_by(
                WorkloadInventory.workload_type,
            )
            .all()
        )
    }

    object_counts = {
        'workloads': db.session.query(func.count(WorkloadInventory.id)).filter(
            WorkloadInventory.cluster_id == namespace.cluster_id,
            WorkloadInventory.namespace == namespace.namespace,
        ).scalar()
        or 0,
        'pods': db.session.query(func.count(PodInventory.id)).filter(
            PodInventory.cluster_id == namespace.cluster_id,
            PodInventory.namespace == namespace.namespace,
        ).scalar()
        or 0,
        'services': db.session.query(func.count(ServiceInventory.id)).filter(
            ServiceInventory.cluster_id == namespace.cluster_id,
            ServiceInventory.namespace == namespace.namespace,
        ).scalar()
        or 0,
        'ingresses': db.session.query(func.count(IngressInventory.id)).filter(
            IngressInventory.cluster_id == namespace.cluster_id,
            IngressInventory.namespace == namespace.namespace,
        ).scalar()
        or 0,
        'persistent_volume_claims': db.session.query(func.count(StorageInventory.id)).filter(
            StorageInventory.cluster_id == namespace.cluster_id,
            StorageInventory.namespace == namespace.namespace,
            StorageInventory.storage_type == 'PersistentVolumeClaim',
        ).scalar()
        or 0,
    }

    object_counts['tracked_total'] = sum(object_counts.values())

    return {
        'id': namespace.id,
        'cluster_name': cluster_name,
        'namespace': namespace.namespace,
        'status': namespace.status or 'Unknown',
        'collected_at': namespace.collected_at,
        'object_counts': object_counts,
        'workload_breakdown': {
            'deployments': workload_counts.get('Deployment', 0),
            'statefulsets': workload_counts.get('StatefulSet', 0),
            'daemonsets': workload_counts.get('DaemonSet', 0),
            'jobs': workload_counts.get('Job', 0),
            'cronjobs': workload_counts.get('CronJob', 0),
        },
    }


def format_age(
    created_at,
) -> str:
    if not created_at:
        return '-'

    delta = datetime.now(UTC) - created_at

    days = delta.days

    if days > 0:
        return f'{days}d'

    hours = delta.seconds // 3600

    return f'{hours}h'


def get_workload_filter_types(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.workload_type,
    )

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.workload_type,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_workload_filter_statuses(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.status,
    )

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.status,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_workload_inventory(
    cluster_id=None,
    workload_type=None,
    status=None,
    search=None,
):
    query = db.session.query(
        WorkloadInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == WorkloadInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(WorkloadInventory.cluster_id == cluster_id)

    if workload_type:
        query = query.filter(WorkloadInventory.workload_type == workload_type)

    if status:
        query = query.filter(WorkloadInventory.status == status)

    if search:
        query = query.filter(WorkloadInventory.name.ilike(f'%{search}%'))

    workloads = query.order_by(
        Cluster.name,
        WorkloadInventory.namespace,
        WorkloadInventory.name,
    ).all()

    type_counts = {}
    status_counts = {}

    deployments = 0
    statefulsets = 0
    daemonsets = 0
    jobs = 0
    cronjobs = 0

    workloads_data = []

    for workload, cluster_name in workloads:
        workload_type = workload.workload_type or 'Unknown'

        status_name = workload.status or 'Unknown'

        type_counts[workload_type] = (
            type_counts.get(
                workload_type,
                0,
            )
            + 1
        )

        status_counts[status_name] = (
            status_counts.get(
                status_name,
                0,
            )
            + 1
        )

        if workload_type == 'Deployment':
            deployments += 1

        elif workload_type == 'StatefulSet':
            statefulsets += 1

        elif workload_type == 'DaemonSet':
            daemonsets += 1

        elif workload_type == 'Job':
            jobs += 1

        elif workload_type == 'CronJob':
            cronjobs += 1

        workloads_data.append(
            {
                'id': workload.id,
                'cluster_name': cluster_name,
                'namespace': workload.namespace,
                'name': workload.name,
                'type': workload_type,
                'ready': workload.ready,
                'status': status_name,
                'age': format_age(
                    workload.created_at,
                ),
                'created_at': workload.created_at,
                'collected_at': workload.collected_at,
            }
        )

    return {
        'total_workloads': len(workloads),
        'deployments': deployments,
        'statefulsets': statefulsets,
        'daemonsets': daemonsets,
        'jobs': jobs,
        'cronjobs': cronjobs,
        'type_counts': type_counts,
        'status_counts': status_counts,
        'workload_types': get_workload_filter_types(
            cluster_id=cluster_id,
        ),
        'workload_statuses': get_workload_filter_statuses(
            cluster_id=cluster_id,
        ),
        'workloads': workloads_data,
    }


def get_workload_detail(
    workload_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            WorkloadInventory,
            Cluster.name.label(
                'cluster_name',
            ),
        )
        .join(
            Cluster,
            Cluster.id == WorkloadInventory.cluster_id,
        )
        .filter(
            WorkloadInventory.id == workload_id,
        )
        .first()
    )

    if result is None:
        return None

    workload, cluster_name = result

    return {
        'id': workload.id,
        'cluster_name': cluster_name,
        'namespace': workload.namespace,
        'name': workload.name,
        'type': workload.workload_type or 'Unknown',
        'ready': workload.ready or '-',
        'status': workload.status or 'Unknown',
        'age': format_age(workload.created_at),
        'created_at': workload.created_at,
        'collected_at': workload.collected_at,
    }


def get_pod_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.namespace,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.namespace,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_pod_filter_statuses(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.phase,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.phase,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_pod_inventory(
    cluster_id=None,
    namespace=None,
    status=None,
    search=None,
):
    query = db.session.query(
        PodInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == PodInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(PodInventory.cluster_id == cluster_id)

    if namespace:
        query = query.filter(PodInventory.namespace == namespace)

    if status:
        query = query.filter(PodInventory.phase == status)

    if search:
        query = query.filter(PodInventory.pod_name.ilike(f'%{search}%'))

    pods = query.order_by(
        Cluster.name,
        PodInventory.namespace,
        PodInventory.pod_name,
    ).all()

    status_counts = {}

    status_query = db.session.query(
        PodInventory.phase,
    ).distinct()

    if cluster_id:
        status_query = status_query.filter(PodInventory.cluster_id == cluster_id)

    for (phase,) in status_query.all():
        phase = phase or 'Unknown'

        status_counts[phase] = 0

    pod_data = []

    running = 0
    pending = 0
    failed = 0

    for pod, cluster_name in pods:
        phase = pod.phase or 'Unknown'

        if phase == 'Running':
            running += 1

        elif phase == 'Pending':
            pending += 1

        elif phase == 'Failed':
            failed += 1

        container_images = pod.container_images or []

        init_container_images = pod.init_container_images or []

        all_images = container_images + init_container_images

        image_count = pod.image_count or len(
            all_images,
        )

        image_preview = all_images[0] if all_images else '-'

        image_more_count = max(
            image_count - 1,
            0,
        )

        pod_data.append(
            {
                'id': pod.id,
                'cluster_name': cluster_name,
                'namespace': pod.namespace,
                'name': pod.pod_name,
                'node': pod.node_name,
                'ready': pod.ready,
                'restarts': pod.restart_count,
                'ip': pod.pod_ip,
                'status': phase,
                'container_images': container_images,
                'init_container_images': init_container_images,
                'all_images': all_images,
                'image_count': image_count,
                'image_preview': image_preview,
                'image_more_count': image_more_count,
                'age': format_age(
                    pod.created_at,
                ),
            }
        )

    return {
        'total_pods': len(pods),
        'running': running,
        'pending': pending,
        'failed': failed,
        'total_image_references': sum(
            pod.get(
                'image_count',
                0,
            )
            for pod in pod_data
        ),
        'unique_image_count': len(
            {
                image
                for pod in pod_data
                for image in pod.get(
                    'all_images',
                    [],
                )
            }
        ),
        'status_counts': status_counts,
        'pod_statuses': get_pod_filter_statuses(
            cluster_id=cluster_id,
        ),
        'namespaces': get_pod_filter_namespaces(cluster_id),
        'pods': pod_data,
    }


def get_pod_detail(
    pod_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            PodInventory,
            Cluster.name.label(
                'cluster_name',
            ),
        )
        .join(
            Cluster,
            Cluster.id == PodInventory.cluster_id,
        )
        .filter(
            PodInventory.id == pod_id,
        )
        .first()
    )

    if result is None:
        return None

    pod, cluster_name = result

    container_images = pod.container_images or []

    init_container_images = pod.init_container_images or []

    all_images = container_images + init_container_images

    return {
        'id': pod.id,
        'cluster_name': cluster_name,
        'namespace': pod.namespace,
        'name': pod.pod_name,
        'node': pod.node_name,
        'ready': pod.ready,
        'restarts': pod.restart_count,
        'ip': pod.pod_ip,
        'status': pod.phase or 'Unknown',
        'container_images': container_images,
        'init_container_images': init_container_images,
        'all_images': all_images,
        'image_count': pod.image_count
        or len(
            all_images,
        ),
        'age': format_age(
            pod.created_at,
        ),
        'created_at': pod.created_at,
        'collected_at': pod.collected_at,
    }


def get_service_filter_types(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        ServiceInventory.service_type,
    )

    if cluster_id:
        query = query.filter(
            ServiceInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            ServiceInventory.service_type,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_service_inventory(
    cluster_id=None,
    namespace=None,
    service_type=None,
    search=None,
):
    query = db.session.query(
        ServiceInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == ServiceInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)

    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)

    if service_type:
        query = query.filter(ServiceInventory.service_type == service_type)

    if search:
        query = query.filter(ServiceInventory.service_name.ilike(f'%{search}%'))

    services = query.order_by(
        Cluster.name,
        ServiceInventory.namespace,
        ServiceInventory.service_name,
    ).all()

    namespace_query = db.session.query(
        ServiceInventory.namespace,
    ).distinct()

    if cluster_id:
        namespace_query = namespace_query.filter(ServiceInventory.cluster_id == cluster_id)

    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    services_data = []

    cluster_ip_count = 0
    node_port_count = 0
    load_balancer_count = 0

    service_types = {
        'ClusterIP': 0,
        'NodePort': 0,
        'LoadBalancer': 0,
    }

    for service, cluster_name in services:
        service_type = service.service_type or 'Unknown'

        if service_type in service_types:
            service_types[service_type] += 1

        if service_type == 'ClusterIP':
            cluster_ip_count += 1

        elif service_type == 'NodePort':
            node_port_count += 1

        elif service_type == 'LoadBalancer':
            load_balancer_count += 1

        services_data.append(
            {
                'id': service.id,
                'cluster_name': cluster_name,
                'namespace': service.namespace,
                'service_name': service.service_name,
                'service_type': service_type,
                'cluster_ip': (service.cluster_ip or '-'),
                'external_ip': (service.external_ip or '-'),
                'ports': (service.ports or '-'),
                'age': format_age(
                    service.created_at,
                ),
                'created_at': service.created_at,
                'collected_at': service.collected_at,
            }
        )

    return {
        'total_services': len(services),
        'cluster_ip': cluster_ip_count,
        'node_port': node_port_count,
        'load_balancer': load_balancer_count,
        'namespaces': namespaces,
        'service_filter_types': get_service_filter_types(
            cluster_id=cluster_id,
        ),
        'service_types': service_types,
        'services': services_data,
    }


def get_service_detail(
    service_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            ServiceInventory,
            Cluster.name.label(
                'cluster_name',
            ),
        )
        .join(
            Cluster,
            Cluster.id == ServiceInventory.cluster_id,
        )
        .filter(
            ServiceInventory.id == service_id,
        )
        .first()
    )

    if result is None:
        return None

    service, cluster_name = result

    return {
        'id': service.id,
        'cluster_name': cluster_name,
        'namespace': service.namespace,
        'service_name': service.service_name,
        'service_type': service.service_type or 'Unknown',
        'cluster_ip': service.cluster_ip or '-',
        'external_ip': service.external_ip or '-',
        'ports': service.ports or '-',
        'age': format_age(service.created_at),
        'created_at': service.created_at,
        'collected_at': service.collected_at,
    }


def get_ingress_filter_classes(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        IngressInventory.ingress_class,
    )

    if cluster_id:
        query = query.filter(
            IngressInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            IngressInventory.ingress_class,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_ingress_inventory(
    cluster_id=None,
    namespace=None,
    ingress_class=None,
    search=None,
):
    query = db.session.query(
        IngressInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == IngressInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)

    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)

    if ingress_class:
        query = query.filter(IngressInventory.ingress_class == ingress_class)

    if search:
        query = query.filter(IngressInventory.ingress_name.ilike(f'%{search}%'))

    ingresses = query.order_by(
        Cluster.name,
        IngressInventory.namespace,
        IngressInventory.ingress_name,
    ).all()

    namespace_query = db.session.query(
        IngressInventory.namespace,
    ).distinct()

    if cluster_id:
        namespace_query = namespace_query.filter(IngressInventory.cluster_id == cluster_id)

    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    ingress_data = []

    tls_enabled = 0
    hosts = set()
    classes = set()

    for ingress, cluster_name in ingresses:
        if ingress.tls_enabled:
            tls_enabled += 1

        if ingress.host:
            hosts.add(
                ingress.host,
            )

        if ingress.ingress_class:
            classes.add(
                ingress.ingress_class,
            )

        ingress_data.append(
            {
                'id': ingress.id,
                'cluster_name': cluster_name,
                'namespace': ingress.namespace,
                'name': ingress.ingress_name,
                'class': ingress.ingress_class or '-',
                'ingress_class': ingress.ingress_class or '-',
                'host': ingress.host or '-',
                'address': ingress.address or '-',
                'tls': ingress.tls_enabled,
                'backend_count': len(
                    ingress.backend_paths or [],
                ),
                'age': format_age(
                    ingress.created_at,
                ),
            }
        )

    return {
        'total_ingresses': len(ingresses),
        'tls_enabled': tls_enabled,
        'total_hosts': len(hosts),
        'ingress_classes': len(classes),
        'classes': get_ingress_filter_classes(
            cluster_id=cluster_id,
        ),
        'namespaces': namespaces,
        'ingresses': ingress_data,
        'total_namespaces': len(namespaces),
    }


def get_ingress_detail(
    ingress_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            IngressInventory,
            Cluster.name.label(
                'cluster_name',
            ),
        )
        .join(
            Cluster,
            Cluster.id == IngressInventory.cluster_id,
        )
        .filter(
            IngressInventory.id == ingress_id,
        )
        .first()
    )

    if result is None:
        return None

    ingress, cluster_name = result

    backend_paths = ingress.backend_paths or []

    hosts = sorted(
        {
            item.get(
                'host',
                '-',
            )
            for item in backend_paths
            if item.get(
                'host',
                '-',
            )
            and item.get(
                'host',
                '-',
            )
            != '-'
        }
    )

    services = sorted(
        {
            item.get(
                'service_name',
                '-',
            )
            for item in backend_paths
            if item.get(
                'service_name',
                '-',
            )
            and item.get(
                'service_name',
                '-',
            )
            != '-'
        }
    )

    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': ingress.ingress_class or '-',
        'host': ingress.host or '-',
        'address': ingress.address or '-',
        'tls': ingress.tls_enabled,
        'backend_paths': backend_paths,
        'backend_count': len(
            backend_paths,
        ),
        'host_count': len(
            hosts,
        ),
        'service_count': len(
            services,
        ),
        'age': format_age(
            ingress.created_at,
        ),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
    }


def get_storage_filter_types(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        StorageInventory.storage_type,
    )

    if cluster_id:
        query = query.filter(
            StorageInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            StorageInventory.storage_type,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_storage_inventory_view(
    cluster_id=None,
    namespace=None,
    storage_type=None,
    search=None,
):
    query = db.session.query(
        StorageInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == StorageInventory.cluster_id,
    )

    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)

    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)

    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)

    if search:
        query = query.filter(StorageInventory.name.ilike(f'%{search}%'))

    items = query.order_by(
        Cluster.name,
        StorageInventory.storage_type,
        StorageInventory.name,
    ).all()

    namespace_query = db.session.query(
        StorageInventory.namespace,
    ).distinct()

    if cluster_id:
        namespace_query = namespace_query.filter(
            StorageInventory.cluster_id == cluster_id,
        )

    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    data = []

    storage_classes = 0
    persistent_volumes = 0
    persistent_volume_claims = 0

    storage_types = {
        'StorageClass': 0,
        'PersistentVolume': 0,
        'PersistentVolumeClaim': 0,
    }

    for item, cluster_name in items:
        if item.storage_type in storage_types:
            storage_types[item.storage_type] += 1

        if item.storage_type == 'StorageClass':
            storage_classes += 1

        elif item.storage_type == 'PersistentVolume':
            persistent_volumes += 1

        elif item.storage_type == 'PersistentVolumeClaim':
            persistent_volume_claims += 1

        namespace_display = item.namespace

        if item.storage_type in [
            'StorageClass',
            'PersistentVolume',
        ]:
            namespace_display = 'Cluster-wide'

        elif not namespace_display:
            namespace_display = '-'

        data.append(
            {
                'id': item.id,
                'cluster_name': cluster_name,
                'namespace': namespace_display,
                'name': item.name,
                'type': item.storage_type,
                'storage_class': (item.storage_class or '-'),
                'capacity': (item.capacity or '-'),
                'status': (item.status or '-'),
                'age': format_age(
                    item.created_at,
                ),
                'created_at': item.created_at,
                'collected_at': item.collected_at,
            }
        )

    return {
        'total_storage': len(items),
        'storage_classes': storage_classes,
        'persistent_volumes': persistent_volumes,
        'persistent_volume_claims': persistent_volume_claims,
        'namespaces': namespaces,
        'storage_filter_types': get_storage_filter_types(
            cluster_id=cluster_id,
        ),
        'storage_types': storage_types,
        'storage_items': data,
    }
