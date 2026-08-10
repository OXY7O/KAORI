from __future__ import annotations

_REGISTERED_OPERATION_LABELS = {
    'inventory_sync_all': 'Inventory Sync',
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
