from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROM_LANDING = ROOT / 'app/templates/integrations/prometheus.html'
PROM_CARD = ROOT / 'app/templates/integrations/prometheus/partials/_instance_inventory.html'
PROM_CONTENT = ROOT / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
ALERT_LANDING = ROOT / 'app/templates/integrations/alertmanager.html'
ALERT_CARD = ROOT / 'app/templates/integrations/alertmanager/partials/_inventory_card.html'
COMPONENT = ROOT / 'app/templates/components/integration_coverage.html'
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
    assert 'Integration Coverage' in component
    assert 'Bind Source' in component
    assert 'Register a new connection only when no suitable source exists.' in component
    assert 'Operational Scopes Without' not in component


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
