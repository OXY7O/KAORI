from pathlib import Path


OVERVIEW = Path("app/templates/integrations/overview.html")
HERO = Path("app/templates/integrations/partials/_hero.html")
RUNTIME = Path("app/templates/integrations/partials/_runtime_overview.html")
SERVICE = Path("app/integrations/service.py")
DOC = Path("docs/modules/integrations/UI_REFERENCE.md")


def test_integrations_hero_has_exactly_two_visible_actions():
    text = HERO.read_text(encoding="utf-8")
    assert text.count("page_hero.primary_action_classes()") == 1
    assert text.count("page_hero.secondary_action_classes()") == 1
    assert "integrations.kubernetes" not in text
    assert "integrations.prometheus" not in text
    assert "integrations.alertmanager" not in text
    assert "activateTab('catalog')" in text
    assert "activateTab('runtime')" in text


def test_portfolio_overview_and_violet_tabs_precede_provider_workspaces():
    text = OVERVIEW.read_text(encoding="utf-8")
    assert text.index('Integration Portfolio Overview') < text.index('id="integration-workspace"')
    assert text.index('id="integration-workspace"') < text.index('id="provider-catalog"')
    assert "Provider Catalog" in text
    assert "Runtime Overview" in text
    assert "Domain Coverage" in text
    assert "bg-kaori-primary text-white shadow-sm" in text
    assert "Connection Contract" in text
    assert "Binding Contract" in text
    assert "Authority Boundary" in text


def test_provider_catalog_precedes_runtime_overview():
    text = OVERVIEW.read_text(encoding="utf-8")
    assert text.index('id="provider-catalog"') < text.index("_runtime_overview.html")
    assert "integrations.kubernetes" in text
    assert "integrations.prometheus" in text
    assert "integrations.alertmanager" in text
    assert "Open Workspace" in text
    assert "Planned Providers" in text


def test_runtime_overview_uses_compact_metric_strip_filters_and_noninteractive_disabled_pagination():
    text = RUNTIME.read_text(encoding="utf-8")
    assert "Runtime Overview" in text
    assert "Integration Health and Capability Posture" in text
    assert "xl:grid-cols-5" in text
    assert "No Runtime Targets Yet" in text
    assert "runtime_has_targets" in text
    assert 'hx-push-url="true"' in text
    assert 'aria-disabled="true"' in text
    assert '<span class="{{ pagination_ui.navigation_classes(disabled=true) }}" aria-disabled="true">' in text


def test_overview_builder_exposes_stable_tab_and_provider_counts():
    text = SERVICE.read_text(encoding="utf-8")
    assert 'tab: str = "catalog"' in text
    assert "'active_tab': tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog'" in text
    assert "'available_provider_count'" in text
    assert "'planned_provider_count'" in text


def test_integrations_ui_reference_records_scalable_page_contract():
    text = DOC.read_text(encoding="utf-8")
    assert "no more than two visible actions" in text
    assert "Integration Portfolio Overview" in text
    assert "Provider Catalog" in text
    assert "must not require redesigning the hero" in text
    assert "live Kubernetes, Prometheus, Thanos, or Alertmanager connectivity" in text
