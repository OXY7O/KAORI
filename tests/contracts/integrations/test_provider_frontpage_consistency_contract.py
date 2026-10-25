from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_front_pages_share_one_canonical_hierarchy() -> None:
    templates = {
        'kubernetes': read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html'
        ),
        'metrics_source': read('app/templates/integrations/observability/metrics_source/frontpage.html'),
        'alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html'
        ),
        'minio': read('app/templates/integrations/storage/object_storage/providers/minio/index.html'),
        'harbor': read('app/templates/integrations/registry/providers/harbor/index.html'),
    }

    for provider, template in templates.items():
        assert 'integrations/components/_provider_frontpage.html' in template, provider
        assert 'components/integration_workspace_tabs.html' in template, provider
        assert 'provider_front.hero(' in template, provider
        assert 'provider_front.overview(' in template, provider
        assert 'integration_tabs.render(' in template, provider


def test_kubernetes_minio_harbor_keep_same_dashboard_frame_order() -> None:
    templates = {
        'kubernetes': read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html'
        ),
        'minio': read('app/templates/integrations/storage/object_storage/providers/minio/index.html'),
        'harbor': read('app/templates/integrations/registry/providers/harbor/index.html'),
    }

    for provider, template in templates.items():
        hero = template.index('provider_front.hero(')
        overview = template.index('provider_front.overview(')
        workspace = template.index('integration_tabs.render(')

        assert hero < overview < workspace, provider
        assert template.count('provider_front.hero(') == 1, provider
        assert template.count('provider_front.overview(') == 1, provider
        assert 'overview_metrics = [' in template, provider
        readiness = 'Active Ready Connections' if provider == 'harbor' else 'Validated Connections'
        for label in ('Registered Connections', readiness, 'Needs Attention', 'Coverage Gaps'):
            assert f'"label": "{label}"' in template, provider


def test_shared_overview_owns_summary_and_boundary_geometry() -> None:
    overview = read('app/templates/integrations/components/_provider_frontpage.html')

    assert 'data-kaori-provider-frontpage-hero' in overview
    assert 'Registered Connections' in overview
    assert 'Ready Connections' in overview
    assert 'Consumer Bindings' in overview
    assert 'Register Connection' in overview
    assert 'page_hero.context_actions_classes(2 if secondary_register_url else 1)' in overview
    assert 'page_hero.context_action_classes()' in overview
    assert 'data-kaori-provider-integration-overview' in overview
    assert 'integration_ui.metric_grid_classes(4)' in overview
    assert 'Integration Contract' in overview
    assert 'Consumer Resolution' in overview
    assert 'Authority Boundary' in overview
    # Architectural explanations live in the shared Guide, not persistent footer cards.
    assert 'md:grid-cols-3' not in overview
    assert '<article class="bg-surface-card px-5 py-4 sm:px-6">' not in overview
    assert 'info_tip.render(' in overview
    for section in ('Integration Contract', 'Consumer Resolution', 'Authority Boundary'):
        assert f'"{section} — "' in overview


def test_kubernetes_frontpage_uses_same_coverage_and_registry_contract() -> None:
    page = read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html')
    coverage = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_integration_coverage.html'
    )
    registry = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html'
    )
    routes = read('app/integrations/routes.py')
    frontpage_service = read('app/integrations/orchestration/container_orchestrator/frontpage.py')

    assert 'Kubernetes Integration Overview' in page
    assert 'integration_tabs.render("kubernetes"' in page
    assert (
        '{% include "integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_integration_coverage.html" %}'
        in page
    )
    assert (
        '{% include "integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html" %}'
        in page
    )
    assert 'provider_registry.asset_coverage_head(' in coverage
    assert 'Kubernetes Cluster' in coverage
    assert 'Kubernetes API' in coverage
    assert 'provider_registry.connection_registry_head()' in registry
    assert '<input type="hidden" name="tab" value="registry">' in registry
    assert "target == 'kubernetes-integration-coverage'" in routes
    assert "request.args.get('coverage_q', '')" in routes
    kubernetes_builder = frontpage_service.split('def build_kubernetes_page', 1)[1]
    assert 'coverage_ids, coverage_pagination = page_connection_ids(' in kubernetes_builder
    assert 'hydrated = _hydrate_connection_rows(' in kubernetes_builder
    assert "'coverage_rows': coverage_rows" in kubernetes_builder
    assert "'coverage_pagination': coverage_pagination" in kubernetes_builder


