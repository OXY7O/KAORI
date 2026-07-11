import base64
from typing import Any, cast

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
    V1EndpointsList,
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


def _container_state_payload(state) -> dict[str, Any]:
    if state is None:
        return {
            'state': 'Unknown',
            'reason': None,
            'message': None,
            'started_at': None,
            'finished_at': None,
            'exit_code': None,
        }

    running = _model_value(state, 'running')
    if running is not None:
        return {
            'state': 'Running',
            'reason': None,
            'message': None,
            'started_at': _isoformat_datetime(_model_value(running, 'started_at', 'startedAt')),
            'finished_at': None,
            'exit_code': None,
        }

    waiting = _model_value(state, 'waiting')
    if waiting is not None:
        return {
            'state': 'Waiting',
            'reason': _model_value(waiting, 'reason'),
            'message': _model_value(waiting, 'message'),
            'started_at': None,
            'finished_at': None,
            'exit_code': None,
        }

    terminated = _model_value(state, 'terminated')
    if terminated is not None:
        return {
            'state': 'Terminated',
            'reason': _model_value(terminated, 'reason'),
            'message': _model_value(terminated, 'message'),
            'started_at': _isoformat_datetime(_model_value(terminated, 'started_at', 'startedAt')),
            'finished_at': _isoformat_datetime(_model_value(terminated, 'finished_at', 'finishedAt')),
            'exit_code': _model_value(terminated, 'exit_code', 'exitCode'),
        }

    return {
        'state': 'Unknown',
        'reason': None,
        'message': None,
        'started_at': None,
        'finished_at': None,
        'exit_code': None,
    }


def _container_runtime_rows(
    specs,
    statuses,
    *,
    kind: str,
) -> list[dict[str, Any]]:
    spec_by_name = {
        _model_value(container, 'name'): container
        for container in specs or []
        if _model_value(container, 'name')
    }
    status_by_name = {
        _model_value(container_status, 'name'): container_status
        for container_status in statuses or []
        if _model_value(container_status, 'name')
    }
    ordered_names = list(spec_by_name)
    for name in status_by_name:
        if name not in ordered_names:
            ordered_names.append(name)

    rows: list[dict[str, Any]] = []
    for name in ordered_names:
        spec = spec_by_name.get(name)
        container_status = status_by_name.get(name)
        current_state = _container_state_payload(
            _model_value(container_status, 'state'),
        )
        previous_state = _container_state_payload(
            _model_value(container_status, 'last_state', 'lastState'),
        )

        rows.append(
            {
                'name': name,
                'kind': kind,
                'image': _model_value(spec, 'image') or _model_value(container_status, 'image') or '-',
                'image_id': _model_value(container_status, 'image_id', 'imageID') or '-',
                'pull_policy': _model_value(spec, 'image_pull_policy', 'imagePullPolicy') or '-',
                'ready': bool(_model_value(container_status, 'ready', default=False)),
                'started': bool(_model_value(container_status, 'started', default=False)),
                'restart_count': int(_model_value(container_status, 'restart_count', 'restartCount', default=0) or 0),
                'state': current_state['state'],
                'reason': current_state['reason'],
                'message': current_state['message'],
                'started_at': current_state['started_at'],
                'finished_at': current_state['finished_at'],
                'exit_code': current_state['exit_code'],
                'previous_state': previous_state['state'],
                'previous_reason': previous_state['reason'],
            }
        )

    return rows


def _volume_source(volume) -> tuple[str, str]:
    sources = [
        ('ConfigMap', 'config_map', 'configMap', 'name'),
        ('Secret', 'secret', 'secret', 'secret_name'),
        ('PersistentVolumeClaim', 'persistent_volume_claim', 'persistentVolumeClaim', 'claim_name'),
        ('CSI', 'csi', 'csi', 'driver'),
        ('HostPath', 'host_path', 'hostPath', 'path'),
    ]

    for volume_type, snake_name, camel_name, value_name in sources:
        source = _model_value(volume, snake_name, camel_name)
        if source is None:
            continue
        camel_value = ''.join(
            word.capitalize() if index else word
            for index, word in enumerate(value_name.split('_'))
        )
        return (
            volume_type,
            _string_value(_model_value(source, value_name, camel_value)),
        )

    if _model_value(volume, 'empty_dir', 'emptyDir') is not None:
        return 'EmptyDir', 'Pod lifecycle storage'
    if _model_value(volume, 'projected') is not None:
        return 'Projected', 'Kubernetes managed'
    if _model_value(volume, 'downward_api', 'downwardAPI') is not None:
        return 'DownwardAPI', 'Pod metadata'
    if _model_value(volume, 'ephemeral') is not None:
        return 'Ephemeral', 'Generic ephemeral volume'

    return 'Other', '-'


