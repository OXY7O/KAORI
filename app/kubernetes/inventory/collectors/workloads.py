from __future__ import annotations

from typing import Any, cast

from kubernetes.client import (
    AppsV1Api,
    BatchV1Api,
    V1CronJobList,
    V1DaemonSetList,
    V1DeploymentList,
    V1JobList,
    V1StatefulSetList,
)
from kubernetes.client.exceptions import ApiException, NotFoundException

from app.kubernetes.inventory.collectors.common import (
    _detail_row,
    _isoformat_datetime,
    _metadata_details,
    _model_value,
    _string_value,
    _to_modelish,
    _toleration_display,
)


def _condition_rows(status) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for condition in list(_model_value(status, 'conditions', default=[]) or []):
        rows.append(
            {
                'type': _string_value(_model_value(condition, 'type'), 'Unknown'),
                'status': _string_value(_model_value(condition, 'status'), 'Unknown'),
                'reason': _string_value(_model_value(condition, 'reason'), 'Not Reported'),
                'message': _string_value(_model_value(condition, 'message'), 'Not Reported'),
                'last_transition_time': _isoformat_datetime(
                    _model_value(condition, 'last_transition_time', 'lastTransitionTime')
                )
                or 'Not Reported',
            }
        )
    return rows


def _condition_is_true(status, condition_type: str) -> bool:
    wanted = condition_type.casefold()
    for condition in list(_model_value(status, 'conditions', default=[]) or []):
        if _string_value(_model_value(condition, 'type'), '').casefold() != wanted:
            continue
        return _string_value(_model_value(condition, 'status'), '').casefold() == 'true'
    return False


def _deployment_progress_deadline_exceeded(status) -> bool:
    for condition in list(_model_value(status, 'conditions', default=[]) or []):
        condition_type = _string_value(_model_value(condition, 'type'), '').casefold()
        reason = _string_value(_model_value(condition, 'reason'), '').casefold()
        condition_status = _string_value(_model_value(condition, 'status'), '').casefold()
        if condition_type == 'progressing' and condition_status == 'false' and reason == 'progressdeadlineexceeded':
            return True
    return False


def _desired_replicas(spec, default: int = 1) -> int:
    value = _model_value(spec, 'replicas')
    return default if value is None else int(value)


def _metadata_identity(metadata) -> tuple[str, str] | None:
    namespace = _string_value(_model_value(metadata, 'namespace'), '')
    name = _string_value(_model_value(metadata, 'name'), '')
    if not namespace or not name:
        return None
    return namespace, name


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
    init_containers = list(_model_value(template_spec, 'init_containers', 'initContainers', default=[]) or [])
    containers: list[dict[str, Any]] = []

    for container in regular_containers:
        resources = _model_value(container, 'resources')
        requests = _model_value(resources, 'requests', default={}) or {}
        limits = _model_value(resources, 'limits', default={}) or {}
        containers.append(
            {
                'name': _string_value(_model_value(container, 'name')),
                'image': _string_value(_model_value(container, 'image')),
                'pull_policy': _string_value(_model_value(container, 'image_pull_policy', 'imagePullPolicy')),
                'kind': 'Container',
                'resources': {
                    'requests': {str(key): str(value) for key, value in dict(requests).items()},
                    'limits': {str(key): str(value) for key, value in dict(limits).items()},
                },
            }
        )

    for container in init_containers:
        resources = _model_value(container, 'resources')
        requests = _model_value(resources, 'requests', default={}) or {}
        limits = _model_value(resources, 'limits', default={}) or {}
        containers.append(
            {
                'name': _string_value(_model_value(container, 'name')),
                'image': _string_value(_model_value(container, 'image')),
                'pull_policy': _string_value(_model_value(container, 'image_pull_policy', 'imagePullPolicy')),
                'kind': 'Init container',
                'resources': {
                    'requests': {str(key): str(value) for key, value in dict(requests).items()},
                    'limits': {str(key): str(value) for key, value in dict(limits).items()},
                },
            }
        )

    tolerations = [
        _toleration_display(toleration) for toleration in (_model_value(template_spec, 'tolerations', default=[]) or [])
    ]
    node_selector = (
        _model_value(
            template_spec,
            'node_selector',
            'nodeSelector',
            default={},
        )
        or {}
    )

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
        'restart_policy': _string_value(_model_value(template_spec, 'restart_policy', 'restartPolicy')),
        'priority_class': _string_value(_model_value(template_spec, 'priority_class_name', 'priorityClassName')),
        'scheduler': _string_value(
            _model_value(template_spec, 'scheduler_name', 'schedulerName'),
            'default-scheduler',
        ),
        'host_network': bool(_model_value(template_spec, 'host_network', 'hostNetwork', default=False)),
        'dns_policy': _string_value(_model_value(template_spec, 'dns_policy', 'dnsPolicy')),
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
        'runtime_class': _string_value(_model_value(template_spec, 'runtime_class_name', 'runtimeClassName')),
    }


