from __future__ import annotations

from typing import Any, Literal, cast, overload

from kubernetes.client import (
    CoreV1Api,
    StorageV1Api,
    V1PersistentVolumeClaimList,
    V1PersistentVolumeList,
    V1StorageClassList,
)
from kubernetes.client.exceptions import ApiException

from app.kubernetes.inventory.collectors.common import (
    _isoformat_datetime,
    _metadata_details,
    _model_value,
    _string_value,
)

COLLECTED = 'Collected'
PERMISSION_UNAVAILABLE = 'Permission Unavailable'
API_UNAVAILABLE = 'API Unavailable'
ADAPTER_NOT_SELECTED = 'Adapter Not Selected'

STORAGE_CLASS_EVIDENCE_KEY = 'inventory.storageclasses'
PERSISTENT_VOLUME_EVIDENCE_KEY = 'inventory.persistentvolumes'
PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY = 'inventory.persistentvolumeclaims'


def _collection_error_state(exc: ApiException) -> str:
    return PERMISSION_UNAVAILABLE if getattr(exc, 'status', None) == 403 else API_UNAVAILABLE


def _collect_api_items(api: Any, method_name: str, list_type: type) -> tuple[list[Any], str]:
    if api is None:
        return [], ADAPTER_NOT_SELECTED
    method = getattr(api, method_name, None)
    if method is None:
        return [], API_UNAVAILABLE
    try:
        result = cast(Any, method())
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            return [], _collection_error_state(exc)
        raise
    if not isinstance(result, list_type) and not hasattr(result, 'items'):
        return [], API_UNAVAILABLE
    return list(getattr(result, 'items', None) or []), COLLECTED


def _persistent_volume_source_details(spec: Any) -> dict[str, Any]:
    if spec is None:
        return {'type': 'Not Reported', 'reported': False}

    sources = (
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
    )
    for display_name, attribute in sources:
        source = _model_value(spec, attribute)
        if source is None:
            continue
        details: dict[str, Any] = {'type': display_name, 'reported': True}
        if display_name == 'CSI':
            details.update(
                {
                    'driver': _string_value(_model_value(source, 'driver'), ''),
                    'volume_handle': _string_value(
                        _model_value(source, 'volume_handle', 'volumeHandle'),
                        '',
                    ),
                    'read_only': bool(_model_value(source, 'read_only', 'readOnly', default=False)),
                    'fs_type': _string_value(_model_value(source, 'fs_type', 'fsType'), ''),
                }
            )
        elif display_name == 'Local':
            details['path'] = _string_value(_model_value(source, 'path'), '')
        elif display_name == 'NFS':
            details.update(
                {
                    'server': _string_value(_model_value(source, 'server'), ''),
                    'path': _string_value(_model_value(source, 'path'), ''),
                    'read_only': bool(_model_value(source, 'read_only', 'readOnly', default=False)),
                }
            )
        elif display_name == 'HostPath':
            details.update(
                {
                    'path': _string_value(_model_value(source, 'path'), ''),
                    'host_path_type': _string_value(_model_value(source, 'type'), ''),
                }
            )
        return details
    return {'type': 'Other', 'reported': True}


