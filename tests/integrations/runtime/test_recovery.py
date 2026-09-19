from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[3] / 'app/integrations/runtime/recovery.py'
SPEC = spec_from_file_location('integration_recovery_contract', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

_bound_cluster_ids = MODULE._bound_cluster_ids
is_runtime_recovery = MODULE.is_runtime_recovery


def test_runtime_recovery_requires_unhealthy_to_healthy_transition() -> None:
    assert is_runtime_recovery('unhealthy', 'healthy') is True
    assert is_runtime_recovery('degraded', 'healthy') is True
    assert is_runtime_recovery('healthy', 'healthy') is False
    assert is_runtime_recovery(None, 'healthy') is False
    assert is_runtime_recovery('unhealthy', 'degraded') is False


def test_bound_cluster_ids_support_direct_kubernetes_connection() -> None:
    assert _bound_cluster_ids(SimpleNamespace(cluster_id='cluster-1')) == ['cluster-1']


def test_bound_cluster_ids_use_enabled_canonical_bindings() -> None:
    instance = SimpleNamespace(
        cluster_id=None,
        integration_instance=SimpleNamespace(
            bindings=[
                SimpleNamespace(enabled=True, asset_type='kubernetes_cluster', asset_key='cluster-2'),
                SimpleNamespace(enabled=True, asset_type='kubernetes_cluster', asset_key='cluster-1'),
                SimpleNamespace(enabled=False, asset_type='kubernetes_cluster', asset_key='cluster-3'),
                SimpleNamespace(enabled=True, asset_type='other', asset_key='cluster-4'),
            ]
        ),
    )
    assert _bound_cluster_ids(instance) == ['cluster-1', 'cluster-2']


def test_alert_provider_recovery_queues_dashboard_and_alerts_snapshots(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class Definition:
        def dispatch(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(accepted=True, created=True)

    monkeypatch.setattr(MODULE, '_get_job_definition', lambda job_key: Definition())

    instance = SimpleNamespace(
        cluster_id=None,
        integration_instance=SimpleNamespace(
            bindings=[SimpleNamespace(enabled=True, asset_type='kubernetes_cluster', asset_key='cluster-1')]
        ),
    )

    result = MODULE.enqueue_recovery_work(integration_type='alert_source', instance=instance)

    assert result['queued'] == 2
    assert [call['parameters']['dataset_key'] for call in calls] == [
        'dashboard.kubernetes.alerts',
        'analytics.alerts',
    ]
    assert all(call['trigger_type'] == 'recovery' for call in calls)


def test_kubernetes_recovery_queues_inventory_and_tls_sync(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Definition:
        def __init__(self, job_key: str):
            self.job_key = job_key

        def dispatch(self, **kwargs):
            calls.append((self.job_key, kwargs))
            return SimpleNamespace(accepted=True, created=True)

    monkeypatch.setattr(MODULE, '_get_job_definition', lambda job_key: Definition(job_key))

    result = MODULE.enqueue_recovery_work(
        integration_type='container_orchestrator',
        instance=SimpleNamespace(cluster_id='cluster-1'),
    )

    assert result['queued'] == 2
    assert calls == [
        (
            'kubernetes.inventory.sync',
            {
                'requested_by_user_id': None,
                'trigger_type': 'recovery',
                'parameters': {'cluster_id': 'cluster-1'},
            },
        ),
        (
            'governance.tls_certificates.sync',
            {
                'requested_by_user_id': None,
                'trigger_type': 'recovery',
                'parameters': {'cluster_id': 'cluster-1'},
            },
        ),
    ]
