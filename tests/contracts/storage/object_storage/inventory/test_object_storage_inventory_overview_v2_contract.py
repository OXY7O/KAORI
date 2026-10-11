from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_overview_is_high_level_fleet_composition() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    hero = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')
    snapshot = read('app/templates/storage/object_storage/inventory/overview/partials/_snapshot_boundary.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')
    navigation = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')

    assert '_fleet_posture.html' in index
    assert '_summary_cards.html' in index
    assert '_systems_snapshot.html' not in index
    assert 'resource_detail_modal.inventory_host(' not in index
    assert "page_hero.intro('database-zap', 'Object Storage Inventory', 'database')" in hero
    assert '<h1 class="{{ page_hero.title_classes() }}">Overview</h1>' in hero
    assert 'Review inventory coverage across registered Object Storage systems.' in hero
    assert 'Systems Registered' in hero
    assert 'Inventory Assets' in hero
    assert 'Inventory Coverage' in hero
    assert 'Manage Storage' in hero
    assert "url_for('integrations.storage')" in hero
    assert 'object_storage_snapshot.render(overview.snapshot)' in snapshot
    assert 'components/section_intro.html' in fleet
    assert 'Fleet Inventory Posture' in fleet
    assert 'components/operational_section_card.html' in fleet
    assert 'components/resource_posture_grid.html' in fleet
    assert "'Object Storage Fleet Evidence'" in fleet
    assert "body_classes='p-0'" in fleet
    assert 'posture_grid.render(overview.fleet_posture_metrics, columns=4)' in fleet
    assert 'operational_callout.render' not in fleet
    assert 'components/section_intro.html' in navigation
    assert "section_intro.render('Inventory Assets'," in navigation
    assert "'Object Storage Asset Catalog'" in navigation
    assert 'components/operational_section_card.html' in navigation
    assert "id='object-storage-asset-catalog'" in navigation
    assert 'header_badge=asset_badge' in navigation
    assert 'inventory_asset_card.render' in navigation
    assert 'action_label=asset.action_label' in navigation


def test_resource_level_system_detail_is_owned_by_systems_workspace() -> None:
    overview = read('app/templates/storage/object_storage/inventory/overview/index.html')
    systems_index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    systems_table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'resource_detail_modal.inventory_host(' not in overview
    assert 'resource_detail_modal.inventory_host(' in systems_index
    assert 'resource_detail_modal.detail_button(' in systems_table
    assert "url_for('object_storage_inventory.system_details', system_id=system.id)" in systems_table
    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert 'System Identity' in detail
    assert 'Provider Connection' in detail
    assert 'Inventory Snapshot' in detail
    assert 'Authority Boundary' in detail
    assert 'system.guidance.title' in detail


def test_overview_does_not_duplicate_system_pagination_or_detail_loading() -> None:
    routes = read('app/storage/object_storage/inventory/routes.py')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert 'build_overview()' in routes
    assert "request.args.get('system_page'" not in routes
    assert 'object-storage-inventory-summary-content' not in routes
    assert 'def build_overview() -> dict[str, Any]:' in presentation
    assert "'systems_pagination': pagination" not in presentation
    assert "'systems': paged_rows" not in presentation


def test_overview_snapshot_and_signals_are_committed_inventory_only() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS = 24' in presentation
    assert "'source_label': 'Committed Snapshot'" in presentation
    assert "'snapshot_source': 'Committed Snapshot'" in presentation
    assert 'Inventory Not Collected' in presentation
    assert 'Stale Snapshot' in presentation
    assert 'Provider Attention' in presentation
    assert (
        'Committed Object Storage Inventory; provider configuration and live health remain integration-owned.' in detail
    )
    assert 'client.list_buckets' not in presentation


def test_overview_inventory_navigation_stays_vendor_neutral() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    navigation = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')

    assert "'title': 'Systems'" in presentation
    assert "'title': 'Buckets & Containers'" in presentation
    assert 'MinIO' not in navigation
    assert 'AStor' not in navigation
    assert 'MinIO' not in fleet
    assert 'AStor' not in fleet


