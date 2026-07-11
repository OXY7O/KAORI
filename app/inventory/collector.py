import base64
from typing import cast

from kubernetes.client import (
    AppsV1Api,
    BatchV1Api,
    CoreV1Api,
    NetworkingV1Api,
    StorageV1Api,
    V1ConfigMapList,
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
    V1ReplicaSetList,
    V1ResourceQuotaList,
    V1SecretList,
    V1ServiceList,
    V1StatefulSetList,
    V1StorageClassList,
    VersionApi,
)
from kubernetes.client.exceptions import ApiException, NotFoundException
from kubernetes.client.models.version_info import VersionInfo


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


def _isoformat_datetime(value) -> str | None:
    if value is None:
        return None

    isoformat = getattr(value, 'isoformat', None)
    if callable(isoformat):
        return isoformat()

    return str(value)


def _string_value(value, default: str = '-') -> str:
    if value is None or value == '':
        return default

    return str(value)


def _model_value(source, *keys: str, default=None):
    """Read Kubernetes model attributes and raw/dict payloads consistently."""
    if source is None:
        return default

    for key in keys:
        if isinstance(source, dict):
            if key in source:
                return source[key]
        else:
            value = getattr(source, key, None)
            if value is not None:
                return value

    return default


def _metadata_details(metadata) -> dict:
    labels = dict(sorted((_model_value(metadata, 'labels', default={}) or {}).items()))
    annotations = dict(sorted((_model_value(metadata, 'annotations', default={}) or {}).items()))

    return {
        'uid': _string_value(_model_value(metadata, 'uid')),
        'labels': labels,
        'annotations': annotations,
    }


def _toleration_display(toleration) -> str:
    key = _model_value(toleration, 'key') or '*'
    operator = _model_value(toleration, 'operator') or 'Equal'
    value = _model_value(toleration, 'value')
    effect = _model_value(toleration, 'effect')

    expression = key
    if operator == 'Exists':
        expression = f'{key} exists'
    elif value not in (None, ''):
        expression = f'{key}={value}'

    if effect:
        expression = f'{expression}:{effect}'

    return expression


def _workload_pod_template_spec(workload_spec):
    template = _model_value(workload_spec, 'template')
    return _model_value(template, 'spec')


def _cronjob_pod_template_spec(cronjob_spec):
    job_template = _model_value(cronjob_spec, 'job_template', 'jobTemplate')
    job_spec = _model_value(job_template, 'spec')
    return _workload_pod_template_spec(job_spec)


