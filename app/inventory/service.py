from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from kubernetes.client import AppsV1Api, BatchV1Api, CoreV1Api, NetworkingV1Api, StorageV1Api, V1NamespaceList, V1Node
from kubernetes.client.exceptions import ApiException
from sqlalchemy import func, or_, select

from app.extensions import db
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
from app.kubernetes.client import KubernetesClient
from app.kubernetes.compatibility import KubernetesDiscovery, list_cluster_resource
from app.kubernetes.tls import legacy_tls_context
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

    current_stage = 'cluster lock'

    try:
        _lock_cluster_inventory_sync(
            cluster.id,
        )

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

            current_stage = 'API discovery'
            discovery = KubernetesDiscovery(core_api.api_client).discover()
            adapters = discovery['selected_adapters']
            cluster.kubernetes_compatibility_profile = discovery['api_profile']
            cluster.kubernetes_compatibility_status = discovery['compatibility_status']
            cluster.kubernetes_readiness_status = discovery['readiness_status']
            cluster.kubernetes_api_discovery_summary = discovery

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


def _parse_kubernetes_size_bytes(
    value: str | int | float | None,
) -> Decimal | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw or raw == '-':
        return None

    units = {
        'Ki': Decimal(1024),
        'Mi': Decimal(1024) ** 2,
        'Gi': Decimal(1024) ** 3,
        'Ti': Decimal(1024) ** 4,
        'Pi': Decimal(1024) ** 5,
        'Ei': Decimal(1024) ** 6,
        'K': Decimal(1000),
        'M': Decimal(1000) ** 2,
        'G': Decimal(1000) ** 3,
        'T': Decimal(1000) ** 4,
        'P': Decimal(1000) ** 5,
        'E': Decimal(1000) ** 6,
    }

    try:
        for suffix in sorted(units, key=len, reverse=True):
            if raw.endswith(suffix):
                number = Decimal(raw.removesuffix(suffix))
                return number * units[suffix]

        return Decimal(raw)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _format_decimal(value: Decimal, decimals: int = 1) -> str:
    quantized = round(value, decimals)
    if quantized == quantized.to_integral():
        return str(int(quantized))
    return f'{quantized:.{decimals}f}'.rstrip('0').rstrip('.')


def format_kubernetes_size(
    value: str | int | float | None,
) -> str:
    size_bytes = _parse_kubernetes_size_bytes(value)

    if size_bytes is None or size_bytes < 0:
        return '-'

    units = [
        ('PiB', Decimal(1024) ** 5),
        ('TiB', Decimal(1024) ** 4),
        ('GiB', Decimal(1024) ** 3),
        ('MiB', Decimal(1024) ** 2),
        ('KiB', Decimal(1024)),
    ]

    for label, divisor in units:
        if size_bytes >= divisor:
            return f'{_format_decimal(size_bytes / divisor)} {label}'

    return f'{int(size_bytes)} B'


def format_byte_count(
    value: int | None,
) -> str:
    return format_kubernetes_size(value)


def convert_ki_to_gib(
    value: str | None,
) -> float:
    size_bytes = _parse_kubernetes_size_bytes(value)
    if size_bytes is None:
        return 0
    return round(float(size_bytes / (Decimal(1024) ** 3)), 1)


def convert_storage_to_gib(
    value: str | None,
) -> float:
    return convert_ki_to_gib(value)


def format_gib(
    value: float,
) -> str:
    if value <= 0:
        return '-'
    return f'{value:g} GiB'


def format_quota_value(
    resource_name: str,
    value: str | None,
) -> str:
    if not value:
        return '-'

    size_markers = (
        'memory',
        'storage',
        'ephemeral-storage',
    )

    if any(marker in resource_name.lower() for marker in size_markers):
        return format_kubernetes_size(value)

    return value


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
                'memory_display': format_kubernetes_size(
                    node.memory,
                ),
                'ephemeral_storage_display': format_kubernetes_size(
                    node.ephemeral_storage,
                ),
                'ephemeral_storage_allocatable_display': format_kubernetes_size(
                    node.ephemeral_storage_allocatable,
                ),
                'os_image': node.os_image,
                'runtime_display': runtime_display,
                'collected_at': node.collected_at,
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


def _pod_summary(
    pod: PodInventory,
) -> dict[str, Any]:
    return {
        'id': pod.id,
        'name': pod.pod_name,
        'status': pod.phase or 'Unknown',
        'ready': pod.ready or '-',
        'node': pod.node_name or '-',
        'container_names': pod.container_names or [],
        'container_count': len(pod.container_names or []),
        'age': format_age(pod.created_at),
    }


def _display_boolean(value: Any) -> str:
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    return '-'