def test_object_storage_system_detail_uses_compact_release_and_profile_labels() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert '_release_display' in presentation
    assert '_compatibility_profile_display' in presentation
    assert "'release_label': _release_display" in presentation
    assert "'compatibility_profile_label': _compatibility_profile_display" in presentation
    assert "detail.inventory_row('Release', system.release_label, nowrap=true)" in detail
    assert "detail.inventory_row('Compatibility Profile', system.compatibility_profile_label, nowrap=true)" in detail


def test_public_exposure_clean_state_names_committed_inventory_evidence() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert (
        'No committed asset is currently classified as public in the latest Object Storage inventory evidence.'
        in presentation
    )
    assert 'No committed asset is currently classified as public.' not in presentation


def test_object_storage_inventory_matches_registry_grouped_visual_hierarchy() -> None:
    from jinja2 import Environment, FileSystemLoader

    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')
    catalog = read('app/templates/storage/object_storage/inventory/overview/partials/_summary_cards.html')
    registry = read('app/templates/artifact_registry/partials/_inventory_overview.html')
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    metrics = read('app/templates/components/resource_posture_grid.html')
    cards = read('app/templates/components/inventory_asset_card.html')

    for template in (fleet, catalog, registry, metrics, cards):
        Environment().parse(template)

    for template in (fleet, catalog):
        assert 'components/operational_section_card.html' in template
        assert 'components/section_intro.html' in template
        assert template.count('operational_section_card.render(') == 1

    assert "section_intro.render('Inventory Assets'," in catalog
    assert "section_intro.render('Inventory Assets'," in registry
    assert "table_label.metadata_label(overview.asset_catalog|length ~ ' Asset Types'" in catalog
    assert "table_label.metadata_label(inventory.asset_catalog|length ~ ' Asset Types'" in registry
    assert "posture_grid.render(overview.fleet_posture_metrics, columns=4)" in fleet
    assert "posture_grid.render(inventory.fleet_posture_metrics, columns=3)" in registry
    assert "body_classes='p-0'" in fleet
    assert "body_classes='p-5'" in catalog
    assert 'sm:grid-cols-2' in catalog
    assert "'action_label': 'Browse Systems'" in presentation
    assert "'action_label': 'Browse Buckets & Containers'" in presentation
    assert "'fleet_readings': fleet_readings" in presentation
    assert "'fleet_posture_metrics': _overview_fleet_posture_metrics(bucket_posture, fleet_readings)" in presentation
    assert "if total else 'No Evidence'" in presentation
    assert 'zip(readings, metric_values, strict=True)' in presentation
    assert 'data-kaori-inventory-identity-icon' in cards

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    overview = {
        'fleet_posture_metrics': [
            ('gauge', 'Quota Assessed', '3/3', 'Quota collected.', 'normal'),
            ('shield-check', 'Protection Attention', '3', 'Review protection.', 'warning'),
            ('key-round', 'Public Exposure', '0', 'No public exposure observed.', 'normal'),
            ('chart-no-axes-column', 'Usage Collected', '3/3', 'Optional usage.', 'info'),
        ],
        'asset_catalog': [
            {'title': 'Systems', 'count': 1, 'description': 'Committed systems.', 'endpoint': 'object_storage_inventory.systems', 'icon': 'server', 'action_label': 'Browse Systems'},
            {'title': 'Buckets & Containers', 'count': 3, 'description': 'Committed assets.', 'endpoint': 'object_storage_inventory.buckets', 'icon': 'container', 'action_label': 'Browse Buckets & Containers'},
        ],
    }
    html_fleet = env.get_template('storage/object_storage/inventory/overview/partials/_fleet_posture.html').render(overview=overview)
    html_catalog = env.get_template('storage/object_storage/inventory/overview/partials/_summary_cards.html').render(
        overview=overview, url_for=lambda endpoint: '/' + endpoint.replace('.', '/')
    )
    assert html_fleet.count('>Quota Assessed</p>') == 1
    assert 'Protection Attention' in html_fleet
    assert 'Public Exposure' in html_fleet
    assert 'Usage Collected' in html_fleet
    assert 'No public exposure observed.' in html_fleet
    assert 'object-storage-asset-catalog' in html_catalog
    assert '2 Asset Types' in html_catalog
    assert 'Browse Systems' in html_catalog
    assert 'Browse Buckets &amp; Containers' in html_catalog
    assert '/object_storage_inventory/systems' in html_catalog
    assert '/object_storage_inventory/buckets' in html_catalog