def test_minio_empty_and_populated_states_keep_registry_geometry() -> None:
    index = read('app/templates/integrations/storage/object_storage/providers/minio/index.html')
    coverage = read('app/templates/integrations/storage/object_storage/providers/minio/partials/_coverage.html')
    coverage_content = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_coverage_content.html'
    )
    registry = read('app/templates/integrations/storage/object_storage/providers/minio/partials/_registry.html')
    registry_content = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_registry_content.html'
    )
    routes = read('app/integrations/storage/object_storage/providers/minio/application/routes.py')
    presentation = read('app/integrations/storage/object_storage/providers/minio/application/presentation.py')

    assert 'MinIO Integration Overview' in index
    assert '{% include "integrations/storage/object_storage/providers/minio/partials/_coverage.html" %}' in index
    assert '{% include "integrations/storage/object_storage/providers/minio/partials/_registry.html" %}' in index

    assert 'minio-coverage-filter-form' in coverage
    assert 'minio-coverage-content' in coverage
    assert 'minio-registry-filter-form' in registry
    assert 'minio-registry-content' in registry

    for content in (coverage_content, registry_content):
        assert 'provider_registry.' in content
        assert '_table_classes()' in content
        assert 'components/states/_empty_state.html' in content
        assert 'provider_registry.pagination_footer(' in content

    assert "target == 'minio-coverage-content'" in routes
    assert "target == 'minio-registry-content'" in routes
    assert 'coverage_query:' in presentation
    assert 'compatibility:' in presentation


def test_provider_connection_registries_share_one_column_contract() -> None:
    registry_component = read('app/templates/integrations/components/_provider_registry.html')
    registries = [
        read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html'
        ),
        read('app/templates/integrations/observability/metrics_source/partials/_inventory_content.html'),
        read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html'
        ),
        read('app/templates/integrations/storage/object_storage/providers/minio/partials/_registry_content.html'),
        read('app/templates/integrations/registry/providers/harbor/partials/_registry.html'),
    ]

    for label in ('Connection', 'Endpoint / Scope', 'Core Readiness', 'Compatibility', 'Bindings', 'Actions'):
        assert label in registry_component
    for template in registries:
        assert 'provider_registry.connection_registry_colgroup()' in template
        assert 'provider_registry.connection_registry_head()' in template


def test_asset_provider_coverage_tables_share_one_column_contract() -> None:
    registry_component = read('app/templates/integrations/components/_provider_registry.html')
    kubernetes = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_integration_coverage.html'
    )
    minio = read('app/templates/integrations/storage/object_storage/providers/minio/partials/_coverage_content.html')

    for label in ('Metrics Source', 'Alert Source', 'Coverage', 'Actions'):
        assert label in registry_component
    assert 'provider_registry.asset_coverage_head(' in kubernetes
    assert 'Kubernetes Cluster' in kubernetes
    assert 'Kubernetes API' in kubernetes
    assert 'provider_registry.asset_coverage_head(' in minio
    assert 'Object Storage Asset' in minio
    assert 'MinIO API' in minio


