from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.cluster import sync_jobs


class _ClusterModelStub:
    def __init__(self, cluster):
        self.query = _Query(cluster)


class _Query:
    def __init__(self, cluster):
        self.cluster = cluster

    def filter_by(self, **kwargs):
        return self

    def populate_existing(self):
        return self

    def first(self):
        return self.cluster


def test_single_cluster_admission_uses_canonical_resolver(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1', name='Production')
    resolved_connection = SimpleNamespace(id=27)
    monkeypatch.setattr(sync_jobs, 'Cluster', _ClusterModelStub(cluster))
    monkeypatch.setattr(sync_jobs, 'acquire_resource_admission_locks', lambda *groups: None)
    monkeypatch.setattr(sync_jobs, 'connection_for_cluster', lambda current: resolved_connection)

    captured = {}

    def _enqueue(**kwargs):
        captured.update(kwargs)
        job = SimpleNamespace(id=5, celery_task_id='task-5', queued_at=None, progress_current=0)
        return job, True

    monkeypatch.setattr(sync_jobs, 'enqueue_canonical_job', _enqueue)
    monkeypatch.setattr(sync_jobs, 'register_individual_sync_task', lambda **kwargs: None)

    sync_jobs.enqueue_cluster_inventory_sync(cluster=cluster, requested_by_user_id=9)

    assert captured['provider_instance_id'] == 27
    assert captured['resource_group'] == 'kubernetes-cluster:cluster-1'


def test_single_cluster_admission_fails_when_canonical_resolution_fails(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1', name='Production')
    monkeypatch.setattr(sync_jobs, 'Cluster', _ClusterModelStub(cluster))
    monkeypatch.setattr(sync_jobs, 'acquire_resource_admission_locks', lambda *groups: None)

    def _missing(current):
        raise RuntimeError('No canonical Kubernetes connection is bound to cluster cluster-1.')

    monkeypatch.setattr(sync_jobs, 'connection_for_cluster', _missing)

    with pytest.raises(RuntimeError, match='No canonical Kubernetes connection'):
        sync_jobs.enqueue_cluster_inventory_sync(cluster=cluster, requested_by_user_id=9)
