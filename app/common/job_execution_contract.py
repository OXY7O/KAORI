from __future__ import annotations

KUBERNETES_INVENTORY_SYNC_OPERATION = 'sync_kubernetes_inventory'
OBJECT_STORAGE_INVENTORY_SYNC_OPERATION = 'sync_object_storage_inventory'
OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION = 'materialize_object_storage_forecast'
SYNC_ALL_INVENTORY_ACTION = 'sync_all_inventory'

_REGISTERED_OPERATION_LABELS = {
    KUBERNETES_INVENTORY_SYNC_OPERATION: 'Kubernetes Inventory Sync',
    OBJECT_STORAGE_INVENTORY_SYNC_OPERATION: 'Object Storage Inventory Sync',
    OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION: 'Object Storage Forecast Data Refresh',
    'dispatch_due_reports': 'Report Schedule Dispatcher',
    'tls_certificate_sync': 'TLS Certificate Sync',
    'materialize_analytics': 'Analytics Data Refresh',
    'materialize_forecast': 'Forecast Data Refresh',
}


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