def _pod_template_details(template_spec) -> dict:
    defaults = {
        'reported': False,
        'schema_version': 2,
        'containers': [],
        'container_count': 0,
        'init_container_count': 0,
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

    if template_spec is None:
        return defaults

    regular_containers = list(_model_value(template_spec, 'containers', default=[]) or [])
    init_containers = list(
        _model_value(template_spec, 'init_containers', 'initContainers', default=[]) or []
    )
    containers: list[dict[str, str]] = []

    for container in regular_containers:
        containers.append(
            {
                'name': _string_value(_model_value(container, 'name')),
                'image': _string_value(_model_value(container, 'image')),
                'pull_policy': _string_value(
                    _model_value(container, 'image_pull_policy', 'imagePullPolicy')
                ),
                'kind': 'Container',
            }
        )

    for container in init_containers:
        containers.append(
            {
                'name': _string_value(_model_value(container, 'name')),
                'image': _string_value(_model_value(container, 'image')),
                'pull_policy': _string_value(
                    _model_value(container, 'image_pull_policy', 'imagePullPolicy')
                ),
                'kind': 'Init container',
            }
        )

    tolerations = [
        _toleration_display(toleration)
        for toleration in (
            _model_value(template_spec, 'tolerations', default=[]) or []
        )
    ]
    node_selector = _model_value(
        template_spec,
        'node_selector',
        'nodeSelector',
        default={},
    ) or {}

    return {
        'reported': True,
        'schema_version': 2,
        'containers': containers,
        'container_count': len(regular_containers),
        'init_container_count': len(init_containers),
        'service_account': _string_value(
            _model_value(
                template_spec,
                'service_account_name',
                'serviceAccountName',
                'service_account',
            ),
            'default',
        ),
        'restart_policy': _string_value(
            _model_value(template_spec, 'restart_policy', 'restartPolicy')
        ),
        'priority_class': _string_value(
            _model_value(template_spec, 'priority_class_name', 'priorityClassName')
        ),
        'scheduler': _string_value(
            _model_value(template_spec, 'scheduler_name', 'schedulerName'),
            'default-scheduler',
        ),
        'host_network': bool(
            _model_value(template_spec, 'host_network', 'hostNetwork', default=False)
        ),
        'dns_policy': _string_value(
            _model_value(template_spec, 'dns_policy', 'dnsPolicy')
        ),
        'volume_count': len(_model_value(template_spec, 'volumes', default=[]) or []),
        'node_selector': dict(sorted(node_selector.items())),
        'affinity_configured': _model_value(template_spec, 'affinity') is not None,
        'tolerations': tolerations,
        'topology_spread_count': len(
            _model_value(
                template_spec,
                'topology_spread_constraints',
                'topologySpreadConstraints',
                default=[],
            )
            or []
        ),
        'runtime_class': _string_value(
            _model_value(template_spec, 'runtime_class_name', 'runtimeClassName')
        ),
    }

def _workload_details(
    metadata,
    template_spec,
    *,
    state_display: str,
    state_rows: list[dict[str, str]],
    delivery_rows: list[dict[str, str]],
) -> dict:
    details = _metadata_details(metadata)
    details.update(
        {
            'schema_version': 2,
            'state_display': state_display,
            'state_rows': state_rows,
            'delivery_rows': delivery_rows,
            'pod_template': _pod_template_details(template_spec),
        }
    )
    return details


def _detail_row(label: str, value) -> dict[str, str]:
    return {
        'label': label,
        'value': _string_value(value),
    }


def get_workloads(
    api: AppsV1Api,
    batch_api: BatchV1Api | None = None,
) -> list[dict]:
    workloads: list[dict] = []

    deployments = cast(
        V1DeploymentList,
        api.list_deployment_for_all_namespaces(),
    )

    for deployment in deployments.items or []:
        metadata = deployment.metadata
        spec = deployment.spec
        status = deployment.status

        if metadata is None or spec is None:
            continue

        desired = spec.replicas or 0
        current = getattr(status, 'replicas', 0) or 0
        updated = getattr(status, 'updated_replicas', 0) or 0
        ready = getattr(status, 'ready_replicas', 0) or 0
        available = getattr(status, 'available_replicas', 0) or 0
        unavailable = getattr(status, 'unavailable_replicas', 0) or max(desired - available, 0)
        strategy = getattr(spec, 'strategy', None)
        rolling_update = getattr(strategy, 'rolling_update', None)
        state_display = f'{available}/{desired} Available'

        details = _workload_details(
            metadata,
            _workload_pod_template_spec(spec),
            state_display=state_display,
            state_rows=[
                _detail_row('Desired replicas', desired),
                _detail_row('Current replicas', current),
                _detail_row('Updated replicas', updated),
                _detail_row('Ready replicas', ready),
                _detail_row('Available replicas', available),
                _detail_row('Unavailable replicas', unavailable),
                _detail_row('Observed generation', getattr(status, 'observed_generation', None)),
            ],
            delivery_rows=[
                _detail_row('Strategy', getattr(strategy, 'type', None)),
                _detail_row('Max surge', getattr(rolling_update, 'max_surge', None)),
                _detail_row('Max unavailable', getattr(rolling_update, 'max_unavailable', None)),
                _detail_row('Min ready seconds', getattr(spec, 'min_ready_seconds', None)),
                _detail_row('Progress deadline', getattr(spec, 'progress_deadline_seconds', None)),
                _detail_row('Revision history limit', getattr(spec, 'revision_history_limit', None)),
            ],
        )

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'Deployment',
                'ready': f'{available}/{desired}',
                'status': ('Running' if available == desired else 'Progressing'),
                'created_at': metadata.creation_timestamp,
                'details': details,
            }
        )

    statefulsets = cast(
        V1StatefulSetList,
        api.list_stateful_set_for_all_namespaces(),
    )

    for statefulset in statefulsets.items or []:
        metadata = statefulset.metadata
        spec = statefulset.spec
        status = statefulset.status

        if metadata is None or spec is None:
            continue

        desired = spec.replicas or 0
        current = getattr(status, 'current_replicas', 0) or 0
        updated = getattr(status, 'updated_replicas', 0) or 0
        ready = getattr(status, 'ready_replicas', 0) or 0
        available = getattr(status, 'available_replicas', 0) or ready
        update_strategy = getattr(spec, 'update_strategy', None)
        rolling_update = getattr(update_strategy, 'rolling_update', None)
        state_display = f'{ready}/{desired} Ready'

        details = _workload_details(
            metadata,
            _workload_pod_template_spec(spec),
            state_display=state_display,
            state_rows=[
                _detail_row('Desired replicas', desired),
                _detail_row('Current replicas', current),
                _detail_row('Updated replicas', updated),
                _detail_row('Ready replicas', ready),
                _detail_row('Available replicas', available),
                _detail_row('Current revision', getattr(status, 'current_revision', None)),
                _detail_row('Update revision', getattr(status, 'update_revision', None)),
            ],
            delivery_rows=[
                _detail_row('Update strategy', getattr(update_strategy, 'type', None)),
                _detail_row('Pod management policy', getattr(spec, 'pod_management_policy', None)),
                _detail_row('Partition', getattr(rolling_update, 'partition', None)),
                _detail_row('Min ready seconds', getattr(spec, 'min_ready_seconds', None)),
                _detail_row('Service name', getattr(spec, 'service_name', None)),
                _detail_row('Revision history limit', getattr(spec, 'revision_history_limit', None)),
            ],
        )

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'StatefulSet',
                'ready': f'{ready}/{desired}',
                'status': ('Running' if ready == desired else 'Progressing'),
                'created_at': metadata.creation_timestamp,
                'details': details,
            }
        )

    daemonsets = cast(
        V1DaemonSetList,
        api.list_daemon_set_for_all_namespaces(),
    )

    for daemonset in daemonsets.items or []:
        metadata = daemonset.metadata
        spec = daemonset.spec
        status = daemonset.status

        if metadata is None or spec is None:
            continue

        desired = getattr(status, 'desired_number_scheduled', 0) or 0
        current = getattr(status, 'current_number_scheduled', 0) or 0
        ready = getattr(status, 'number_ready', 0) or 0
        available = getattr(status, 'number_available', 0) or 0
        updated = getattr(status, 'updated_number_scheduled', 0) or 0
        misscheduled = getattr(status, 'number_misscheduled', 0) or 0
        unavailable = getattr(status, 'number_unavailable', 0) or max(desired - available, 0)
        update_strategy = getattr(spec, 'update_strategy', None)
        rolling_update = getattr(update_strategy, 'rolling_update', None)
        state_display = f'{ready}/{desired} Ready'

        details = _workload_details(
            metadata,
            _workload_pod_template_spec(spec),
            state_display=state_display,
            state_rows=[
                _detail_row('Desired scheduled', desired),
                _detail_row('Current scheduled', current),
                _detail_row('Ready', ready),
                _detail_row('Available', available),
                _detail_row('Updated', updated),
                _detail_row('Misscheduled', misscheduled),
                _detail_row('Unavailable', unavailable),
            ],
            delivery_rows=[
                _detail_row('Update strategy', getattr(update_strategy, 'type', None)),
                _detail_row('Max unavailable', getattr(rolling_update, 'max_unavailable', None)),
                _detail_row('Max surge', getattr(rolling_update, 'max_surge', None)),
                _detail_row('Min ready seconds', getattr(spec, 'min_ready_seconds', None)),
                _detail_row('Revision history limit', getattr(spec, 'revision_history_limit', None)),
            ],
        )

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'DaemonSet',
                'ready': f'{ready}/{desired}',
                'status': ('Running' if ready == desired else 'Progressing'),
                'created_at': metadata.creation_timestamp,
                'details': details,
            }
        )

    if batch_api is None:
        return workloads

    jobs = cast(
        V1JobList,
        batch_api.list_job_for_all_namespaces(),
    )

    for job in jobs.items or []:
        metadata = job.metadata
        spec = job.spec
        status = job.status

        if metadata is None or spec is None:
            continue

        completions = spec.completions if spec.completions is not None else 1
        parallelism = spec.parallelism if spec.parallelism is not None else 1
        succeeded = getattr(status, 'succeeded', 0) or 0
        failed = getattr(status, 'failed', 0) or 0
        active = getattr(status, 'active', 0) or 0

        if failed > 0:
            job_status = 'Failed'
            state_display = f'{failed} Failed'
        elif succeeded >= completions:
            job_status = 'Running'
            state_display = f'{succeeded}/{completions} Complete'
        elif active > 0:
            job_status = 'Progressing'
            state_display = f'{active} Active'
        else:
            job_status = 'Progressing'
            state_display = 'Pending'

        details = _workload_details(
            metadata,
            _workload_pod_template_spec(spec),
            state_display=state_display,
            state_rows=[
                _detail_row('Completions', completions),
                _detail_row('Parallelism', parallelism),
                _detail_row('Active', active),
                _detail_row('Succeeded', succeeded),
                _detail_row('Failed', failed),
                _detail_row('Backoff limit', getattr(spec, 'backoff_limit', None)),
                _detail_row('Completion mode', getattr(spec, 'completion_mode', None)),
            ],
            delivery_rows=[
                _detail_row('Backoff limit', getattr(spec, 'backoff_limit', None)),
                _detail_row('Active deadline', getattr(spec, 'active_deadline_seconds', None)),
                _detail_row('TTL after finished', getattr(spec, 'ttl_seconds_after_finished', None)),
                _detail_row('Suspend', getattr(spec, 'suspend', None)),
            ],
        )

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'Job',
                'ready': f'{succeeded}/{completions}',
                'status': job_status,
                'created_at': metadata.creation_timestamp,
                'details': details,
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
        if getattr(exc, 'status', None) == 404:
            cronjob_items = []
        else:
            raise

    for cronjob in cronjob_items:
        metadata = cronjob.metadata
        spec = cronjob.spec
        status = cronjob.status

        if metadata is None or spec is None:
            continue

        active_count = len(getattr(status, 'active', None) or [])
        schedule = spec.schedule or '-'
        suspended = bool(getattr(spec, 'suspend', False))
        cronjob_status = 'Suspended' if suspended else 'Running'
        state_display = 'Suspended' if suspended else (f'{active_count} Active' if active_count else 'Scheduled')
        pod_template_spec = _cronjob_pod_template_spec(spec)

        details = _workload_details(
            metadata,
            pod_template_spec,
            state_display=state_display,
            state_rows=[
                _detail_row('Schedule', schedule),
                _detail_row('Time zone', getattr(spec, 'time_zone', None)),
                _detail_row('Suspended', suspended),
                _detail_row('Active Jobs', active_count),
                _detail_row('Last schedule', _isoformat_datetime(getattr(status, 'last_schedule_time', None))),
                _detail_row('Last successful execution', _isoformat_datetime(getattr(status, 'last_successful_time', None))),
                _detail_row('Concurrency policy', getattr(spec, 'concurrency_policy', None)),
            ],
            delivery_rows=[
                _detail_row('Concurrency policy', getattr(spec, 'concurrency_policy', None)),
                _detail_row('Starting deadline', getattr(spec, 'starting_deadline_seconds', None)),
                _detail_row('Successful history limit', getattr(spec, 'successful_jobs_history_limit', None)),
                _detail_row('Failed history limit', getattr(spec, 'failed_jobs_history_limit', None)),
                _detail_row('Suspend', suspended),
            ],
        )

        workloads.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'workload_type': 'CronJob',
                'ready': f'{active_count} active',
                'status': cronjob_status,
                'created_at': metadata.creation_timestamp,
                'schedule': schedule,
                'details': details,
            }
        )

    return workloads

