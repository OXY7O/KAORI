from app.jobs.registry import job_operation_label


def test_tls_certificate_sync_preserves_tls_acronym():
    assert job_operation_label('tls_certificate_sync') == 'TLS Certificate Sync'


def test_registered_job_operations_use_definition_names():
    assert job_operation_label('inventory_sync_all') == 'Inventory Sync'
    assert job_operation_label('materialize_analytics') == 'Analytics Data Refresh'
    assert job_operation_label('materialize_forecast') == 'Forecast Data Refresh'
    assert job_operation_label('dispatch_due_reports') == 'Report Schedule Dispatcher'


def test_unknown_operation_keeps_safe_title_case_fallback():
    assert job_operation_label('custom_housekeeping') == 'Custom Housekeeping'
