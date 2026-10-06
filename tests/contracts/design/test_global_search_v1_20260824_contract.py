from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_global_search_replaces_placeholder_with_keyboard_first_snapshot_search() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    search = read('app/templates/components/navigation/_global_search.html')
    script = read('app/static/js/navbar.js')

    assert 'future global search placeholder' not in navbar
    assert '>Soon<' not in navbar
    assert '{{ global_search.desktop_trigger() }}' in navbar
    assert '{{ global_search.mobile_trigger() }}' in navbar
    assert '{{ global_search.dialog() }}' in navbar
    assert '@keydown.window="handleGlobalSearchShortcut($event)"' in navbar
    assert 'Ctrl K' in search
    assert 'Ctrl/Cmd + K' in search
    assert 'Search resources and pages...' in search
    assert 'Snapshot-backed search · no live Kubernetes or provider query' in search
    assert 'x-teleport="body"' in search
    assert "event.key === '/'" in script
    assert "event.key?.toLowerCase() === 'k'" in script


def test_global_search_v1_is_read_only_rbac_aware_and_snapshot_backed() -> None:
    routes = read('app/platform_operations/global_search/routes.py')
    service = read('app/platform_operations/global_search/service.py')
    platform_operations = read('app/platform_operations/__init__.py')

    assert "Blueprint('global_search', __name__, url_prefix='/search')" in routes
    assert "@bp.get('/global')" in routes
    assert '@login_required' in routes
    assert "has_permission('inventory.view')" in routes
    assert "has_permission('object_storage_inventory.view')" in routes
    assert 'bp.register_blueprint(global_search_bp)' in platform_operations
    assert 'db.session.query' in service
    assert 'NodeInventory' in service
    assert 'NamespaceInventory' in service
    assert 'WorkloadInventory' in service
    assert 'PodInventory' in service
    assert 'ServiceInventory' in service
    assert 'IngressInventory' in service
    assert 'StorageInventory' in service
    assert 'ObjectStorageSystem' in service
    assert 'ObjectStorageBucket' in service
    assert 'kubernetes.client' not in service
    assert 'prometheus' not in service.lower()
    assert 'requests.' not in service
    assert 'httpx' not in service
    assert 'execute' not in routes


def test_global_search_v1_prioritizes_exact_prefix_and_current_cluster_matches() -> None:
    service = read('app/platform_operations/global_search/service.py')
    script = read('app/static/js/navbar.js')

    assert 'title_value == q' in service
    assert 'title_value.startswith(q)' in service
    assert 'if current_scope:' in service
    assert 'score += 20' in service
    assert "searchParams.get('cluster_id')" in script
    assert "url.searchParams.set('cluster_id', currentClusterId)" in script
    assert 'MIN_RESOURCE_QUERY_LENGTH = 2' in service
    assert 'MAX_RESULTS_TOTAL = 24' in service


def test_global_search_v1_supports_debounce_cancel_keyboard_and_local_recent_history() -> None:
    script = read('app/static/js/navbar.js')
    search = read('app/templates/components/navigation/_global_search.html')

    assert 'globalSearchDebounceTimer' in script
    assert 'window.setTimeout(() => this.runGlobalSearch(), 180)' in script
    assert 'new AbortController()' in script
    assert 'moveGlobalSearchSelection(direction)' in script
    assert 'openSelectedGlobalSearchResult()' in script
    assert "window.localStorage?.getItem('kaori.globalSearch.recent')" in script
    assert "window.localStorage?.setItem('kaori.globalSearch.recent'" in script
    assert "window.localStorage?.removeItem('kaori.globalSearch.recent')" in script
    assert '@keydown.down.prevent="moveGlobalSearchSelection(1)"' in search
    assert '@keydown.up.prevent="moveGlobalSearchSelection(-1)"' in search
    assert '@keydown.enter.prevent="openSelectedGlobalSearchResult()"' in search
    assert ':aria-activedescendant=' in search
    assert '@keydown.tab="trapGlobalSearchFocus($event)"' in search
    assert 'globalSearchDomId(value)' in script
    assert 'trapGlobalSearchFocus(event)' in script
    assert "scrollIntoView({ block: 'nearest' })" in script
    assert 'No matching results' in search


def test_global_search_uses_kaori_semantic_tokens_without_raw_palette_drift() -> None:
    search = read('app/templates/components/navigation/_global_search.html')
    script = read('app/static/js/navbar.js')

    forbidden = ('violet-', 'purple-', 'gray-', 'slate-', 'zinc-', 'neutral-', 'stone-')
    for token in forbidden:
        assert token not in search
        assert token not in script

    assert 'bg-kaori-soft' in search
    assert 'text-kaori-primary' in search
    assert 'border-outline-default' in search
    assert 'bg-surface-elevated' in search
    assert 'border-status-normal-border' in script
    assert 'border-status-warning-border' in script
    assert 'border-status-critical-border' in script
    assert 'border-status-unknown-border' in script
