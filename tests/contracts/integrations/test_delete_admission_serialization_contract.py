from pathlib import Path


def test_job_and_delete_paths_share_resource_admission_lock() -> None:
    job_service = Path('app/jobs/service.py').read_text()
    prometheus = Path('app/prometheus/service.py').read_text()
    alertmanager = Path('app/alertmanager/service.py').read_text()
    cluster = Path('app/cluster/service.py').read_text()
    validation = Path('app/integrations/validation/web.py').read_text()
    sync_jobs = Path('app/cluster/sync_jobs.py').read_text()

    assert 'def acquire_resource_admission_locks' in job_service
    assert 'acquire_resource_admission_locks(resource_group)' in job_service
    assert "acquire_resource_admission_locks(f'integration:prometheus:{instance.id}')" in prometheus
    assert "acquire_resource_admission_locks(f'integration:alertmanager:{instance.id}')" in alertmanager
    assert "f'kubernetes-cluster:{cluster_id}'" in cluster
    assert "f'integration:kubernetes:{connection_id}'" in cluster
    assert '_assert_provider_target_exists' in validation
    assert 'acquire_resource_admission_locks(resource_group)' in validation
    assert 'populate_existing().first()' in sync_jobs
