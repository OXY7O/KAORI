from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP_LAYOUT = ROOT / "app/templates/layouts/app.html"
SIDEBAR = ROOT / "app/templates/components/navigation/sidebar.html"
NAVBAR = ROOT / "app/templates/components/navigation/navbar.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_application_shell_owns_independent_mobile_navigation_state() -> None:
    source = _read(APP_LAYOUT)

    assert "mobileNavOpen: false" in source
    assert "openMobileNavigation()" in source
    assert "closeMobileNavigation()" in source
    assert "@keydown.escape.window=\"closeMobileNavigation()\"" in source


def test_desktop_sidebar_does_not_consume_mobile_layout_width() -> None:
    source = _read(SIDEBAR)

    assert "data-desktop-navigation" in source
    assert "hidden" in source
    assert "lg:flex" in source


def test_mobile_navigation_is_fixed_overlay_with_backdrop() -> None:
    source = _read(SIDEBAR)

    assert "data-mobile-navigation-backdrop" in source
    assert "data-mobile-navigation-drawer" in source
    assert "fixed inset-0" in source
    assert "fixed inset-y-0 left-0" in source
    assert "@click=\"closeMobileNavigation()\"" in source


def test_mobile_app_bar_exposes_navigation_trigger() -> None:
    source = _read(NAVBAR)

    assert "data-mobile-navigation-trigger" in source
    assert "@click=\"openMobileNavigation()\"" in source
    assert "lg:hidden" in source
    assert "aria-label=\"Open navigation\"" in source


def test_primary_content_can_shrink_without_document_overflow() -> None:
    source = _read(APP_LAYOUT)

    assert "data-application-workspace" in source
    assert "min-w-0" in source
    assert "w-full" in source
