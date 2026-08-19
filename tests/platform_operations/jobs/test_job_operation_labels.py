from app.common.job_execution_contract import (
    KUBERNETES_INVENTORY_SYNC_OPERATION,
    OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION,
    OBJECT_STORAGE_INVENTORY_SYNC_OPERATION,
    job_operation_label,
)


def test_tls_certificate_sync_preserves_tls_acronym():
    assert job_operation_label('tls_certificate_sync') == 'TLS Certificate Sync'


def test_registered_job_operations_use_definition_names():
    assert job_operation_label(KUBERNETES_INVENTORY_SYNC_OPERATION) == 'Kubernetes Inventory Sync'
    assert job_operation_label(OBJECT_STORAGE_INVENTORY_SYNC_OPERATION) == 'Object Storage Inventory Sync'
    assert job_operation_label(OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION) == 'Object Storage Forecast Data Refresh'
    assert job_operation_label('materialize_analytics') == 'Kubernetes Analytics Data Refresh'
    assert job_operation_label('materialize_forecast') == 'Kubernetes Forecast Data Refresh'
    assert job_operation_label('dispatch_due_reports') == 'Report Schedule Dispatcher'


def test_unknown_operation_keeps_safe_title_case_fallback():
    assert job_operation_label('custom_housekeeping') == 'Custom Housekeeping'