def test_observability_coverage_includes_kubernetes_and_object_storage_assets() -> None:
    coverage_service = read('app/integrations/coverage.py')
    coverage_template = read('app/templates/components/integration_coverage_content.html')
    consumer_assets = read('app/integrations/consumer_assets.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')

    assert 'registered_consumer_asset_definitions()' in coverage_service
    assert 'integration_taxonomy_document()' in consumer_assets
    assert 'asset_type: kubernetes_cluster' in taxonomy_catalog
    assert 'asset_type: object_storage_system' in taxonomy_catalog
    assert 'for definition in registered_consumer_asset_definitions()' in coverage_service
    assert 'Choose Source' in coverage_template
    assert 'Manage Binding' in coverage_template
    assert 'url_for(provider.registry_endpoint' in coverage_template


def test_metrics_source_provider_selector_inherits_canonical_shared_hero() -> None:
    selector = read('app/templates/integrations/observability/metrics_source/provider_selector.html')
    shared = read('app/templates/integrations/provider_selector.html')

    assert '{% extends "integrations/provider_selector.html" %}' in selector
    assert 'page_hero.shell_classes()' in shared
    assert 'page_hero.layout_classes()' in shared
    assert 'page_hero.content_classes()' in shared
    assert 'page_hero.intro(domain.icon, domain.label, "package-search")' in shared
    assert '<h1 class="{{ page_hero.title_classes() }}">Choose Provider</h1>' in shared
    assert 'page_hero.hero(' not in shared
    assert 'page_hero.shell_classes()' not in selector


def test_harbor_frontpage_uses_registry_evidence_coverage_contract() -> None:
    page = read('app/templates/integrations/registry/providers/harbor/index.html')
    coverage = read('app/templates/integrations/registry/providers/harbor/partials/_coverage.html')
    registry = read('app/templates/integrations/registry/providers/harbor/partials/_registry.html')
    provider_registry = read('app/templates/integrations/components/_provider_registry.html')
    routes = read('app/integrations/registry/providers/harbor/application/routes.py')
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')

    assert 'Harbor Integration Overview' in page
    assert 'integration_tabs.render("harbor"' in page
    assert '{% include "integrations/registry/providers/harbor/partials/_coverage.html" %}' in page
    assert '{% include "integrations/registry/providers/harbor/partials/_registry.html" %}' in page

    assert 'provider_registry.registry_evidence_coverage_colgroup()' in coverage
    assert 'provider_registry.registry_evidence_coverage_head(' in coverage
    assert 'Harbor API' in coverage
    for label in ('Registry Instance', 'Inventory', 'Metrics Source', 'Webhook', 'Coverage', 'Actions'):
        assert label in provider_registry

    assert 'provider_registry.connection_registry_colgroup()' in registry
    assert 'provider_registry.connection_registry_head()' in registry
    assert '<input type="hidden" name="tab" value="registry">' in registry

    assert "target == 'harbor-integration-coverage'" in routes
    assert "target == 'harbor-connection-registry'" in routes
    assert "request.args.get('coverage_q', '')" in routes
    assert "'coverage_rows': coverage_page_rows" in presentation
    assert 'registry_metrics_readiness(identity)' in presentation
    assert 'RegistryCollectionState' in presentation
    assert 'RegistryWebhookEndpoint' in presentation


