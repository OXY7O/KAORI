from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.inventory import synchronization


class _Session:
    def __init__(self) -> None:
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    def flush(self) -> None:
        self.flushes += 1

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _Client:
    def __init__(self) -> None:
        self._core = SimpleNamespace(api_client=object())

    def core_api(self):
        return self._core

    def apps_api(self):
        return object()

    def networking_api(self):
        return object()

    def storage_api(self):
        return object()


def test_one_refresh_passes_one_generation_to_every_inventory_family(monkeypatch) -> None:
    session = _Session()
    seen = []
    cluster = SimpleNamespace(id='cluster-1')
    connection = SimpleNamespace(cluster_id='cluster-1', allow_weak_tls=False)

    monkeypatch.setattr(synchronization.db, 'session', session)
    monkeypatch.setattr(synchronization, '_lock_cluster_inventory_sync', lambda cluster_id: None)
    monkeypatch.setattr(synchronization, 'weak_tls_context', lambda enabled: nullcontext())
    monkeypatch.setattr(
        synchronization,
        'get_integration',
        lambda provider: SimpleNamespace(execute=lambda operation, target: _Client()),
    )
    monkeypatch.setattr(
        synchronization,
        'KubernetesDiscovery',
        lambda api_client: SimpleNamespace(
            discover=lambda: {
                'selected_adapters': {},
                'api_profile': 'kubernetes-v1',
                'compatibility_status': 'compatible',
                'readiness_status': 'ready',
            }
        ),
    )
    monkeypatch.setattr(synchronization, 'BatchV1Api', lambda api_client: object())

    def recorder(*args, **kwargs):
        seen.append(args[1])

    for name in (
        'save_cluster_info',
        'save_nodes',
        'save_namespaces',
        'save_workloads',
        'save_pods',
        'save_services',
        'save_storage_inventory',
        'save_configuration_inventory',
        'save_resource_quotas',
    ):
        monkeypatch.setattr(synchronization, name, recorder)

    synchronization.sync_inventory(cluster, connection)

    assert len(seen) == 9
    assert len({id(value) for value in seen}) == 1
    assert session.commits == 1
    assert session.rollbacks == 0


def test_failed_refresh_rolls_back_logs_the_stage_and_reraises(monkeypatch) -> None:
    session = _Session()
    cluster = SimpleNamespace(id='cluster-1')
    connection = SimpleNamespace(cluster_id='cluster-1', allow_weak_tls=False)
    logged: list[tuple[str, tuple[object, ...]]] = []

    monkeypatch.setattr(synchronization.db, 'session', session)

    def fail_cluster_lock(cluster_id: str) -> None:
        raise RuntimeError(f'lock failed for {cluster_id}')

    monkeypatch.setattr(synchronization, '_lock_cluster_inventory_sync', fail_cluster_lock)
    monkeypatch.setattr(
        synchronization.logger,
        'exception',
        lambda message, *args: logged.append((message, args)),
    )

    with pytest.raises(RuntimeError, match='lock failed for cluster-1'):
        synchronization.sync_inventory(cluster, connection)

    assert session.commits == 0
    assert session.rollbacks == 1
    assert logged == [
        (
            'Kubernetes inventory synchronization failed for cluster %s during %s.',
            ('cluster-1', 'cluster lock'),
        )
    ]
