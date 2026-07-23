from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_readiness_requires_failure_mode_and_rollback_evidence():
    source = read('app/resolver/production_readiness.py')
    for check in (
        'duplicate_delivery',
        'worker_loss_recovery',
        'resource_version_conflict',
        'kill_switch',
        'circuit_breaker',
        'rollback_drill',
        'kubernetes_rbac',
    ):
        assert repr(check) in source


def test_rollout_is_staged_and_production_requires_complete_assessment():
    source = read('app/resolver/production_readiness.py')
    assert "STAGE_ORDER = ('disabled', 'shadow', 'non_production', 'canary', 'production')" in source
    assert 'Rollout stages must advance one step at a time.' in source
    assert "target_stage in {'canary', 'production'} and not assessment.ready" in source
    assert 'Resolver deployment policy must be active before rollout.' in source
    assert 'Non-production rollout stage cannot execute against a production cluster.' in source


def test_migration_is_default_disabled_and_has_domain19_parent():
    source = read('migrations/versions/20260723_resolver_readiness.py')
    assert "down_revision = '20260723_resolver_controls'" in source
    assert "server_default='disabled'" in source
    assert 'resolver_production_readiness' in source

def test_worker_enforces_policy_readiness_and_controls_before_execution_lease():
    source = read('app/resolver/tasks.py')
    body = source[source.index('def execute_authorized_resolution'):]

    policy = body.index('assert_deployment_policy_allows(')
    readiness = body.index('assert_production_execution_ready(')
    controls = body.index('assert_execution_allowed(journal)')
    lease = body.index('lease = acquire_execution_lease')
    dispatch = body.index('result = dispatch_resolver_execution')

    assert policy < readiness < controls < lease < dispatch