def _workload_detail_rows(
    details: dict[str, Any],
    key: str,
) -> list[dict[str, str]]:
    rows = details.get(key) or []
    return [
        {
            'label': str(row.get('label') or '-'),
            'value': str(row.get('value') if row.get('value') not in (None, '') else '-'),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def _compact_runtime_state_rows(
    workload_type: str,
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    preferred_labels = {
        'Deployment': ('Desired replicas', 'Ready replicas', 'Available replicas', 'Unavailable replicas'),
        'StatefulSet': ('Desired replicas', 'Ready replicas', 'Available replicas', 'Current revision'),
        'DaemonSet': ('Desired scheduled', 'Ready', 'Available', 'Unavailable'),
        'Job': ('Completions', 'Active', 'Succeeded', 'Failed'),
        'CronJob': ('Schedule', 'Suspended', 'Active Jobs', 'Last schedule'),
    }
    preferred = preferred_labels.get(workload_type, ())
    indexed = {str(row.get('label')): row for row in rows}
    compact = [indexed[label] for label in preferred if label in indexed]
    fallback = [row for row in rows if row.get('label') != 'Managed Pods'][:4]
    return compact or fallback


def _fallback_pod_template_from_associated_pods(
    related_pods: list[PodInventory],
) -> dict[str, Any]:
    """Provide a safe partial view for snapshots created by an older worker."""
    if not related_pods:
        return {}

    reference_pod = max(
        related_pods,
        key=lambda pod: len(pod.container_names or []) + len(pod.init_container_images or []),
    )
    container_names = list(reference_pod.container_names or [])
    container_images = list(reference_pod.container_images or [])
    init_images = list(reference_pod.init_container_images or [])
    containers: list[dict[str, str]] = []

    regular_count = max(len(container_names), len(container_images))
    for index in range(regular_count):
        containers.append(
            {
                'name': container_names[index] if index < len(container_names) else f'container-{index + 1}',
                'image': container_images[index] if index < len(container_images) else '-',
                'pull_policy': '-',
                'kind': 'Container',
            }
        )

    for index, image in enumerate(init_images):
        containers.append(
            {
                'name': f'init-container-{index + 1}',
                'image': image,
                'pull_policy': '-',
                'kind': 'Init container',
            }
        )

    return {
        'reported': False,
        'schema_version': 1,
        'source': 'associated-pod-fallback',
        'containers': containers,
        'container_count': regular_count,
        'init_container_count': len(init_images),
        'service_account': '-',
        'restart_policy': '-',
        'priority_class': '-',
        'scheduler': '-',
        'host_network': False,
        'dns_policy': '-',
        'volume_count': 0,
        'node_selector': {},
        'affinity_configured': False,
        'tolerations': [],
        'topology_spread_count': 0,
        'runtime_class': '-',
    }


def _pod_template_has_inventory_data(
    pod_template: dict[str, Any],
) -> bool:
    if pod_template.get('containers'):
        return True

    if int(pod_template.get('container_count') or 0) > 0:
        return True

    if int(pod_template.get('init_container_count') or 0) > 0:
        return True

    for key in (
        'service_account',
        'restart_policy',
        'priority_class',
        'scheduler',
        'dns_policy',
        'runtime_class',
    ):
        if pod_template.get(key) not in (None, '', '-'):
            return True

    return bool(
        pod_template.get('volume_count')
        or pod_template.get('node_selector')
        or pod_template.get('affinity_configured')
        or pod_template.get('tolerations')
        or pod_template.get('topology_spread_count')
    )


def _resolve_workload_pod_template(
    details: dict[str, Any],
    related_pods: list[PodInventory],
) -> tuple[dict[str, Any], str]:
    pod_template = details.get('pod_template')
    if isinstance(pod_template, dict) and (
        pod_template.get('reported') is True or _pod_template_has_inventory_data(pod_template)
    ):
        return pod_template, 'workload-template'

    fallback = _fallback_pod_template_from_associated_pods(related_pods)
    if fallback:
        return fallback, 'associated-pod-fallback'

    return {}, 'not-reported'


def _pod_configuration_rows(
    pod_template: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {'label': 'Containers', 'value': str(pod_template.get('container_count', 0))},
        {'label': 'Init containers', 'value': str(pod_template.get('init_container_count', 0))},
        {'label': 'Service account', 'value': str(pod_template.get('service_account') or '-')},
        {'label': 'Restart policy', 'value': str(pod_template.get('restart_policy') or '-')},
        {'label': 'Priority class', 'value': str(pod_template.get('priority_class') or '-')},
        {'label': 'Scheduler', 'value': str(pod_template.get('scheduler') or '-')},
        {'label': 'Host network', 'value': _display_boolean(pod_template.get('host_network'))},
        {'label': 'DNS policy', 'value': str(pod_template.get('dns_policy') or '-')},
        {'label': 'Volumes', 'value': str(pod_template.get('volume_count', 0))},
    ]


def _placement_rows(
    pod_template: dict[str, Any],
) -> list[dict[str, str]]:
    node_selector = pod_template.get('node_selector') or {}
    tolerations = pod_template.get('tolerations') or []

    return [
        {
            'label': 'Node selector',
            'value': f'{len(node_selector)} rule' + ('s' if len(node_selector) != 1 else ''),
        },
        {
            'label': 'Affinity',
            'value': 'Configured' if pod_template.get('affinity_configured') else 'Not configured',
        },
        {
            'label': 'Tolerations',
            'value': str(len(tolerations)),
        },
        {
            'label': 'Topology spread',
            'value': str(pod_template.get('topology_spread_count', 0)),
        },
        {
            'label': 'Runtime class',
            'value': str(pod_template.get('runtime_class') or '-'),
        },
    ]


def get_node_detail(node_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            NodeInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == NodeInventory.cluster_id)
        .filter(NodeInventory.id == node_id)
        .first()
    )

    if result is None:
        return None

    node, cluster_name = result
    runtime = node.container_runtime or ''
    role = node.role or 'Unknown'
    role_key = role.lower()

    pod_scope = (
        PodInventory.cluster_id == node.cluster_id,
        PodInventory.node_name == node.node_name,
    )
    scheduled_pod_count = db.session.query(func.count(PodInventory.id)).filter(*pod_scope).scalar() or 0

    if node.unschedulable is True:
        scheduling_display = 'Cordoned'
    elif node.unschedulable is False:
        scheduling_display = 'Schedulable'
    else:
        scheduling_display = 'Not reported'

    network_availability = 'Not reported'
    if node.network_unavailable == 'True':
        network_availability = 'Unavailable'
    elif node.network_unavailable == 'False':
        network_availability = 'Available'

    ready_condition = {
        'Ready': 'True',
        'NotReady': 'False',
    }.get(node.status or '', 'Unknown')

    node_labels = node.labels or {}
    operating_system = node.operating_system or node_labels.get('kubernetes.io/os') or 'Unknown'
    operating_system_display = (
        operating_system.title() if operating_system.lower() in {'linux', 'windows'} else operating_system
    )
    architecture = node.architecture or node_labels.get('kubernetes.io/arch') or 'Not reported'

    return {
        'id': node.id,
        'cluster_name': cluster_name,
        'node_name': node.node_name,
        'system_uuid': node.system_uuid or 'Not reported',
        'role': role,
        'age': format_age(node.created_at),
        'role_description': NODE_ROLE_DESCRIPTIONS.get(
            role_key,
            'Provides Kubernetes node capacity. Its exact function depends on the labels and workloads assigned to it.',
        ),
        'status': node.status or 'Unknown',
        'internal_ip': node.internal_ip,
        'external_ip': node.external_ip,
        'hostname_address': node.hostname_address,
        'scheduled_pod_count': scheduled_pod_count,
        'network_availability': network_availability,
        'scheduling_display': scheduling_display,
        'ready_condition': ready_condition,
        'memory_pressure': node.memory_pressure or 'Not reported',
        'disk_pressure': node.disk_pressure or 'Not reported',
        'pid_pressure': node.pid_pressure or 'Not reported',
        'taints': node.taints or [],
        'labels': dict(
            sorted(
                node_labels.items(),
            )
        ),
        'operating_system_display': operating_system_display,
        'architecture': architecture,
        'kubelet_version': node.kubelet_version or 'Not reported',
        'kube_proxy_version': node.kube_proxy_version or 'Not reported',
        'cpu': node.cpu,
        'memory_display': format_kubernetes_size(node.memory),
        'ephemeral_storage_display': format_kubernetes_size(node.ephemeral_storage),
        'ephemeral_storage_allocatable_display': format_kubernetes_size(node.ephemeral_storage_allocatable),
        'os_image': node.os_image,
        'kernel_version': node.kernel_version,
        'runtime_display': runtime.split('://')[0] if '://' in runtime else runtime,
        'collected_at': node.collected_at,
    }


def get_workload_detail(workload_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            WorkloadInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == WorkloadInventory.cluster_id)
        .filter(WorkloadInventory.id == workload_id)
        .first()
    )

    if result is None:
        return None

    workload, cluster_name = result
    workload_type = workload.workload_type or 'Unknown'
    details = workload.details or {}

    related_pods = (
        PodInventory.query.filter_by(
            cluster_id=workload.cluster_id,
            namespace=workload.namespace,
            workload_type=workload_type,
            workload_name=workload.name,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )

    pod_template, pod_configuration_source = _resolve_workload_pod_template(
        details,
        related_pods,
    )

    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    node_selector = pod_template.get('node_selector') or {}
    tolerations = pod_template.get('tolerations') or []
    containers = pod_template.get('containers') or []

    state_rows = _workload_detail_rows(details, 'state_rows')
    if not state_rows:
        state_rows = [
            {'label': 'Ready', 'value': workload.ready or '-'},
            {'label': 'Status', 'value': workload.status or 'Unknown'},
            {'label': 'Managed Pods', 'value': str(len(related_pods))},
        ]

    delivery_rows = _workload_detail_rows(details, 'delivery_rows')
    placement_rows = _placement_rows(pod_template)
    placement_summary_rows = [
        row
        for row in placement_rows
        if row['value'] not in {'0', '0 rules', 'Not configured', '-'}
    ]

    return {
        'id': workload.id,
        'cluster_id': workload.cluster_id,
        'cluster_name': cluster_name,
        'namespace': workload.namespace,
        'name': workload.name,
        'type': workload_type,
        'type_description': WORKLOAD_TYPE_DESCRIPTIONS.get(
            workload_type,
            'Represents a Kubernetes workload controller or batch resource that manages Pods.',
        ),
        'uid': details.get('uid') or '-',
        'ready': workload.ready or '-',
        'status': workload.status or 'Unknown',
        'state_display': details.get('state_display') or workload.ready or workload.status or 'Unknown',
        'age': format_age(workload.created_at),
        'created_at': workload.created_at,
        'collected_at': workload.collected_at,
        'state_rows': state_rows,
        'runtime_state_rows': _compact_runtime_state_rows(workload_type, state_rows),
        'pod_configuration_rows': _pod_configuration_rows(pod_template),
        'pod_configuration_reported': pod_configuration_source == 'workload-template',
        'pod_configuration_source': pod_configuration_source,
        'delivery_rows': delivery_rows,
        'placement_rows': placement_rows,
        'placement_summary_rows': placement_summary_rows,
        'placement_constraint_count': (
            len(node_selector)
            + len(tolerations)
            + (1 if pod_template.get('affinity_configured') else 0)
            + int(pod_template.get('topology_spread_count') or 0)
        ),
        'placement_configured': bool(
            node_selector
            or tolerations
            or pod_template.get('affinity_configured')
            or pod_template.get('topology_spread_count')
        ),
        'node_selectors': [f'{key}={value}' for key, value in sorted(node_selector.items())],
        'tolerations': [str(item) for item in tolerations],
        'containers': containers,
        'container_count': int(pod_template.get('container_count') or 0),
        'init_container_count': int(pod_template.get('init_container_count') or 0),
        'pod_count': len(related_pods),
        'pods': [_pod_summary(pod) for pod in related_pods[:8]],
        'pods_truncated': len(related_pods) > 8,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
        'details_reported': bool(details),
    }


def _split_inventory_values(value: str | None) -> list[str]:
    return [item.strip() for item in (value or '').split(',') if item.strip() and item.strip() != '-']


def _selector_matches(
    selector: dict[str, str],
    labels: dict[str, str],
) -> bool:
    return bool(selector) and all(labels.get(key) == value for key, value in selector.items())


def _service_port_rows(service: ServiceInventory) -> list[dict[str, Any]]:
    details = service.details or {}
    ports = details.get('ports') or []
    rows: list[dict[str, Any]] = []

    for port in ports:
        if not isinstance(port, dict):
            continue
        rows.append(
            {
                'name': str(port.get('name') or '-'),
                'protocol': str(port.get('protocol') or 'TCP'),
                'port': int(port.get('port') or 0),
                'target_port': str(port.get('target_port') or '-'),
                'node_port': int(port.get('node_port') or 0),
                'app_protocol': str(port.get('app_protocol') or '-'),
            }
        )

    if rows:
        return rows

    for value in _split_inventory_values(service.ports):
        port_value, _, protocol = value.partition('/')
        rows.append(
            {
                'name': '-',
                'protocol': protocol or 'TCP',
                'port': int(port_value) if port_value.isdigit() else 0,
                'target_port': '-',
                'node_port': 0,
                'app_protocol': '-',
            }
        )

    return rows


def get_service_detail(service_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            ServiceInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == ServiceInventory.cluster_id)
        .filter(ServiceInventory.id == service_id)
        .first()
    )

    if result is None:
        return None

    service, cluster_name = result
    service_type = service.service_type or 'Unknown'
    selector = service.selector or {}
    details = dict(service.details or {})
    endpoints = dict(details.get('endpoints') or {})
    ready_endpoints = [item for item in endpoints.get('ready_addresses') or [] if isinstance(item, dict)]
    not_ready_endpoints = [item for item in endpoints.get('not_ready_addresses') or [] if isinstance(item, dict)]

    candidate_pods = (
        PodInventory.query.filter_by(
            cluster_id=service.cluster_id,
            namespace=service.namespace,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )
    matched_pods = [pod for pod in candidate_pods if _selector_matches(selector, pod.labels or {})]

    effective_type = 'Headless' if service_type == 'ClusterIP' and service.cluster_ip == 'None' else service_type
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    cluster_ips = details.get('cluster_ips') or []
    if not cluster_ips and service.cluster_ip:
        cluster_ips = [service.cluster_ip]

    return {
        'id': service.id,
        'cluster_name': cluster_name,
        'namespace': service.namespace,
        'name': service.service_name,
        'type': effective_type,
        'type_description': SERVICE_TYPE_DESCRIPTIONS.get(
            effective_type,
            'Exposes a stable network endpoint for an application or external destination.',
        ),
        'uid': details.get('uid') or '-',
        'generation': int(details.get('generation') or 0),
        'cluster_ip': service.cluster_ip or '-',
        'cluster_ips': cluster_ips,
        'external_ips': _split_inventory_values(service.external_ip),
        'external_name': details.get('external_name') or '-',
        'ip_families': details.get('ip_families') or [],
        'ip_family_policy': details.get('ip_family_policy') or '-',
        'session_affinity': details.get('session_affinity') or 'None',
        'internal_traffic_policy': details.get('internal_traffic_policy') or '-',
        'external_traffic_policy': details.get('external_traffic_policy') or '-',
        'publish_not_ready_addresses': bool(details.get('publish_not_ready_addresses')),
        'health_check_node_port': int(details.get('health_check_node_port') or 0),
        'load_balancer_class': details.get('load_balancer_class') or '-',
        'allocate_load_balancer_node_ports': details.get('allocate_load_balancer_node_ports'),
        'ports': _service_port_rows(service),
        'port_count': len(_service_port_rows(service)),
        'selector': selector,
        'selectors': [f'{key}={value}' for key, value in sorted(selector.items())],
        'age': format_age(service.created_at),
        'created_at': service.created_at,
        'collected_at': service.collected_at,
        'pod_count': len(matched_pods),
        'pods': [_pod_summary(pod) for pod in matched_pods[:8]],
        'pods_truncated': len(matched_pods) > 8,
        'has_selector': bool(selector),
        'endpoints_reported': bool(endpoints.get('reported')),
        'ready_endpoint_count': len(ready_endpoints),
        'not_ready_endpoint_count': len(not_ready_endpoints),
        'endpoints': ready_endpoints[:12],
        'not_ready_endpoints': not_ready_endpoints[:12],
        'endpoints_truncated': len(ready_endpoints) > 12 or len(not_ready_endpoints) > 12,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
        'details_reported': bool(details),
    }


STORAGE_TYPE_DESCRIPTIONS = {
    'StorageClass': 'Defines dynamic volume provisioning behavior and lifecycle defaults for PersistentVolumes.',
    'PersistentVolume': 'Represents cluster-scoped storage capacity that can be bound to a PersistentVolumeClaim.',
    'PersistentVolumeClaim': 'Represents a namespace-scoped request for storage consumed by one or more Pods.',
}


def _storage_bound_pods(
    item: StorageInventory,
) -> tuple[list[PodInventory], list[dict[str, str]]]:
    details = item.details or {}
    claims: list[dict[str, str]] = []

    if item.storage_type == 'PersistentVolumeClaim' and item.namespace:
        claims.append({'namespace': item.namespace, 'name': item.name})

    elif item.storage_type == 'PersistentVolume':
        claim_namespace = details.get('claim_namespace')
        claim_name = details.get('claim_name')
        if claim_namespace and claim_name:
            claims.append({'namespace': claim_namespace, 'name': claim_name})

    elif item.storage_type == 'StorageClass':
        pvc_rows = (
            StorageInventory.query.filter_by(
                cluster_id=item.cluster_id,
                storage_type='PersistentVolumeClaim',
                storage_class=item.name,
            )
            .order_by(StorageInventory.namespace, StorageInventory.name)
            .all()
        )
        claims.extend(
            {
                'namespace': pvc.namespace or '-',
                'name': pvc.name,
            }
            for pvc in pvc_rows
            if pvc.namespace
        )

    if not claims:
        return [], []

    claim_lookup = {(claim['namespace'], claim['name']) for claim in claims}
    pods = (
        PodInventory.query.filter_by(cluster_id=item.cluster_id)
        .order_by(
            PodInventory.namespace,
            PodInventory.pod_name,
        )
        .all()
    )

    matched = [
        pod
        for pod in pods
        if any((pod.namespace, claim_name) in claim_lookup for claim_name in (pod.persistent_volume_claims or []))
    ]

    return matched, claims


def get_storage_detail(storage_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            StorageInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == StorageInventory.cluster_id)
        .filter(StorageInventory.id == storage_id)
        .first()
    )

    if result is None:
        return None

    item, cluster_name = result
    namespace = item.namespace
    if item.storage_type in {'StorageClass', 'PersistentVolume'}:
        namespace = 'Cluster-wide'

    bound_pods, claims = _storage_bound_pods(item)
    details = dict(item.details or {})
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    source = details.get('source') or {}

    requested_storage = details.get('requested_storage')
    if requested_storage:
        requested_storage = format_kubernetes_size(requested_storage)

    if item.storage_type == 'PersistentVolume':
        binding_reference = (
            f'{details.get("claim_namespace")}/{details.get("claim_name")}'
            if details.get('claim_namespace') and details.get('claim_name')
            else 'Unbound'
        )
    elif item.storage_type == 'PersistentVolumeClaim':
        binding_reference = details.get('volume_name') or 'Unbound'
    else:
        binding_reference = f'{len(claims)} claim(s)'

    return {
        'id': item.id,
        'cluster_name': cluster_name,
        'namespace': namespace or '-',
        'name': item.name,
        'type': item.storage_type,
        'type_description': STORAGE_TYPE_DESCRIPTIONS.get(
            item.storage_type,
            'Kubernetes storage metadata from the latest inventory snapshot.',
        ),
        'storage_class': item.storage_class or '-',
        'capacity': format_kubernetes_size(item.capacity),
        'requested_storage': requested_storage or '-',
        'status': item.status or 'Unknown',
        'details': details,
        'uid': details.get('uid') or '-',
        'finalizers': details.get('finalizers') or [],
        'access_modes': details.get('access_modes') or [],
        'volume_mode': details.get('volume_mode') or '-',
        'reclaim_policy': details.get('reclaim_policy') or '-',
        'binding_mode': details.get('volume_binding_mode') or '-',
        'allow_expansion': bool(details.get('allow_volume_expansion')),
        'provisioner': details.get('provisioner') or '-',
        'parameters': sorted((details.get('parameters') or {}).items()),
        'mount_options': details.get('mount_options') or [],
        'allowed_topology_count': int(details.get('allowed_topology_count') or 0),
        'is_default': bool(details.get('is_default')),
        'node_affinity_configured': bool(details.get('node_affinity_configured')),
        'source': source,
        'selector': sorted((details.get('selector') or {}).items()),
        'data_source': details.get('data_source'),
        'conditions': details.get('conditions') or [],
        'binding_reference': binding_reference,
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'claim_count': len(claims),
        'claims': claims[:8],
        'claims_truncated': len(claims) > 8,
        'pod_count': len(bound_pods),
        'pods': [_pod_summary(pod) for pod in bound_pods[:8]],
        'pods_truncated': len(bound_pods) > 8,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
        'details_reported': bool(details),
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
    cluster_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
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

    namespace_records = query.order_by(
        Cluster.name,
        NamespaceInventory.namespace,
    ).all()

    def _namespace_count_map(model) -> dict[tuple[str, str], int]:
        count_query = db.session.query(
            model.cluster_id,
            model.namespace,
            func.count(model.id),
        )

        if cluster_id:
            count_query = count_query.filter(model.cluster_id == cluster_id)

        return {
            (row_cluster_id, row_namespace): count
            for row_cluster_id, row_namespace, count in (
                count_query.group_by(
                    model.cluster_id,
                    model.namespace,
                ).all()
            )
        }

    workload_counts = _namespace_count_map(WorkloadInventory)
    pod_counts = _namespace_count_map(PodInventory)
    service_counts = _namespace_count_map(ServiceInventory)
    quota_counts = _namespace_count_map(ResourceQuotaInventory)

    status_counts: dict[str, int] = {}
    inventory_rows: list[dict[str, Any]] = []

    for namespace, cluster_name in namespace_records:
        namespace_status = namespace.status or 'Unknown'
        status_counts[namespace_status] = status_counts.get(namespace_status, 0) + 1

        key = (
            namespace.cluster_id,
            namespace.namespace,
        )
        quota_count = quota_counts.get(key, 0)
        limit_range_count = namespace.limit_range_count
        network_policy_count = namespace.network_policy_count

        inventory_rows.append(
            {
                'id': namespace.id,
                'cluster_name': cluster_name,
                'namespace': namespace.namespace,
                'status': namespace_status,
                'age': format_age(namespace.created_at),
                'workload_count': workload_counts.get(key, 0),
                'pod_count': pod_counts.get(key, 0),
                'service_count': service_counts.get(key, 0),
                'quota_count': quota_count,
                'limit_range_count': limit_range_count,
                'network_policy_count': network_policy_count,
                'controls_reported': (limit_range_count is not None and network_policy_count is not None),
            }
        )

    cluster_count = len({cluster_name for _, cluster_name in namespace_records})

    return {
        'total_namespaces': len(namespace_records),
        'total_clusters': cluster_count,
        'active_namespaces': status_counts.get('Active', 0),
        'status_counts': status_counts,
        'namespace_statuses': get_namespace_filter_statuses(
            cluster_id=cluster_id,
        ),
        'namespaces': inventory_rows,
    }


def get_namespace_detail(
    namespace_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            NamespaceInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == NamespaceInventory.cluster_id)
        .filter(NamespaceInventory.id == namespace_id)
        .first()
    )

    if result is None:
        return None

    namespace, cluster_name = result

    workload_counts = {
        workload_type or 'Unknown': count
        for workload_type, count in (
            db.session.query(
                WorkloadInventory.workload_type,
                func.count(WorkloadInventory.id),
            )
            .filter(
                WorkloadInventory.cluster_id == namespace.cluster_id,
                WorkloadInventory.namespace == namespace.namespace,
            )
            .group_by(WorkloadInventory.workload_type)
            .all()
        )
    }

    object_counts = {
        'workloads': WorkloadInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'pods': PodInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'services': ServiceInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'ingresses': IngressInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'persistent_volume_claims': StorageInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
            storage_type='PersistentVolumeClaim',
        ).count(),
        'config_maps': ConfigurationInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
            object_type='ConfigMap',
        ).count(),
        'secrets': ConfigurationInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
            object_type='Secret',
        ).count(),
        'resource_quotas': ResourceQuotaInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
    }

    object_counts['tracked_total'] = sum(
        object_counts[key]
        for key in (
            'workloads',
            'pods',
            'services',
            'ingresses',
            'persistent_volume_claims',
            'config_maps',
            'secrets',
        )
    )

    quota_rows = (
        ResourceQuotaInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        )
        .order_by(ResourceQuotaInventory.name)
        .all()
    )

    quotas: list[dict[str, Any]] = []

    for quota in quota_rows:
        resources = []

        for resource_name in sorted((quota.hard or {}).keys()):
            resources.append(
                {
                    'name': resource_name,
                    'hard': format_quota_value(
                        resource_name,
                        (quota.hard or {}).get(resource_name),
                    ),
                }
            )

        quotas.append(
            {
                'name': quota.name,
                'resources': resources[:10],
                'resource_count': len(resources),
                'truncated': len(resources) > 10,
            }
        )

    labels = dict(sorted((namespace.labels or {}).items()))
    annotations = dict(sorted((namespace.annotations or {}).items()))

    if namespace.default_service_account_present is True:
        default_service_account = 'Present'
    elif namespace.default_service_account_present is False:
        default_service_account = 'Missing'
    else:
        default_service_account = 'Not reported'

    return {
        'id': namespace.id,
        'cluster_name': cluster_name,
        'namespace': namespace.namespace,
        'status': namespace.status or 'Unknown',
        'uid': namespace.uid or '-',
        'age': format_age(namespace.created_at),
        'created_at': namespace.created_at,
        'collected_at': namespace.collected_at,
        'labels': labels,
        'annotations': annotations,
        'object_counts': object_counts,
        'workload_breakdown': {
            'deployments': workload_counts.get('Deployment', 0),
            'statefulsets': workload_counts.get('StatefulSet', 0),
            'daemonsets': workload_counts.get('DaemonSet', 0),
            'jobs': workload_counts.get('Job', 0),
            'cronjobs': workload_counts.get('CronJob', 0),
        },
        'quotas': quotas,
        'quota_count': len(quotas),
        'limit_range_count': namespace.limit_range_count,
        'network_policy_count': namespace.network_policy_count,
        'service_account_count': namespace.service_account_count,
        'default_service_account': default_service_account,
        'pod_security_enforce': labels.get(
            'pod-security.kubernetes.io/enforce',
            'Not configured',
        ),
        'pod_security_audit': labels.get(
            'pod-security.kubernetes.io/audit',
            'Not configured',
        ),
        'pod_security_warn': labels.get(
            'pod-security.kubernetes.io/warn',
            'Not configured',
        ),
    }


