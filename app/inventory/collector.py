from typing import cast

from kubernetes.client import (
    AppsV1Api,
    BatchV1Api,
    CoreV1Api,
    NetworkingV1Api,
    StorageV1Api,
    V1CronJobList,
    V1DaemonSetList,
    V1DeploymentList,
    V1IngressList,
    V1JobList,
    V1Node,
    V1NodeList,
    V1PersistentVolumeClaimList,
    V1PersistentVolumeList,
    V1PodList,
    V1ServiceList,
    V1StatefulSetList,
    V1StorageClassList,
    VersionApi,
)
from kubernetes.client.models.version_info import VersionInfo
from kubernetes.client.exceptions import ApiException, NotFoundException


def get_cluster_version(
    api: CoreV1Api,
) -> str:
    version_api = VersionApi(
        api.api_client,
    )

    version = cast(
        VersionInfo,
        version_api.get_code(),
    )

    return version.git_version or 'unknown'


def get_nodes(
    api: CoreV1Api,
) -> list[V1Node]:
    result = cast(
        V1NodeList,
        api.list_node(),
    )

    if result.items is None:
        return []

    return result.items


def get_workloads(
    api: AppsV1Api,
    batch_api: BatchV1Api | None = None,
) -> list[dict]:
    workloads: list[dict] = []

    deployments = cast(
        V1DeploymentList,
        api.list_deployment_for_all_namespaces(),
    )

    deployment_items = deployments.items or []

    deployment_items = deployments.items or []

    for deployment in deployment_items:
        metadata = deployment.metadata
        spec = deployment.spec
        status = deployment.status

        desired = spec.replicas or 0
        ready = status.ready_replicas or 0

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'Deployment',
                'ready': f'{ready}/{desired}',
                'status': ('Running' if ready == desired else 'Progressing'),
                'created_at': metadata.creation_timestamp,
            }
        )

    statefulsets = cast(
        V1StatefulSetList,
        api.list_stateful_set_for_all_namespaces(),
    )

    statefulset_items = statefulsets.items or []

    for statefulset in statefulset_items:
        metadata = statefulset.metadata
        spec = statefulset.spec
        status = statefulset.status

        desired = spec.replicas or 0
        ready = status.ready_replicas or 0

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'StatefulSet',
                'ready': f'{ready}/{desired}',
                'status': ('Running' if ready == desired else 'Progressing'),
                'created_at': metadata.creation_timestamp,
            }
        )

    daemonsets = cast(
        V1DaemonSetList,
        api.list_daemon_set_for_all_namespaces(),
    )

    daemonset_items = daemonsets.items or []

    for daemonset in daemonset_items:
        metadata = daemonset.metadata
        status = daemonset.status

        desired = status.desired_number_scheduled or 0

        ready = status.number_ready or 0

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'DaemonSet',
                'ready': f'{ready}/{desired}',
                'status': ('Running' if ready == desired else 'Progressing'),
                'created_at': metadata.creation_timestamp,
            }
        )

    if batch_api is None:
        return workloads

    jobs = cast(
        V1JobList,
        batch_api.list_job_for_all_namespaces(),
    )

    job_items = jobs.items or []

    for job in job_items:
        metadata = job.metadata
        spec = job.spec
        status = job.status

        if metadata is None:
            continue

        completions = spec.completions if spec and spec.completions is not None else 1

        succeeded = status.succeeded if status and status.succeeded is not None else 0

        failed = status.failed if status and status.failed is not None else 0

        active = status.active if status and status.active is not None else 0

        if failed > 0:
            job_status = 'Failed'

        elif succeeded >= completions:
            job_status = 'Running'

        elif active > 0:
            job_status = 'Progressing'

        else:
            job_status = 'Progressing'

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'Job',
                'ready': f'{succeeded}/{completions}',
                'status': job_status,
                'created_at': metadata.creation_timestamp,
            }
        )

    try:
        cronjobs = cast(
            V1CronJobList,
            batch_api.list_cron_job_for_all_namespaces(),
        )
        cronjob_items = cronjobs.items or []
    except NotFoundException:
        cronjob_items = []
    except ApiException as exc:
        if getattr(
            exc,
            'status',
            None,
        ) == 404:
            cronjob_items = []
        else:
            raise

    for cronjob in cronjob_items:
        metadata = cronjob.metadata
        spec = cronjob.spec
        status = cronjob.status

        if metadata is None:
            continue

        active_count = len(status.active or []) if status else 0

        schedule = spec.schedule if spec and spec.schedule else '-'

        cronjob_status = 'Running'

        if spec and spec.suspend:
            cronjob_status = 'Suspended'

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'CronJob',
                'ready': f'{active_count} active',
                'status': cronjob_status,
                'created_at': metadata.creation_timestamp,
                'schedule': schedule,
            }
        )

    return workloads


