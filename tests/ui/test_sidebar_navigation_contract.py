from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NAVIGATION_DIR = ROOT / "app" / "templates" / "components" / "navigation"
SIDEBAR = NAVIGATION_DIR / "sidebar.html"
STANDARD = ROOT / "docs" / "design" / "components" / "SIDEBAR_NAVIGATION.md"
DESIGN_SYSTEM = ROOT / "docs" / "design" / "KAORI_DESIGN_SYSTEM.md"


def _navigation_sources() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(NAVIGATION_DIR.glob("*.html"))
    )


def test_sidebar_standard_is_registered() -> None:
    assert STANDARD.exists()
    design_system = DESIGN_SYSTEM.read_text(encoding="utf-8")
    assert "components/SIDEBAR_NAVIGATION.md" in design_system


def test_sidebar_keeps_shell_specific_widths() -> None:
    source = SIDEBAR.read_text(encoding="utf-8")
    assert "w-[250px]" in source
    assert "[.sidebar-collapsed_&]:w-[78px]" in source


def test_parent_navigation_is_stronger_than_submenu() -> None:
    source = _navigation_sources()
    assert "text-[12px] font-semibold" in source
    assert "text-[11px] leading-4" in source
    assert "min-h-11" in source


def test_collapsed_mode_hides_text_instead_of_shrinking_it() -> None:
    source = SIDEBAR.read_text(encoding="utf-8")
    assert "sidebar-expanded-only" in source
    assert "[.sidebar-collapsed_&]:justify-center" in source


def test_active_parent_and_child_use_different_emphasis() -> None:
    source = _navigation_sources()
    assert "bg-kaori-primary text-white" in source
    assert "bg-white/[0.08] text-kaori-accent" in source


def test_documented_sidebar_exceptions_remain_explicit() -> None:
    standard = STANDARD.read_text(encoding="utf-8")
    assert "Parent menu: 12 px semibold" in standard
    assert "Submenu:     11 px regular/medium" in standard
    assert "approved exceptions" in standard
    assert "must never be reduced" in standard