def _pod_volumes(spec, regular_containers, init_containers) -> list[dict[str, Any]]:
    mounted_by: dict[str, list[str]] = {}
    for container in [*(regular_containers or []), *(init_containers or [])]:
        container_name = _model_value(container, 'name') or '-'
        for mount in _model_value(container, 'volume_mounts', 'volumeMounts', default=[]) or []:
            volume_name = _model_value(mount, 'name')
            if not volume_name:
                continue
            mounted_by.setdefault(volume_name, [])
            if container_name not in mounted_by[volume_name]:
                mounted_by[volume_name].append(container_name)

    rows: list[dict[str, Any]] = []
    for volume in _model_value(spec, 'volumes', default=[]) or []:
        name = _model_value(volume, 'name') or '-'
        volume_type, source = _volume_source(volume)
        rows.append(
            {
                'name': name,
                'type': volume_type,
                'source': source,
                'mounted_by': mounted_by.get(name, []),
            }
        )
    return rows


def _pod_condition_rows(status) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in _model_value(status, 'conditions', default=[]) or []:
        rows.append(
            {
                'type': _model_value(condition, 'type') or 'Unknown',
                'status': _model_value(condition, 'status') or 'Unknown',
                'reason': _model_value(condition, 'reason'),
                'message': _model_value(condition, 'message'),
                'last_transition_time': _isoformat_datetime(
                    _model_value(condition, 'last_transition_time', 'lastTransitionTime'),
                ),
            }
        )
    return rows