def get_configuration_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(ConfigurationInventory.namespace)
    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)

    return [
        namespace for (namespace,) in query.distinct().order_by(ConfigurationInventory.namespace).all() if namespace
    ]


def get_configuration_inventory_view(
    cluster_id: str | None = None,
    namespace: str | None = None,
    object_type: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    query = db.session.query(
        ConfigurationInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)

    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ConfigurationInventory.namespace == namespace)
    if object_type:
        query = query.filter(ConfigurationInventory.object_type == object_type)
    if search:
        query = query.filter(ConfigurationInventory.name.ilike(f'%{search}%'))

    rows = query.order_by(
        Cluster.name,
        ConfigurationInventory.namespace,
        ConfigurationInventory.object_type,
        ConfigurationInventory.name,
    ).all()

    items = [
        {
            'id': item.id,
            'cluster_name': cluster_name,
            'namespace': item.namespace,
            'name': item.name,
            'type': item.object_type,
            'secret_type': item.secret_type,
            'key_count': item.key_count,
            'immutable': item.immutable,
            'payload_size': format_byte_count(item.payload_size_bytes),
            'age': format_age(item.created_at),
        }
        for item, cluster_name in rows
    ]

    return {
        'items': items,
        'total_items': len(items),
        'config_maps': sum(1 for item in items if item['type'] == 'ConfigMap'),
        'secrets': sum(1 for item in items if item['type'] == 'Secret'),
        'immutable_items': sum(1 for item in items if item['immutable']),
        'namespaces': get_configuration_filter_namespaces(cluster_id),
        'types': ['ConfigMap', 'Secret'],
    }


