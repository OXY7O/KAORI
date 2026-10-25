from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


PROVIDER_TEMPLATE_ROOTS = {
    'metrics': 'app/templates/integrations/observability/metrics_source',
    'alertmanager': 'app/templates/integrations/observability/alert_source/providers/alertmanager',
    'minio': 'app/templates/integrations/storage/object_storage/providers/minio',
}


def test_domain_workspace_separates_tabs_from_registry_surface_and_preserves_readability() -> None:
    template = read('app/templates/integrations/partials/_domain_workspace.html')
    assert 'data-kaori-domain-registry-surface' in template
    assert 'overflow-hidden rounded-xl border border-outline-subtle' in template
    assert 'overflow-x-auto' in template
    assert 'min-w-[920px]' in template
    assert '[overflow-wrap:anywhere]' in template
    assert 'table-fixed' not in template


def test_operator_facing_metrics_sources_use_provider_neutral_contract() -> None:
    module = read('app/integrations/observability/metrics_source/__init__.py')
    service = read('app/integrations/service.py')
    detail = read('app/templates/integrations/observability/metrics_source/partials/_detail_configuration.html')
    form = read('app/templates/integrations/observability/metrics_source/instance_form.html')
    assert "runtime_label='Metrics Sources'" in module
    assert "'provider_key': provider.key" in service
    assert "'provider_label': provider.label" in service
    assert "'provider_key': provider.key" in service
    assert '{% set metrics_source_label = provider.label %}' in detail
    assert '{% set metrics_source_label = provider.label %}' in form
    assert 'Metrics Source Contract' in form


def test_loading_bars_are_operation_scoped() -> None:
    for provider in ('metrics', 'alertmanager', 'minio'):
        registry = read(f'{PROVIDER_TEMPLATE_ROOTS[provider]}/partials/_capability_registry.html')
        assert 'active=validation_job and validation_job.is_active' not in registry
        assert 'hx-indicator="#{{ loading_id }}"' in registry or provider == 'minio'

        validation_name = '_detail_validation_content.html' if provider != 'minio' else '_detail_validation.html'
        validation = read(f'{PROVIDER_TEMPLATE_ROOTS[provider]}/partials/{validation_name}')
        loading_key = 'metrics-source' if provider == 'metrics' else provider
        assert f'{loading_key}-validation-loading' in validation
        assert f'hx-indicator="#{loading_key}-validation-loading"' in validation


def test_validation_and_runtime_refresh_tab_badges_oob() -> None:
    tabs = read('app/templates/components/framed_workspace_tabs.html')
    assert 'macro badge_oob' in tabs
    assert 'hx-swap-oob="innerHTML"' in tabs
    assert 'class="hidden"' in tabs
    assert 'hx-swap-oob="outerHTML"' not in tabs.split('macro badge_oob', 1)[1]

    for provider in ('metrics', 'alertmanager', 'minio'):
        validation_name = '_detail_validation_content.html' if provider != 'minio' else '_detail_validation.html'
        runtime_name = '_runtime_panel.html' if provider != 'minio' else '_detail_runtime.html'
        validation = read(f'{PROVIDER_TEMPLATE_ROOTS[provider]}/partials/{validation_name}')
        runtime = read(f'{PROVIDER_TEMPLATE_ROOTS[provider]}/partials/{runtime_name}')

        badge_key = 'metrics-source' if provider == 'metrics' else provider
        assert f'badge_oob("{badge_key}", "validation"' in validation
        assert f'badge_oob("{badge_key}", "runtime"' in runtime


def test_source_control_hero_copy_uses_compact_taxonomy_text() -> None:
    taxonomy = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    domain = read('app/templates/integrations/domain.html')
    source_control = taxonomy.split('- key: source_control\n  label: Source Control\n', 1)[1]
    description = source_control.split('  description: ', 1)[1].split('\n', 1)[0]

    # Prefer a concise semantic description over clipping or nowrap at mobile widths.
    assert len(description) <= 60
    assert 'source control providers' in description.lower()
    assert 'governed' in description.lower()
    assert 'page_hero.description_classes()' in domain


def test_source_control_header_uses_one_canonical_provider_workspace_action() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    # The reviewed Registry flow uses the provider type's existing workspace link.
    assert workspace.count('Open {{ item.runtime_label }}') == 1
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    assert 'GitHub · First Provider' not in workspace
    assert 'GitHub · Open Provider' not in workspace
    assert "domain.key == 'source_control'" in workspace
    assert 'workspace_tabs = [workspace_tabs[0]]' in workspace