def _pod_owner_chain(
    *,
    pod_name: str,
    direct_kind: str | None,
    direct_name: str | None,
    workload_type: str | None,
    workload_name: str | None,
) -> list[dict[str, str]]:
    chain: list[dict[str, str]] = []

    if workload_type and workload_name and (
        workload_type != direct_kind or workload_name != direct_name
    ):
        chain.append({'kind': workload_type, 'name': workload_name})

    if direct_kind and direct_name:
        chain.append({'kind': direct_kind, 'name': direct_name})

    chain.append({'kind': 'Pod', 'name': pod_name})
    return chain


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

        container_statuses = _model_value(status, 'container_statuses', 'containerStatuses', default=[]) or []
        init_container_statuses = _model_value(status, 'init_container_statuses', 'initContainerStatuses', default=[]) or []
        ephemeral_container_statuses = _model_value(status, 'ephemeral_container_statuses', 'ephemeralContainerStatuses', default=[]) or []

        total_containers = len(container_statuses)
        ready_containers = sum(
            1
            for container in container_statuses
            if bool(_model_value(container, 'ready', default=False))
        )
        restart_count = sum(
            int(_model_value(container, 'restart_count', 'restartCount', default=0) or 0)
            for container in [*container_statuses, *init_container_statuses]
        )

        containers = _model_value(spec, 'containers', default=[]) or []
        init_containers = _model_value(spec, 'init_containers', 'initContainers', default=[]) or []
        ephemeral_containers = _model_value(spec, 'ephemeral_containers', 'ephemeralContainers', default=[]) or []

        container_images = [
            _model_value(container, 'image')
            for container in containers
            if _model_value(container, 'image')
        ]
        init_container_images = [
            _model_value(container, 'image')
            for container in init_containers
            if _model_value(container, 'image')
        ]
        container_names = [
            _model_value(container, 'name')
            for container in containers
            if _model_value(container, 'name')
        ]
        image_count = len(container_images) + len(init_container_images)

        direct_owner_type, direct_owner_name = _controller_reference(metadata)
        workload_type = direct_owner_type
        workload_name = direct_owner_name

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
            for pull_secret in _model_value(spec, 'image_pull_secrets', 'imagePullSecrets', default=[]) or []:
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    _model_value(pull_secret, 'name'),
                )

            for volume in _model_value(spec, 'volumes', default=[]) or []:
                config_map = _model_value(volume, 'config_map', 'configMap')
                secret = _model_value(volume, 'secret')
                claim = _model_value(volume, 'persistent_volume_claim', 'persistentVolumeClaim')

                _configuration_reference(
                    configuration_references,
                    'ConfigMap',
                    _model_value(config_map, 'name') if config_map else None,
                )
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    _model_value(secret, 'secret_name', 'secretName') if secret else None,
                )

                claim_name = _model_value(claim, 'claim_name', 'claimName') if claim else None
                if claim_name and claim_name not in persistent_volume_claims:
                    persistent_volume_claims.append(claim_name)

        for container in [*containers, *init_containers]:
            for source in _model_value(container, 'env_from', 'envFrom', default=[]) or []:
                config_map_ref = _model_value(source, 'config_map_ref', 'configMapRef')
                secret_ref = _model_value(source, 'secret_ref', 'secretRef')
                _configuration_reference(
                    configuration_references,
                    'ConfigMap',
                    _model_value(config_map_ref, 'name') if config_map_ref else None,
                )
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    _model_value(secret_ref, 'name') if secret_ref else None,
                )

            for env_var in _model_value(container, 'env', default=[]) or []:
                value_from = _model_value(env_var, 'value_from', 'valueFrom')
                if value_from is None:
                    continue

                config_map_key_ref = _model_value(value_from, 'config_map_key_ref', 'configMapKeyRef')
                secret_key_ref = _model_value(value_from, 'secret_key_ref', 'secretKeyRef')
                _configuration_reference(
                    configuration_references,
                    'ConfigMap',
                    _model_value(config_map_key_ref, 'name') if config_map_key_ref else None,
                )
                _configuration_reference(
                    configuration_references,
                    'Secret',
                    _model_value(secret_key_ref, 'name') if secret_key_ref else None,
                )

        tolerations = [
            _toleration_display(toleration)
            for toleration in _model_value(spec, 'tolerations', default=[]) or []
        ]
        labels = dict(sorted((metadata.labels or {}).items()))
        annotations = dict(sorted((metadata.annotations or {}).items()))

        details = {
            'schema_version': 1,
            'uid': _string_value(metadata.uid),
            'annotations': annotations,
            'host_ip': _model_value(status, 'host_ip', 'hostIP'),
            'reason': _model_value(status, 'reason'),
            'message': _model_value(status, 'message'),
            'qos_class': _model_value(status, 'qos_class', 'qosClass') or '-',
            'conditions': _pod_condition_rows(status),
            'owner_chain': _pod_owner_chain(
                pod_name=metadata.name or '-',
                direct_kind=direct_owner_type,
                direct_name=direct_owner_name,
                workload_type=workload_type,
                workload_name=workload_name,
            ),
            'placement': {
                'scheduler': _model_value(spec, 'scheduler_name', 'schedulerName') or '-',
                'priority_class': _model_value(spec, 'priority_class_name', 'priorityClassName') or '-',
                'node_selector': dict(sorted((_model_value(spec, 'node_selector', 'nodeSelector', default={}) or {}).items())),
                'tolerations': tolerations,
                'affinity_configured': _model_value(spec, 'affinity') is not None,
                'topology_spread_count': len(
                    _model_value(spec, 'topology_spread_constraints', 'topologySpreadConstraints', default=[]) or []
                ),
                'host_network': bool(_model_value(spec, 'host_network', 'hostNetwork', default=False)),
            },
            'configuration': {
                'service_account': _model_value(spec, 'service_account_name', 'serviceAccountName') or 'default',
                'restart_policy': _model_value(spec, 'restart_policy', 'restartPolicy') or '-',
                'dns_policy': _model_value(spec, 'dns_policy', 'dnsPolicy') or '-',
                'runtime_class': _model_value(spec, 'runtime_class_name', 'runtimeClassName') or '-',
                'security_context_configured': _model_value(spec, 'security_context', 'securityContext') is not None,
                'image_pull_secret_count': len(
                    _model_value(spec, 'image_pull_secrets', 'imagePullSecrets', default=[]) or []
                ),
                'volume_count': len(_model_value(spec, 'volumes', default=[]) or []),
                'container_count': len(containers),
                'init_container_count': len(init_containers),
                'ephemeral_container_count': len(ephemeral_containers),
            },
            'container_statuses': [
                *_container_runtime_rows(containers, container_statuses, kind='Regular'),
                *_container_runtime_rows(init_containers, init_container_statuses, kind='Init'),
                *_container_runtime_rows(ephemeral_containers, ephemeral_container_statuses, kind='Ephemeral'),
            ],
            'volumes': _pod_volumes(spec, containers, init_containers),
        }

        pods.append(
            {
                'namespace': metadata.namespace,
                'pod_name': metadata.name,
                'node_name': _model_value(spec, 'node_name', 'nodeName'),
                'phase': _model_value(status, 'phase'),
                'pod_ip': _model_value(status, 'pod_ip', 'podIP'),
                'ready': f'{ready_containers}/{total_containers}',
                'restart_count': restart_count,
                'container_images': container_images,
                'init_container_images': init_container_images,
                'container_names': container_names,
                'image_count': image_count,
                'labels': labels,
                'details': details,
                'workload_type': workload_type,
                'workload_name': workload_name,
                'configuration_references': configuration_references,
                'persistent_volume_claims': persistent_volume_claims,
                'created_at': metadata.creation_timestamp,
            }
        )

    return pods

