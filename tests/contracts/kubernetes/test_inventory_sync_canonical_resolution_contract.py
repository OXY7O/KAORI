from pathlib import Path


def test_inventory_sync_never_uses_direct_cluster_connection_relationship() -> None:
    task_source = Path('app/cluster/tasks.py').read_text()
    admission_source = Path('app/cluster/sync_jobs.py').read_text()

    assert 'connection_for_cluster(cluster)' in task_source
    assert 'connection_for_cluster(current_cluster)' in admission_source
    assert 'cluster.kubernetes_connection' not in task_source
    assert 'current_cluster.kubernetes_connection' not in admission_source
