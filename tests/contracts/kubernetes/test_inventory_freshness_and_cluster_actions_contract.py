from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_TEMPLATES = ROOT / 'app' / 'templates' / 'inventory' / 'kubernetes'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


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
        if page in {'nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage'}:
            source += read(INVENTORY_TEMPLATES / page / 'partials' / '_page_workspace.html')
        assert 'inventory/kubernetes/components/_data_freshness.html' in source, page

    freshness = read(INVENTORY_TEMPLATES / 'components' / '_data_freshness.html')
    shared = read(ROOT / 'app/templates/components/snapshot_context_bar.html')
    assert 'components/snapshot_context_bar.html' in freshness
    assert 'Inventory Data Snapshot' in shared
    assert 'inventory_freshness.latest_collected_at|user_datetime' in freshness
    assert 'Latest Collected' in shared
    assert 'Active Scope' in shared
    assert 'Committed Coverage' in shared
    assert 'Snapshot Exceptions' in shared
    assert 'inventory_freshness.exception_label' in freshness
    assert 'table_label.status_label' in shared
    assert 'p-4' in shared
    assert 'xl:col-span-4' in shared
    assert 'xl:col-span-8' in shared
    assert 'xl:grid-cols-4' in shared
    assert 'xl:divide-x' in shared
    assert 'xl:divide-outline-subtle' in shared
    assert 'bg-surface-hover' not in shared
    assert 'coverage_tone' in shared
    assert 'exceptions_tone' in shared
    assert '>Source:</span>' in shared
    assert 'h-9 w-9' in shared
    assert 'p-5' not in shared
    assert 'h-11 w-11' not in shared
    assert 'Snapshot Source</p>' not in shared


def test_inventory_snapshot_is_hidden_when_cluster_onboarding_blocks_the_workspace() -> None:
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
        path = INVENTORY_TEMPLATES / page / 'index.html'
        source = read(path)
        if page in {'nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage'}:
            source = read(INVENTORY_TEMPLATES / page / 'partials' / '_page_workspace.html')

        blocker = source.index('{% if cluster_onboarding.is_blocked %}')
        blocker_else = source.index('{% else %}', blocker)
        snapshot = source.index('inventory/kubernetes/components/_data_freshness.html')
        blocker_end = source.index('{% endif %}', snapshot)

        assert blocker < blocker_else < snapshot < blocker_end, page


def test_inventory_freshness_uses_committed_cluster_inventory_snapshots() -> None:
    overview = read(ROOT / 'app' / 'inventory' / 'kubernetes' / 'overview.py')
    routes = read(ROOT / 'app' / 'inventory' / 'kubernetes' / 'routes.py')

    assert 'def get_inventory_freshness_context(' in overview
    assert 'get_inventory_cluster_summary()' in overview
    assert "'source_label': 'Committed Inventory Snapshot'" in overview
    assert "'coverage_label': coverage_label" in overview
    assert "'coverage_supporting': coverage_supporting" in overview
    assert "'exceptions_tone': 'warning' if has_exceptions else 'normal'" in overview
    assert '1 of 1 snapshots' not in overview  # Built dynamically from committed scope counts.
    assert "'exception_label': exception_label" in overview
    assert '@inventory_bp.context_processor' in routes
    assert 'get_inventory_freshness_context(cluster_id=cluster_id)' in routes


def test_network_and_storage_inventory_offer_open_cluster_list() -> None:
    for page in ('services', 'ingresses', 'storage'):
        source = read(INVENTORY_TEMPLATES / page / 'partials' / '_table_card.html')
        assert "url_for('integrations.kubernetes')" in source
        assert 'Open Cluster List' in source
        assert source.count('<header') == source.count('</header>')