def _service_endpoint_map(api: CoreV1Api) -> dict[tuple[str, str], dict]:
    endpoint_map: dict[tuple[str, str], dict] = {}

    try:
        result = cast(
            V1EndpointsList,
            api.list_endpoints_for_all_namespaces(),
        )
    except ApiException:
        return endpoint_map

    for endpoint in result.items or []:
        metadata = endpoint.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        ready_addresses: list[dict[str, str]] = []
        not_ready_addresses: list[dict[str, str]] = []
        endpoint_ports: list[dict[str, str | int]] = []

        for subset in endpoint.subsets or []:
            for address in subset.addresses or []:
                target_ref = getattr(address, 'target_ref', None)
                ready_addresses.append(
                    {
                        'ip': _string_value(getattr(address, 'ip', None)),
                        'hostname': _string_value(getattr(address, 'hostname', None)),
                        'node_name': _string_value(getattr(address, 'node_name', None)),
                        'target_kind': _string_value(getattr(target_ref, 'kind', None)),
                        'target_name': _string_value(getattr(target_ref, 'name', None)),
                    }
                )

            for address in subset.not_ready_addresses or []:
                target_ref = getattr(address, 'target_ref', None)
                not_ready_addresses.append(
                    {
                        'ip': _string_value(getattr(address, 'ip', None)),
                        'hostname': _string_value(getattr(address, 'hostname', None)),
                        'node_name': _string_value(getattr(address, 'node_name', None)),
                        'target_kind': _string_value(getattr(target_ref, 'kind', None)),
                        'target_name': _string_value(getattr(target_ref, 'name', None)),
                    }
                )

            for port in subset.ports or []:
                endpoint_ports.append(
                    {
                        'name': _string_value(getattr(port, 'name', None)),
                        'port': int(getattr(port, 'port', 0) or 0),
                        'protocol': _string_value(getattr(port, 'protocol', None), 'TCP'),
                    }
                )

        endpoint_map[(metadata.namespace, metadata.name)] = {
            'reported': True,
            'ready_addresses': ready_addresses,
            'not_ready_addresses': not_ready_addresses,
            'ports': endpoint_ports,
        }

    return endpoint_map


