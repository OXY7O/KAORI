from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_context_panel_macros_exist():
    source = read("app/templates/components/page_hero.html")
    for macro in (
        "context_panel_classes",
        "context_panel_eyebrow_classes",
        "context_panel_title_classes",
        "context_panel_metrics_classes",
        "context_metric",
    ):
        assert f"macro {macro}" in source
    assert "min-h-[13rem]" in source


def test_node_inventory_uses_shared_context_panel():
    source = read("app/templates/inventory/nodes/partials/_hero.html")
    assert "page_hero.context_panel_classes()" in source
    assert "page_hero.context_panel_metrics_classes()" in source
    assert source.count("page_hero.context_metric(") == 2
    assert "Nodes Tracked" in source
    assert "CPU Cores" in source
    assert "GiB Memory" in source


def test_hero_standard_documents_metadata_title_case():
    source = read("docs/design/components/HERO.md")
    assert "## Right-side context panel" in source
    assert "## Hero metadata casing" in source
    assert "Human-readable metadata labels use **Title Case**" in source
