from typing import Any, cast

from kubernetes.client import (
    AppsV1Api,
    BatchV1Api,
    CoreV1Api,
    NetworkingV1Api,
    StorageV1Api,
    V1NamespaceList,
    V1Node,
)
from kubernetes.client.exceptions import ApiException

from app.extensions import db
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