def get_pods(
    api: CoreV1Api,
) -> list[dict]:
    result = cast(
        V1PodList,
        api.list_pod_for_all_namespaces(),
    )

    pods = []

    for pod in result.items or []:
        metadata = pod.metadata
        status = pod.status
        spec = pod.spec

        if metadata is None:
            continue

        container_statuses = status.container_statuses or []

        total_containers = len(
            container_statuses,
        )

        ready_containers = sum(1 for container in container_statuses if container.ready)

        restart_count = sum(container.restart_count for container in container_statuses)

        containers = spec.containers if spec and spec.containers else []

        init_containers = spec.init_containers if spec and spec.init_containers else []

        container_images = [container.image for container in containers if container.image]

        init_container_images = [container.image for container in init_containers if container.image]

        image_count = len(container_images) + len(init_container_images)

        pods.append(
            {
                'namespace': metadata.namespace,
                'pod_name': metadata.name,
                'node_name': (spec.node_name if spec else None),
                'phase': (status.phase if status else None),
                'pod_ip': (status.pod_ip if status else None),
                'ready': (f'{ready_containers}/{total_containers}'),
                'restart_count': restart_count,
                'container_images': container_images,
                'init_container_images': init_container_images,
                'image_count': image_count,
                'created_at': (metadata.creation_timestamp),
            }
        )

    return pods


def get_services(
    api: CoreV1Api,
) -> list[dict]:
    result = cast(
        V1ServiceList,
        api.list_service_for_all_namespaces(),
    )

    services = []

    for svc in result.items or []:
        metadata = svc.metadata
        spec = svc.spec

        if metadata is None:
            continue

        if spec is None:
            continue

        ports = []

        for port in spec.ports or []:
            ports.append(f'{port.port}/{port.protocol}')

        services.append(
            {
                'namespace': metadata.namespace,
                'service_name': metadata.name,
                'service_type': spec.type,
                'cluster_ip': spec.cluster_ip,
                'external_ip': (','.join(spec.external_ips) if spec.external_ips else '-'),
                'ports': ','.join(ports),
                'created_at': metadata.creation_timestamp,
            }
        )

    return services