def _workload_details(
    metadata,
    template_spec,
    *,
    state_display: str,
    state_rows: list[dict[str, str]],
    delivery_rows: list[dict[str, str]],
    status=None,
    canonical_fields: dict[str, Any] | None = None,
) -> dict:
    details = _metadata_details(metadata)
    details.update(
        {
            'schema_version': 3,
            'state_display': state_display,
            'state_rows': state_rows,
            'delivery_rows': delivery_rows,
            'pod_template': _pod_template_details(template_spec),
            'status_reported': status is not None,
            'conditions': _condition_rows(status),
        }
    )
    details.update(canonical_fields or {})
    return details


def _deployment_row(deployment) -> dict | None:
    metadata = deployment.metadata
    spec = deployment.spec
    status = deployment.status
    identity = _metadata_identity(metadata)
    if identity is None or spec is None:
        return None
    namespace, name = identity

    desired = _desired_replicas(spec)
    current = getattr(status, 'replicas', 0) or 0
    updated = getattr(status, 'updated_replicas', 0) or 0
    ready = getattr(status, 'ready_replicas', 0) or 0
    available = getattr(status, 'available_replicas', 0) or 0
    unavailable = getattr(status, 'unavailable_replicas', 0) or max(desired - available, 0)
    observed_generation = getattr(status, 'observed_generation', None)
    metadata_generation = getattr(metadata, 'generation', None)
    strategy = getattr(spec, 'strategy', None)
    rolling_update = getattr(strategy, 'rolling_update', None)
    strategy_name = getattr(strategy, 'type', None)

    generation_current = metadata_generation is None or (
        observed_generation is not None and int(observed_generation) >= int(metadata_generation)
    )
    if status is None:
        workload_status = 'Unknown'
        state_display = 'Runtime State Not Reported'
    elif _deployment_progress_deadline_exceeded(status):
        workload_status = 'Failed'
        state_display = 'Progress Deadline Exceeded'
    elif _condition_is_true(status, 'ReplicaFailure'):
        workload_status = 'Failed'
        state_display = 'Replica Failure Reported'
    elif generation_current and available >= desired and updated >= desired and unavailable == 0:
        workload_status = 'Stable'
        state_display = f'{available}/{desired} Available'
    else:
        workload_status = 'Progressing'
        state_display = f'{available}/{desired} Available'

    details = _workload_details(
        metadata,
        _workload_pod_template_spec(spec),
        state_display=state_display,
        state_rows=[
            _detail_row('Desired Replicas', desired),
            _detail_row('Current Replicas', current),
            _detail_row('Updated Replicas', updated),
            _detail_row('Ready Replicas', ready),
            _detail_row('Available Replicas', available),
            _detail_row('Unavailable Replicas', unavailable),
            _detail_row('Observed Generation', observed_generation),
        ],
        delivery_rows=[
            _detail_row('Strategy', strategy_name),
            _detail_row('Max Surge', getattr(rolling_update, 'max_surge', None)),
            _detail_row('Max Unavailable', getattr(rolling_update, 'max_unavailable', None)),
            _detail_row('Min Ready Seconds', getattr(spec, 'min_ready_seconds', None)),
            _detail_row('Progress Deadline', getattr(spec, 'progress_deadline_seconds', None)),
            _detail_row('Revision History Limit', getattr(spec, 'revision_history_limit', None)),
        ],
        status=status,
        canonical_fields={
            'desired_replicas': desired,
            'current_replicas': current,
            'updated_replicas': updated,
            'ready_replicas': ready,
            'available_replicas': available,
            'unavailable_replicas': unavailable,
            'update_strategy': strategy_name,
            'generation': metadata_generation,
            'observed_generation': observed_generation,
        },
    )
    return {
        'namespace': namespace,
        'name': name,
        'workload_type': 'Deployment',
        'ready': f'{available}/{desired}',
        'status': workload_status,
        'created_at': metadata.creation_timestamp,
        'details': details,
    }