def get_configuration_detail(
    configuration_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            ConfigurationInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)
        .filter(ConfigurationInventory.id == configuration_id)
        .first()
    )

    if result is None:
        return None

    item, cluster_name = result
    candidate_pods = (
        PodInventory.query.filter_by(
            cluster_id=item.cluster_id,
            namespace=item.namespace,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )

    used_by = []
    for pod in candidate_pods:
        references = pod.configuration_references or []
        if any(
            reference.get('type') == item.object_type and reference.get('name') == item.name for reference in references
        ):
            used_by.append(
                {
                    **_pod_summary(pod),
                    'workload_type': pod.workload_type or '-',
                    'workload_name': pod.workload_name or '-',
                }
            )

    return {
        'id': item.id,
        'cluster_name': cluster_name,
        'namespace': item.namespace,
        'name': item.name,
        'type': item.object_type,
        'secret_type': item.secret_type or '-',
        'key_names': item.key_names or [],
        'key_count': item.key_count,
        'immutable': item.immutable,
        'payload_size': format_byte_count(item.payload_size_bytes),
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'used_by_count': len(used_by),
        'used_by': used_by[:8],
        'used_by_truncated': len(used_by) > 8,
    }


def format_age(
    created_at,
) -> str:
    if not created_at:
        return '-'

    normalized_created_at = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - normalized_created_at

    days = delta.days

    if days > 0:
        return f'{days}d'

    hours = delta.seconds // 3600

    return f'{hours}h'


def get_workload_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.namespace,
    )

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.namespace,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_workload_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.workload_type,
    )

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            WorkloadInventory.namespace == namespace,
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
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.status,
    )

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            WorkloadInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.status,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def _workload_update_strategy(
    workload_type: str,
    details: dict[str, Any],
) -> tuple[str, str]:
    if workload_type in {'Job', 'CronJob'}:
        return 'Not applicable', 'not_applicable'

    delivery_rows = details.get('delivery_rows') or []

    if not isinstance(delivery_rows, list):
        return 'Not reported', 'unknown'

    for row in delivery_rows:
        if not isinstance(row, dict):
            continue

        label = str(row.get('label') or '').strip().lower()

        if label not in {'strategy', 'update strategy'}:
            continue

        raw_value = str(row.get('value') or '').strip()

        if not raw_value or raw_value in {'-', 'None'}:
            break

        normalized_value = raw_value.replace(' ', '').lower()

        return _WORKLOAD_UPDATE_STRATEGIES.get(
            normalized_value,
            (raw_value, 'other'),
        )

    return 'Not reported', 'unknown'


