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
    assert 'href="{{ url_for(item.workspace_endpoint) }}"' in workspace
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


def test_source_control_action_uses_github_provider_landing_not_domain_self_link() -> None:
    """The shared workspace link must resolve to the provider, not its domain."""
    kernel = read('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    provider_routes = read('app/integrations/source_control/source_control/providers/github/application/routes.py')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    assert "workspace_endpoint='github_source.index'" in kernel
    assert "workspace_endpoint='integrations.source_control'" not in kernel
    assert "url_prefix='/integrations/source-control/github'" in provider_routes
    assert "@github_source_bp.get('/')" in provider_routes
    assert 'href="{{ url_for(item.workspace_endpoint) }}"' in workspace
    assert 'Open {{ item.runtime_label }}' in workspace
