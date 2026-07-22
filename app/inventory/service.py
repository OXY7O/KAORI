
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from kubernetes.client import AppsV1Api, BatchV1Api, CoreV1Api, NetworkingV1Api, StorageV1Api, V1NamespaceList, V1Node
from kubernetes.client.exceptions import ApiException
from sqlalchemy import func, or_, select

from app.extensions import db
from app.integrations.registry import get_integration
from app.inventory.collector import (
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
from app.integrations.kubernetes.compatibility import KubernetesDiscovery, list_cluster_resource
from app.integrations.kubernetes.tls import legacy_tls_context
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ResourceQuotaInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)

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


def _extract_node_taints(
    node: V1Node,
) -> list[str]:
    spec = node.spec
    taints = spec.taints if spec and spec.taints else []
    result: list[str] = []

    for taint in taints:
        key = getattr(taint, 'key', None)
        if not key:
            continue

        value = getattr(taint, 'value', None)
        effect = getattr(taint, 'effect', None)
        label = key

        if value:
            label = f'{label}={value}'

        if effect:
            label = f'{label}:{effect}'

        result.append(label)

    return result


def _get_node_condition_status(
    node: V1Node,
    condition_type: str,
) -> str | None:
    status = node.status

    if status is None:
        return None

    for condition in status.conditions or []:
        if condition.type == condition_type:
            return condition.status or 'Unknown'

    return None


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
        node_inventory.node_uid = str(metadata.uid) if metadata.uid else None
        node_inventory.system_uuid = getattr(status.node_info, 'system_uuid', None) or None
        node_inventory.role = get_node_role(node)
        node_inventory.created_at = metadata.creation_timestamp
        node_inventory.status = ready_status
        node_inventory.labels = dict(
            sorted(
                (metadata.labels or {}).items(),
            )
        )
        node_inventory.unschedulable = bool(
            node.spec.unschedulable if node.spec and node.spec.unschedulable is not None else False
        )
        node_inventory.memory_pressure = _get_node_condition_status(
            node,
            'MemoryPressure',
        )
        node_inventory.disk_pressure = _get_node_condition_status(
            node,
            'DiskPressure',
        )
        node_inventory.pid_pressure = _get_node_condition_status(
            node,
            'PIDPressure',
        )
        node_inventory.network_unavailable = _get_node_condition_status(
            node,
            'NetworkUnavailable',
        )
        node_inventory.taints = _extract_node_taints(
            node,
        )

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
        node_inventory.operating_system = status.node_info.operating_system or (metadata.labels or {}).get(
            'kubernetes.io/os'
        )
        node_inventory.architecture = status.node_info.architecture or (metadata.labels or {}).get('kubernetes.io/arch')
        node_inventory.kubelet_version = status.node_info.kubelet_version
        node_inventory.kube_proxy_version = status.node_info.kube_proxy_version

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


def _namespace_count_snapshot(
    fetcher,
) -> dict[str, int] | None:
    try:
        result = fetcher()
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            return None
        raise

    counts: dict[str, int] = {}

    for item in getattr(result, 'items', None) or []:
        metadata = getattr(item, 'metadata', None)
        namespace_name = getattr(metadata, 'namespace', None)

        if not namespace_name:
            continue

        counts[namespace_name] = counts.get(namespace_name, 0) + 1

    return counts


def _namespace_service_account_snapshot(
    api: CoreV1Api,
) -> tuple[dict[str, int] | None, set[str] | None]:
    try:
        result = api.list_service_account_for_all_namespaces()
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            return None, None
        raise

    counts: dict[str, int] = {}
    default_namespaces: set[str] = set()

    for item in getattr(result, 'items', None) or []:
        metadata = getattr(item, 'metadata', None)
        namespace_name = getattr(metadata, 'namespace', None)
        service_account_name = getattr(metadata, 'name', None)

        if not namespace_name:
            continue

        counts[namespace_name] = counts.get(namespace_name, 0) + 1

        if service_account_name == 'default':
            default_namespaces.add(namespace_name)

    return counts, default_namespaces


