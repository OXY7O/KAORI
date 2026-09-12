from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_sidebar_owns_independent_mobile_navigation_state() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')

    assert 'mobileNavOpen: false' in sidebar
    assert '@kaori:mobile-nav-open.window="mobileNavOpen = true"' in sidebar
    assert '@keydown.escape.window="mobileNavOpen = false"' in sidebar
    assert 'data-mobile-navigation-backdrop' in sidebar


def test_sidebar_is_off_canvas_on_mobile_and_persistent_on_desktop() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')

    assert 'data-mobile-navigation' in sidebar
    assert 'fixed inset-y-2 left-2' in sidebar
    assert 'lg:relative' in sidebar
    assert 'lg:translate-x-0' in sidebar
    assert ':class="mobileNavOpen ?' in sidebar
    assert 'data-mobile-navigation-close' in sidebar
    assert '@click="mobileNavOpen = false"' in sidebar


def test_navbar_exposes_mobile_menu_without_reusing_desktop_collapse_control() -> None:
    navbar = _read('app/templates/components/navigation/navbar.html')

    assert 'data-mobile-menu-trigger' in navbar
    assert "$dispatch('kaori:mobile-nav-open')" in navbar
    assert 'lg:hidden' in navbar
    assert 'hidden lg:inline-flex' in navbar
    assert 'aria-controls="app-sidebar"' in navbar
    assert 'data-mobile-current-page' in navbar


def test_shared_hero_recomposes_without_fixed_mobile_height() -> None:
    hero = _read('app/templates/components/page_hero.html')

    assert 'min-h-0 lg:min-h-[15.5rem]' in hero
    assert 'min-h-0 lg:min-h-[13rem]' in hero
    assert 'grid-cols-1 sm:grid-cols-2' in hero
    assert 'text-2xl' in hero
    assert 'sm:text-3xl' in hero
    assert 'lg:text-4xl' in hero