def get_workload_inventory(
    cluster_id=None,
    namespace=None,
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

    if namespace:
        query = query.filter(WorkloadInventory.namespace == namespace)

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

    pod_count_map: dict[tuple[str, str, str, str], int] = {}

    if workloads:
        cluster_ids = sorted({workload.cluster_id for workload, _ in workloads})

        pod_counts = (
            db.session.query(
                PodInventory.cluster_id,
                PodInventory.namespace,
                PodInventory.workload_type,
                PodInventory.workload_name,
                func.count(PodInventory.id),
            )
            .filter(PodInventory.cluster_id.in_(cluster_ids))
            .filter(PodInventory.workload_type.is_not(None))
            .filter(PodInventory.workload_name.is_not(None))
            .group_by(
                PodInventory.cluster_id,
                PodInventory.namespace,
                PodInventory.workload_type,
                PodInventory.workload_name,
            )
            .all()
        )

        pod_count_map = {
            (cluster_key, namespace, pod_workload_type, pod_workload_name): count
            for cluster_key, namespace, pod_workload_type, pod_workload_name, count in pod_counts
        }

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}

    deployments = 0
    statefulsets = 0
    daemonsets = 0
    jobs = 0
    cronjobs = 0

    workloads_data = []

    for workload, cluster_name in workloads:
        current_type = workload.workload_type or 'Unknown'
        status_name = workload.status or 'Unknown'
        details = workload.details or {}
        pod_template = details.get('pod_template') or {}

        type_counts[current_type] = type_counts.get(current_type, 0) + 1
        status_counts[status_name] = status_counts.get(status_name, 0) + 1

        if current_type == 'Deployment':
            deployments += 1
        elif current_type == 'StatefulSet':
            statefulsets += 1
        elif current_type == 'DaemonSet':
            daemonsets += 1
        elif current_type == 'Job':
            jobs += 1
        elif current_type == 'CronJob':
            cronjobs += 1

        pod_count = pod_count_map.get(
            (
                workload.cluster_id,
                workload.namespace,
                current_type,
                workload.name,
            ),
            0,
        )

        update_strategy, update_strategy_key = _workload_update_strategy(
            current_type,
            details,
        )

        workloads_data.append(
            {
                'id': workload.id,
                'cluster_name': cluster_name,
                'namespace': workload.namespace,
                'name': workload.name,
                'type': current_type,
                'ready': workload.ready,
                'status': status_name,
                'state_display': details.get('state_display') or workload.ready or status_name,
                'pod_count': pod_count,
                'update_strategy': update_strategy,
                'update_strategy_key': update_strategy_key,
                'container_count': int(pod_template.get('container_count') or 0),
                'init_container_count': int(pod_template.get('init_container_count') or 0),
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
        'namespaces': get_workload_filter_namespaces(
            cluster_id=cluster_id,
        ),
        'workload_types': get_workload_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'workload_statuses': get_workload_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'workloads': workloads_data,
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
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.phase,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            PodInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.phase,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_pod_filter_owner_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.workload_type,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            PodInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.workload_type,
        )
        .all()
    )

    owner_types = [row[0] for row in rows if row[0]]
    standalone_exists = db.session.query(PodInventory.id).filter(
        PodInventory.workload_type.is_(None),
    )
    if cluster_id:
        standalone_exists = standalone_exists.filter(
            PodInventory.cluster_id == cluster_id,
        )
    if namespace:
        standalone_exists = standalone_exists.filter(
            PodInventory.namespace == namespace,
        )
    if standalone_exists.first() is not None:
        owner_types.append('Standalone')

    return sorted(set(owner_types))


