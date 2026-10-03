from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_provider_prerequisite_components_delegate_to_existing_shared_owners() -> None:
    hero = read('app/templates/components/provider_prerequisite/_hero_context.html')
    setup = read('app/templates/components/provider_prerequisite/_setup_blocker.html')

    assert 'page_hero.blocked_context_body(' in hero
    assert 'provider_prerequisite_action_label|default(none)' in hero
    assert 'components/states/_blocked_state.html' in setup
    assert "blocked_state_variant = 'section'" in setup


def test_kubernetes_and_object_storage_provider_wrappers_share_one_contract() -> None:
    cluster_hero = read('app/templates/components/cluster/_hero_blocked_context.html')
    cluster_setup = read('app/templates/components/cluster/_onboarding_banner.html')
    storage_hero = read('app/templates/storage/object_storage/inventory/components/_hero_blocked_context.html')
    storage_setup = read('app/templates/storage/object_storage/inventory/components/_onboarding_banner.html')

    assert 'components/provider_prerequisite/_hero_context.html' in cluster_hero
    assert 'components/provider_prerequisite/_setup_blocker.html' in cluster_setup
    assert 'components/provider_prerequisite/_hero_context.html' in storage_hero
    assert 'components/provider_prerequisite/_setup_blocker.html' in storage_setup


def test_tenant_zero_provider_state_preserves_route_navigation_but_not_operational_content() -> None:
    tenant = read('app/templates/kubernetes/tenant/base.html')

    assert '{% block page_capability_navigation %}' not in tenant
    assert '{% if registered_cluster_count == 0 %}' in tenant
    zero_branch = tenant.rsplit('{% if registered_cluster_count == 0 %}', 1)[1].split('{% else %}', 1)[0]
    registered_branch = tenant.rsplit('{% if registered_cluster_count == 0 %}', 1)[1].split('{% else %}', 1)[1]

    assert 'components/cluster/_onboarding_banner.html' in zero_branch
    assert 'block tenant_content' not in zero_branch
    assert 'block tenant_content' in registered_branch


def test_inventory_blocked_state_preserves_normal_metadata_roles() -> None:
    kubernetes = read('app/templates/kubernetes/inventory/overview/partials/_hero.html')
    object_storage = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')

    assert "page_hero.meta_label('server', overview.total_clusters" in kubernetes
    assert "page_hero.meta_label('layers-3', overview.asset_catalog|length" in kubernetes
    assert "page_hero.meta_label('database', overview.inventory_total" in kubernetes
    assert "'Cluster Setup Required')" not in kubernetes

    assert "page_hero.meta_label('server', overview.total_systems" in object_storage
    assert "page_hero.meta_label('boxes', overview.total_buckets" in object_storage
    assert "page_hero.meta_label('database-backup', overview.inventory_coverage" in object_storage


    storage_systems = read('app/templates/storage/object_storage/inventory/systems/partials/_hero.html')
    storage_assets = read('app/templates/storage/object_storage/inventory/buckets/partials/_hero.html')
    systems_metadata = storage_systems.split('page_hero.metadata_row_classes()', 1)[1].split('</div>', 1)[0]
    assets_metadata = storage_assets.split('page_hero.metadata_row_classes()', 1)[1].split('</div>', 1)[0]
    assert 'inventory.setup.is_blocked' not in systems_metadata
    assert 'Object Storage Setup Required' not in systems_metadata
    assert 'inventory.setup.is_blocked' not in assets_metadata
    assert 'Object Storage Setup Required' not in assets_metadata


def test_analytics_provider_absence_uses_provider_prerequisite_before_secondary_dependencies() -> None:
    kubernetes_page = read('app/templates/kubernetes/analytics/materialization/blocked.html')
    kubernetes_posture = read('app/templates/kubernetes/analytics/components/_blocked_posture.html')
    storage_blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    storage_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')

    assert "dependency_blocker.kind == 'cluster_required'" in kubernetes_page
    assert 'components/provider_prerequisite/_setup_blocker.html' in kubernetes_page
    assert 'components/provider_prerequisite/_hero_context.html' in kubernetes_posture
    assert "dependency_blocker.kind == 'system_required'" in storage_blocker
    assert 'components/provider_prerequisite/_setup_blocker.html' in storage_blocker
    assert 'components/provider_prerequisite/_hero_context.html' in storage_posture


def test_provider_prerequisite_standard_is_locked_in_documentation() -> None:
    standard = read('docs/design/components/PROVIDER_PREREQUISITE.md')

    assert 'Provider Prerequisite Blocking Standard v1.0' in standard
    assert 'level-3 route navigation remains visible' in standard
    assert 'normal operational content is not rendered' in standard.lower()
    assert 'Registry / Harbor operational consumers must adopt this contract' in standard
