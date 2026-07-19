from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"

MIGRATED_TEMPLATES = [
    "inventory/pods/partials/_table_content.html",
    "inventory/nodes/partials/_table_content.html",
    "inventory/namespaces/partials/_table_content.html",
    "inventory/workloads/partials/_table_content.html",
    "inventory/services/partials/_table_content.html",
    "inventory/ingresses/partials/_table_content.html",
    "integrations/prometheus/partials/_inventory_content.html",
    "integrations/alertmanager/partials/_inventory_content.html",
    "users/partials/_table.html",
    "analytics/alerts/partials/_pagination.html",
]


def test_shared_numeric_pagination_macro_and_script_exist():
    component = (TEMPLATES / "components" / "pagination.html").read_text(encoding="utf-8")
    script = (ROOT / "app" / "static" / "js" / "pagination.js").read_text(encoding="utf-8")
    assert "macro numeric_pages" in component
    assert "data-kaori-numeric-pagination" in component
    assert "aria-current=\"page\"" in component
    assert "function pageWindow" in script
    assert "current <= 3" in script
    assert "current >= total - 2" in script
    assert "htmx:afterSwap" in script


def test_representative_operational_tables_use_numeric_macro():
    failures = []
    for relative in MIGRATED_TEMPLATES:
        text = (TEMPLATES / relative).read_text(encoding="utf-8")
        if "pagination_ui.numeric_pages(" not in text:
            failures.append(relative)
    assert not failures, "Numeric pagination macro missing:\n" + "\n".join(failures)


def test_numeric_pagination_script_is_loaded_globally():
    layout = (TEMPLATES / "layouts" / "app.html").read_text(encoding="utf-8")
    assert "js/pagination.js" in layout


def test_numeric_pagination_documentation_is_frozen():
    doc = (ROOT / "docs" / "design" / "components" / "PAGINATION.md").read_text(encoding="utf-8")
    assert "Numeric pagination contract" in doc
    assert "at most five numeric page buttons" in doc
    assert "non-interactive ellipsis" in doc
    assert "must never use solid Primary Violet" in doc
