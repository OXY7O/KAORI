from pathlib import Path


OVERVIEW = Path("app/templates/integrations/overview.html")
HERO = Path("app/templates/integrations/partials/_hero.html")
RUNTIME = Path("app/templates/integrations/partials/_runtime_overview.html")
DOC = Path("docs/modules/integrations/UI_REFERENCE.md")


def test_integrations_hero_has_exactly_two_visible_actions():
    text = HERO.read_text(encoding="utf-8")
    assert text.count("page_hero.primary_action_classes()") == 1
    assert text.count("page_hero.secondary_action_classes()") == 1
    assert "integrations.kubernetes" not in text
    assert "integrations.prometheus" not in text
    assert "integrations.alertmanager" not in text


def test_provider_catalog_precedes_runtime_overview():
    text = OVERVIEW.read_text(encoding="utf-8")
    assert text.index('id="provider-catalog"') < text.index("_runtime_overview.html")
    assert "Provider Catalog" in text
    assert "integrations.kubernetes" in text
    assert "integrations.prometheus" in text
    assert "integrations.alertmanager" in text


def test_runtime_overview_uses_compact_metric_strip_and_empty_state():
    text = RUNTIME.read_text(encoding="utf-8")
    assert "Runtime Overview" in text
    assert "Integration Health and Capability Posture" in text
    assert "xl:grid-cols-5" in text
    assert "No Runtime Targets Yet" in text
    assert "runtime_has_targets" in text


def test_integrations_ui_reference_records_scalable_page_contract():
    text = DOC.read_text(encoding="utf-8")
    assert "no more than two visible actions" in text
    assert "Provider Catalog" in text
    assert "must not require redesigning the hero" in text
    assert "live Kubernetes, Prometheus, Thanos, or Alertmanager connectivity" in text