def get_services(
    api: CoreV1Api,
) -> list[dict]:
    result = cast(
        V1ServiceList,
        api.list_service_for_all_namespaces(),
    )
    endpoint_map = _service_endpoint_map(api)
    services: list[dict] = []

    for svc in result.items or []:
        metadata = svc.metadata
        spec = svc.spec
        status = svc.status

        if metadata is None or spec is None:
            continue

        port_details: list[dict[str, Any]] = []
        compact_ports: list[str] = []

        for port in spec.ports or []:
            target_port = getattr(port, 'target_port', None)
            target_port_value = (
                getattr(target_port, 'value', None)
                if target_port is not None
                else None
            )
            if target_port_value is None and target_port is not None:
                target_port_value = str(target_port)

            port_value = int(getattr(port, 'port', 0) or 0)
            protocol = _string_value(getattr(port, 'protocol', None), 'TCP')
            compact_ports.append(f'{port_value}/{protocol}')
            port_details.append(
                {
                    'name': _string_value(getattr(port, 'name', None)),
                    'protocol': protocol,
                    'port': port_value,
                    'target_port': _string_value(target_port_value),
                    'node_port': int(getattr(port, 'node_port', 0) or 0),
                    'app_protocol': _string_value(getattr(port, 'app_protocol', None)),
                }
            )

        external_addresses: list[str] = []
        for value in spec.external_ips or []:
            if value and value not in external_addresses:
                external_addresses.append(value)

        load_balancer = getattr(status, 'load_balancer', None)
        for item in getattr(load_balancer, 'ingress', None) or []:
            value = getattr(item, 'ip', None) or getattr(item, 'hostname', None)
            if value and value not in external_addresses:
                external_addresses.append(value)

        metadata_details = _metadata_details(metadata)
        endpoints = endpoint_map.get(
            (metadata.namespace, metadata.name),
            {
                'reported': False,
                'ready_addresses': [],
                'not_ready_addresses': [],
                'ports': [],
            },
        )

        details = {
            **metadata_details,
            'generation': int(getattr(metadata, 'generation', 0) or 0),
            'cluster_ips': list(getattr(spec, 'cluster_ips', None) or []),
            'ip_families': list(getattr(spec, 'ip_families', None) or []),
            'ip_family_policy': _string_value(getattr(spec, 'ip_family_policy', None)),
            'external_name': _string_value(getattr(spec, 'external_name', None)),
            'session_affinity': _string_value(getattr(spec, 'session_affinity', None), 'None'),
            'internal_traffic_policy': _string_value(getattr(spec, 'internal_traffic_policy', None)),
            'external_traffic_policy': _string_value(getattr(spec, 'external_traffic_policy', None)),
            'publish_not_ready_addresses': bool(getattr(spec, 'publish_not_ready_addresses', False)),
            'health_check_node_port': int(getattr(spec, 'health_check_node_port', 0) or 0),
            'load_balancer_class': _string_value(getattr(spec, 'load_balancer_class', None)),
            'allocate_load_balancer_node_ports': getattr(spec, 'allocate_load_balancer_node_ports', None),
            'ports': port_details,
            'endpoints': endpoints,
        }

        services.append(
            {
                'namespace': metadata.namespace,
                'service_name': metadata.name,
                'service_type': spec.type,
                'cluster_ip': spec.cluster_ip,
                'external_ip': ','.join(external_addresses) if external_addresses else '-',
                'ports': ','.join(compact_ports),
                'selector': dict(spec.selector or {}),
                'details': details,
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

    ingresses: list[dict] = []

    for ingress in result.items or []:
        metadata = ingress.metadata
        spec = ingress.spec
        status = ingress.status

        if metadata is None:
            continue

        backend_paths: list[dict[str, str]] = []
        hosts: list[str] = []

        def _backend_to_dict(backend):
            service = getattr(backend, 'service', None)
            if service is None:
                return {'service_name': '-', 'service_port': '-'}

            port = getattr(service, 'port', None)
            port_value = '-'
            if port is not None:
                port_value = getattr(port, 'name', None) or getattr(port, 'number', None) or '-'

            return {
                'service_name': getattr(service, 'name', None) or '-',
                'service_port': str(port_value),
            }

        default_backend = None
        if spec and spec.default_backend:
            default_backend = _backend_to_dict(spec.default_backend)
            backend_paths.append(
                {
                    'host': '-',
                    'path': '/',
                    'path_type': 'DefaultBackend',
                    **default_backend,
                }
            )

        if spec and spec.rules:
            for rule in spec.rules:
                rule_host = rule.host or '-'
                if rule_host != '-' and rule_host not in hosts:
                    hosts.append(rule_host)

                http_rule = getattr(rule, 'http', None)
                if not http_rule or not http_rule.paths:
                    continue

                for path in http_rule.paths:
                    backend_info = _backend_to_dict(path.backend)
                    backend_paths.append(
                        {
                            'host': rule_host,
                            'path': path.path or '/',
                            'path_type': path.path_type or '-',
                            **backend_info,
                        }
                    )

        addresses: list[str] = []
        if status and status.load_balancer and status.load_balancer.ingress:
            for item in status.load_balancer.ingress:
                value = item.ip or item.hostname
                if value and value not in addresses:
                    addresses.append(value)

        tls_entries: list[dict[str, Any]] = []
        if spec and spec.tls:
            for tls in spec.tls:
                tls_entries.append(
                    {
                        'secret_name': _string_value(getattr(tls, 'secret_name', None)),
                        'hosts': list(getattr(tls, 'hosts', None) or []),
                    }
                )

        metadata_details = _metadata_details(metadata)
        details = {
            **metadata_details,
            'generation': int(getattr(metadata, 'generation', 0) or 0),
            'hosts': hosts,
            'tls': tls_entries,
            'rule_count': len(spec.rules or []) if spec else 0,
            'default_backend': default_backend,
            'finalizers': list(getattr(metadata, 'finalizers', None) or []),
        }

        ingresses.append(
            {
                'namespace': metadata.namespace,
                'ingress_name': metadata.name,
                'ingress_class': (
                    spec.ingress_class_name
                    if spec and spec.ingress_class_name
                    else (metadata.annotations or {}).get('kubernetes.io/ingress.class')
                ),
                'host': hosts[0] if hosts else '-',
                'address': ', '.join(addresses) if addresses else '-',
                'tls_enabled': bool(tls_entries),
                'backend_paths': backend_paths,
                'details': details,
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


def _persistent_volume_source_details(spec) -> dict[str, Any]:
    sources = [
        ('CSI', 'csi'),
        ('Local', 'local'),
        ('NFS', 'nfs'),
        ('HostPath', 'host_path'),
        ('iSCSI', 'iscsi'),
        ('FibreChannel', 'fc'),
        ('CephFS', 'cephfs'),
        ('RBD', 'rbd'),
        ('AzureDisk', 'azure_disk'),
        ('AzureFile', 'azure_file'),
        ('AWSElasticBlockStore', 'aws_elastic_block_store'),
        ('GCEPersistentDisk', 'gce_persistent_disk'),
        ('vSphereVolume', 'vsphere_volume'),
        ('PortworxVolume', 'portworx_volume'),
        ('FlexVolume', 'flex_volume'),
    ]

    for display_name, attribute in sources:
        source = _model_value(spec, attribute)
        if source is None:
            continue

        details: dict[str, Any] = {'type': display_name}
        if display_name == 'CSI':
            details.update(
                {
                    'driver': _string_value(_model_value(source, 'driver')),
                    'volume_handle': _string_value(_model_value(source, 'volume_handle', 'volumeHandle')),
                    'read_only': bool(_model_value(source, 'read_only', 'readOnly', default=False)),
                    'fs_type': _string_value(_model_value(source, 'fs_type', 'fsType')),
                }
            )
        elif display_name == 'Local':
            details['path'] = _string_value(_model_value(source, 'path'))
        elif display_name == 'NFS':
            details.update(
                {
                    'server': _string_value(_model_value(source, 'server')),
                    'path': _string_value(_model_value(source, 'path')),
                    'read_only': bool(_model_value(source, 'read_only', 'readOnly', default=False)),
                }
            )
        elif display_name == 'HostPath':
            details.update(
                {
                    'path': _string_value(_model_value(source, 'path')),
                    'host_path_type': _string_value(_model_value(source, 'type')),
                }
            )

        return details

    return {'type': 'Other'}


def _pvc_conditions(status) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for condition in _model_value(status, 'conditions', default=[]) or []:
        rows.append(
            {
                'type': _string_value(_model_value(condition, 'type')),
                'status': _string_value(_model_value(condition, 'status')),
                'reason': _string_value(_model_value(condition, 'reason')),
                'message': _string_value(_model_value(condition, 'message')),
                'last_transition_time': _isoformat_datetime(
                    _model_value(condition, 'last_transition_time', 'lastTransitionTime')
                ),
            }
        )
    return rows


def get_storage_inventory(
    core_api: CoreV1Api,
    storage_api: StorageV1Api,
) -> list[dict]:
    items: list[dict] = []

    storage_classes = cast(
        V1StorageClassList,
        storage_api.list_storage_class(),
    )

    for storage_class in storage_classes.items or []:
        metadata = storage_class.metadata
        if metadata is None:
            continue

        annotations = dict(metadata.annotations or {})
        metadata_details = _metadata_details(metadata)
        is_default = any(
            annotations.get(key) == 'true'
            for key in (
                'storageclass.kubernetes.io/is-default-class',
                'storageclass.beta.kubernetes.io/is-default-class',
            )
        )

        details = {
            **metadata_details,
            'finalizers': list(metadata.finalizers or []),
            'provisioner': storage_class.provisioner,
            'reclaim_policy': storage_class.reclaim_policy,
            'volume_binding_mode': storage_class.volume_binding_mode,
            'allow_volume_expansion': bool(storage_class.allow_volume_expansion),
            'parameters': dict(sorted((storage_class.parameters or {}).items())),
            'mount_options': list(storage_class.mount_options or []),
            'allowed_topology_count': len(storage_class.allowed_topologies or []),
            'is_default': is_default,
        }

        items.append(
            {
                'namespace': None,
                'name': metadata.name,
                'storage_type': 'StorageClass',
                'storage_class': metadata.name,
                'capacity': '-',
                'status': 'Available',
                'details': details,
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
            capacity = spec.capacity.get('storage', '-')

        source = _persistent_volume_source_details(spec)
        metadata_details = _metadata_details(metadata)
        details = {
            **metadata_details,
            'finalizers': list(metadata.finalizers or []),
            'claim_namespace': spec.claim_ref.namespace if spec and spec.claim_ref else None,
            'claim_name': spec.claim_ref.name if spec and spec.claim_ref else None,
            'reclaim_policy': spec.persistent_volume_reclaim_policy if spec else None,
            'access_modes': list(spec.access_modes or []) if spec else [],
            'volume_mode': spec.volume_mode if spec else None,
            'mount_options': list(spec.mount_options or []) if spec else [],
            'node_affinity_configured': bool(spec and spec.node_affinity),
            'source': source,
        }

        items.append(
            {
                'namespace': None,
                'name': metadata.name,
                'storage_type': 'PersistentVolume',
                'storage_class': spec.storage_class_name if spec else None,
                'capacity': capacity,
                'status': status.phase if status else None,
                'details': details,
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
            capacity = status.capacity.get('storage', '-')

        selector = _model_value(spec, 'selector')
        data_source = _model_value(spec, 'data_source', 'dataSource')
        metadata_details = _metadata_details(metadata)
        details = {
            **metadata_details,
            'finalizers': list(metadata.finalizers or []),
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
            'selector': dict(_model_value(selector, 'match_labels', 'matchLabels', default={}) or {}),
            'data_source': (
                {
                    'kind': _string_value(_model_value(data_source, 'kind')),
                    'name': _string_value(_model_value(data_source, 'name')),
                    'api_group': _string_value(_model_value(data_source, 'api_group', 'apiGroup')),
                }
                if data_source is not None
                else None
            ),
            'conditions': _pvc_conditions(status),
        }

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'storage_type': 'PersistentVolumeClaim',
                'storage_class': spec.storage_class_name if spec else None,
                'capacity': capacity,
                'status': status.phase if status else None,
                'details': details,
                'created_at': metadata.creation_timestamp,
            }
        )

    return items