def _pvc_conditions(status: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in _model_value(status, 'conditions', default=[]) or []:
        rows.append(
            {
                'type': _string_value(_model_value(condition, 'type'), 'Unknown'),
                'status': _string_value(_model_value(condition, 'status'), 'Unknown'),
                'reason': _string_value(_model_value(condition, 'reason'), ''),
                'message': _string_value(_model_value(condition, 'message'), ''),
                'last_transition_time': _isoformat_datetime(
                    _model_value(condition, 'last_transition_time', 'lastTransitionTime')
                ),
            }
        )
    return rows


def _metadata_evidence(metadata: Any) -> dict[str, Any]:
    return {
        **_metadata_details(metadata),
        'finalizers': list(_model_value(metadata, 'finalizers', default=[]) or []),
        'deletion_timestamp': _isoformat_datetime(_model_value(metadata, 'deletion_timestamp', 'deletionTimestamp')),
    }


def _storage_class_row(storage_class: Any) -> dict[str, Any] | None:
    metadata = _model_value(storage_class, 'metadata')
    name = _model_value(metadata, 'name')
    provisioner = _model_value(storage_class, 'provisioner')
    if metadata is None or name in (None, '') or provisioner in (None, ''):
        return None

    annotations = dict(_model_value(metadata, 'annotations', default={}) or {})
    is_default = any(
        str(annotations.get(key) or '').casefold() == 'true'
        for key in (
            'storageclass.kubernetes.io/is-default-class',
            'storageclass.beta.kubernetes.io/is-default-class',
        )
    )
    allow_expansion = _model_value(storage_class, 'allow_volume_expansion', 'allowVolumeExpansion')
    reclaim_policy = _model_value(storage_class, 'reclaim_policy', 'reclaimPolicy')
    binding_mode = _model_value(storage_class, 'volume_binding_mode', 'volumeBindingMode')
    details = {
        **_metadata_evidence(metadata),
        'specification_evidence_reported': True,
        'provisioner': str(provisioner),
        'reclaim_policy': str(reclaim_policy) if reclaim_policy not in (None, '') else None,
        'volume_binding_mode': str(binding_mode) if binding_mode not in (None, '') else None,
        'allow_volume_expansion': bool(allow_expansion) if allow_expansion is not None else None,
        'allow_volume_expansion_reported': allow_expansion is not None,
        'parameters': dict(sorted((_model_value(storage_class, 'parameters', default={}) or {}).items())),
        'mount_options': list(_model_value(storage_class, 'mount_options', 'mountOptions', default=[]) or []),
        'allowed_topology_count': len(
            _model_value(storage_class, 'allowed_topologies', 'allowedTopologies', default=[]) or []
        ),
        'is_default': is_default,
    }
    return {
        'namespace': None,
        'name': str(name),
        'storage_type': 'StorageClass',
        'storage_class': str(name),
        'capacity': None,
        'status': 'Configured',
        'details': details,
        'created_at': _model_value(metadata, 'creation_timestamp', 'creationTimestamp'),
    }


def _persistent_volume_row(pv: Any) -> dict[str, Any] | None:
    metadata = _model_value(pv, 'metadata')
    name = _model_value(metadata, 'name')
    spec = _model_value(pv, 'spec')
    status = _model_value(pv, 'status')
    if metadata is None or name in (None, ''):
        return None

    capacity_map = _model_value(spec, 'capacity', default={}) or {}
    claim_ref = _model_value(spec, 'claim_ref', 'claimRef')
    details = {
        **_metadata_evidence(metadata),
        'specification_evidence_reported': spec is not None,
        'status_evidence_reported': status is not None,
        'kubernetes_phase': str(_model_value(status, 'phase'))
        if _model_value(status, 'phase') not in (None, '')
        else None,
        'claim_namespace': _model_value(claim_ref, 'namespace'),
        'claim_name': _model_value(claim_ref, 'name'),
        'reclaim_policy': _model_value(spec, 'persistent_volume_reclaim_policy', 'persistentVolumeReclaimPolicy'),
        'access_modes': list(_model_value(spec, 'access_modes', 'accessModes', default=[]) or []),
        'volume_mode': _model_value(spec, 'volume_mode', 'volumeMode'),
        'mount_options': list(_model_value(spec, 'mount_options', 'mountOptions', default=[]) or []),
        'node_affinity_configured': bool(_model_value(spec, 'node_affinity', 'nodeAffinity')),
        'source': _persistent_volume_source_details(spec),
    }
    storage_class = _model_value(spec, 'storage_class_name', 'storageClassName')
    phase = _model_value(status, 'phase')
    lifecycle = (
        'Terminating' if details.get('deletion_timestamp') else (None if status is None else str(phase or 'Unknown'))
    )
    return {
        'namespace': None,
        'name': str(name),
        'storage_type': 'PersistentVolume',
        'storage_class': str(storage_class) if storage_class not in (None, '') else None,
        'capacity': capacity_map.get('storage'),
        'status': lifecycle,
        'details': details,
        'created_at': _model_value(metadata, 'creation_timestamp', 'creationTimestamp'),
    }


def _persistent_volume_claim_row(pvc: Any) -> dict[str, Any] | None:
    metadata = _model_value(pvc, 'metadata')
    namespace = _model_value(metadata, 'namespace')
    name = _model_value(metadata, 'name')
    spec = _model_value(pvc, 'spec')
    status = _model_value(pvc, 'status')
    if metadata is None or namespace in (None, '') or name in (None, ''):
        return None

    status_capacity = _model_value(status, 'capacity', default={}) or {}
    resources = _model_value(spec, 'resources')
    resource_requests = _model_value(resources, 'requests', default={}) or {}
    selector = _model_value(spec, 'selector')
    data_source = _model_value(spec, 'data_source', 'dataSource')
    if data_source is None:
        data_source = _model_value(spec, 'data_source_ref', 'dataSourceRef')
    allocated_resources = _model_value(status, 'allocated_resources', 'allocatedResources', default={}) or {}
    details = {
        **_metadata_evidence(metadata),
        'specification_evidence_reported': spec is not None,
        'status_evidence_reported': status is not None,
        'kubernetes_phase': str(_model_value(status, 'phase'))
        if _model_value(status, 'phase') not in (None, '')
        else None,
        'capacity_evidence_reported': bool(status is not None and _model_value(status, 'capacity') is not None),
        'volume_name': _model_value(spec, 'volume_name', 'volumeName'),
        'requested_access_modes': list(_model_value(spec, 'access_modes', 'accessModes', default=[]) or []),
        'reported_access_modes': list(_model_value(status, 'access_modes', 'accessModes', default=[]) or []),
        'volume_mode': _model_value(spec, 'volume_mode', 'volumeMode'),
        'requested_storage': str(resource_requests.get('storage'))
        if resource_requests.get('storage') not in (None, '')
        else None,
        'allocated_storage': (
            str(allocated_resources.get('storage')) if allocated_resources.get('storage') not in (None, '') else None
        ),
        'selector': dict(_model_value(selector, 'match_labels', 'matchLabels', default={}) or {}),
        'data_source': (
            {
                'kind': _string_value(_model_value(data_source, 'kind'), ''),
                'name': _string_value(_model_value(data_source, 'name'), ''),
                'api_group': _string_value(_model_value(data_source, 'api_group', 'apiGroup'), ''),
            }
            if data_source is not None
            else None
        ),
        'conditions': _pvc_conditions(status),
    }
    storage_class = _model_value(spec, 'storage_class_name', 'storageClassName')
    phase = _model_value(status, 'phase')
    lifecycle = (
        'Terminating' if details.get('deletion_timestamp') else (None if status is None else str(phase or 'Unknown'))
    )
    return {
        'namespace': str(namespace),
        'name': str(name),
        'storage_type': 'PersistentVolumeClaim',
        'storage_class': str(storage_class) if storage_class not in (None, '') else None,
        'capacity': status_capacity.get('storage'),
        'status': lifecycle,
        'details': details,
        'created_at': _model_value(metadata, 'creation_timestamp', 'creationTimestamp'),
    }


@overload
def get_storage_inventory(
    core_api: CoreV1Api | None,
    storage_api: StorageV1Api | None,
    *,
    with_evidence: Literal[False] = False,
) -> list[dict[str, Any]]: ...


@overload
def get_storage_inventory(
    core_api: CoreV1Api | None,
    storage_api: StorageV1Api | None,
    *,
    with_evidence: Literal[True],
) -> tuple[list[dict[str, Any]], dict[str, str]]: ...


def get_storage_inventory(
    core_api: CoreV1Api | None,
    storage_api: StorageV1Api | None,
    *,
    with_evidence: bool = False,
):
    storage_classes, storage_class_state = _collect_api_items(
        storage_api,
        'list_storage_class',
        V1StorageClassList,
    )
    persistent_volumes, persistent_volume_state = _collect_api_items(
        core_api,
        'list_persistent_volume',
        V1PersistentVolumeList,
    )
    persistent_volume_claims, persistent_volume_claim_state = _collect_api_items(
        core_api,
        'list_persistent_volume_claim_for_all_namespaces',
        V1PersistentVolumeClaimList,
    )

    items = [
        row
        for row in (
            *(_storage_class_row(item) for item in storage_classes),
            *(_persistent_volume_row(item) for item in persistent_volumes),
            *(_persistent_volume_claim_row(item) for item in persistent_volume_claims),
        )
        if row is not None
    ]
    evidence = {
        STORAGE_CLASS_EVIDENCE_KEY: storage_class_state,
        PERSISTENT_VOLUME_EVIDENCE_KEY: persistent_volume_state,
        PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY: persistent_volume_claim_state,
    }
    if with_evidence:
        return items, evidence
    return items
