from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_job_progress_metadata_is_canonical_without_schema_expansion() -> None:
    service = read('app/jobs/service.py')
    execution = read('app/jobs/execution.py')
    presentation = read('app/common/job_execution_presentation.py')

    assert "payload['_progress'] = metadata" in service
    assert "metadata['percent']" in service
    assert "metadata['stage']" in service
    assert "metadata['target']" in service
    assert 'percent: int | None = None' in execution
    assert 'stage: str | None = None' in execution
    assert 'target: str | None = None' in execution
    assert "payload.get('_progress')" in presentation
    assert "'progress_stage':" in presentation
    assert "'progress_target':" in presentation


def test_all_job_execution_surfaces_use_shared_progress_renderer() -> None:
    component = read('app/templates/components/progress_bar.html')
    assert 'macro job_progress(' in component
    assert 'transition-all duration-500 ease-out' in component
    assert 'style="width: {{ safe_value }}%"' in component
    assert 'data-progress="{{ safe_value }}"' in component
    assert 'style="width: {{ safe_primary_value }}%"' in component
    assert 'style="width: {{ safe_secondary_value }}%"' in component

    for relative in (
        'app/templates/jobs/configuration/_execution_activity.html',
        'app/templates/jobs/executions/partials/_active_jobs.html',
        'app/templates/jobs/executions/partials/_registry.html',
        'app/templates/jobs/executions/partials/_execution_details.html',
        'app/templates/notifications/components/_activity_center_items.html',
        'app/templates/reports/generated/detail.html',
    ):
        source = read(relative)
        assert 'progress_bar.job_progress' in source, relative
        assert 'progress_bar.determinate' not in source, relative


def test_domain_progress_reports_real_work_boundaries() -> None:
    kubernetes = read('app/inventory/kubernetes/synchronization.py')
    cluster_tasks = read('app/cluster/tasks.py')
    storage_tasks = read('app/inventory/object_storage/tasks.py')
    minio_client = read('app/integrations/minio/client.py')
    analytics = read('app/analytics/kubernetes/tasks.py')

    for stage in (
        'Collecting Nodes',
        'Collecting Workloads',
        'Collecting Pods',
        'Collecting Configuration Metadata',
        'Committing Inventory Snapshot',
    ):
        assert stage in kubernetes
    assert 'progress_callback=report_cluster_progress' in cluster_tasks
    assert "'Enriching Bucket Inventory'" in storage_tasks
    assert 'progress_callback(index, total_buckets, summary.name)' in minio_client
    assert "stage='Querying Analytics Sources'" in analytics
    assert "stage='Committing Analytics Snapshot'" in analytics


def test_job_related_specialized_bars_share_the_same_low_level_violet_primitive() -> None:
    operational = read('app/templates/components/operational_progress_toast.html')
    tls_live = read('app/templates/governance/tls_certificates/partials/_sync_live_state.html')
    analytics_pending = read('app/templates/analytics/kubernetes/materialization/_pending.html')

    assert 'progress_bar.bar' in operational
    assert 'progress_bar.bar' in tls_live
    assert 'progress_bar.bar' in analytics_pending
    assert 'progress_bar.determinate' not in operational
    assert '<progress ' not in tls_live


def test_navigation_inventory_sync_toasts_surface_real_worker_progress() -> None:
    quick = read('app/templates/components/navigation/_quick_sync_status.html')
    individual = read('app/templates/components/navigation/_individual_sync_status.html')
    individual_state = read('app/cluster/individual_sync_state.py')

    assert 'progress_percent=sync.progress_percent' in quick
    assert 'sync.progress_stage' in quick
    assert 'sync.message' in quick
    global_state = read('app/cluster/sync_state.py')
    assert "payload.setdefault('progress_percent', progress_metadata.get('percent'))" in global_state
    assert 'progress_percent=sync.progress_percent' in individual
    assert 'sync.progress_stage' in individual
    assert "payload.setdefault('progress_percent', progress_metadata.get('percent'))" in individual_state
