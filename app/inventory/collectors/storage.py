from __future__ import annotations

from typing import Any, cast

from kubernetes.client import (
    CoreV1Api,
    StorageV1Api,
    V1PersistentVolumeClaimList,
    V1PersistentVolumeList,
    V1StorageClassList,
)

from app.inventory.collectors.common import _isoformat_datetime, _metadata_details, _model_value, _string_value


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
                )
                or '-',
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
                if spec and spec.resources and spec.resources.requests and spec.resources.requests.get('storage')
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