def test_domain_registry_clear_filters_stays_on_header_right() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    clear_action = read('app/templates/components/table_registry.html')
    registry = workspace.split('data-kaori-domain-registry-surface', 1)[1]
    header = registry.split('{% call registry_ui.filter_form(', 1)[0]

    assert 'Provider Registry Filters' in header
    assert header.index('Provider Registry Filters') < header.index('registry_ui.clear_filters_link(')
    assert '{% if provider_filters_active %}' in header
    assert 'registry_ui.clear_filters_link(' in header
    assert 'lead=false' in header  # Avoid shared macro default order-first.
    assert 'table_ui.action_classes()' in header
    assert 'query_params=provider_clear_query' in header
    assert "page_param='provider_page'" in header
    assert "per_page_param='provider_per_page'" in header

    # Keep existing canonical GET/HTMX/reset, Rows and conditional visibility.
    assert 'clear_filters_action(clear_url,' in clear_action
    assert "sync='closest section:replace'" in clear_action
    assert 'lead=lead' in clear_action
    assert "'binding_per_page': binding_per_page" in workspace


def test_source_control_action_selects_provider_before_registration() -> None:
    """The shared workspace link must resolve to the provider, not its domain."""
    kernel = read('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    provider_routes = read('app/integrations/source_control/source_control/providers/github/application/routes.py')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    assert "workspace_endpoint='github_source.index'" in kernel
    assert "workspace_endpoint='integrations.source_control'" not in kernel
    assert "url_prefix='/integrations/source-control/github'" in provider_routes
    assert "@github_source_bp.route('/connections/new', methods=['GET', 'POST'])" in provider_routes
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    assert 'Open {{ item.runtime_label }}' in workspace
    assert "'Source Control Connections' if domain.key == 'source_control'" in workspace


def test_all_integration_domains_select_provider_before_registration() -> None:
    routes = read('app/integrations/routes.py')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    picker = read('app/templates/integrations/provider_selector.html')
    matrix = read('app/definitions/catalogs/integrations/provider_matrix.yaml')

    assert "@integrations_bp.get('/providers/<string:integration_type>')" in routes
    assert "@permission_required('integrations.manage')" in routes
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    assert 'provider_kinds(integration_type)' in routes
    assert 'if kind.available and (kind.integration_type, kind.key) in _PROVIDER_REGISTRATION_ENDPOINTS' in routes

    for domain in ('orchestration', 'observability', 'storage', 'registry', 'secrets_management', 'source_control'):
        assert f'domain_key: {domain}' in matrix
    for target in (
        "'cluster.add_cluster'",
        "'alertmanager.new_instance'",
        "'minio.new_instance'",
        "'harbor.new_instance'",
        "'vault.new_instance'",
        "'github_source.new_connection'",
    ):
        assert target in routes

    assert "redirect(url_for('integrations.select_metrics_source_provider'))" in routes
    assert 'data-kaori-provider-selector' in picker
    assert 'if provider.registration_url' in picker
    assert 'Register {{ provider.label }}' in picker
    assert 'components/info_tip.html' in picker
    assert 'url_for(domain.workspace_endpoint)' in picker


def test_provider_overviews_share_provider_first_registration_contract() -> None:
    provider_landing_pages = {
        'object_storage': 'app/templates/integrations/storage/object_storage/providers/minio/index.html',
        'registry': 'app/templates/integrations/registry/providers/harbor/index.html',
        'secrets_pki': 'app/templates/integrations/secrets_management/vault/index.html',
        'container_orchestrator': (
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html'
        ),
        'alert_source': 'app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html',
        'source_control': 'app/templates/integrations/source_control/github/index.html',
    }
    for integration_type, path in provider_landing_pages.items():
        assert 'integrations.choose_integration_provider' in read(path), integration_type
        assert f'integration_type="{integration_type}"' in read(path) or (
            f"integration_type='{integration_type}'" in read(path)
        )

    metrics_landing = read('app/templates/integrations/observability/metrics_source/frontpage.html')
    assert 'integrations.select_metrics_source_provider' in metrics_landing


def test_metrics_provider_selector_uses_compact_hero_and_shared_info_tips() -> None:
    selector = read('app/templates/integrations/observability/metrics_source/provider_selector.html')
    routes = read('app/integrations/routes.py')
    tooltips = read('app/templates/components/info_tip.html')

    assert 'Adapters own validation and runtime.' in selector
    assert 'Choose a provider here; adapter, query language, validation' not in selector
    assert 'info_tip.render("metrics-selector-guide"' in selector
    assert 'info_tip.render("metrics-adapter-" ~ provider.key' in selector
    assert 'info_tip.render("metrics-query-" ~ provider.key' in selector
    assert 'variant="guide"' in selector
    assert 'data-kaori-info-tip-trigger' in tooltips
    assert 'sm:grid-cols-2' in selector
    assert 'hover:border-brand-outline' in selector
    assert 'href="{{ provider.registration_url }}"' in selector
    assert 'Register {{ provider.label }}' in selector
    assert "url_for('integrations.register_metrics_source', provider_key=provider.key)" in routes


def test_source_control_provider_matrix_declares_planned_inert_provider_choices() -> None:
    from app.integrations.provider_matrix import provider_kinds

    kinds = {provider.key: provider for provider in provider_kinds('source_control')}
    assert set(kinds) == {'github', 'gitlab', 'bitbucket'}
    assert kinds['github'].available is True
    assert kinds['github'].lifecycle == 'available'
    assert kinds['github'].adapter_key == 'github_rest_v3'

    for key in ('gitlab', 'bitbucket'):
        assert kinds[key].lifecycle == 'planned'
        assert kinds[key].available is False
        assert kinds[key].adapter_key == 'not_implemented'
        assert kinds[key].protocol == 'not_defined'


def test_source_control_provider_card_registration_is_provider_owned_and_disabled_when_planned() -> None:
    route = read('app/integrations/routes.py')
    selector = read('app/templates/integrations/provider_selector.html')

    assert 'kinds = sorted(provider_kinds(integration_type)' in route
    assert '(not kind.available, kind.label.casefold())' in route
    assert "'lifecycle': kind.lifecycle" in route
    assert "('source_control', 'github'): 'github_source.new_connection'" in route
    assert "('source_control', 'gitlab')" not in route
    assert "('source_control', 'bitbucket')" not in route
    assert 'data-kaori-provider-card-grid' in selector
    assert 'xl:grid-cols-3' in selector
    assert 'data-kaori-provider-lifecycle="{{ provider.lifecycle }}"' in selector
    assert "table_label.status_label('Planned', 'unknown')" in selector
    assert "table_label.status_label('Available', 'normal')" in selector
    assert 'if provider.registration_url' in selector
    assert 'href="{{ provider.registration_url }}"' in selector
    assert 'data-kaori-provider-register' in selector
    assert 'data-kaori-provider-disabled' in selector
    assert "action_button.classes('locked-info', full=true)" in selector
    assert 'disabled' in selector
    assert 'Register {{ provider.label }}' in selector
    assert 'Not implemented' in route
    assert 'Not defined' in route


def test_provider_cards_preserve_section_guide_without_field_question_icons() -> None:
    selector = read('app/templates/integrations/provider_selector.html')
    tooltip = read('app/templates/components/info_tip.html')
    controller = read('app/static/js/info_tips.js')

    # Contextual guidance belongs to the shared section header, not each field.
    assert selector.count('info_tip.render(') == 1
    assert 'info_tip.render("provider-choices-" ~ integration_type' in selector
    assert 'variant="guide"' in selector
    assert 'info_tip.render("adapter-" ~ integration_type' not in selector
    assert 'info_tip.render("protocol-" ~ integration_type' not in selector
    assert '<dt class="text-xs font-semibold text-content-muted">Adapter</dt>' in selector
    assert '<dt class="text-xs font-semibold text-content-muted">Protocol</dt>' in selector
    assert 'integration_ui.palette_icon("layers-3", "brand", size="lg")' in selector

    # Compact text fits desktop grid without forcing clipping on phones.
    assert 'Registration is not yet available.' in selector
    assert 'Provider support is planned. No registration or runtime is available.' not in selector
    assert 'whitespace-nowrap' not in selector
    assert 'truncate' not in selector

    # The remaining title-level Guide retains KAORI's established controller.
    assert 'data-kaori-info-tip-trigger' in tooltip
    assert 'data-kaori-info-tip-preview' in tooltip
    for interaction in ("'pointerover'", "'focusin'", "'click'", "'keydown'"):
        assert interaction in controller
    assert "event.key === 'Escape'" in controller
    assert 'portal.appendChild(preview)' in controller
    assert '<style' not in selector
    assert '<script' not in selector
