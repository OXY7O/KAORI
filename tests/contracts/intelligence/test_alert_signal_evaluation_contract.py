from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_fast_alert_signal_evaluation_is_separate_from_full_inventory() -> None:
    rules = read('app/definitions/catalogs/intelligence/rules.yaml')
    config = read('app/intelligence/alert_signals/config.py')
    service = read('app/intelligence/alert_signals/service.py')
    runtime = read('app/intelligence/kubernetes_runtime_recommendations.py')

    assert 'ALERT_SIGNAL_EVALUATION_INTERVAL_MINUTES' in config
    assert "_bounded_int('ALERT_SIGNAL_EVALUATION_INTERVAL_MINUTES', 5, 1, 60)" in config
    assert 'list_pod_for_all_namespaces' in service
    assert 'list_node' in service
    assert "KUBERNETES_RUNTIME_HEALTH_SIGNAL = 'kubernetes.runtime_health'" in service
    assert 'runtime_signal_payloads()' in runtime
    assert rules.count('alert_signal_profile: kubernetes_runtime_health') >= 3
    assert 'kubernetes.inventory.sync' not in service


def test_alert_signal_snapshot_is_durable_and_freshness_aware() -> None:
    model = read('app/models/alert_signal.py')
    migration = read('migrations/versions/20260823_alert_signal_evaluation.py')
    source = read('app/intelligence/alert_intelligence/recommendation_source.py')

    assert "__tablename__ = 'alert_signal_snapshots'" in model
    assert "status IN ('ready', 'failed')" in model
    assert 'expires_at' in model
    assert "revision = '20260823_alert_signal_eval'" in migration
    assert "down_revision = '20260823_alert_false_positive'" in migration
    assert 'alert_signal_source_posture' in source
    assert 'alert_signal_profile' in source


def test_alert_signal_task_is_registered_and_configured() -> None:
    default = read('app/config/default.py')
    env_example = read('.env.example')
    production_app = read('deploy/env/app.env.example')

    assert "'app.intelligence.alert_signals.tasks'" in default
    assert "'app.intelligence.alert_signals.tasks.refresh_alert_signals'" in default
    for source in (env_example, production_app):
        assert 'ALERT_SIGNAL_EVALUATION_ENABLED=true' in source
        assert 'ALERT_SIGNAL_EVALUATION_INTERVAL_MINUTES=5' in source
        assert 'ALERT_SIGNAL_FRESHNESS_MINUTES=10' in source
