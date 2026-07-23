from types import SimpleNamespace

from app.cluster import sync_jobs


class _OrderedQuery:
    def __init__(self, clusters):
        self._clusters = clusters
        self.order_columns = ()

    def order_by(self, *columns):
        self.order_columns = columns
        return self

    def all(self):
        return self._clusters


class _ClusterModelStub:
    name = SimpleNamespace(asc=lambda: 'name-asc')
    id = SimpleNamespace(asc=lambda: 'id-asc')

    def __init__(self, clusters):
        self.query = _OrderedQuery(clusters)


def test_fleet_target_snapshot_preserves_admission_order(monkeypatch) -> None:
    clusters = [
        SimpleNamespace(id='cluster-b', name='Beta'),
        SimpleNamespace(id='cluster-a', name='Alpha'),
    ]
    model = _ClusterModelStub(clusters)
    monkeypatch.setattr(sync_jobs, 'Cluster', model)

    targets = sync_jobs._fleet_target_snapshot()

    assert targets == [
        {'cluster_id': 'cluster-b', 'cluster_name': 'Beta'},
        {'cluster_id': 'cluster-a', 'cluster_name': 'Alpha'},
    ]
    assert model.query.order_columns == ('name-asc', 'id-asc')


def test_fleet_enqueue_dispatches_the_exact_target_snapshot(monkeypatch) -> None:
    targets = [
        {'cluster_id': 'cluster-1', 'cluster_name': 'Production'},
        {'cluster_id': 'cluster-2', 'cluster_name': 'Disaster Recovery'},
    ]
    captured = {}
    job = SimpleNamespace(
        queued_at=None,
        progress_current=0,
        id=91,
        celery_task_id='task-91',
    )
    monkeypatch.setattr(sync_jobs, '_fleet_target_snapshot', lambda: targets)
    monkeypatch.setattr(
        sync_jobs,
        'enqueue_canonical_job',
        lambda **kwargs: (captured.update(kwargs) or job, True),
    )
    monkeypatch.setattr(sync_jobs, 'store_cluster_sync_metadata', lambda **kwargs: None)

    result, created = sync_jobs.enqueue_all_cluster_inventory_sync(requested_by_user_id=7)

    assert result is job
    assert created is True
    assert captured['task_kwargs']['targets'] == targets
    assert captured['parameters']['targets'] == targets
    assert captured['payload']['targets'] == targets
    assert captured['parameters']['cluster_count'] == 2
