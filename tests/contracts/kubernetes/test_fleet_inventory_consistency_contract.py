from pathlib import Path


def test_fleet_sync_uses_snapshot_reload_and_canonical_resolution() -> None:
    admission = Path('app/cluster/sync_jobs.py').read_text()
    worker = Path('app/cluster/tasks.py').read_text()

    assert "'targets': targets" in admission
    assert "targets: list[dict[str, str]] | None = None" in worker
    assert 'cluster = db.session.get(Cluster, cluster_id)' in worker
    assert 'connection = connection_for_cluster(cluster)' in worker
    assert 'failure_evidence.append(' in worker
    assert 'cluster.kubernetes_connection' not in worker
