from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROM_LANDING = ROOT / 'app/templates/integrations/prometheus.html'
PROM_CARD = ROOT / 'app/templates/integrations/prometheus/partials/_instance_inventory.html'
PROM_CONTENT = ROOT / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
ALERT_LANDING = ROOT / 'app/templates/integrations/alertmanager.html'
ALERT_CARD = ROOT / 'app/templates/integrations/alertmanager/partials/_inventory_card.html'
COMPONENT = ROOT / 'app/templates/components/integration_coverage.html'
CONTENT = ROOT / 'app/templates/components/integration_coverage_content.html'
TABS = ROOT / 'app/templates/components/integration_workspace_tabs.html'
COVERAGE = ROOT / 'app/integrations/coverage.py'
SERVICE = ROOT / 'app/integrations/service.py'
PRESENTATION = ROOT / 'app/alertmanager/presentation.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_integration_coverage_uses_shared_bind_first_component_above_each_registry() -> None:
    prom = read(PROM_LANDING)
    alert = read(ALERT_LANDING)
    assert 'integration_coverage.render' in prom
    assert 'integration_coverage.render' in alert
    assert prom.index('integration_coverage.render') < prom.index("_instance_inventory.html")
    assert alert.index('integration_coverage.render') < alert.index("_inventory_card.html")
    component = read(COMPONENT)
    content = read(CONTENT)
    assert 'Integration Coverage' in component
    assert 'Bind operational scopes to existing {{ provider.label }} sources.' in component
    assert 'Bind Source' in content
    assert 'Review Binding' in content
    assert 'Operational Scopes Without' not in component


def test_provider_landings_use_the_same_tabbed_workspace_contract() -> None:
    prom = read(PROM_LANDING)
    alert = read(ALERT_LANDING)
    tabs = read(TABS)

    for source in (prom, alert):
        assert 'integration_tabs.render' in source
        assert "active_tab" in source
        assert "tab_name == 'coverage'" in source
        assert 'Connection Registry' in tabs
        assert 'Integration Coverage' in tabs
    assert "history.replaceState" in tabs
    assert "activeTab = 'coverage'" in tabs
    assert "activeTab = 'registry'" in tabs


def test_coverage_filters_are_active_for_both_providers() -> None:
    component = read(COMPONENT)
    routes = read(ROOT / 'app/integrations/routes.py')
    coverage = read(COVERAGE)

    for fragment in (
        'name="coverage_q"',
        'name="coverage_environment"',
        'name="coverage_status"',
        'hx-target="#{{ provider.key }}-coverage-content"',
        'hx-push-url="true"',
    ):
        assert fragment in component
    assert "request.headers.get('HX-Target') == 'prometheus-coverage-content'" in routes
    assert "request.headers.get('HX-Target') == 'alertmanager-coverage-content'" in routes
    assert "if normalized_query:" in coverage
    assert "if environment:" in coverage
    assert "if status:" in coverage


def test_alertmanager_inventory_builds_provider_neutral_coverage() -> None:
    presentation = read(PRESENTATION)
    coverage = read(COVERAGE)
    assert "build_provider_coverage(" in presentation
    assert "'alertmanager'" in presentation
    assert "IntegrationInstance.provider_type == provider_type" in coverage
    assert "binding.asset_type == 'kubernetes_cluster'" in coverage
    assert "'coverage_rows': page_rows" in coverage
    assert "'source_options': source_options" in coverage


def test_prometheus_filters_match_registry_pattern() -> None:
    card = read(PROM_CARD)
    service = read(SERVICE)
    assert 'Search Connection' in card
    assert 'name="q"' in card
    assert 'Readiness' in card
    assert 'Compatibility' in card
    assert 'Environment' not in card
    assert 'hx-push-url="true"' in card
    assert "normalized_query = query.strip().lower()" in service
    assert "'selected_query': query" in service
    assert 'selected_environment' not in service[service.index('def build_prometheus_page'):service.index('def build_alertmanager_page')]


def test_prometheus_pagination_matches_alertmanager_density_and_url_state() -> None:
    prom = read(PROM_CONTENT)
    alert = read(ROOT / 'app/templates/integrations/alertmanager/partials/_inventory_content.html')
    assert 'py-3.5 text-xs' in prom
    assert 'py-3.5 text-xs' in alert
    assert prom.count('hx-push-url="true"') >= 3
    assert 'name="q" value="{{ selected_query }}"' in prom
    assert 'class="h-4 w-4"' in prom
    assert 'pagination_ui.page_size_classes()' in prom
    assert 'pagination_ui.navigation_classes' in prom
    assert 'No Prometheus connections found' in prom
    assert 'No Alertmanager connections found' in alert
    assert prom.index('No Prometheus connections found') < prom.index('<footer')
    assert alert.index('No Alertmanager connections found') < alert.index('<footer')


def test_provider_registry_tables_share_the_same_column_contract() -> None:
    prom = read(PROM_CONTENT)
    alert = read(ROOT / 'app/templates/integrations/alertmanager/partials/_inventory_content.html')
    columns = (
        '>Connection<',
        '>Endpoint<',
        '>Runtime<',
        '>Compatibility<',
        '>Readiness<',
        '>Bindings<',
        '>Last Validated<',
        '>Action<',
    )
    for column in columns:
        assert column in prom
        assert column in alert
    for fragment in ('status_badge(row.compatibility)', 'status_badge(row.readiness)', 'table_label.metadata_label'):
        assert fragment in prom
        assert fragment in alert

def test_workspace_tabs_use_violet_selected_and_unselected_states() -> None:
    tabs = read(TABS)
    assert "border-kaori-primary bg-kaori-primary text-white shadow-sm" in tabs
    assert "border-brand-outline bg-surface-card text-kaori-primary" in tabs
    assert "border-white bg-white text-kaori-primary-dark" in tabs
    assert "border-transparent bg-transparent text-content-secondary" not in tabs


def test_coverage_title_box_matches_registry_header_hierarchy() -> None:
    coverage = read(COMPONENT)
    prom_registry = read(PROM_CARD)
    alert_registry = read(ALERT_CARD)
    shared_header = 'header class="border-b border-outline-subtle px-5 py-4 sm:px-6"'
    shared_loader = 'htmx-indicator mt-4 h-1 overflow-hidden rounded-full bg-kaori-soft'
    assert shared_header in coverage
    assert shared_header in prom_registry
    assert shared_header in alert_registry
    assert shared_loader in coverage
    assert shared_loader in prom_registry
    assert shared_loader in alert_registry
    assert 'Operational Coverage' not in coverage


def test_registry_action_column_is_compact_and_table_width_is_reduced() -> None:
    prom = read(PROM_CONTENT)
    alert = read(ROOT / 'app/templates/integrations/alertmanager/partials/_inventory_content.html')
    for source in (prom, alert):
        assert 'min-w-[980px] table-fixed' in source
        assert '<colgroup>' in source
        assert 'w-[100px] whitespace-nowrap px-3 py-3.5 text-right">Action' in source
        assert 'w-[100px] whitespace-nowrap px-3 py-4 text-right align-top' in source
        assert 'min-w-[1180px]' not in source

