from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
NAVIGATION_DIR = ROOT / "app" / "templates" / "components" / "navigation"
PAGE_HERO = ROOT / "app" / "templates" / "components" / "page_hero.html"

PARENT_NAVIGATION_TEMPLATES = (
    "access_management_menu.html",
    "analytics_menu.html",
    "dashboards_menu.html",
    "governance_menu.html",
    "integrations_menu.html",
    "intelligence_menu.html",
    "inventory_menu.html",
    "kubernetes_operations_menu.html",
    "platform_operations_menu.html",
    "reports_menu.html",
    "settings_menu.html",
    "sidebar.html",
)


def test_sidebar_parent_navigation_uses_larger_type_than_children() -> None:
    for filename in PARENT_NAVIGATION_TEMPLATES:
        source = (NAVIGATION_DIR / filename).read_text(encoding="utf-8")
        parent_lines = [line for line in source.splitlines() if "sidebar-parent-link" in line]

        assert parent_lines, f"No sidebar parent link found in {filename}"
        assert all("text-base" in line for line in parent_lines), filename
        assert all("text-sm font-semibold" not in line for line in parent_lines), filename

    submenu_sources = "\n".join(
        (NAVIGATION_DIR / filename).read_text(encoding="utf-8")
        for filename in PARENT_NAVIGATION_TEMPLATES
    )
    assert "sidebar-submenu" in submenu_sources
    assert "py-1.5 text-sm" in submenu_sources
    assert "py-1.5 text-xs" not in submenu_sources


def test_page_hero_description_is_one_type_step_above_supporting_copy() -> None:
    source = PAGE_HERO.read_text(encoding="utf-8")
    macro_start = source.index("{% macro description_classes()")
    macro_end = source.index("{%- endmacro %}", macro_start)
    description_macro = source[macro_start:macro_end]

    assert "text-base" in description_macro
    assert "leading-7" in description_macro
    assert "text-sm" not in description_macro
