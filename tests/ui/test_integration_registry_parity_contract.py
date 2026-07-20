from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROM_LANDING = ROOT / 'app/templates/integrations/prometheus.html'
PROM_CARD = ROOT / 'app/templates/integrations/prometheus/partials/_instance_inventory.html'
PROM_CONTENT = ROOT / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
ALERT_LANDING = ROOT / 'app/templates/integrations/alertmanager.html'
ALERT_CARD = ROOT / 'app/templates/integrations/alertmanager/partials/_inventory_card.html'
COMPONENT = ROOT / 'app/templates/components/uncovered_operational_scopes.html'
SERVICE = ROOT / 'app/integrations/service.py'
PRESENTATION = ROOT / 'app/alertmanager/presentation.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_uncovered_scopes_use_shared_component_above_each_registry() -> None:
    prom = read(PROM_LANDING)
    alert = read(ALERT_LANDING)
    assert 'Operational Scopes Without a Prometheus Source' in prom
    assert 'Operational Scopes Without an Alertmanager Source' in alert
    assert prom.index('Operational Scopes Without a Prometheus Source') < prom.index("_instance_inventory.html")
    assert alert.index('Operational Scopes Without an Alertmanager Source') < alert.index("_inventory_card.html")
    component = read(COMPONENT)
    assert 'Register & Bind' in component
    assert 'bg-status-warning-soft' in component
    assert 'bg-kaori-primary' in component


def test_alertmanager_inventory_builds_uncovered_cluster_coverage() -> None:
    source = read(PRESENTATION)
    assert "IntegrationInstance.provider_type == 'alertmanager'" in source
    assert "IntegrationBinding.asset_type == 'kubernetes_cluster'" in source
    assert "'uncovered_clusters': uncovered_clusters" in source


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
