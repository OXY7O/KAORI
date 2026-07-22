from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "app/templates/integrations/kubernetes.html"
COVERAGE = ROOT / "app/templates/integrations/kubernetes/partials/_integration_coverage.html"
SERVICE = ROOT / "app/integrations/service.py"


def test_kubernetes_page_keeps_coverage_between_hero_and_registry():
    source = PAGE.read_text(encoding="utf-8")
    coverage = "integrations/kubernetes/partials/_integration_coverage.html"
    registry = "integrations/kubernetes/partials/_registry.html"

    assert coverage in source
    assert registry in source
    assert source.index(coverage) < source.index(registry)
    assert "_operating_model.html" not in source


def test_delete_action_has_alpine_handler():
    source = PAGE.read_text(encoding="utf-8")

    assert "openDelete(url, name)" in source
