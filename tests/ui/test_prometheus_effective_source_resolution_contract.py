from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_binding_capabilities_are_declared_at_creation_authority() -> None:
    source = (ROOT / 'app/prometheus/service.py').read_text()
    assert not (ROOT / 'app/prometheus/binding_contract.py').exists()
    for capability in (
        'metrics',
        'capacity',
        'utilization',
        'storage',
        'workload',
        'forecast',
        'top_consumers',
        'alert_metrics',
    ):
        assert repr(capability) in source
    assert 'capability_scope=PROMETHEUS_BINDING_CAPABILITIES' in source


def test_foundation_migration_normalizes_prometheus_binding_scope() -> None:
    migration = (
        ROOT / 'migrations/versions/20260722_foundation_compatibility_cleanup.py'
    ).read_text()
    assert '_PROMETHEUS_CAPABILITIES' in migration
    assert 'capability_scope=list(_PROMETHEUS_CAPABILITIES)' in migration


