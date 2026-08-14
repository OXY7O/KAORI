from __future__ import annotations

from typing import Any

from app.inventory.kubernetes.formatting import format_kubernetes_size

COLLECTED = 'Collected'
NOT_REPORTED = 'Not Reported'
NOT_CONFIGURED = 'Not Configured'
NOT_ASSIGNED = 'Not Assigned'
UNKNOWN_FILTER = '__unknown__'

STORAGE_CLASS_EVIDENCE_KEY = 'inventory.storageclasses'
PERSISTENT_VOLUME_EVIDENCE_KEY = 'inventory.persistentvolumes'
PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY = 'inventory.persistentvolumeclaims'

STORAGE_TYPE_LABELS = {
    'StorageClass': 'StorageClass',
    'PersistentVolume': 'PersistentVolume',
    'PersistentVolumeClaim': 'PersistentVolumeClaim',
}

LIFECYCLE_ORDER = (
    'Configured',
    'Bound',
    'Available',
    'Pending',
    'Released',
    'Terminating',
    'Failed',
    'Lost',
    'Unknown',
    NOT_REPORTED,
)


def lifecycle_presentation(
    storage_type: str,
    status: str | None,
    details: dict[str, Any] | None = None,
) -> tuple[str, str]:
    details = details or {}
    if details.get('deletion_timestamp'):
        return 'Terminating', 'warning'
    if storage_type == 'StorageClass':
        return 'Configured', 'normal'
    if status in (None, ''):
        return NOT_REPORTED, 'unknown'
    value = str(status)
    tones = {
        'Bound': 'normal',
        'Available': 'info',
        'Pending': 'warning',
        'Released': 'warning',
        'Terminating': 'warning',
        'Failed': 'critical',
        'Lost': 'critical',
        'Unknown': 'unknown',
    }
    return value, tones.get(value, 'unknown')


def lifecycle_filter_value(storage_type: str, status: str | None, details: dict[str, Any] | None = None) -> str:
    label, _ = lifecycle_presentation(storage_type, status, details)
    return UNKNOWN_FILTER if label == NOT_REPORTED else label


def lifecycle_filter_label(value: str) -> str:
    return NOT_REPORTED if value == UNKNOWN_FILTER else value


def size_presentation(value: Any, *, missing: str = NOT_REPORTED) -> str:
    rendered = format_kubernetes_size(value) if value not in (None, '') else '-'
    return missing if rendered == '-' else rendered


def list_presentation(
    values: list[Any] | tuple[Any, ...] | None,
    *,
    evidence_reported: bool,
) -> str:
    if not evidence_reported:
        return NOT_REPORTED
    normalized = [str(value) for value in (values or []) if value not in (None, '')]
    return ', '.join(normalized) if normalized else NOT_CONFIGURED


def capacity_presentation(
    storage_type: str,
    capacity: str | None,
    details: dict[str, Any],
) -> tuple[str, str]:
    if storage_type == 'StorageClass':
        expansion = expansion_presentation(storage_type, details)
        return 'Not Applicable', f'Volume expansion · {expansion}'
    if storage_type == 'PersistentVolume':
        specification_reported = details.get('specification_evidence_reported') is True
        capacity_label = size_presentation(
            capacity,
            missing=NOT_CONFIGURED if specification_reported else NOT_REPORTED,
        )
        access_label = list_presentation(
            details.get('access_modes'),
            evidence_reported=specification_reported,
        )
        return capacity_label, f'Access modes · {access_label}'

    requested = details.get('requested_storage')
    specification_reported = details.get('specification_evidence_reported') is True
    status_reported = details.get('status_evidence_reported') is True
    requested_label = size_presentation(
        requested,
        missing=NOT_CONFIGURED if specification_reported else NOT_REPORTED,
    )
    capacity_label = size_presentation(
        capacity if details.get('capacity_evidence_reported') else None,
        missing=NOT_ASSIGNED if status_reported else NOT_REPORTED,
    )
    return f'Requested {requested_label}', f'Bound capacity · {capacity_label}'


def expansion_presentation(storage_type: str, details: dict[str, Any]) -> str:
    if storage_type != 'StorageClass':
        return 'Not Applicable'
    if not details.get('allow_volume_expansion_reported'):
        return NOT_REPORTED
    return 'Allowed' if details.get('allow_volume_expansion') else 'Not Allowed'


def binding_reference(storage_type: str, details: dict[str, Any]) -> str:
    if storage_type == 'StorageClass':
        return 'Provisioning Class'
    if details.get('specification_evidence_reported') is not True:
        return NOT_REPORTED
    if storage_type == 'PersistentVolume':
        namespace = details.get('claim_namespace')
        name = details.get('claim_name')
        return f'{namespace}/{name}' if namespace and name else 'Unbound'
    volume_name = details.get('volume_name')
    return str(volume_name) if volume_name else 'Waiting for Volume'


def provisioning_presentation(
    storage_type: str,
    storage_class: str | None,
    details: dict[str, Any],
) -> tuple[str, str]:
    if storage_type == 'StorageClass':
        return (
            str(details.get('provisioner') or NOT_REPORTED),
            str(details.get('volume_binding_mode') or NOT_REPORTED),
        )
    specification_reported = details.get('specification_evidence_reported') is True
    class_label = (
        str(storage_class)
        if storage_class not in (None, '')
        else (NOT_CONFIGURED if specification_reported else NOT_REPORTED)
    )
    if storage_type == 'PersistentVolume':
        raw_source = details.get('source')
        source = raw_source if isinstance(raw_source, dict) else {}
        return class_label, str(source.get('type') or NOT_REPORTED)
    return class_label, 'PersistentVolumeClaim'


def data_source_presentation(details: dict[str, Any]) -> str:
    value = details.get('data_source')
    if isinstance(value, dict):
        kind = str(value.get('kind') or 'Resource')
        name = str(value.get('name') or NOT_REPORTED)
        api_group = str(value.get('api_group') or 'core')
        return f'{kind}/{name} · {api_group}'
    if details.get('specification_evidence_reported') is False:
        return NOT_REPORTED
    return 'Not Configured'


def collection_posture(states: list[str]) -> tuple[str, str, int]:
    if not states:
        return NOT_REPORTED, 'unknown', 0
    exceptions = sum(1 for state in states if state != COLLECTED)
    if exceptions == 0:
        return 'Complete', 'normal', 0
    if exceptions == len(states):
        return NOT_REPORTED, 'unknown', exceptions
    return 'Partial', 'warning', exceptions