def _controller_reference(metadata) -> tuple[str | None, str | None]:
    references = getattr(metadata, 'owner_references', None) or []

    for reference in references:
        if getattr(reference, 'controller', False):
            return getattr(reference, 'kind', None), getattr(reference, 'name', None)

    if references:
        reference = references[0]
        return getattr(reference, 'kind', None), getattr(reference, 'name', None)

    return None, None


def _configuration_reference(
    references: list[dict[str, str]],
    object_type: str,
    name: str | None,
) -> None:
    if not name:
        return

    candidate = {
        'type': object_type,
        'name': name,
    }

    if candidate not in references:
        references.append(candidate)


def get_pods(
    api: CoreV1Api,
    apps_api: AppsV1Api | None = None,
    batch_api: BatchV1Api | None = None,
) -> list[dict]:
    replica_set_owners: dict[tuple[str, str], str] = {}

    if apps_api is not None:
        replica_sets = cast(
            V1ReplicaSetList,
            apps_api.list_replica_set_for_all_namespaces(),
        )

        for replica_set in replica_sets.items or []:
            metadata = replica_set.metadata

            if metadata is None or not metadata.namespace or not metadata.name:
                continue

            owner_kind, owner_name = _controller_reference(metadata)

            if owner_kind == 'Deployment' and owner_name:
                replica_set_owners[(metadata.namespace, metadata.name)] = owner_name

    job_owners: dict[tuple[str, str], str] = {}

    if batch_api is not None:
        jobs = cast(
            V1JobList,
            batch_api.list_job_for_all_namespaces(),
        )

        for job in jobs.items or []:
            metadata = job.metadata

            if metadata is None or not metadata.namespace or not metadata.name:
                continue

            owner_kind, owner_name = _controller_reference(metadata)

            if owner_kind == 'CronJob' and owner_name:
                job_owners[(metadata.namespace, metadata.name)] = owner_name

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

        container_statuses = status.container_statuses or [] if status else []

        total_containers = len(container_statuses)
        ready_containers = sum(1 for container in container_statuses if container.ready)
        restart_count = sum(container.restart_count for container in container_statuses)

        containers = spec.containers if spec and spec.containers else []
        init_containers = spec.init_containers if spec and spec.init_containers else []

        container_images = [container.image for container in containers if container.image]
        init_container_images = [container.image for container in init_containers if container.image]
        container_names = [container.name for container in containers if container.name]
        image_count = len(container_images) + len(init_container_images)

        workload_type, workload_name = _controller_reference(metadata)

        if workload_type == 'ReplicaSet' and metadata.namespace and workload_name:
            deployment_name = replica_set_owners.get((metadata.namespace, workload_name))
            if deployment_name:
                workload_type = 'Deployment'
                workload_name = deployment_name

        elif workload_type == 'Job' and metadata.namespace and workload_name:
            cronjob_name = job_owners.get((metadata.namespace, workload_name))
            if cronjob_name:
                workload_type = 'CronJob'
                workload_name = cronjob_name

        configuration_references: list[dict[str, str]] = []
        persistent_volume_claims: list[str] = []

        if spec:
            for pull_secret in spec.image_pull_secrets or []:
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    getattr(pull_secret, 'name', None),
                )

            for volume in spec.volumes or []:
                config_map = getattr(volume, 'config_map', None)
                secret = getattr(volume, 'secret', None)
                claim = getattr(volume, 'persistent_volume_claim', None)

                _configuration_reference(
                    configuration_references,
                    'ConfigMap',
                    getattr(config_map, 'name', None) if config_map else None,
                )
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    getattr(secret, 'secret_name', None) if secret else None,
                )

                claim_name = getattr(claim, 'claim_name', None) if claim else None
                if claim_name and claim_name not in persistent_volume_claims:
                    persistent_volume_claims.append(claim_name)

        for container in [*containers, *init_containers]:
            for source in getattr(container, 'env_from', None) or []:
                config_map_ref = getattr(source, 'config_map_ref', None)
                secret_ref = getattr(source, 'secret_ref', None)
                _configuration_reference(
                    configuration_references,
                    'ConfigMap',
                    getattr(config_map_ref, 'name', None) if config_map_ref else None,
                )
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    getattr(secret_ref, 'name', None) if secret_ref else None,
                )

            for env_var in getattr(container, 'env', None) or []:
                value_from = getattr(env_var, 'value_from', None)
                if value_from is None:
                    continue

                config_map_key_ref = getattr(value_from, 'config_map_key_ref', None)
                secret_key_ref = getattr(value_from, 'secret_key_ref', None)
                _configuration_reference(
                    configuration_references,
                    'ConfigMap',
                    getattr(config_map_key_ref, 'name', None) if config_map_key_ref else None,
                )
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    getattr(secret_key_ref, 'name', None) if secret_key_ref else None,
                )

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
                'container_names': container_names,
                'image_count': image_count,
                'labels': dict(metadata.labels or {}),
                'workload_type': workload_type,
                'workload_name': workload_name,
                'configuration_references': configuration_references,
                'persistent_volume_claims': persistent_volume_claims,
                'created_at': metadata.creation_timestamp,
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
                'selector': dict(spec.selector or {}),
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