def get_pod_filter_nodes(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.node_name,
    ).filter(
        PodInventory.node_name.is_not(None),
        PodInventory.node_name != '',
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            PodInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.node_name,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def _pod_container_count(pod: PodInventory) -> int:
    details = pod.details or {}
    configuration = details.get('configuration') or {}
    configured_count = configuration.get('container_count')
    if configured_count is not None:
        try:
            return int(configured_count)
        except (TypeError, ValueError):
            pass

    if pod.container_names:
        return len(pod.container_names)

    ready_value = pod.ready or ''
    if '/' in ready_value:
        try:
            return int(ready_value.split('/', maxsplit=1)[1])
        except (TypeError, ValueError):
            pass

    return 0


def _pod_ready_values(value: str | None) -> tuple[int, int]:
    if not value or '/' not in value:
        return 0, 0

    ready, total = value.split('/', maxsplit=1)
    try:
        return int(ready), int(total)
    except (TypeError, ValueError):
        return 0, 0


def _parse_inventory_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def get_pod_inventory(
    cluster_id=None,
    namespace=None,
    status=None,
    owner_type=None,
    node=None,
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

    if owner_type == 'Standalone':
        query = query.filter(PodInventory.workload_type.is_(None))
    elif owner_type:
        query = query.filter(PodInventory.workload_type == owner_type)

    if node:
        query = query.filter(PodInventory.node_name == node)

    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                PodInventory.pod_name.ilike(pattern),
                PodInventory.pod_ip.ilike(pattern),
                PodInventory.workload_name.ilike(pattern),
                PodInventory.node_name.ilike(pattern),
            )
        )

    pods = query.order_by(
        Cluster.name,
        PodInventory.namespace,
        PodInventory.pod_name,
    ).all()

    status_counts: dict[str, int] = {}
    pod_data = []

    running = 0
    pending = 0
    failed = 0

    for pod, cluster_name in pods:
        phase = pod.phase or 'Unknown'
        status_counts[phase] = status_counts.get(phase, 0) + 1

        if phase == 'Running':
            running += 1
        elif phase == 'Pending':
            pending += 1
        elif phase == 'Failed':
            failed += 1

        container_images = pod.container_images or []
        init_container_images = pod.init_container_images or []
        all_images = container_images + init_container_images
        image_count = pod.image_count or len(all_images)
        ready_count, total_count = _pod_ready_values(pod.ready)
        container_count = _pod_container_count(pod)

        pod_data.append(
            {
                'id': pod.id,
                'cluster_name': cluster_name,
                'namespace': pod.namespace,
                'name': pod.pod_name,
                'node': pod.node_name,
                'ready': pod.ready or '0/0',
                'ready_count': ready_count,
                'ready_total': total_count,
                'restarts': pod.restart_count or 0,
                'ip': pod.pod_ip,
                'status': phase,
                'owner_type': pod.workload_type or 'Standalone',
                'owner_name': pod.workload_name or '-',
                'container_count': container_count,
                'container_images': container_images,
                'init_container_images': init_container_images,
                'all_images': all_images,
                'image_count': image_count,
            }
        )

    return {
        'total_pods': len(pods),
        'running': running,
        'pending': pending,
        'failed': failed,
        'total_image_references': sum(pod.get('image_count', 0) for pod in pod_data),
        'unique_image_count': len({image for pod in pod_data for image in pod.get('all_images', [])}),
        'status_counts': status_counts,
        'pod_statuses': get_pod_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'owner_types': get_pod_filter_owner_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'nodes': get_pod_filter_nodes(
            cluster_id=cluster_id,
            namespace=namespace,
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
    details = pod.details or {}
    configuration = details.get('configuration') or {}
    placement = details.get('placement') or {}
    conditions = details.get('conditions') or []
    container_statuses = details.get('container_statuses') or []
    volumes = details.get('volumes') or []
    owner_chain = details.get('owner_chain') or []

    if not owner_chain:
        if pod.workload_type and pod.workload_name:
            owner_chain.append(
                {
                    'kind': pod.workload_type,
                    'name': pod.workload_name,
                }
            )
        owner_chain.append({'kind': 'Pod', 'name': pod.pod_name})

    if not container_statuses:
        container_statuses = []
        names = pod.container_names or []
        images = pod.container_images or []
        for index, image in enumerate(images):
            container_statuses.append(
                {
                    'name': names[index] if index < len(names) else f'container-{index + 1}',
                    'kind': 'Regular',
                    'image': image,
                    'image_id': '-',
                    'pull_policy': '-',
                    'ready': False,
                    'started': False,
                    'restart_count': 0,
                    'state': 'Not reported',
                    'reason': None,
                    'message': None,
                    'started_at': None,
                    'finished_at': None,
                    'exit_code': None,
                    'previous_state': 'Unknown',
                    'previous_reason': None,
                }
            )

        for index, image in enumerate(pod.init_container_images or []):
            container_statuses.append(
                {
                    'name': f'init-container-{index + 1}',
                    'kind': 'Init',
                    'image': image,
                    'image_id': '-',
                    'pull_policy': '-',
                    'ready': False,
                    'started': False,
                    'restart_count': 0,
                    'state': 'Not reported',
                    'reason': None,
                    'message': None,
                    'started_at': None,
                    'finished_at': None,
                    'exit_code': None,
                    'previous_state': 'Unknown',
                    'previous_reason': None,
                }
            )

    for container in container_statuses:
        container['started_at_value'] = _parse_inventory_datetime(
            container.get('started_at'),
        )
        container['finished_at_value'] = _parse_inventory_datetime(
            container.get('finished_at'),
        )

    labels = dict(sorted((pod.labels or {}).items()))
    annotations = dict(sorted((details.get('annotations') or {}).items()))
    ready_count, ready_total = _pod_ready_values(pod.ready)

    return {
        'id': pod.id,
        'cluster_name': cluster_name,
        'namespace': pod.namespace,
        'name': pod.pod_name,
        'node': pod.node_name,
        'ready': pod.ready or '0/0',
        'ready_count': ready_count,
        'ready_total': ready_total,
        'restarts': pod.restart_count or 0,
        'ip': pod.pod_ip,
        'host_ip': details.get('host_ip'),
        'status': pod.phase or 'Unknown',
        'reason': details.get('reason'),
        'message': details.get('message'),
        'qos_class': details.get('qos_class') or '-',
        'owner_type': pod.workload_type or 'Standalone',
        'owner_name': pod.workload_name or '-',
        'owner_chain': owner_chain,
        'uid': details.get('uid') or '-',
        'conditions': conditions,
        'placement': {
            'scheduler': placement.get('scheduler') or '-',
            'priority_class': placement.get('priority_class') or '-',
            'node_selector': placement.get('node_selector') or {},
            'tolerations': placement.get('tolerations') or [],
            'affinity_configured': bool(placement.get('affinity_configured')),
            'topology_spread_count': int(placement.get('topology_spread_count') or 0),
            'host_network': bool(placement.get('host_network')),
        },
        'configuration': {
            'service_account': configuration.get('service_account') or 'default',
            'restart_policy': configuration.get('restart_policy') or '-',
            'dns_policy': configuration.get('dns_policy') or '-',
            'runtime_class': configuration.get('runtime_class') or '-',
            'security_context_configured': bool(configuration.get('security_context_configured')),
            'image_pull_secret_count': int(configuration.get('image_pull_secret_count') or 0),
            'volume_count': int(configuration.get('volume_count') or len(volumes)),
            'container_count': int(configuration.get('container_count') or _pod_container_count(pod)),
            'init_container_count': int(
                configuration.get('init_container_count') or len(pod.init_container_images or [])
            ),
            'ephemeral_container_count': int(configuration.get('ephemeral_container_count') or 0),
        },
        'container_statuses': container_statuses,
        'volumes': volumes,
        'labels': labels,
        'annotations': annotations,
        'age': format_age(pod.created_at),
        'created_at': pod.created_at,
        'collected_at': pod.collected_at,
        'details_reported': bool(details),
    }


def get_service_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(ServiceInventory.service_type)

    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)

    rows = query.distinct().order_by(ServiceInventory.service_type).all()
    types = [row[0] for row in rows if row[0]]

    headless_query = db.session.query(
        ServiceInventory.id,
    ).filter(
        ServiceInventory.service_type == 'ClusterIP',
        ServiceInventory.cluster_ip == 'None',
    )
    if cluster_id:
        headless_query = headless_query.filter(
            ServiceInventory.cluster_id == cluster_id,
        )
    if namespace:
        headless_query = headless_query.filter(
            ServiceInventory.namespace == namespace,
        )

    if headless_query.first() is not None and 'Headless' not in types:
        types.append('Headless')

    return sorted(types)


def get_service_inventory(
    cluster_id=None,
    namespace=None,
    service_type=None,
    search=None,
):
    query = db.session.query(
        ServiceInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ServiceInventory.cluster_id)

    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)
    if service_type:
        if service_type == 'Headless':
            query = query.filter(
                ServiceInventory.service_type == 'ClusterIP',
                ServiceInventory.cluster_ip == 'None',
            )
        elif service_type == 'ClusterIP':
            query = query.filter(
                ServiceInventory.service_type == 'ClusterIP',
                ServiceInventory.cluster_ip != 'None',
            )
        else:
            query = query.filter(ServiceInventory.service_type == service_type)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                ServiceInventory.service_name.ilike(pattern),
                ServiceInventory.cluster_ip.ilike(pattern),
                ServiceInventory.external_ip.ilike(pattern),
                ServiceInventory.ports.ilike(pattern),
            )
        )

    services = query.order_by(
        Cluster.name,
        ServiceInventory.namespace,
        ServiceInventory.service_name,
    ).all()

    namespace_query = db.session.query(ServiceInventory.namespace).distinct()
    if cluster_id:
        namespace_query = namespace_query.filter(ServiceInventory.cluster_id == cluster_id)
    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    services_data: list[dict[str, Any]] = []
    cluster_ip_count = 0
    node_port_count = 0
    load_balancer_count = 0
    external_name_count = 0
    headless_count = 0
    service_types: dict[str, int] = {}

    for service, cluster_name in services:
        raw_type = service.service_type or 'Unknown'
        effective_type = 'Headless' if raw_type == 'ClusterIP' and service.cluster_ip == 'None' else raw_type
        service_types[effective_type] = service_types.get(effective_type, 0) + 1

        if effective_type == 'ClusterIP':
            cluster_ip_count += 1
        elif effective_type == 'NodePort':
            node_port_count += 1
        elif effective_type == 'LoadBalancer':
            load_balancer_count += 1
        elif effective_type == 'ExternalName':
            external_name_count += 1
        elif effective_type == 'Headless':
            headless_count += 1

        details = service.details or {}
        endpoints = details.get('endpoints') or {}
        ready_endpoint_count = len(endpoints.get('ready_addresses') or [])
        not_ready_endpoint_count = len(endpoints.get('not_ready_addresses') or [])
        port_rows = _service_port_rows(service)
        port_summary = '-'
        if port_rows:
            first = port_rows[0]
            port_summary = f'{first["port"]}/{first["protocol"]}'
            if len(port_rows) > 1:
                port_summary = f'{port_summary} +{len(port_rows) - 1}'

        external_addresses = _split_inventory_values(service.external_ip)
        services_data.append(
            {
                'id': service.id,
                'cluster_name': cluster_name,
                'namespace': service.namespace,
                'service_name': service.service_name,
                'service_type': effective_type,
                'cluster_ip': service.cluster_ip or '-',
                'external_address': external_addresses[0] if external_addresses else '-',
                'external_address_count': len(external_addresses),
                'port_count': len(port_rows),
                'port_summary': port_summary,
                'endpoint_count': ready_endpoint_count,
                'not_ready_endpoint_count': not_ready_endpoint_count,
                'endpoints_reported': bool(endpoints.get('reported')),
                'created_at': service.created_at,
                'collected_at': service.collected_at,
            }
        )

    return {
        'total_services': len(services),
        'cluster_ip': cluster_ip_count,
        'node_port': node_port_count,
        'load_balancer': load_balancer_count,
        'external_name': external_name_count,
        'headless': headless_count,
        'namespaces': namespaces,
        'service_filter_types': get_service_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'service_types': service_types,
        'services': services_data,
    }


