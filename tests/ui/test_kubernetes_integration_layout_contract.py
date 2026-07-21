from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "app/templates/integrations/kubernetes.html"
OPERATING_MODEL = ROOT / "app/templates/integrations/kubernetes/partials/_operating_model.html"


def test_kubernetes_page_keeps_operating_model_between_hero_and_registry():
    source = PAGE.read_text(encoding="utf-8")
    operating_model = "integrations/kubernetes/partials/_operating_model.html"
    registry = "integrations/kubernetes/partials/_registry.html"

    assert operating_model in source
    assert registry in source
    assert source.index(operating_model) < source.index(registry)


def test_operating_model_preserves_three_canonical_concepts():
    source = OPERATING_MODEL.read_text(encoding="utf-8")

    assert "Integration Operating Model" in source
    assert "Connection Contract" in source
    assert "Capability Discovery" in source
    assert "Authority Boundary" in source


def test_delete_action_has_alpine_handler():
    source = PAGE.read_text(encoding="utf-8")

    assert "openDelete(url, name)" in source
