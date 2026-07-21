from pathlib import Path


def test_data_lifecycle_uses_one_domain_registry_and_archive_engine() -> None:
    registry = Path('app/retention/domains/__init__.py').read_text(encoding='utf-8')
    service = Path('app/retention/service.py').read_text(encoding='utf-8')
    assert "'operational_activity': OperationalActivityArchiveDomain" in registry
    assert "'job_execution': JobExecutionArchiveDomain" in registry
    assert 'run_retention_archive' in service
    assert 'ArchiveArtifact' in service


def test_job_execution_retention_is_terminal_only_and_result_safe() -> None:
    source = Path('app/retention/domains/job_execution.py').read_text(encoding='utf-8')
    for fragment in (
        'TERMINAL_STATUSES',
        'JobExecution.active_deduplication_key.is_(None)',
        "'preserve_result_references': True",
        "'result_reference': job.result_reference",
        'JobExecutionSubscriber',
    ):
        assert fragment in source
    job_model = Path('app/models/job.py').read_text(encoding='utf-8')
    assert "ondelete='CASCADE'" in job_model
    assert "ondelete='SET NULL'" in job_model
    assert 'delete(job.result_reference)' not in source
    assert 'result_reference.delete' not in source


def test_lifecycle_execution_uses_canonical_job_foundation() -> None:
    routes = Path('app/settings/data_lifecycle/routes.py').read_text(encoding='utf-8')
    tasks = Path('app/retention/tasks.py').read_text(encoding='utf-8')
    assert 'enqueue_canonical_job(' in routes
    assert "job_type='data_lifecycle'" in routes
    assert "resource_group=f'data-lifecycle:{domain_name}'" in routes
    assert 'JobExecutionContext' in tasks
    assert 'run_scheduled_retention_task' in tasks
    assert 'enqueue_canonical_job(' in tasks


def test_data_lifecycle_policy_is_persistent_and_per_domain() -> None:
    model = Path('app/models/lifecycle.py').read_text(encoding='utf-8')
    migration = Path('migrations/versions/20260721_data_lifecycle_foundation.py').read_text(encoding='utf-8')
    for fragment in (
        'domain:', 'hot_retention_days', 'archive_retention_days', 'batch_size',
        'operation_mode', 'schedule_enabled', 'settings_json',
    ):
        assert fragment in model
    assert "'operational_activity'" in migration
    assert "'job_execution'" in migration
    assert "down_revision = '20260720_job_execution'" in migration
