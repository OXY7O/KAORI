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

from app.inventory.collectors.common import (
    _detail_row,
    _isoformat_datetime,
    _metadata_details,
    _model_value,
    _string_value,
    _to_modelish,
    _toleration_display,
)


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


def get_workloads(
    api: AppsV1Api,
    batch_api: BatchV1Api | None = None,
    cronjob_items: list[Any] | None = None,
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

    if cronjob_items is None:
        try:
            cronjobs = cast(
                V1CronJobList,
                batch_api.list_cron_job_for_all_namespaces(),
            )
            cronjob_items = list(cronjobs.items or [])
        except NotFoundException:
            cronjob_items = []
        except ApiException as exc:
            if getattr(exc, 'status', None) == 404:
                cronjob_items = []
            else:
                raise

    for raw_cronjob in cronjob_items:
        cronjob = _to_modelish(raw_cronjob)
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
