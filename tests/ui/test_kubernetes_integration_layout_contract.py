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


def test_coverage_explains_kubernetes_integration_dependencies():
    source = COVERAGE.read_text(encoding="utf-8")

    assert "Kubernetes Integration Coverage" in source
    for section in ("Kubernetes API", "Metrics Source", "Alert Source"):
        assert f">{section}<" in source

    for dependency in (
        "Required For Analytics",
        "Required For Alerts",
        "Inventory can run after Kubernetes validation",
    ):
        assert dependency in source


def test_coverage_uses_live_binding_statistics():
    template = COVERAGE.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    for key in ("prometheus_bound", "alertmanager_bound", "fully_observable"):
        assert f"stats.{key}" in template
        assert f"'{key}'" in service


def test_coverage_documents_recommended_setup_order():
    source = COVERAGE.read_text(encoding="utf-8")

    assert "Recommended Setup Order" in source
    for step in ("1. Register", "2. Validate", "3. Bind Metrics", "4. Bind Alerts"):
        assert step in source


def test_delete_action_has_alpine_handler():
    source = PAGE.read_text(encoding="utf-8")

    assert "openDelete(url, name)" in source
