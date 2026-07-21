from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_only_one_binding_readiness_resolver_exists() -> None:
    assert (ROOT / "app/integrations/readiness.py").exists()
    assert not (ROOT / "app/integrations/binding_posture.py").exists()


def test_dead_analytics_prometheus_wrapper_is_removed() -> None:
    assert not (ROOT / "app/analytics/base/prometheus_service.py").exists()


def test_shared_detail_tip_is_domain_neutral() -> None:
    assert (ROOT / "app/templates/components/detail_tip.html").exists()
    assert not (ROOT / "app/templates/components/inventory_detail_tip.html").exists()


def test_readiness_resolver_explains_source_and_binding_gates() -> None:
    source = (ROOT / "app/integrations/readiness.py").read_text(encoding="utf-8")
    assert "Source Validation Required" in source
    assert "Binding Validation Required" in source
    assert "Source readiness and binding validation are both Ready" in source