def get_configuration_inventory(
    api: CoreV1Api,
) -> list[dict]:
    items: list[dict] = []

    config_maps = cast(
        V1ConfigMapList,
        api.list_config_map_for_all_namespaces(),
    )

    for config_map in config_maps.items or []:
        metadata = config_map.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        data = config_map.data or {}
        binary_data = config_map.binary_data or {}
        key_names = sorted({*data.keys(), *binary_data.keys()})
        payload_size = sum(len(value.encode('utf-8')) for value in data.values())

        for value in binary_data.values():
            try:
                payload_size += len(base64.b64decode(value))
            except (ValueError, TypeError):
                payload_size += len(str(value).encode('utf-8'))

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'object_type': 'ConfigMap',
                'secret_type': None,
                'key_names': key_names,
                'key_count': len(key_names),
                'immutable': bool(config_map.immutable),
                'payload_size_bytes': payload_size,
                'created_at': metadata.creation_timestamp,
            }
        )

    secrets = cast(
        V1SecretList,
        api.list_secret_for_all_namespaces(),
    )

    for secret in secrets.items or []:
        metadata = secret.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        data = secret.data or {}
        string_data = secret.string_data or {}
        key_names = sorted({*data.keys(), *string_data.keys()})
        payload_size = 0

        for value in data.values():
            try:
                payload_size += len(base64.b64decode(value))
            except (ValueError, TypeError):
                payload_size += len(str(value).encode('utf-8'))

        payload_size += sum(len(value.encode('utf-8')) for value in string_data.values())

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'object_type': 'Secret',
                'secret_type': secret.type or 'Opaque',
                'key_names': key_names,
                'key_count': len(key_names),
                'immutable': bool(secret.immutable),
                'payload_size_bytes': payload_size,
                'created_at': metadata.creation_timestamp,
            }
        )

    return items