def get_ingress_filter_classes(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(IngressInventory.ingress_class)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)

    rows = query.distinct().order_by(IngressInventory.ingress_class).all()
    return [row[0] for row in rows if row[0]]


def get_ingress_inventory(
    cluster_id=None,
    namespace=None,
    ingress_class=None,
    tls_status=None,
    search=None,
):
    query = db.session.query(
        IngressInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == IngressInventory.cluster_id)

    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)
    if ingress_class:
        query = query.filter(IngressInventory.ingress_class == ingress_class)
    if tls_status == 'enabled':
        query = query.filter(IngressInventory.tls_enabled.is_(True))
    elif tls_status == 'disabled':
        query = query.filter(IngressInventory.tls_enabled.is_(False))
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                IngressInventory.ingress_name.ilike(pattern),
                IngressInventory.host.ilike(pattern),
                IngressInventory.address.ilike(pattern),
                IngressInventory.ingress_class.ilike(pattern),
            )
        )

    ingresses = query.order_by(
        Cluster.name,
        IngressInventory.namespace,
        IngressInventory.ingress_name,
    ).all()

    namespace_query = db.session.query(IngressInventory.namespace).distinct()
    if cluster_id:
        namespace_query = namespace_query.filter(IngressInventory.cluster_id == cluster_id)
    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    ingress_data: list[dict[str, Any]] = []
    tls_enabled_count = 0
    hosts: set[str] = set()
    classes: set[str] = set()

    for ingress, cluster_name in ingresses:
        details = ingress.details or {}
        ingress_hosts = [value for value in (details.get('hosts') or []) if value]
        if not ingress_hosts and ingress.host and ingress.host != '-':
            ingress_hosts = [ingress.host]

        tls_entries = details.get('tls') or []
        if ingress.tls_enabled:
            tls_enabled_count += 1
        hosts.update(ingress_hosts)
        if ingress.ingress_class:
            classes.add(ingress.ingress_class)

        ingress_data.append(
            {
                'id': ingress.id,
                'cluster_name': cluster_name,
                'namespace': ingress.namespace,
                'name': ingress.ingress_name,
                'class': ingress.ingress_class or '-',
                'host': ingress_hosts[0] if ingress_hosts else '-',
                'host_count': len(ingress_hosts),
                'address': ingress.address or '-',
                'tls': ingress.tls_enabled,
                'tls_secret_count': len(
                    {
                        item.get('secret_name')
                        for item in tls_entries
                        if isinstance(item, dict) and item.get('secret_name') not in (None, '', '-')
                    }
                ),
                'backend_count': len(ingress.backend_paths or []),
                'created_at': ingress.created_at,
                'collected_at': ingress.collected_at,
            }
        )

    return {
        'total_ingresses': len(ingresses),
        'tls_enabled': tls_enabled_count,
        'tls_disabled': len(ingresses) - tls_enabled_count,
        'total_hosts': len(hosts),
        'ingress_classes': len(classes),
        'classes': get_ingress_filter_classes(
            cluster_id=cluster_id,
            namespace=namespace,
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
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == IngressInventory.cluster_id)
        .filter(IngressInventory.id == ingress_id)
        .first()
    )

    if result is None:
        return None

    ingress, cluster_name = result
    backend_paths = ingress.backend_paths or []
    details = dict(ingress.details or {})
    raw_hosts = [value for value in (details.get('hosts') or []) if value]
    if not raw_hosts:
        raw_hosts = sorted(
            {
                item.get('host')
                for item in backend_paths
                if isinstance(item, dict) and item.get('host') not in (None, '', '-')
            }
        )
    services = sorted(
        {
            item.get('service_name')
            for item in backend_paths
            if isinstance(item, dict) and item.get('service_name') not in (None, '', '-')
        }
    )
    tls_entries = [item for item in (details.get('tls') or []) if isinstance(item, dict)]
    tls_secrets = sorted(
        {item.get('secret_name') for item in tls_entries if item.get('secret_name') not in (None, '', '-')}
    )
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}

    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': ingress.ingress_class or '-',
        'uid': details.get('uid') or '-',
        'generation': int(details.get('generation') or 0),
        'host': ingress.host or '-',
        'hosts': [
            {
                'value': host,
                'url': f'{"https" if ingress.tls_enabled else "http"}://{host}',
            }
            for host in raw_hosts
        ],
        'address': ingress.address or '-',
        'tls': ingress.tls_enabled,
        'tls_entries': tls_entries,
        'tls_secrets': tls_secrets,
        'backend_paths': backend_paths,
        'backend_count': len(backend_paths),
        'host_count': len(raw_hosts),
        'service_count': len(services),
        'rule_count': int(details.get('rule_count') or 0),
        'default_backend': details.get('default_backend'),
        'finalizers': details.get('finalizers') or [],
        'age': format_age(ingress.created_at),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
        'details_reported': bool(details),
    }