def _statefulset_row(statefulset) -> dict | None:
    metadata = statefulset.metadata
    spec = statefulset.spec
    status = statefulset.status
    identity = _metadata_identity(metadata)
    if identity is None or spec is None:
        return None
    namespace, name = identity

    desired = _desired_replicas(spec)
    current = getattr(status, 'current_replicas', 0) or 0
    updated = getattr(status, 'updated_replicas', 0) or 0
    ready = getattr(status, 'ready_replicas', 0) or 0
    available = getattr(status, 'available_replicas', 0) or ready
    current_revision = getattr(status, 'current_revision', None)
    update_revision = getattr(status, 'update_revision', None)
    update_strategy = getattr(spec, 'update_strategy', None)
    rolling_update = getattr(update_strategy, 'rolling_update', None)
    strategy_name = getattr(update_strategy, 'type', None)
    revisions_current = not current_revision or not update_revision or current_revision == update_revision

    if status is None:
        workload_status = 'Unknown'
        state_display = 'Runtime State Not Reported'
    elif _condition_is_true(status, 'ReplicaFailure'):
        workload_status = 'Failed'
        state_display = 'Replica Failure Reported'
    elif ready >= desired and updated >= desired and revisions_current:
        workload_status = 'Stable'
        state_display = f'{ready}/{desired} Ready'
    else:
        workload_status = 'Progressing'
        state_display = f'{ready}/{desired} Ready'

    details = _workload_details(
        metadata,
        _workload_pod_template_spec(spec),
        state_display=state_display,
        state_rows=[
            _detail_row('Desired Replicas', desired),
            _detail_row('Current Replicas', current),
            _detail_row('Updated Replicas', updated),
            _detail_row('Ready Replicas', ready),
            _detail_row('Available Replicas', available),
            _detail_row('Current Revision', current_revision),
            _detail_row('Update Revision', update_revision),
        ],
        delivery_rows=[
            _detail_row('Update Strategy', strategy_name),
            _detail_row('Pod Management Policy', getattr(spec, 'pod_management_policy', None)),
            _detail_row('Partition', getattr(rolling_update, 'partition', None)),
            _detail_row('Min Ready Seconds', getattr(spec, 'min_ready_seconds', None)),
            _detail_row('Service Name', getattr(spec, 'service_name', None)),
            _detail_row('Revision History Limit', getattr(spec, 'revision_history_limit', None)),
        ],
        status=status,
        canonical_fields={
            'desired_replicas': desired,
            'current_replicas': current,
            'updated_replicas': updated,
            'ready_replicas': ready,
            'available_replicas': available,
            'unavailable_replicas': max(desired - available, 0),
            'update_strategy': strategy_name,
            'current_revision': current_revision,
            'update_revision': update_revision,
        },
    )
    return {
        'namespace': namespace,
        'name': name,
        'workload_type': 'StatefulSet',
        'ready': f'{ready}/{desired}',
        'status': workload_status,
        'created_at': metadata.creation_timestamp,
        'details': details,
    }


