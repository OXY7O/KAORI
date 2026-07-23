from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.inventory import synchronization


class FakeSession:
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


class FakeClient:
    def core_api(self):
        return SimpleNamespace(api_client=object())

    def apps_api(self):
        return object()

    def networking_api(self):
        return object()

    def storage_api(self):
        return object()


class FakeIntegration:
    def execute(self, operation, connection):
        assert operation == 'client.build'
        return FakeClient()


def test_inventory_failure_rolls_back_entire_snapshot(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1')
    connection = SimpleNamespace(
        id=17,
        cluster_id='cluster-1',
        allow_weak_tls=False,
        compatibility_profile=None,
        compatibility_status=None,
        readiness_status=None,
        discovery_summary=None,
    )
    session = FakeSession()

    monkeypatch.setattr(synchronization.db, 'session', session)
    monkeypatch.setattr(synchronization, '_lock_cluster_inventory_sync', lambda cluster_id: None)
    monkeypatch.setattr(synchronization, 'weak_tls_context', lambda **kwargs: nullcontext())
    monkeypatch.setattr(synchronization, 'get_integration', lambda provider: FakeIntegration())
    monkeypatch.setattr(
        synchronization.KubernetesDiscovery,
        'discover',
        lambda self: {
            'selected_adapters': {},
            'api_profile': 'kubernetes-v1',
            'compatibility_status': 'supported',
            'readiness_status': 'ready',
        },
    )
    monkeypatch.setattr(synchronization, 'save_cluster_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(synchronization, 'save_nodes', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        synchronization,
        'save_namespaces',
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('namespace collection failed')),
    )

    with pytest.raises(RuntimeError, match='namespace collection failed'):
        synchronization.sync_inventory(cluster, connection)

    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.flushes == 2


def test_inventory_rejects_connection_from_another_cluster(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1')
    connection = SimpleNamespace(cluster_id='cluster-2')

    with pytest.raises(ValueError, match='does not belong'):
        synchronization.sync_inventory(cluster, connection)
