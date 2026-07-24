from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_orchestration_uses_isolated_resolver_queues_and_late_ack() -> None:
    tasks = read('app/resolver/tasks.py')
    orchestration = read('app/resolver/orchestration.py')
    config = read('app/config/default.py')
    assert "RESOLVER_QUEUE = 'resolver-execution'" in orchestration
    assert "'app.resolver.tasks'" in config
    assert "'app.resolver.tasks.execute_authorized_resolution'" in config
    assert "'app.resolver.tasks.reconcile_stale_execution_leases'" in config
    assert 'RESOLVER_EXECUTION_CELERY_QUEUE' in config
    assert 'RESOLVER_MAINTENANCE_CELERY_QUEUE' in config
    assert 'acks_late=True' in tasks
    assert 'reject_on_worker_lost=True' in tasks


def test_resolver_workers_and_beat_recovery_are_deployed() -> None:
    compose = read('compose.production.yml')
    config = read('app/config/default.py')
    assert 'resolver-execution-worker:' in compose
    assert 'resolver-maintenance-worker:' in compose
    assert 'RESOLVER_EXECUTION_CELERY_QUEUE:-resolver-execution' in compose
    assert 'RESOLVER_MAINTENANCE_CELERY_QUEUE:-resolver-maintenance' in compose
    assert "schedule['resolver-lease-recovery']" in config
    assert "'task': 'app.resolver.tasks.reconcile_stale_execution_leases'" in config


def test_execution_lease_and_retry_are_persisted_contracts() -> None:
    model = read('app/models/intelligence.py')
    migration = read('migrations/versions/20260723_resolver_orchestration_safety.py')
    for token in (
        'idempotency_key',
        'orchestration_status',
        'lease_owner',
        'lease_expires_at',
        'attempt_count',
        'max_attempts',
        'next_retry_at',
        'last_error_code',
    ):
        assert token in model
        assert token in migration
    assert "UniqueConstraint('idempotency_key'" in model
    assert 'with_for_update=True' in read('app/resolver/orchestration.py')


def test_retry_stale_recovery_and_preflight_failure_are_fail_closed() -> None:
    source = read('app/resolver/orchestration.py')
    tasks = read('app/resolver/tasks.py')
    assert "journal.orchestration_status = 'dead_letter'" in source
    assert 'journal.attempt_count < journal.max_attempts' in source
    assert 'Execution lease expired before completion.' in source
    assert 'with_for_update(skip_locked=True)' in source
    assert 'def record_preflight_failure(' in source
    assert 'record_preflight_failure(' in tasks


def test_resolver_delivery_uses_canonical_job_dispatcher_without_broker_secret() -> None:
    source = read('app/resolver/orchestration.py')
    tasks = read('app/resolver/tasks.py')
    assert 'from app.jobs.dispatcher import enqueue_canonical_job' in source
    assert 'def enqueue_execution_delivery(' in source
    assert "job_type='resolver_execution'" in source
    assert "workload_class='mutation'" in source
    assert 'journal.resolver_job_id = job.id' in source
    assert "journal.orchestration_status = 'pending'" in source
    assert "journal.last_error_code = 'dispatch_failed'" in source
    assert 'job_execution_id: int | None = None' in tasks
    assert 'JobExecutionContext(task_id)' in tasks
    assert 'execution.succeed(' in tasks
    assert 'execution.retrying(' in tasks
    assert 'execution.fail(' in tasks
    task_kwargs = source[source.index("task_kwargs={"): source.index("job_type='resolver_execution'")]
    assert "'secret_key'" not in task_kwargs
    assert "current_app.config.get('RESOLVER_TOKEN_SIGNING_KEY')" in tasks
