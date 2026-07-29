from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_TEMPLATES = ROOT / 'app' / 'templates' / 'inventory'


def read(path: Path) -> str:
    return path.read_text()


def test_every_inventory_workspace_shows_committed_snapshot_freshness() -> None:
    pages = (
        'overview',
        'nodes',
        'namespaces',
        'workloads',
        'pods',
        'services',
        'ingresses',
        'storage',
        'configuration',
        'topology',
    )
    for page in pages:
        source = read(INVENTORY_TEMPLATES / page / 'index.html')
        assert 'inventory/components/_data_freshness.html' in source, page

    freshness = read(INVENTORY_TEMPLATES / 'components' / '_data_freshness.html')
    assert 'Inventory Data Snapshot' in freshness
    assert 'Latest Collected' in freshness
    assert 'Data Scope' in freshness
    assert 'Coverage' in freshness
    assert 'inventory_freshness.latest_collected_at|user_datetime' in freshness


def test_inventory_freshness_uses_committed_cluster_inventory_snapshots() -> None:
    overview = read(ROOT / 'app' / 'inventory' / 'overview.py')
    routes = read(ROOT / 'app' / 'inventory' / 'routes.py')

    assert 'def get_inventory_freshness_context(' in overview
    assert 'get_inventory_cluster_summary()' in overview
    assert "'source_label': 'Committed Database Snapshot'" in overview
    assert '@inventory_bp.context_processor' in routes
    assert 'get_inventory_freshness_context(cluster_id=cluster_id)' in routes


def test_service_and_ingress_inventory_offer_open_cluster_list() -> None:
    for page in ('services', 'ingresses'):
        source = read(INVENTORY_TEMPLATES / page / 'partials' / '_table_card.html')
        assert "url_for('integrations.kubernetes')" in source
        assert 'Open Cluster List' in source
        assert source.count('<header') == source.count('</header>')
