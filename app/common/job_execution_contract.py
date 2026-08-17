from __future__ import annotations

from app.definitions.loader import load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str

KUBERNETES_INVENTORY_SYNC_OPERATION = 'sync_kubernetes_inventory'
OBJECT_STORAGE_INVENTORY_SYNC_OPERATION = 'sync_object_storage_inventory'
OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION = 'materialize_object_storage_forecast'
SYNC_ALL_INVENTORY_ACTION = 'sync_all_inventory'


def _registered_operation_labels() -> dict[str, str]:
    document = load_definition_document(
        'platform_operations/jobs/registered_jobs.yaml', expected_kind='registered_jobs'
    )
    return {
        require_str(require_mapping(item, f'jobs[{index}]'), 'operation', f'jobs[{index}]'): require_str(
            require_mapping(item, f'jobs[{index}]'), 'name', f'jobs[{index}]'
        )
        for index, item in enumerate(require_list(document.get('jobs'), 'jobs'))
    }


_REGISTERED_OPERATION_LABELS = _registered_operation_labels()


def registered_job_operation_label(operation: str) -> str:
    """Return the canonical label for a registered KAORI job operation."""
    try:
        return _REGISTERED_OPERATION_LABELS[operation]
    except KeyError as exc:
        raise LookupError(f'Unknown registered job operation: {operation}') from exc


def job_operation_label(operation: str) -> str:
    """Return a safe label for registered and historical job operations."""
    return _REGISTERED_OPERATION_LABELS.get(
        operation,
        operation.replace('_', ' ').title(),
    )
