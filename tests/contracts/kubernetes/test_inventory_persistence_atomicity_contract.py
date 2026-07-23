from pathlib import Path


def test_inventory_sync_has_single_commit_and_rollback_boundary() -> None:
    source = Path('app/inventory/synchronization.py').read_text()

    assert source.count('db.session.commit()') == 1
    assert source.count('db.session.rollback()') == 1
    assert 'connection = cluster.kubernetes_connection' not in source
    assert 'connection: KubernetesConnection' in source


def test_adapter_passes_the_canonical_connection_to_persistence() -> None:
    source = Path('app/integrations/kubernetes/adapter.py').read_text()

    assert 'sync_inventory(self._cluster(connection), connection)' in source