def get_resource_quotas(
    api: CoreV1Api,
) -> list[dict]:
    result = cast(
        V1ResourceQuotaList,
        api.list_resource_quota_for_all_namespaces(),
    )

    items: list[dict] = []

    for quota in result.items or []:
        metadata = quota.metadata
        status = quota.status

        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        hard = {str(key): str(value) for key, value in ((status.hard or {}) if status else {}).items()}
        used = {str(key): str(value) for key, value in ((status.used or {}) if status else {}).items()}

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'hard': hard,
                'used': used,
                'created_at': metadata.creation_timestamp,
            }
        )

    return items


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
                'details': {
                    'provisioner': storage_class.provisioner,
                    'reclaim_policy': storage_class.reclaim_policy,
                    'volume_binding_mode': storage_class.volume_binding_mode,
                    'allow_volume_expansion': bool(storage_class.allow_volume_expansion),
                },
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
                'details': {
                    'claim_namespace': (spec.claim_ref.namespace if spec and spec.claim_ref else None),
                    'claim_name': (spec.claim_ref.name if spec and spec.claim_ref else None),
                    'reclaim_policy': (spec.persistent_volume_reclaim_policy if spec else None),
                    'access_modes': list(spec.access_modes or []) if spec else [],
                    'volume_mode': spec.volume_mode if spec else None,
                },
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
                'details': {
                    'volume_name': spec.volume_name if spec else None,
                    'access_modes': list(spec.access_modes or []) if spec else [],
                    'volume_mode': spec.volume_mode if spec else None,
                    'requested_storage': (
                        str(spec.resources.requests.get('storage'))
                        if spec
                        and spec.resources
                        and spec.resources.requests
                        and spec.resources.requests.get('storage')
                        else None
                    ),
                },
                'created_at': metadata.creation_timestamp,
            }
        )

    return items
