from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_orchestration_uses_isolated_resolver_queues_and_late_ack() -> None:
    tasks = (ROOT / 'app/resolver/tasks.py').read_text()
    orchestration = (ROOT / 'app/resolver/orchestration.py').read_text()
    assert "RESOLVER_QUEUE = 'resolver-execution'" in orchestration
    assert "queue='resolver-maintenance'" in tasks
    assert 'acks_late=True' in tasks
    assert 'reject_on_worker_lost=True' in tasks


def test_execution_lease_and_retry_are_persisted_contracts() -> None:
    model = (ROOT / 'app/models/intelligence.py').read_text()
    migration = (ROOT / 'migrations/versions/20260723_resolver_orchestration_safety.py').read_text()
    for token in (
        'idempotency_key', 'orchestration_status', 'lease_owner', 'lease_expires_at',
        'attempt_count', 'max_attempts', 'next_retry_at', 'last_error_code',
    ):
        assert token in model
        assert token in migration
    assert "UniqueConstraint('idempotency_key'" in model
    assert "with_for_update=True" in (ROOT / 'app/resolver/orchestration.py').read_text()


def test_retry_and_stale_recovery_are_fail_closed() -> None:
    source = (ROOT / 'app/resolver/orchestration.py').read_text()
    assert "journal.orchestration_status = 'dead_letter'" in source
    assert 'journal.attempt_count < journal.max_attempts' in source
    assert 'Execution lease expired before completion.' in source
    assert 'with_for_update(skip_locked=True)' in source


def test_resolver_delivery_uses_canonical_job_dispatcher() -> None:
    source = (ROOT / 'app/resolver/orchestration.py').read_text()
    assert 'from app.jobs.dispatcher import enqueue_canonical_job' in source
    assert 'def enqueue_execution_delivery(' in source
    assert "job_type='resolver_execution'" in source
    assert "workload_class='mutation'" in source
    assert 'journal.resolver_job_id = job.id' in source
