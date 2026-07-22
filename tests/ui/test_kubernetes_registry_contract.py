from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FULL_TEMPLATE = ROOT / "app/templates/integrations/kubernetes.html"
REGISTRY_PARTIAL = ROOT / "app/templates/integrations/kubernetes/partials/_registry.html"


def test_full_page_uses_canonical_registry_partial() -> None:
    source = FULL_TEMPLATE.read_text(encoding="utf-8")
    assert "{% include 'integrations/kubernetes/partials/_registry.html' %}" in source
    assert "prometheus.new_instance" not in source


