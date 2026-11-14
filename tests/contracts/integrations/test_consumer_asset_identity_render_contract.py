"""Rendered contracts for shared Integration Consumer Asset identity (#4611)."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app/templates"


def _identity(label: str, asset_type: str, metadata: str, type_label: str) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    component = env.get_template("integrations/components/_workspace.html").module
    return str(
        component.consumer_asset_identity(
            label,
            asset_type,
            metadata=metadata,
            type_label=type_label,
            metadata_is_key=True,
        )
    )


def test_consumer_identity_deduplicates_matching_taxonomy_without_losing_key() -> None:
    for label, asset_type, icon in (
        ("Kubernetes Cluster", "kubernetes_cluster", "boxes"),
        ("Object Storage System", "object_storage_system", "database"),
    ):
        key = "c0e9f10c-8b25-49d2-b5e1-116c06f3a289"
        html = _identity(label, asset_type, key, label.upper())
        assert html.count(f">{label}</p>") == 1
        assert html.count(key) >= 1
        assert f'data-lucide="{icon}"' in html
        assert "data-kaori-consumer-asset-identity" in html
        assert "font-mono" in html


def test_consumer_identity_preserves_distinct_type_and_full_correlation_key() -> None:
    key = "asset-tenant-000000000000000000000000000001"
    html = _identity("Payments Cluster", "kubernetes_cluster", key, "Kubernetes Cluster")
    assert ">Payments Cluster</p>" in html
    assert ">Kubernetes Cluster</span>" in html
    assert key in html
    assert "overflow-wrap:anywhere" in html


def test_all_binding_registries_use_one_shared_identity_component() -> None:
    paths = (
        "integrations/partials/_domain_workspace.html",
        "integrations/observability/metrics_source/partials/_binding_registry.html",
        "integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html",
    )
    for path in paths:
        template = (TEMPLATES / path).read_text(encoding="utf-8")
        assert "integration_ui.consumer_asset_identity(" in template, path
