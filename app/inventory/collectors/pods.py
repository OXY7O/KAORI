from __future__ import annotations

from typing import (
    Any,
    cast,
)
from kubernetes.client import (
    AppsV1Api,
    BatchV1Api,
    CoreV1Api,
    V1JobList,
    V1PodList,
    V1ReplicaSetList,
)

from app.inventory.collectors.common import _isoformat_datetime, _model_value, _string_value, _toleration_display

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