def get_storage_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(StorageInventory.storage_type)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    rows = query.distinct().order_by(StorageInventory.storage_type).all()
    return [row[0] for row in rows if row[0]]


def get_storage_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
    storage_type: str | None = None,
) -> list[str]:
    query = db.session.query(StorageInventory.status)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)
    rows = query.distinct().order_by(StorageInventory.status).all()
    return [row[0] for row in rows if row[0]]


def get_storage_inventory_view(
    cluster_id=None,
    namespace=None,
    storage_type=None,
    status=None,
    search=None,
):
    query = db.session.query(
        StorageInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == StorageInventory.cluster_id)

    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)
    if status:
        query = query.filter(StorageInventory.status == status)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                StorageInventory.name.ilike(pattern),
                StorageInventory.storage_class.ilike(pattern),
                StorageInventory.status.ilike(pattern),
            )
        )

    items = query.order_by(
        Cluster.name,
        StorageInventory.storage_type,
        StorageInventory.name,
    ).all()

    namespace_query = db.session.query(StorageInventory.namespace).distinct()
    if cluster_id:
        namespace_query = namespace_query.filter(StorageInventory.cluster_id == cluster_id)
    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    data: list[dict[str, Any]] = []
    storage_classes = 0
    persistent_volumes = 0
    persistent_volume_claims = 0
    storage_types: dict[str, int] = {
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
        if item.storage_type in {'StorageClass', 'PersistentVolume'}:
            namespace_display = 'Cluster-wide'
        elif not namespace_display:
            namespace_display = '-'

        details = item.details or {}
        if item.storage_type == 'PersistentVolume':
            binding = (
                f'{details.get("claim_namespace")}/{details.get("claim_name")}'
                if details.get('claim_namespace') and details.get('claim_name')
                else 'Unbound'
            )
        elif item.storage_type == 'PersistentVolumeClaim':
            binding = details.get('volume_name') or 'Unbound'
        else:
            binding = details.get('provisioner') or '-'

        capacity = item.capacity
        if item.storage_type == 'PersistentVolumeClaim' and details.get('requested_storage'):
            capacity = details.get('requested_storage')

        data.append(
            {
                'id': item.id,
                'cluster_name': cluster_name,
                'namespace': namespace_display,
                'name': item.name,
                'type': item.storage_type,
                'storage_class': item.storage_class or '-',
                'capacity': format_kubernetes_size(capacity),
                'status': item.status or 'Unknown',
                'binding': binding,
                'is_default': bool(details.get('is_default')),
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
            namespace=namespace,
        ),
        'storage_filter_statuses': get_storage_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
            storage_type=storage_type,
        ),
        'storage_types': storage_types,
        'storage_items': data,
    }
