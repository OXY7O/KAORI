from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_operational_controls_are_fail_closed_and_audited():
    source = (ROOT / 'app/resolver/operations.py').read_text()
    assert 'Global resolver kill switch is active.' in source
    assert 'Resolver maintenance mode is active for this cluster.' in source
    assert 'Resolver concurrency limit has been reached' in source
    assert 'Resolver circuit breaker is open' in source
    assert 'resolver.operational_control.updated' in source


def test_worker_checks_controls_before_lease_and_dispatch():
    source = (ROOT / 'app/resolver/tasks.py').read_text()
    prepare = source[source.index('def _prepare_execution'): source.index('def _persist_preflight_failure')]
    execute = source[source.index('def _execute_with_lease'): source.index('@shared_task', source.index('def _execute_with_lease'))]
    task = source[source.index('def execute_authorized_resolution'): ]

    assert prepare.index('assert_execution_allowed(journal)') < prepare.index('lease = acquire_execution_lease')
    lease = prepare.index('lease = acquire_execution_lease')
    commit = prepare.index('db.session.commit()', lease)
    assert lease < commit
    assert 'result = dispatch_resolver_execution' in execute
    assert task.index('state = _prepare_execution') < task.index('return _execute_with_lease')
    assert 'record_preflight_failure(' in source


def test_migration_is_default_safe_and_chained():
    source = (ROOT / 'migrations/versions/20260723_resolver_controls.py').read_text()
    assert "down_revision = '20260723_resolver_registry'" in source
    assert "server_default=sa.false()" in source
    assert "server_default='1'" in source