def save_namespaces(
    cluster: Cluster,
    api: CoreV1Api,
    networking_api: NetworkingV1Api,
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

    limit_range_counts = _namespace_count_snapshot(
        api.list_limit_range_for_all_namespaces,
    )
    network_policy_counts = _namespace_count_snapshot(
        networking_api.list_network_policy_for_all_namespaces,
    )
    service_account_counts, default_service_account_namespaces = _namespace_service_account_snapshot(api)

    for namespace in namespaces:
        metadata = namespace.metadata

        if metadata is None or not metadata.name:
            continue

        namespace_name = metadata.name
        namespace_inventory = NamespaceInventory()

        namespace_inventory.cluster_id = cluster.id
        namespace_inventory.namespace = namespace_name
        namespace_inventory.status = namespace.status.phase if namespace.status else None
        namespace_inventory.uid = str(metadata.uid) if metadata.uid else None
        namespace_inventory.created_at = metadata.creation_timestamp
        namespace_inventory.labels = dict(
            sorted(
                (metadata.labels or {}).items(),
            )
        )
        namespace_inventory.annotations = dict(
            sorted(
                (metadata.annotations or {}).items(),
            )
        )
        namespace_inventory.limit_range_count = (
            None if limit_range_counts is None else limit_range_counts.get(namespace_name, 0)
        )
        namespace_inventory.network_policy_count = (
            None if network_policy_counts is None else network_policy_counts.get(namespace_name, 0)
        )
        namespace_inventory.service_account_count = (
            None if service_account_counts is None else service_account_counts.get(namespace_name, 0)
        )
        namespace_inventory.default_service_account_present = (
            None if default_service_account_namespaces is None else namespace_name in default_service_account_namespaces
        )

        db.session.add(namespace_inventory)


def save_workloads(
    cluster: Cluster,
    apps_api: AppsV1Api,
    batch_api: BatchV1Api | None = None,
    *,
    cronjob_items: list[Any] | None = None,
) -> None:
    WorkloadInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    workloads = get_workloads(
        apps_api,
        batch_api,
        cronjob_items=cronjob_items,
    )

    for workload in workloads:
        workload_inventory = WorkloadInventory()

        workload_inventory.cluster_id = cluster.id
        workload_inventory.namespace = workload['namespace']
        workload_inventory.name = workload['name']

        workload_inventory.workload_type = workload['workload_type']

        workload_inventory.ready = workload['ready']
        workload_inventory.status = workload['status']
        workload_inventory.details = workload.get(
            'details',
            {},
        )

        workload_inventory.created_at = workload['created_at']

        db.session.add(workload_inventory)


def save_pods(
    cluster: Cluster,
    api: CoreV1Api,
    apps_api: AppsV1Api | None = None,
    batch_api: BatchV1Api | None = None,
) -> None:
    PodInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    pods = get_pods(
        api,
        apps_api,
        batch_api,
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

        pod_inventory.labels = pod.get(
            'labels',
            {},
        )

        pod_inventory.details = pod.get(
            'details',
            {},
        )

        pod_inventory.container_names = pod.get(
            'container_names',
            [],
        )

        pod_inventory.workload_type = pod.get(
            'workload_type',
        )

        pod_inventory.workload_name = pod.get(
            'workload_name',
        )

        pod_inventory.configuration_references = pod.get(
            'configuration_references',
            [],
        )

        pod_inventory.persistent_volume_claims = pod.get(
            'persistent_volume_claims',
            [],
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

        service_inventory.selector = service.get(
            'selector',
            {},
        )

        service_inventory.details = service.get(
            'details',
            {},
        )

        service_inventory.created_at = service['created_at']

        db.session.add(service_inventory)


def save_ingresses(
    cluster: Cluster,
    api: NetworkingV1Api | None,
    *,
    ingress_items: list[Any] | None = None,
) -> None:
    IngressInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    ingresses = get_ingresses(
        api,
        ingress_items=ingress_items,
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

        ingress_inventory.details = ingress.get(
            'details',
            {},
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

        storage_inventory.details = item.get(
            'details',
            {},
        )

        storage_inventory.created_at = item['created_at']

        db.session.add(storage_inventory)


def save_configuration_inventory(
    cluster: Cluster,
    api: CoreV1Api,
    *,
    include_configmaps: bool = True,
    include_secrets: bool = True,
) -> None:
    if include_configmaps:
        ConfigurationInventory.query.filter_by(
            cluster_id=cluster.id, object_type='ConfigMap',
        ).delete(synchronize_session=False)
    if include_secrets:
        ConfigurationInventory.query.filter_by(
            cluster_id=cluster.id, object_type='Secret',
        ).delete(synchronize_session=False)

    for item in get_configuration_inventory(
        api,
        include_configmaps=include_configmaps,
        include_secrets=include_secrets,
    ):
        inventory = ConfigurationInventory()
        inventory.cluster_id = cluster.id
        inventory.namespace = item['namespace']
        inventory.name = item['name']
        inventory.object_type = item['object_type']
        inventory.secret_type = item['secret_type']
        inventory.key_names = item['key_names']
        inventory.key_count = item['key_count']
        inventory.immutable = item['immutable']
        inventory.payload_size_bytes = item['payload_size_bytes']
        inventory.created_at = item['created_at']
        db.session.add(inventory)


def save_resource_quotas(
    cluster: Cluster,
    api: CoreV1Api,
) -> None:
    ResourceQuotaInventory.query.filter_by(
        cluster_id=cluster.id,
    ).delete(
        synchronize_session=False,
    )

    for item in get_resource_quotas(api):
        inventory = ResourceQuotaInventory()
        inventory.cluster_id = cluster.id
        inventory.namespace = item['namespace']
        inventory.name = item['name']
        inventory.hard = item['hard']
        inventory.used = item['used']
        inventory.created_at = item['created_at']
        db.session.add(inventory)


def _lock_cluster_inventory_sync(
    cluster_id: str,
) -> None:
    """Serialize inventory replacement for one cluster within the DB transaction."""
    db.session.execute(
        select(Cluster.id)
        .where(
            Cluster.id == cluster_id,
        )
        .with_for_update(),
    ).scalar_one()


def sync_inventory(
    cluster: Cluster,
) -> None:
    connection = cluster.kubernetes_connection
    if connection is None:
        raise ValueError('The selected cluster has no canonical Kubernetes connection.')
    allow_weak_tls = bool(connection.allow_weak_tls)

    current_stage = 'cluster lock'

    try:
        _lock_cluster_inventory_sync(
            cluster.id,
        )

        with legacy_tls_context(
            enabled=allow_weak_tls,
        ):
            client = get_integration('kubernetes').execute('client.build', connection)

            core_api = client.core_api()

            apps_api = client.apps_api()

            batch_api = BatchV1Api(
                core_api.api_client,
            )

            networking_api = client.networking_api()

            storage_api = client.storage_api()

            current_stage = 'API discovery'
            discovery = KubernetesDiscovery(core_api.api_client).discover()
            adapters = discovery['selected_adapters']
            connection.compatibility_profile = discovery['api_profile']
            connection.compatibility_status = discovery['compatibility_status']
            connection.readiness_status = discovery['readiness_status']
            connection.discovery_summary = discovery

            cronjob_items = None
            cronjob_adapter = adapters.get('inventory.cronjobs')
            if cronjob_adapter and cronjob_adapter.get('stability') == 'legacy':
                cronjob_items = list_cluster_resource(core_api.api_client, cronjob_adapter)

            ingress_items = None
            ingress_adapter = adapters.get('inventory.ingresses')
            if ingress_adapter and ingress_adapter.get('stability') == 'legacy':
                ingress_items = list_cluster_resource(core_api.api_client, ingress_adapter)

            current_stage = 'cluster information'
            save_cluster_info(
                cluster,
                core_api,
            )
            db.session.flush()

            current_stage = 'nodes'
            save_nodes(
                cluster,
                core_api,
            )
            db.session.flush()

            current_stage = 'namespaces'
            save_namespaces(
                cluster,
                core_api,
                networking_api,
            )
            db.session.flush()

            current_stage = 'workloads'
            save_workloads(
                cluster,
                apps_api,
                batch_api,
                cronjob_items=cronjob_items,
            )
            db.session.flush()

            current_stage = 'pods'
            save_pods(
                cluster,
                core_api,
                apps_api,
                batch_api,
            )
            db.session.flush()

            current_stage = 'services'
            save_services(
                cluster,
                core_api,
            )
            db.session.flush()

            current_stage = 'ingresses'
            if ingress_adapter:
                save_ingresses(
                    cluster,
                    networking_api if ingress_adapter.get('stability') == 'stable' else None,
                    ingress_items=ingress_items,
                )
            db.session.flush()

            current_stage = 'storage'
            save_storage_inventory(
                cluster,
                core_api,
                storage_api,
            )
            db.session.flush()

            current_stage = 'configuration'
            save_configuration_inventory(
                cluster,
                core_api,
                include_configmaps='inventory.configmaps' in adapters,
                include_secrets='inventory.secrets' in adapters,
            )
            db.session.flush()

            current_stage = 'resource quotas'
            save_resource_quotas(
                cluster,
                core_api,
            )
            db.session.flush()

        current_stage = 'commit'
        db.session.commit()

    except Exception as exc:
        print('=== INVENTORY SYNC EXCEPTION ===')
        print(f'Stage: {current_stage}')
        print(type(exc).__name__)
        print(str(exc))

        db.session.rollback()
        raise


















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
