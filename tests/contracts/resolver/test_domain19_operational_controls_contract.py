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
    body = source[source.index('def execute_authorized_resolution'): ]
    assert body.index('assert_execution_allowed(journal)') < body.index('lease = acquire_execution_lease')
    assert body.index('lease = acquire_execution_lease') < body.index('result = dispatch_resolver_execution')


def test_migration_is_default_safe_and_chained():
    source = (ROOT / 'migrations/versions/20260723_resolver_controls.py').read_text()
    assert "down_revision = '20260723_resolver_registry'" in source
    assert "server_default=sa.false()" in source
    assert "server_default='1'" in source
