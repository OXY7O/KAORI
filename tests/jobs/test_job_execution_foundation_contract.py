from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_canonical_job_model_has_database_deduplication_and_subscribers() -> None:
    source = read('app/models/job.py')
    assert "__tablename__ = 'job_executions'" in source
    assert 'active_deduplication_key' in source
    assert 'unique=True' in source
    assert "__tablename__ = 'job_execution_subscribers'" in source
    assert "UniqueConstraint('job_execution_id', 'user_id'" in source


def test_validation_web_uses_canonical_job_registry_before_celery_dispatch() -> None:
    source = read('app/integrations/validation/web.py')
    assert 'create_or_attach_job(' in source
    assert "resource_group=f'integration:{provider_type}:{instance_id}'" in source
    assert "'job_execution_id': job.id" in source
    assert 'priority=job.priority' in source


def test_worker_pools_are_isolated_for_runtime_validation_analytics_and_forecasting() -> None:
    development = yaml.safe_load(read('.devcontainer/compose.devcontainer.yml'))['services']
    production = yaml.safe_load(read('compose.production.yml'))['services']
    for services in (development, production):
        assert 'runtime-worker' in services
        assert 'validation-worker' in services
        assert 'analytics-worker' in services
        assert 'forecasting-worker' in services
        assert 'integration-runtime' in str(services['runtime-worker']['command'])
        assert 'integration-validation' in str(services['validation-worker']['command'])
        assert 'analytics-batch' in str(services['analytics-worker']['command'])
        assert 'forecasting' in str(services['forecasting-worker']['command'])


def test_large_query_guardrails_are_configurable() -> None:
    config = read('app/config/default.py')
    planner = read('app/jobs/query_planning.py')
    for key in (
        'ANALYTICS_QUERY_MAXIMUM_RANGE_DAYS',
        'ANALYTICS_QUERY_CHUNK_DAYS',
        'ANALYTICS_QUERY_MINIMUM_STEP_SECONDS',
        'ANALYTICS_QUERY_MAXIMUM_SAMPLES_PER_SERIES',
        'ANALYTICS_QUERY_MAX_CONCURRENT_PER_SOURCE',
    ):
        assert key in config
    assert 'build_query_chunks' in planner
    assert 'maximum_samples_per_series' in planner


def test_jobs_package_initializer_does_not_eagerly_import_routes_or_tasks() -> None:
    source = read('app/jobs/__init__.py')
    assert 'from app.jobs.service import' not in source
    assert 'from app.jobs.tasks import' not in source


def test_job_admission_uses_postgresql_advisory_locks() -> None:
    source = (ROOT / 'app/jobs/service.py').read_text()
    assert 'pg_advisory_xact_lock' in source
    assert "f'job-user:{requested_by_user_id}'" in source
    assert "f'job-resource:{resource_group}'" in source


def test_large_query_execution_requires_resource_slot_and_chunk_checkpoint() -> None:
    source = (ROOT / 'app/jobs/query_execution.py').read_text()
    assert 'prepare_large_query_execution' in source
    assert 'acquire_resource_slot' in source
    assert 'release_resource_slot' in source
    assert 'checkpoint_query_chunk' in source
    assert 'job.checkpoint' in source


def test_running_provider_validation_cannot_be_force_canceled() -> None:
    source = (ROOT / 'app/jobs/service.py').read_text()
    assert 'def job_can_cancel' in source
    assert "job.status == 'queued'" in source
    assert 'job.workload_class in HEAVY_WORKLOAD_CLASSES' in source
    assert 'JobCancellationNotAllowed' in source