def _daemonset_row(daemonset) -> dict | None:
    metadata = daemonset.metadata
    spec = daemonset.spec
    status = daemonset.status
    identity = _metadata_identity(metadata)
    if identity is None or spec is None:
        return None
    namespace, name = identity

    desired = getattr(status, 'desired_number_scheduled', 0) or 0
    current = getattr(status, 'current_number_scheduled', 0) or 0
    ready = getattr(status, 'number_ready', 0) or 0
    available = getattr(status, 'number_available', 0) or 0
    updated = getattr(status, 'updated_number_scheduled', 0) or 0
    misscheduled = getattr(status, 'number_misscheduled', 0) or 0
    unavailable = getattr(status, 'number_unavailable', 0) or max(desired - available, 0)
    update_strategy = getattr(spec, 'update_strategy', None)
    rolling_update = getattr(update_strategy, 'rolling_update', None)
    strategy_name = getattr(update_strategy, 'type', None)

    if status is None:
        workload_status = 'Unknown'
        state_display = 'Runtime State Not Reported'
    elif _condition_is_true(status, 'ReplicaFailure'):
        workload_status = 'Failed'
        state_display = 'Replica Failure Reported'
    elif ready >= desired and updated >= desired and unavailable == 0 and misscheduled == 0:
        workload_status = 'Stable'
        state_display = f'{ready}/{desired} Ready'
    else:
        workload_status = 'Progressing'
        state_display = f'{ready}/{desired} Ready'

    details = _workload_details(
        metadata,
        _workload_pod_template_spec(spec),
        state_display=state_display,
        state_rows=[
            _detail_row('Desired Scheduled', desired),
            _detail_row('Current Scheduled', current),
            _detail_row('Ready', ready),
            _detail_row('Available', available),
            _detail_row('Updated', updated),
            _detail_row('Misscheduled', misscheduled),
            _detail_row('Unavailable', unavailable),
        ],
        delivery_rows=[
            _detail_row('Update Strategy', strategy_name),
            _detail_row('Max Unavailable', getattr(rolling_update, 'max_unavailable', None)),
            _detail_row('Max Surge', getattr(rolling_update, 'max_surge', None)),
            _detail_row('Min Ready Seconds', getattr(spec, 'min_ready_seconds', None)),
            _detail_row('Revision History Limit', getattr(spec, 'revision_history_limit', None)),
        ],
        status=status,
        canonical_fields={
            'desired_replicas': desired,
            'current_replicas': current,
            'updated_replicas': updated,
            'ready_replicas': ready,
            'available_replicas': available,
            'unavailable_replicas': unavailable,
            'misscheduled_replicas': misscheduled,
            'update_strategy': strategy_name,
        },
    )
    return {
        'namespace': namespace,
        'name': name,
        'workload_type': 'DaemonSet',
        'ready': f'{ready}/{desired}',
        'status': workload_status,
        'created_at': metadata.creation_timestamp,
        'details': details,
    }


def _job_row(job) -> dict | None:
    metadata = job.metadata
    spec = job.spec
    status = job.status
    identity = _metadata_identity(metadata)
    if identity is None or spec is None:
        return None
    namespace, name = identity

    completions = spec.completions if spec.completions is not None else 1
    parallelism = spec.parallelism if spec.parallelism is not None else 1
    succeeded = getattr(status, 'succeeded', 0) or 0
    failed = getattr(status, 'failed', 0) or 0
    active = getattr(status, 'active', 0) or 0
    suspended = bool(getattr(spec, 'suspend', False))

    if suspended:
        job_status = 'Suspended'
        state_display = 'Suspended'
    elif status is None:
        job_status = 'Unknown'
        state_display = 'Runtime State Not Reported'
    elif _condition_is_true(status, 'Failed'):
        job_status = 'Failed'
        state_display = f'{failed} Failed'
    elif _condition_is_true(status, 'Complete') or (succeeded >= completions and active == 0):
        job_status = 'Stable'
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
            _detail_row('Backoff Limit', getattr(spec, 'backoff_limit', None)),
            _detail_row('Completion Mode', getattr(spec, 'completion_mode', None)),
        ],
        delivery_rows=[
            _detail_row('Backoff Limit', getattr(spec, 'backoff_limit', None)),
            _detail_row('Active Deadline', getattr(spec, 'active_deadline_seconds', None)),
            _detail_row('TTL After Finished', getattr(spec, 'ttl_seconds_after_finished', None)),
            _detail_row('Suspend', suspended),
        ],
        status=status,
        canonical_fields={
            'desired_replicas': completions,
            'current_replicas': active,
            'updated_replicas': None,
            'ready_replicas': succeeded,
            'available_replicas': succeeded,
            'unavailable_replicas': None,
            'update_strategy': 'Job Execution',
            'parallelism': parallelism,
            'failed_replicas': failed,
            'suspended': suspended,
        },
    )
    return {
        'namespace': namespace,
        'name': name,
        'workload_type': 'Job',
        'ready': f'{succeeded}/{completions}',
        'status': job_status,
        'created_at': metadata.creation_timestamp,
        'details': details,
    }


