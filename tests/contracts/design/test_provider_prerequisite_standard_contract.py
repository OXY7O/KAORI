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
    assert 'blocked_state_variant = "section"' in setup


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


def test_analytics_provider_absence_keeps_full_dependency_path_visible() -> None:
    kubernetes_page = read('app/templates/kubernetes/analytics/materialization/blocked.html')
    kubernetes_posture = read('app/templates/kubernetes/analytics/components/_blocked_posture.html')
    storage_blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    storage_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')

    assert 'components/dependencies/_blocker.html' in kubernetes_page
    assert 'components/provider_prerequisite/_setup_blocker.html' not in kubernetes_page
    assert 'components/provider_prerequisite/_hero_context.html' in kubernetes_posture

    assert '"Object Storage"' in storage_blocker
    assert '"Metrics Source"' in storage_blocker
    assert '"Alert Source"' in storage_blocker
    assert 'Object Storage → Metrics Source → Alert Source' in storage_blocker
    assert 'components/dependencies/_blocker.html' in storage_blocker
    assert 'components/provider_prerequisite/_setup_blocker.html' not in storage_blocker
    assert 'components/provider_prerequisite/_hero_context.html' in storage_posture


def test_provider_prerequisite_standard_is_locked_in_documentation() -> None:
    standard = read('docs/design/components/PROVIDER_PREREQUISITE.md')

    assert 'Provider Prerequisite Blocking Standard v1.0' in standard
    assert 'level-3 route navigation remains visible' in standard
    assert 'normal operational content is not rendered' in standard.lower()
    assert 'Registry / Harbor operational consumers must adopt this contract' in standard

def test_registry_blocked_hero_contract_is_admitted_by_existing_hero_gate() -> None:
    import runpy

    verifier = runpy.run_path(str(ROOT / 'scripts/verify_hero_component_standard.py'))
    verifier['_verify_registry_blocked_hero_actions']()


def test_shared_context_card_renders_info_not_action_when_blocked() -> None:
    from jinja2 import Environment, FileSystemLoader

    templates = ROOT / 'app/templates'
    hero = Environment(loader=FileSystemLoader(str(templates)), autoescape=True).get_template(
        'components/page_hero.html'
    ).module
    args = (
        'Registry inventory posture',
        'Committed State',
        'Inventory Posture',
        'Ready',
        'normal',
        [('database-backup', 'Committed Providers', '0/0', 'Retained snapshots')],
        'Open Registry Integrations',
        '/integrations/registry',
    )
    normal = str(hero.context_card(*args))
    blocked = str(
        hero.context_card(
            *args,
            blocked=True,
            blocked_info='Register and validate a Registry provider.',
        )
    )

    assert 'href="/integrations/registry"' in normal
    assert 'Open Registry Integrations' in normal
    assert 'href="/integrations/registry"' not in blocked
    assert 'Open Registry Integrations' not in blocked
    assert 'data-kaori-blocked-state' in blocked
    assert 'Setup Required' in blocked
    assert 'Register and validate a Registry provider.' in blocked
    assert 'Committed Providers' in normal
    assert 'Committed Providers' in blocked


def test_registry_secondary_inventory_blocker_keeps_its_distinct_action_owner() -> None:
    security = read('app/templates/artifact_registry/partials/_security_workspace.html')
    runtime = read('app/templates/artifact_registry/partials/_runtime_workspace.html')

    assert security.count('blocked=security.setup_blocked or security.inventory_required') == 2
    assert security.count("'Inventory Required'") >= 2
    assert 'components/states/_blocked_state.html' in security
    assert 'blocked=runtime.setup.is_blocked' in runtime
    assert 'components/states/_blocked_state.html' in runtime
