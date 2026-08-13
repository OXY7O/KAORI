from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_inventory_is_a_registered_periodic_job() -> None:
    definition = read('app/jobs/definitions/object_storage_inventory_sync.py')
    registry = read('app/jobs/registry.py')
    template = read('app/templates/jobs/configuration/definitions/object_storage_inventory_sync.html')
    scheduler = read('app/jobs/scheduler.py')

    assert "JOB_KEY = 'object_storage.inventory.sync'" in definition
    assert "domain='Object Storage Inventory'" in definition
    assert "queue_name='inventory'" in definition
    assert "domain_execute_permission='storage.sync'" in definition
    assert 'default_enabled=True' in definition
    assert 'default_interval_minutes=60' in definition
    assert 'OBJECT_STORAGE_INVENTORY_SYNC_DEFINITION' in registry
    assert 'Automatic Object Storage Inventory Sync' in template
    assert 'Object Storage Inventory Sync Policy' in template
    assert 'dispatch_registered_job(' in scheduler
    assert '.with_for_update(skip_locked=True)' in scheduler


def test_object_storage_job_uses_canonical_job_execution_and_inventory_worker() -> None:
    sync_jobs = read('app/storage_inventory/sync_jobs.py')
    tasks = read('app/storage_inventory/tasks.py')
    config = read('app/config/default.py')
    adapter = read('app/storage_inventory/job_adapter.py')

    assert 'enqueue_canonical_job(' in sync_jobs
    assert "job_type='object_storage_inventory'" in sync_jobs
    assert 'OBJECT_STORAGE_INVENTORY_SYNC_OPERATION' in sync_jobs
    assert 'operation=OBJECT_STORAGE_INVENTORY_SYNC_OPERATION' in sync_jobs
    assert "resource_group='object-storage-inventory:global'" in sync_jobs
    assert "instance.readiness_status != 'ready'" in sync_jobs
    assert "name='app.storage_inventory.tasks.sync_all_object_storage'" in tasks
    assert "get_integration('minio').execute(" in tasks
    assert "'inventory.sync'," in tasks
    assert 'progress_callback=report_bucket_progress' in tasks
    assert "'app.storage_inventory.tasks'" in config
    assert "'app.storage_inventory.tasks.sync_all_object_storage'" in config
    assert "'queue': 'inventory'" in config
    assert "'eligible_target_count': eligible_system_count" in adapter


def test_minio_validation_runtime_and_inventory_ownership_are_separated() -> None:
    integration = read('app/integrations/minio/__init__.py')
    adapter = read('app/integrations/minio/adapter.py')
    client = read('app/integrations/minio/client.py')
    sync = read('app/storage_inventory/sync.py')
    validation = read('app/templates/minio/partials/_detail_validation.html')
    runtime = read('app/templates/minio/partials/_detail_runtime.html')

    assert "'runtime.validate': 'integration-validation'" in integration
    assert "'runtime.health': 'integration-runtime'" in integration
    assert "'inventory.sync': 'inventory'" in integration
    assert 'commit_bucket_inventory(' not in adapter
    assert "'inventory_owner': 'job_execution'" in adapter
    assert 'probe_instance_runtime_health(instance)' in adapter
    assert "instance.object_storage_system.status = 'connected'" in adapter
    assert "if operation == 'inventory.sync'" in adapter
    assert 'collect_instance_bucket_inventory(' in sync
    assert "collect_usage_stats=usage_stats_mode == 'full_scan'" in sync
    assert '_lock_system_inventory_sync(' in sync
    assert 'db.session.commit()' in sync
    assert 'db.session.rollback()' in sync
    assert 'lightweight provider health probe without collecting inventory' in client.lower()
    assert 'Visible Buckets' not in validation
    assert 'Required Contracts' in validation
    assert 'Inventory Sync owns committed storage assets' in validation
    assert 'without capability mutation or inventory discovery' in runtime


def test_inventory_pages_and_minio_lifecycle_read_only_committed_job_snapshot() -> None:
    minio_presentation = read('app/minio/presentation.py')
    scope = read('app/templates/minio/partials/_detail_scope.html')
    storage_presentation = read('app/storage_inventory/presentation.py')

    assert 'len(instance.object_storage_system.buckets or ())' in minio_presentation
    assert 'instance.object_storage_system.inventory_observed_at' in minio_presentation
    assert 'Inventory Snapshot · ' in scope
    assert 'Object Storage Inventory Sync' in scope
    assert 'Manage Inventory Jobs' in scope
    assert "job_key='object_storage.inventory.sync'" in scope
    assert 'latest completed MinIO Full Validation' not in scope
    assert 'Run Object Storage Inventory Sync from Job Execution' in storage_presentation
    assert "'source_label': 'Committed Snapshot'" in storage_presentation
    bucket_detail = read('app/templates/object_storage_inventory/buckets/partials/_bucket_detail_content.html')
    bucket_table = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    assert 'Object Storage Inventory Sync snapshot' in bucket_detail
    assert 'run Object Storage Inventory Sync from Job Configuration' in bucket_table
    assert 'Full Validation snapshot' not in bucket_detail


def test_object_storage_manual_execution_has_domain_permission_and_migration() -> None:
    defaults = read('app/rbac/defaults.py')
    service = read('app/rbac/service.py')
    migration = read('migrations/versions/20260813_object_storage_inventory_jobs.py')
    jobs_readme = read('app/jobs/README.md')

    assert "'storage.sync'" in defaults
    assert "'operator': {" in defaults and "'editor': {" in defaults
    role_defaults = defaults.split('DEFAULT_ROLE_PERMISSIONS = {', 1)[1]
    assert role_defaults.count("        'storage.sync',") == 2
    assert "'storage.sync': {'inventory.view', 'jobs.execute'}" in service
    assert "revision = '20260813_obj_storage_jobs'" in migration
    assert "down_revision = '20260812_obj_storage_inv'" in migration
    assert "ROLE_NAMES = ('operator', 'editor', 'admin')" in migration
    assert '`jobs.execute` + `storage.sync`' in jobs_readme