def _cronjob_row(raw_cronjob) -> dict | None:
    cronjob = _to_modelish(raw_cronjob)
    metadata = cronjob.metadata
    spec = cronjob.spec
    status = cronjob.status
    identity = _metadata_identity(metadata)
    if identity is None or spec is None:
        return None
    namespace, name = identity

    active_count = len(getattr(status, 'active', None) or [])
    schedule = spec.schedule or '-'
    suspended = bool(getattr(spec, 'suspend', False))
    cronjob_status = 'Suspended' if suspended else 'Stable'
    state_display = 'Suspended' if suspended else (f'{active_count} Active' if active_count else 'Scheduled')

    details = _workload_details(
        metadata,
        _cronjob_pod_template_spec(spec),
        state_display=state_display,
        state_rows=[
            _detail_row('Schedule', schedule),
            _detail_row('Time Zone', getattr(spec, 'time_zone', None)),
            _detail_row('Suspended', suspended),
            _detail_row('Active Jobs', active_count),
            _detail_row('Last Schedule', _isoformat_datetime(getattr(status, 'last_schedule_time', None))),
            _detail_row(
                'Last successful execution',
                _isoformat_datetime(getattr(status, 'last_successful_time', None)),
            ),
            _detail_row('Concurrency Policy', getattr(spec, 'concurrency_policy', None)),
        ],
        delivery_rows=[
            _detail_row('Concurrency Policy', getattr(spec, 'concurrency_policy', None)),
            _detail_row('Starting Deadline', getattr(spec, 'starting_deadline_seconds', None)),
            _detail_row('Successful History Limit', getattr(spec, 'successful_jobs_history_limit', None)),
            _detail_row('Failed History Limit', getattr(spec, 'failed_jobs_history_limit', None)),
            _detail_row('Suspend', suspended),
        ],
        status=status,
        canonical_fields={
            'desired_replicas': None,
            'current_replicas': active_count,
            'updated_replicas': None,
            'ready_replicas': None,
            'available_replicas': active_count,
            'unavailable_replicas': None,
            'update_strategy': 'Scheduled Execution',
            'schedule': schedule,
            'suspended': suspended,
        },
    )
    return {
        'namespace': namespace,
        'name': name,
        'workload_type': 'CronJob',
        'ready': f'{active_count} active',
        'status': cronjob_status,
        'created_at': metadata.creation_timestamp,
        'schedule': schedule,
        'details': details,
    }


def _collect_rows(items, builder) -> list[dict]:
    rows: list[dict] = []
    for item in items or []:
        row = builder(item)
        if row is not None:
            rows.append(row)
    return rows


def _load_cronjob_items(batch_api: BatchV1Api) -> list[Any]:
    try:
        cronjobs = cast(V1CronJobList, batch_api.list_cron_job_for_all_namespaces())
        return list(cronjobs.items or [])
    except NotFoundException:
        return []
    except ApiException as exc:
        if getattr(exc, 'status', None) == 404:
            return []
        raise


def get_workloads(
    api: AppsV1Api,
    batch_api: BatchV1Api | None = None,
    cronjob_items: list[Any] | None = None,
) -> list[dict]:
    deployments = cast(V1DeploymentList, api.list_deployment_for_all_namespaces())
    statefulsets = cast(V1StatefulSetList, api.list_stateful_set_for_all_namespaces())
    daemonsets = cast(V1DaemonSetList, api.list_daemon_set_for_all_namespaces())

    workloads = _collect_rows(deployments.items, _deployment_row)
    workloads.extend(_collect_rows(statefulsets.items, _statefulset_row))
    workloads.extend(_collect_rows(daemonsets.items, _daemonset_row))

    if batch_api is None:
        return workloads

    jobs = cast(V1JobList, batch_api.list_job_for_all_namespaces())
    workloads.extend(_collect_rows(jobs.items, _job_row))
    workloads.extend(
        _collect_rows(
            cronjob_items if cronjob_items is not None else _load_cronjob_items(batch_api),
            _cronjob_row,
        )
    )
    return workloads
