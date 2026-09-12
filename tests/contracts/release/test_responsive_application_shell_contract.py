from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SIDEBAR = ROOT / 'app/templates/components/navigation/sidebar.html'
NAVBAR = ROOT / 'app/templates/components/navigation/navbar.html'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_sidebar_owns_independent_mobile_navigation_state() -> None:
    source = _read(SIDEBAR)

    assert 'mobileNavOpen: false' in source
    assert 'openMobileNavigation()' in source
    assert 'closeMobileNavigation(' in source
    assert '@keydown.escape.window="closeMobileNavigation()"' in source
    assert '@kaori:mobile-nav-open.window="openMobileNavigation()"' in source


def test_sidebar_does_not_consume_mobile_layout_width() -> None:
    source = _read(SIDEBAR)

    assert 'data-mobile-navigation-drawer' in source
    assert 'fixed inset-y-0 left-0' in source
    assert 'lg:relative' in source
    assert 'lg:translate-x-0' in source


def test_mobile_navigation_has_backdrop_and_explicit_close_paths() -> None:
    source = _read(SIDEBAR)

    assert 'data-mobile-navigation-backdrop' in source
    assert 'fixed inset-0' in source
    assert '@click="closeMobileNavigation()"' in source
    assert 'aria-label="Close navigation"' in source
    assert '@click="if ($event.target.closest(\'a\')) closeMobileNavigation(false)"' in source


def test_mobile_app_bar_exposes_navigation_trigger_and_desktop_toggle_is_separate() -> None:
    source = _read(NAVBAR)

    assert 'data-mobile-navigation-trigger' in source
    assert "$dispatch('kaori:mobile-nav-open')" in source
    assert 'aria-label="Open navigation"' in source
    assert 'lg:hidden' in source
    assert 'data-desktop-navigation-toggle' in source
    assert 'hidden' in source
    assert 'lg:inline-flex' in source


def test_compact_navbar_keeps_primary_mobile_actions_reachable() -> None:
    source = _read(NAVBAR)

    assert 'data-mobile-page-context' in source
    assert 'Open global search' in source
    assert 'Open notification deck' not in source or '_notification_center.html' in source
    assert 'Open user menu' in source
    assert 'data-mobile-theme-toggle' in source
