from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_all_three_analytics_domains_reuse_registered_job_and_analytics_batch() -> None:
    catalog = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    expected = {
        'analytics.materialize': (
            'app.kubernetes.analytics.job_adapter:dispatch_analytics_materialization',
            'analytics_materialization',
        ),
        'object_storage.analytics.materialize': (
            'app.storage.object_storage.analytics.job_adapter:dispatch_object_storage_analytics_materialization',
            'object_storage_analytics_materialization',
        ),
        'artifact_registry.analytics.materialize': (
            'app.artifact_registry.analytics_job_adapter:dispatch_registry_analytics_materialization',
            'artifact_registry_analytics',
        ),
    }
    for job_key, (dispatcher, job_type) in expected.items():
        row = catalog.split(f'- key: {job_key}\n', 1)[1].split('\n- key:', 1)[0]
        assert 'queue_name: analytics-batch' in row
        assert 'workload_class: analytics' in row
        assert f'job_type: {job_type}' in row
        assert 'default_enabled: true' in row
        assert 'execute_permission: jobs.execute' in row
        assert f'dispatcher_path: {dispatcher}' in row
        assert 'context_builder_path:' in row
        assert 'default_interval_minutes: 15' in row


def test_source_and_worker_ownership_stay_with_existing_kaori_contracts() -> None:
    consumer = read('app/integrations/observability/metrics_source/application/consumer.py')
    dispatcher = read('app/platform_operations/jobs/dispatcher.py')
    k8s = read('app/kubernetes/analytics/tasks.py')
    storage = read('app/storage/object_storage/analytics/job_adapter.py')
    registry = read('app/artifact_registry/analytics_job_adapter.py')
    registry_collector = read('app/artifact_registry/analytics.py')

    assert 'class MetricsConsumer:' in consumer
    assert 'def query_range(' in consumer
    assert 'def query(' in consumer
    assert 'def enqueue_canonical_job(' in dispatcher
    assert 'JobExecutionContext' in k8s
    assert 'enqueue_canonical_job(' in storage
    assert 'enqueue_canonical_job(' in registry
    assert 'MetricsConsumer.for_asset(' in registry_collector
    assert "snapshot.time_range = 'current'" in registry_collector
    assert 'consumer.query_range(' not in registry_collector


def test_new_analytics_domain_extension_does_not_require_another_framework() -> None:
    guide = read('docs/architecture/analytics-materialization-extension-standard.md')
    jobs = read('app/platform_operations/jobs/README.md')
    shared = read('app/templates/analytics/components/_section_load_tracker.html')
    progress = read('app/templates/components/progress_bar.html')
    k8s = read('app/templates/kubernetes/analytics/overview/index.html')
    registry = read('app/templates/artifact_registry/analytics.html')

    assert 'Extension checklist for a fourth domain' in guide
    assert 'No analytics domain may create another scheduler' in guide
    assert 'snapshot_window' in guide
    assert 'JobExecution' in jobs
    assert 'data-analytics-section-load-tracker' in shared
    assert 'macro job_progress' in progress
    assert "js/analytics/section_load_tracker.js" in k8s
    assert "js/analytics/section_load_tracker.js" in registry
    assert 'section loading' in guide.lower()


def test_analytics_time_range_values_have_one_canonical_owner() -> None:
    from app.common.analytics.params import (
        ALLOWED_TIME_RANGE_VALUES,
        TIME_RANGE_LABELS,
        get_allowed_time_ranges,
    )

    expected = ['1h', '6h', '12h', '24h', '7d', '30d', '60d']
    assert ALLOWED_TIME_RANGE_VALUES == expected
    assert [row['value'] for row in get_allowed_time_ranges()] == expected
    assert [row['label'] for row in get_allowed_time_ranges()] == [
        'Last 1 Hour',
        'Last 6 Hours',
        'Last 12 Hours',
        'Last 24 Hours',
        'Last 7 Days',
        'Last 30 Days',
        'Last 60 Days',
    ]
    assert all(TIME_RANGE_LABELS[key] for key in expected)
    storage = read('app/storage/object_storage/analytics/job_adapter.py')
    k8s = read('app/templates/kubernetes/analytics/overview/partials/_health_summary.html')
    registry = read('app/templates/artifact_registry/partials/_analytics_controls_readiness.html')
    assert 'allowed = set(ALLOWED_TIME_RANGE_VALUES)' in storage
    assert 'requested_time_range in ALLOWED_TIME_RANGE_VALUES' in storage
    for range_id in expected:
        assert f'value="{range_id}"' in k8s
        assert f"('{range_id}'," in registry
