from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_inventory_has_canonical_setup_state() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    assert 'def _setup_state(total_systems: int)' in presentation
    assert "'is_blocked': total_systems == 0" in presentation
    assert "'setup': _setup_state(total_systems)" in presentation
    assert "'setup': _setup_state(len(all_rows))" in presentation
    assert "'setup': _setup_state(len(system_rows))" in presentation


def test_object_storage_overview_hides_inventory_evidence_while_setup_is_blocked() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    hero = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')
    assert '{% if overview.setup.is_blocked %}' in index
    assert 'storage/object_storage/inventory/components/_onboarding_banner.html' in index
    assert '_snapshot_boundary.html' in index
    assert '_fleet_posture.html' in index
    assert '_systems_snapshot.html' in index
    assert 'Committed Inventory' in hero
    assert 'Object Storage Setup Required' in hero
    assert 'storage/object_storage/inventory/components/_hero_blocked_context.html' in hero
    assert 'page_hero.aside_classes()' in hero


def test_systems_and_buckets_use_setup_blocker_and_inventory_data_snapshot() -> None:
    for resource in ('systems', 'buckets'):
        workspace = read(f'app/templates/storage/object_storage/inventory/{resource}/partials/_page_workspace.html')
        snapshot = read(f'app/templates/storage/object_storage/inventory/{resource}/partials/_snapshot_boundary.html')
        hero = read(f'app/templates/storage/object_storage/inventory/{resource}/partials/_hero.html')
        assert 'inventory.setup.is_blocked' in workspace
        assert 'storage/object_storage/inventory/components/_onboarding_banner.html' in workspace
        assert f'storage/object_storage/inventory/{resource}/partials/_snapshot_boundary.html' in workspace
        assert 'object_storage_snapshot.render(inventory.snapshot)' in snapshot
        assert 'Committed Inventory' in hero
        assert 'Object Storage Setup Required' in hero
        assert 'storage/object_storage/inventory/components/_hero_blocked_context.html' in hero
        assert 'page_hero.aside_classes()' in hero


def test_object_storage_setup_banner_is_integration_owned_and_permission_aware() -> None:
    banner = read('app/templates/storage/object_storage/inventory/components/_onboarding_banner.html')
    blocker = read('app/templates/storage/object_storage/inventory/components/_hero_blocked_context.html')
    assert 'Register Your First Object Storage System' in banner
    assert "url_for('integrations.storage')" in banner
    assert 'integrations.manage' in banner
    assert 'Registered Systems' in blocker
    assert 'Workspace State' in blocker
    assert 'Blocked' in blocker


def test_direct_htmx_inventory_reads_fail_closed_to_setup_banner() -> None:
    routes = read('app/storage/object_storage/inventory/routes.py')
    assert 'def _setup_blocked_htmx' in routes
    assert "request.headers.get('HX-Request') == 'true'" in routes
    assert 'storage/object_storage/inventory/components/_onboarding_banner.html' in routes
    assert routes.count('blocked_response = _setup_blocked_htmx(') == 3


def test_object_storage_analytics_setup_blocker_routes_to_storage_integrations() -> None:
    dependencies = read('app/storage/object_storage/analytics/dependencies.py')
    assert "'badge': 'Storage Setup Required'" in dependencies
    assert "'title': 'Object Storage Setup Required'" in dependencies
    assert "'action_label': 'Open Storage Integrations'" in dependencies
    assert "'action_endpoint': 'integrations.storage'" in dependencies


def test_ready_inventory_empty_states_distinguish_filters_from_collection_pending() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')

    assert "'total_committed_assets': len(rows)" in presentation
    assert 'No Object Storage Systems Match These Filters' in systems
    assert 'No Matches' in systems
    assert 'Storage Required' not in systems
    assert 'inventory.total_committed_assets == 0' in buckets
    assert 'Collection Pending' in buckets
    assert 'No Buckets or Containers Collected Yet' in buckets
    assert 'No Buckets or Containers Match These Filters' in buckets