def get_ingresses(
    api: NetworkingV1Api,
) -> list[dict]:
    result = cast(
        V1IngressList,
        api.list_ingress_for_all_namespaces(),
    )

    ingresses = []

    for ingress in result.items or []:
        metadata = ingress.metadata
        spec = ingress.spec
        status = ingress.status

        if metadata is None:
            continue

        host = '-'
        backend_paths = []

        def _backend_to_dict(backend):
            service = getattr(
                backend,
                'service',
                None,
            )

            if service is None:
                return {
                    'service_name': '-',
                    'service_port': '-',
                }

            port = getattr(
                service,
                'port',
                None,
            )

            port_value = '-'

            if port is not None:
                port_value = (
                    getattr(
                        port,
                        'name',
                        None,
                    )
                    or getattr(
                        port,
                        'number',
                        None,
                    )
                    or '-'
                )

            return {
                'service_name': getattr(
                    service,
                    'name',
                    None,
                )
                or '-',
                'service_port': str(
                    port_value,
                ),
            }

        if spec and spec.default_backend:
            backend_info = _backend_to_dict(
                spec.default_backend,
            )

            backend_paths.append(
                {
                    'host': '-',
                    'path': '/',
                    'path_type': 'DefaultBackend',
                    **backend_info,
                }
            )

        if spec and spec.rules:
            host = spec.rules[0].host or '-'

            for rule in spec.rules:
                rule_host = rule.host or '-'
                http_rule = getattr(
                    rule,
                    'http',
                    None,
                )

                if not http_rule or not http_rule.paths:
                    continue

                for path in http_rule.paths:
                    backend_info = _backend_to_dict(
                        path.backend,
                    )

                    backend_paths.append(
                        {
                            'host': rule_host,
                            'path': path.path or '/',
                            'path_type': path.path_type or '-',
                            **backend_info,
                        }
                    )

        addresses = []

        if status and status.load_balancer and status.load_balancer.ingress:
            for item in status.load_balancer.ingress:
                if item.ip:
                    addresses.append(item.ip)

                elif item.hostname:
                    addresses.append(item.hostname)

        address = ', '.join(addresses) if addresses else '-'

        tls_enabled = bool(spec and spec.tls)

        ingresses.append(
            {
                'namespace': metadata.namespace,
                'ingress_name': metadata.name,
                'ingress_class': (
                    spec.ingress_class_name
                    if spec and spec.ingress_class_name
                    else (metadata.annotations or {}).get('kubernetes.io/ingress.class')
                ),
                'host': host,
                'address': address,
                'tls_enabled': tls_enabled,
                'backend_paths': backend_paths,
                'created_at': metadata.creation_timestamp,
            }
        )

    return ingresses


def get_storage_inventory(
    core_api: CoreV1Api,
    storage_api: StorageV1Api,
) -> list[dict]:
    items = []

    storage_classes = cast(
        V1StorageClassList,
        storage_api.list_storage_class(),
    )

    for storage_class in storage_classes.items or []:
        metadata = storage_class.metadata

        if metadata is None:
            continue

        items.append(
            {
                'namespace': None,
                'name': metadata.name,
                'storage_type': 'StorageClass',
                'storage_class': metadata.name,
                'capacity': '-',
                'status': 'Available',
                'created_at': metadata.creation_timestamp,
            }
        )

    persistent_volumes = cast(
        V1PersistentVolumeList,
        core_api.list_persistent_volume(),
    )

    for pv in persistent_volumes.items or []:
        metadata = pv.metadata
        spec = pv.spec
        status = pv.status

        if metadata is None:
            continue

        capacity = '-'

        if spec and spec.capacity:
            capacity = spec.capacity.get(
                'storage',
                '-',
            )

        items.append(
            {
                'namespace': None,
                'name': metadata.name,
                'storage_type': 'PersistentVolume',
                'storage_class': (spec.storage_class_name if spec else None),
                'capacity': capacity,
                'status': (status.phase if status else None),
                'created_at': metadata.creation_timestamp,
            }
        )

    pvcs = cast(
        V1PersistentVolumeClaimList,
        core_api.list_persistent_volume_claim_for_all_namespaces(),
    )

    for pvc in pvcs.items or []:
        metadata = pvc.metadata
        spec = pvc.spec
        status = pvc.status

        if metadata is None:
            continue

        capacity = '-'

        if status and status.capacity:
            capacity = status.capacity.get(
                'storage',
                '-',
            )

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'storage_type': 'PersistentVolumeClaim',
                'storage_class': (spec.storage_class_name if spec else None),
                'capacity': capacity,
                'status': (status.phase if status else None),
                'created_at': metadata.creation_timestamp,
            }
        )

    return items