def test_every_provider_integration_overview_inherits_canonical_title_guide() -> None:
    shared = read('app/templates/integrations/components/_provider_frontpage.html')
    tip = read('app/templates/components/info_tip.html')
    pages = (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html',
        'app/templates/integrations/observability/metrics_source/frontpage.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html',
        'app/templates/integrations/storage/object_storage/providers/minio/index.html',
        'app/templates/integrations/registry/providers/harbor/index.html',
        'app/templates/integrations/secrets_management/vault/index.html',
        'app/templates/integrations/source_control/github/index.html',
    )

    assert 'components/info_tip.html' in shared
    assert shared.count('info_tip.render(') == 1
    # Whitespace around the Jinja replace call is owned by djLint.
    assert '"provider-overview-" ~ (title|lower|replace(" ", "-")' in shared
    assert 'title ~ " Guide"' in shared
    assert 'items=overview_guide_items' in shared
    assert 'md:grid-cols-3' not in shared
    assert 'integration_ui.metric_grid_classes(4)' in shared
    for section in ('Integration Contract', 'Consumer Resolution', 'Authority Boundary'):
        assert f'"{section} — "' in shared
    assert 'bg-surface-card px-5 py-4 sm:px-6' not in shared
    assert 'placement="right", variant="guide"' in shared
    for token in (
        'contract_title',
        'contract_description',
        'resolution_title',
        'resolution_description',
        'authority_title',
        'authority_description',
    ):
        assert token in shared
    assert 'data-kaori-info-tip-trigger' in tip
    assert 'data-kaori-info-tip-variant' in tip

    for path in pages:
        page = read(path)
        assert 'integrations/components/_provider_frontpage.html' in page, path
        assert page.count('provider_front.overview(') == 1, path
        assert 'info_tip.render(' not in page, path

    github = read('app/templates/integrations/source_control/github/index.html')
    assert 'Register GitHub Apps with governed Source Control evidence.' in github
    assert 'whitespace-nowrap' not in github
    assert 'line-clamp' not in github


def test_provider_workspace_tabs_share_title_description_and_existing_tab_geometry() -> None:
    tabs = read('app/templates/components/integration_workspace_tabs.html')
    pages = (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html',
        'app/templates/integrations/observability/metrics_source/frontpage.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html',
        'app/templates/integrations/storage/object_storage/providers/minio/index.html',
        'app/templates/integrations/registry/providers/harbor/index.html',
        'app/templates/integrations/secrets_management/vault/index.html',
        'app/templates/integrations/source_control/github/index.html',
    )

    assert 'integrations/components/_workspace.html' in tabs
    assert 'integration_ui.section_header("layout-dashboard",' in tabs
    assert '"Integration Workspace"' in tabs
    assert '"Switch between integration coverage and registered connections."' in tabs
    assert 'data-kaori-integration-workspace-section' in tabs
    assert 'integration_ui.workspace_section_intro(' in tabs
    assert 'Provider Connections & Coverage' in tabs
    assert 'Monitor provider readiness, committed coverage, and registered connections.' in tabs
    outer_heading = tabs.split('data-kaori-integration-workspace-tabs')[0]
    assert 'integration_ui.palette_icon(' not in outer_heading
    assert tabs.index('integration_ui.workspace_section_intro(') < tabs.index('data-kaori-integration-workspace-tabs')
    assert 'components/info_tip.html' in tabs
    assert tabs.count('info_tip.render(') == 1
    assert '"integration-workspace-" ~ provider_key' in tabs
    assert 'placement="right"' in tabs
    assert 'variant="guide"' in tabs
    assert 'items=workspace_guide_items' in tabs
    for section in ('Integration Coverage —', 'Connection Registry —', 'Authority Boundary —'):
        assert section in tabs
    shared_header = read('app/templates/integrations/components/_workspace.html')
    assert 'macro workspace_section_intro(title, description, aria_label)' in shared_header
    assert '<header class="min-w-0 px-1" aria-label="{{ aria_label }}">' in shared_header
    assert 'palette_icon(' not in shared_header.split('macro workspace_section_intro', 1)[1].split('{%- endmacro %}', 1)[0]
    assert 'title_extra=None' in shared_header
    assert '{% if title_extra %}{{ title_extra }}{% endif %}' in shared_header
    assert 'title_extra=workspace_guide' in tabs
    assert tabs.index('integration_ui.section_header(') < tabs.index('framed_workspace_tabs.render(')
    assert 'framed_workspace_tabs.render(workspace_tabs, workspace_prefix, workspace_label)' in tabs
    assert "('coverage', 'Integration Coverage'" in tabs
    assert "('registry', 'Connection Registry'" in tabs
    assert 'x-on:popstate.window="syncTab()"' in tabs
    for page in pages:
        assert 'components/integration_workspace_tabs.html' in read(page), page
