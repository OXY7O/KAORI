from app.reports.jobs.service import get_report_job_integration_dimensions


def test_job_integration_dimensions_align_with_asset_scope_taxonomy() -> None:
    assert get_report_job_integration_dimensions('kubernetes_cluster', 'cluster-1') == ('kubernetes', None)
    assert get_report_job_integration_dimensions('object_storage_system', 'object-store-1') == (
        'object_storage',
        None,
    )
    assert get_report_job_integration_dimensions('registry_integration', '42') == ('registry', 42)


def test_future_unknown_scope_is_not_misclassified_as_kubernetes() -> None:
    assert get_report_job_integration_dimensions('compute_instance', 'vm-1') == (None, None)
